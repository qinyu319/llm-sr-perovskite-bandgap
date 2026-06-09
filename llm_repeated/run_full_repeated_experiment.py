from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from repeated_modeling import (
    TERM_ORDER,
    TrainingEvaluator,
    evaluate_final_test,
    write_json,
)


STAGES = ("M0", "M1", "M2", "M3", "M4")
REPO_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_WRAPPER = """Repeated-run batch instruction:
- This is one stage inside an independently repeated M0-to-M4 experiment.
- Apply the scientific and structural constraints in the stage prompt exactly.
- Generate exactly 16 candidate expression structures.
- Make the candidates structurally distinct where the constraints allow.
- Each candidate must itself follow the original one-line expression format.
- Do not fit coefficients, use data, report performance, or explain.
- Return only the schema-conforming object containing the 16 candidate strings.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 30 complete Codex M0-M4 experiments.")
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--start-run", type=int, default=1)
    parser.add_argument("--parallelism", type=int, default=6)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--cv-seed", type=int, default=20260607)
    parser.add_argument("--output-dir", type=Path, default=Path("repeated_runs_30"))
    parser.add_argument(
        "--train", type=Path, default=REPO_ROOT / "data" / "train_518.xlsx"
    )
    parser.add_argument(
        "--test", type=Path, default=REPO_ROOT / "data" / "test_92.xlsx"
    )
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_codex() -> str:
    found = shutil.which("codex")
    if found:
        return found
    extension_root = Path.home() / ".vscode" / "extensions"
    matches = sorted(extension_root.glob("openai.chatgpt-*/bin/windows-x86_64/codex.exe"))
    if not matches:
        raise FileNotFoundError("Could not locate codex executable")
    return str(matches[-1])


def parse_thread_id(stdout: str, stderr: str) -> str | None:
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("thread_id", "session_id"):
            value = event.get(key)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", value):
                return value
        nested = event.get("thread")
        if isinstance(nested, dict):
            value = nested.get("id")
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", value):
                return value
    match = re.search(r"(?:session id|thread id):\s*([0-9a-fA-F-]{36})", stderr)
    return match.group(1) if match else None


def build_stage_prompt(
    stage: str,
    base_prompt: str,
    run_id: int,
    previous_selection: dict[str, Any] | None,
    correction: str | None = None,
) -> str:
    context = ""
    if previous_selection:
        context = f"""
Previous-stage deterministic training-set selection for this same run:
- selected structure: {previous_selection['selected_expression']}
- selected non-constant terms: {', '.join(previous_selection['selected_terms'])}
- mean five-fold CV RMSE: {previous_selection['selected_cv_rmse_mean']:.8f} eV

Use this selected structure as the baseline inherited from the previous stage. Extend,
revise, or simplify it only within the current stage's allowed term pool and constraints.
"""
    correction_text = f"\nCorrection required after parser validation:\n{correction}\n" if correction else ""
    return (
        f"Independent repeated-run ID: {run_id:03d}; current stage: {stage}.\n\n"
        + SYSTEM_WRAPPER
        + context
        + correction_text
        + "\nOriginal frozen stage prompt:\n"
        + base_prompt.strip()
    )


def invoke_codex(
    *,
    codex: str,
    workspace: Path,
    schema_path: Path,
    model: str,
    reasoning_effort: str,
    prompt: str,
    output_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    thread_id: str | None,
    timeout_seconds: int = 600,
) -> tuple[str | None, dict[str, Any]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    common = [
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
        "--json",
    ]
    if thread_id is None:
        command = [
            codex,
            "exec",
            "--sandbox",
            "read-only",
            "--cd",
            str(workspace),
            *common,
            prompt,
        ]
    else:
        command = [codex, "exec", "resume", *common, thread_id, prompt]

    started_at_utc = utc_now()
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    metadata = {
        "command_exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "started_at_utc": started_at_utc,
        "finished_at_utc": utc_now(),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            f"Codex failed with exit code {completed.returncode}; see {stderr_path}"
        )

    response = json.loads(output_path.read_text(encoding="utf-8"))
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 16:
        raise ValueError(f"Expected 16 candidates in {output_path}")
    if not all(isinstance(candidate, str) for candidate in candidates):
        raise ValueError(f"Non-string candidate in {output_path}")
    return thread_id or parse_thread_id(completed.stdout, completed.stderr), metadata


def save_stage_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        flattened.append(
            {
                "candidate_index": row["candidate_index"],
                "raw": row["raw"],
                "valid": row["valid"],
                "invalid_reasons": "; ".join(row["invalid_reasons"]),
                "duplicate_of": row["duplicate_of"],
                "canonical_expression": row["canonical_expression"],
                "terms": ";".join(row["terms"]),
                "term_count": row.get("term_count"),
                "cv_rmse_mean": row.get("cv_rmse_mean"),
                "cv_rmse_std": row.get("cv_rmse_std"),
                "cv_r2": row.get("cv_r2"),
                "condition_number": row.get("condition_number"),
                "fold_rmse": ";".join(
                    f"{value:.10f}" for value in row.get("fold_rmse", [])
                ),
                "coefficients_json": json.dumps(
                    row.get("coefficients"), ensure_ascii=False
                )
                if row.get("coefficients")
                else "",
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flattened).to_csv(path, index=False, encoding="utf-8-sig")


def run_one(
    run_id: int,
    *,
    args: argparse.Namespace,
    codex: str,
    workspace: Path,
    prompts: dict[str, str],
    evaluator: TrainingEvaluator,
    schema_path: Path,
) -> dict[str, Any]:
    run_dir = args.output_dir / f"run_{run_id:03d}"
    final_path = run_dir / "selected_models" / "final.json"
    if final_path.exists() and not args.overwrite:
        return json.loads(final_path.read_text(encoding="utf-8"))
    run_dir.mkdir(parents=True, exist_ok=True)

    thread_id: str | None = None
    previous_selection: dict[str, Any] | None = None
    stage_selections: list[dict[str, Any]] = []
    session_metadata: dict[str, Any] = {
        "run_id": run_id,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "independent_run_session": True,
        "created_at_utc": utc_now(),
        "stages": [],
    }

    for stage in STAGES:
        selection: dict[str, Any] | None = None
        rows: list[dict[str, Any]] | None = None
        correction: str | None = None
        errors: list[str] = []

        for attempt in range(1, args.max_generation_attempts + 1):
            response_path = (
                run_dir / "raw_outputs" / f"{stage}_attempt_{attempt}.json"
            )
            stdout_path = run_dir / "logs" / f"{stage}_attempt_{attempt}.stdout.jsonl"
            stderr_path = run_dir / "logs" / f"{stage}_attempt_{attempt}.stderr.log"
            prompt_path = run_dir / "prompts" / f"{stage}_attempt_{attempt}.txt"
            prompt = build_stage_prompt(
                stage,
                prompts[stage],
                run_id,
                previous_selection,
                correction,
            )
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")

            try:
                thread_id, call_metadata = invoke_codex(
                    codex=codex,
                    workspace=workspace,
                    schema_path=schema_path,
                    model=args.model,
                    reasoning_effort=args.reasoning_effort,
                    prompt=prompt,
                    output_path=response_path,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    thread_id=thread_id,
                )
                response = json.loads(response_path.read_text(encoding="utf-8"))
                rows, selection = evaluator.evaluate_stage(
                    response["candidates"], stage
                )
                write_json(
                    run_dir / "parsed_structures" / f"{stage}_attempt_{attempt}.json",
                    rows,
                )
                call_metadata.update(
                    {
                        "stage": stage,
                        "attempt": attempt,
                        "valid_candidate_count": selection["valid_candidate_count"],
                        "selected_expression": selection["selected_expression"],
                    }
                )
                session_metadata["stages"].append(call_metadata)
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                errors.append(error)
                correction = (
                    "The previous attempt could not be accepted. Return exactly 16 legal, "
                    f"structurally varied {stage} expressions. Validation error: {error}"
                )

        if selection is None or rows is None:
            write_json(run_dir / "failure.json", {"stage": stage, "errors": errors})
            raise RuntimeError(f"Run {run_id:03d} failed at {stage}: {errors}")

        save_stage_csv(run_dir / "cv_results" / f"{stage}.csv", rows)
        write_json(run_dir / "selected_models" / f"{stage}.json", selection)
        stage_selections.append(selection)
        previous_selection = selection
        write_json(run_dir / "session.json", {**session_metadata, "thread_id": thread_id})

    assert previous_selection is not None
    test_metrics = evaluate_final_test(
        evaluator, args.test, previous_selection["selected_terms"]
    )
    final = {
        "run_id": run_id,
        "thread_id": thread_id,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "cv_seed": args.cv_seed,
        "selection_policy": (
            "Within each stage, structures within 5% of the best training-set "
            "five-fold CV RMSE were accuracy-equivalent; fewest terms won, then "
            "lower CV RMSE. Test data were evaluated only after M4 selection."
        ),
        "stage_selections": stage_selections,
        "final_stage": "M4",
        "final_cv_rmse_mean": previous_selection["selected_cv_rmse_mean"],
        "final_cv_rmse_std": previous_selection["selected_cv_rmse_std"],
        "final_cv_r2": previous_selection["selected_cv_r2"],
        **test_metrics,
        "completed_at_utc": utc_now(),
    }
    write_json(final_path, final)
    return final


def summarize(output_dir: Path, finals: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    summary_dir = output_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    finals = sorted(finals, key=lambda item: item["run_id"])

    metric_rows = [
        {
            "run_id": item["run_id"],
            "final_expression": item["symbolic_expression"],
            "fitted_expression": item["fitted_expression"],
            "terms": ";".join(item["terms"]),
            "term_count": item["term_count"],
            "cv_rmse_mean": item["final_cv_rmse_mean"],
            "cv_rmse_std": item["final_cv_rmse_std"],
            "cv_r2": item["final_cv_r2"],
            "train_rmse": item["train_rmse"],
            "train_mae": item["train_mae"],
            "train_r2": item["train_r2"],
            "test_rmse": item["test_rmse"],
            "test_mae": item["test_mae"],
            "test_r2": item["test_r2"],
        }
        for item in finals
    ]
    pd.DataFrame(metric_rows).to_csv(
        summary_dir / "repeated_run_metrics.csv", index=False, encoding="utf-8-sig"
    )

    term_rows = []
    for term in TERM_ORDER:
        frequency = sum(term in item["terms"] for item in finals)
        term_rows.append(
            {
                "term": term,
                "frequency": frequency,
                "percentage": 100.0 * frequency / len(finals),
            }
        )
    pd.DataFrame(term_rows).to_csv(
        summary_dir / "term_frequency.csv", index=False, encoding="utf-8-sig"
    )

    jaccard_rows = []
    for left, right in combinations(finals, 2):
        left_terms = set(left["terms"])
        right_terms = set(right["terms"])
        jaccard_rows.append(
            {
                "run_a": left["run_id"],
                "run_b": right["run_id"],
                "jaccard": len(left_terms & right_terms) / len(left_terms | right_terms),
            }
        )
    pd.DataFrame(jaccard_rows).to_csv(
        summary_dir / "jaccard_similarity.csv", index=False, encoding="utf-8-sig"
    )

    signs: dict[str, Counter[str]] = defaultdict(Counter)
    for item in finals:
        for coefficient in item["coefficients"]:
            term = coefficient["term"]
            value = coefficient["coefficient"]
            signs[term]["positive" if value > 0 else "negative" if value < 0 else "zero"] += 1
    sign_rows = [
        {
            "term": term,
            "positive_runs": counts["positive"],
            "negative_runs": counts["negative"],
            "zero_runs": counts["zero"],
        }
        for term, counts in sorted(
            signs.items(), key=lambda pair: (-1 if pair[0] == "Intercept" else TERM_ORDER.index(pair[0]))
        )
    ]
    pd.DataFrame(sign_rows).to_csv(
        summary_dir / "coefficient_sign_stability.csv",
        index=False,
        encoding="utf-8-sig",
    )

    stage_rows = []
    for item in finals:
        for selection in item["stage_selections"]:
            stage_rows.append(
                {
                    "run_id": item["run_id"],
                    "stage": selection["stage"],
                    "valid_candidate_count": selection["valid_candidate_count"],
                    "unique_valid_structure_count": selection[
                        "unique_valid_structure_count"
                    ],
                    "selected_expression": selection["selected_expression"],
                    "selected_terms": ";".join(selection["selected_terms"]),
                    "selected_term_count": selection["selected_term_count"],
                    "selected_cv_rmse_mean": selection["selected_cv_rmse_mean"],
                    "selected_cv_rmse_std": selection["selected_cv_rmse_std"],
                    "selected_cv_r2": selection["selected_cv_r2"],
                }
            )
    pd.DataFrame(stage_rows).to_csv(
        summary_dir / "stage_selections.csv", index=False, encoding="utf-8-sig"
    )

    with (summary_dir / "final_models.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for item in finals:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    test_rmse = [item["test_rmse"] for item in finals]
    cv_rmse = [item["final_cv_rmse_mean"] for item in finals]
    jaccard_values = [row["jaccard"] for row in jaccard_rows]
    structure_counts = Counter(tuple(item["terms"]) for item in finals)
    aggregate = {
        **manifest,
        "completed_runs": len(finals),
        "unique_final_structures": len(structure_counts),
        "final_structure_frequencies": [
            {"terms": list(terms), "frequency": frequency}
            for terms, frequency in structure_counts.most_common()
        ],
        "cv_rmse": {
            "mean": statistics.mean(cv_rmse),
            "std": statistics.stdev(cv_rmse) if len(cv_rmse) > 1 else 0.0,
            "min": min(cv_rmse),
            "median": statistics.median(cv_rmse),
            "max": max(cv_rmse),
        },
        "test_rmse": {
            "mean": statistics.mean(test_rmse),
            "std": statistics.stdev(test_rmse) if len(test_rmse) > 1 else 0.0,
            "min": min(test_rmse),
            "median": statistics.median(test_rmse),
            "max": max(test_rmse),
        },
        "mean_pairwise_jaccard": statistics.mean(jaccard_values)
        if jaccard_values
        else 1.0,
    }
    write_json(summary_dir / "experiment_summary.json", aggregate)


def main() -> int:
    args = parse_args()
    workspace = Path.cwd().resolve()
    args.output_dir = (workspace / args.output_dir).resolve()
    args.train = (workspace / args.train).resolve()
    args.test = (workspace / args.test).resolve()
    schema_path = (workspace / "candidate_batch.schema.json").resolve()
    codex = find_codex()

    if args.overwrite and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    prompts = {
        stage: (workspace / "prompts" / f"{stage}.txt").read_text(encoding="utf-8")
        for stage in STAGES
    }
    evaluator = TrainingEvaluator(args.train, seed=args.cv_seed)
    evaluator.fold_manifest().to_csv(
        args.output_dir / "fold_manifest.csv", index=False, encoding="utf-8-sig"
    )

    manifest = {
        "started_at_utc": utc_now(),
        "requested_runs": args.runs,
        "run_range": [args.start_run, args.runs],
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "codex_executable": codex,
        "codex_version": subprocess.run(
            [codex, "--version"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "cv_seed": args.cv_seed,
        "folds": 5,
        "candidates_per_stage": 16,
        "train_path": str(args.train),
        "train_sha256": sha256(args.train),
        "test_path": str(args.test),
        "test_sha256": sha256(args.test),
        "prompt_sha256": {
            stage: sha256(workspace / "prompts" / f"{stage}.txt") for stage in STAGES
        },
        "schema_sha256": sha256(schema_path),
        "codex_controls_note": (
            "Codex CLI does not expose temperature or seed. Runs use separate new "
            "sessions with the same model, prompts, data, CV folds, and selection rules."
        ),
    }
    write_json(args.output_dir / "experiment_manifest.json", manifest)

    run_ids = list(range(args.start_run, args.runs + 1))
    finals: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        futures = {
            executor.submit(
                run_one,
                run_id,
                args=args,
                codex=codex,
                workspace=workspace,
                prompts=prompts,
                evaluator=evaluator,
                schema_path=schema_path,
            ): run_id
            for run_id in run_ids
        }
        for future in as_completed(futures):
            run_id = futures[future]
            try:
                final = future.result()
                finals.append(final)
                print(
                    f"Run {run_id:03d} complete: CV RMSE "
                    f"{final['final_cv_rmse_mean']:.6f}, test RMSE "
                    f"{final['test_rmse']:.6f}",
                    flush=True,
                )
            except Exception as exc:
                failures.append(
                    {"run_id": run_id, "error": f"{type(exc).__name__}: {exc}"}
                )
                print(f"Run {run_id:03d} failed: {exc}", file=sys.stderr, flush=True)

    existing_finals = []
    for final_path in sorted(args.output_dir.glob("run_*/selected_models/final.json")):
        existing_finals.append(json.loads(final_path.read_text(encoding="utf-8")))
    summarize(args.output_dir, existing_finals, manifest)
    write_json(args.output_dir / "failures.json", failures)
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
