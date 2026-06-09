from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import openai
import pandas as pd
from openai import OpenAI

from repeated_modeling import (
    TERM_ORDER,
    TrainingEvaluator,
    evaluate_final_test,
    write_json,
)


STAGES = ("M0", "M1", "M2", "M3", "M4")
REPO_ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
}

SYSTEM_MESSAGE = """You propose symbolic structures for a controlled scientific experiment.
Follow the supplied stage constraints exactly. Do not fit coefficients, inspect data,
report performance, or explain your choices. Return only one JSON object with exactly
this shape: {"candidates": ["expression 1", "...", "expression 16"]}.
The candidates should be structurally distinct where the stage constraints allow."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run auditable repeated M0-M4 experiments through Qwen or DeepSeek APIs."
    )
    parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    parser.add_argument(
        "--temperatures",
        type=float,
        nargs="+",
        default=[0.2, 0.7, 1.0],
    )
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--runs-per-temperature", type=int, default=10)
    parser.add_argument("--start-run", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=3000)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=300.0)
    parser.add_argument("--cv-seed", type=int, default=20260607)
    parser.add_argument("--qwen-seed-base", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--train", type=Path, default=REPO_ROOT / "data" / "train_518.xlsx"
    )
    parser.add_argument(
        "--test", type=Path, default=REPO_ROOT / "data" / "test_92.xlsx"
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_secret_from_environment(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(value, str) and value:
            return value
    return None


def temperature_label(value: float) -> str:
    return f"temperature_{value:.2f}".replace(".", "p")


def build_stage_prompt(
    stage: str,
    frozen_prompt: str,
    run_id: int,
    temperature: float,
    previous_selection: dict[str, Any] | None,
    correction: str | None,
) -> str:
    inherited = ""
    if previous_selection:
        inherited = f"""
Previous-stage deterministic training-set selection within this same independent run:
- selected structure: {previous_selection['selected_expression']}
- selected non-constant terms: {', '.join(previous_selection['selected_terms'])}
- mean five-fold CV RMSE: {previous_selection['selected_cv_rmse_mean']:.8f} eV

Use that structure only as the previous-stage baseline. Do not use results from any
other run. Extend, revise, or simplify it only under the current stage constraints.
"""
    correction_text = ""
    if correction:
        correction_text = (
            "\nThe preceding API response could not be parsed or contained no legal "
            f"candidate. Correct this in the new response: {correction}\n"
        )
    return f"""Independent workflow run: {run_id:03d}
Sampling temperature: {temperature}
Current stage: {stage}

Generate exactly 16 expression structures. Every expression must include a constant
term and follow the frozen stage prompt below. Return only JSON, without Markdown.
{inherited}{correction_text}
Frozen stage prompt:
{frozen_prompt.strip()}
"""


def parse_candidate_batch(content: str) -> list[str]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("response does not contain a JSON object")
        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("response JSON has no candidates array")
    if len(candidates) != 16:
        raise ValueError(f"expected 16 candidates, received {len(candidates)}")
    if not all(isinstance(candidate, str) and candidate.strip() for candidate in candidates):
        raise ValueError("all candidates must be non-empty strings")
    return candidates


def response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return json.loads(response.model_dump_json())


def call_model(
    *,
    client: OpenAI,
    provider: str,
    model: str,
    prompt: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    qwen_seed: int | None,
) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any]]:
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if provider == "qwen" and qwen_seed is not None:
        request["seed"] = qwen_seed
    if provider == "deepseek":
        request["extra_body"] = {"thinking": {"type": "disabled"}}

    started_at = utc_now()
    started = time.perf_counter()
    response = client.chat.completions.create(**request)
    elapsed = time.perf_counter() - started
    response_dict = response_to_dict(response)
    content = response.choices[0].message.content or ""

    public_request = {
        key: value for key, value in request.items() if key != "extra_body"
    }
    if "extra_body" in request:
        public_request["extra_body"] = request["extra_body"]
    metadata = {
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "elapsed_seconds": round(elapsed, 3),
        "response_id": response_dict.get("id"),
        "response_model": response_dict.get("model"),
        "system_fingerprint": response_dict.get("system_fingerprint"),
        "finish_reason": response_dict.get("choices", [{}])[0].get("finish_reason"),
        "usage": response_dict.get("usage"),
    }
    return public_request, response_dict, content, metadata


def save_stage_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flattened = []
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
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(flattened).to_csv(path, index=False, encoding="utf-8-sig")


def run_one(
    *,
    client: OpenAI,
    provider: str,
    model: str,
    temperature: float,
    run_id: int,
    prompts: dict[str, str],
    evaluator: TrainingEvaluator,
    args: argparse.Namespace,
    condition_dir: Path,
) -> dict[str, Any]:
    run_dir = condition_dir / f"run_{run_id:03d}"
    final_path = run_dir / "selected_models" / "final.json"
    if final_path.exists() and not args.overwrite:
        return json.loads(final_path.read_text(encoding="utf-8"))

    previous_selection: dict[str, Any] | None = None
    stage_selections: list[dict[str, Any]] = []
    call_records: list[dict[str, Any]] = []
    qwen_seed = (
        args.qwen_seed_base + run_id - 1
        if provider == "qwen" and args.qwen_seed_base is not None
        else None
    )

    for stage in STAGES:
        correction = None
        selection = None
        rows = None
        errors: list[str] = []
        for attempt in range(1, args.max_generation_attempts + 1):
            attempt_dir = run_dir / "api_calls" / stage / f"attempt_{attempt}"
            prompt = build_stage_prompt(
                stage,
                prompts[stage],
                run_id,
                temperature,
                previous_selection,
                correction,
            )
            attempt_dir.mkdir(parents=True, exist_ok=True)
            (attempt_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
            try:
                request, response, content, api_metadata = call_model(
                    client=client,
                    provider=provider,
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    top_p=args.top_p,
                    max_tokens=args.max_tokens,
                    qwen_seed=qwen_seed,
                )
                write_json(attempt_dir / "request.json", request)
                write_json(attempt_dir / "response.json", response)
                (attempt_dir / "raw_content.txt").write_text(content, encoding="utf-8")
                candidates = parse_candidate_batch(content)
                rows, selection = evaluator.evaluate_stage(candidates, stage)
                write_json(attempt_dir / "parsed_candidates.json", rows)
                record = {
                    "stage": stage,
                    "attempt": attempt,
                    "status": "accepted",
                    **api_metadata,
                    "valid_candidate_count": selection["valid_candidate_count"],
                    "selected_expression": selection["selected_expression"],
                }
                call_records.append(record)
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                errors.append(error)
                write_json(
                    attempt_dir / "error.json",
                    {"error": error, "recorded_at_utc": utc_now()},
                )
                call_records.append(
                    {
                        "stage": stage,
                        "attempt": attempt,
                        "status": "failed",
                        "error": error,
                    }
                )
                correction = error

        if selection is None or rows is None:
            write_json(
                run_dir / "failure.json",
                {"stage": stage, "errors": errors, "calls": call_records},
            )
            raise RuntimeError(f"run {run_id:03d} failed at {stage}: {errors}")

        save_stage_csv(run_dir / "cv_results" / f"{stage}.csv", rows)
        write_json(run_dir / "selected_models" / f"{stage}.json", selection)
        stage_selections.append(selection)
        previous_selection = selection

    assert previous_selection is not None
    test_metrics = evaluate_final_test(
        evaluator,
        args.test,
        previous_selection["selected_terms"],
    )
    final = {
        "provider": provider,
        "requested_model": model,
        "temperature": temperature,
        "top_p": args.top_p,
        "qwen_seed": qwen_seed,
        "run_id": run_id,
        "selection_policy": (
            "Within each stage, candidates within 5% of the best training-set "
            "five-fold CV RMSE were accuracy-equivalent; the fewest-term candidate "
            "won, followed by lower CV RMSE and candidate index. Test data were "
            "loaded only after M4 selection."
        ),
        "stage_selections": stage_selections,
        "api_calls": call_records,
        "final_cv_rmse_mean": previous_selection["selected_cv_rmse_mean"],
        "final_cv_rmse_std": previous_selection["selected_cv_rmse_std"],
        "final_cv_r2": previous_selection["selected_cv_r2"],
        **test_metrics,
        "completed_at_utc": utc_now(),
    }
    write_json(final_path, final)
    write_json(
        run_dir / "run_manifest.json",
        {
            "provider": provider,
            "requested_model": model,
            "temperature": temperature,
            "top_p": args.top_p,
            "qwen_seed": qwen_seed,
            "run_id": run_id,
            "calls": call_records,
        },
    )
    return final


def mean_pairwise_jaccard(finals: list[dict[str, Any]]) -> float | None:
    similarities = []
    for left, right in combinations(finals, 2):
        a = set(left["terms"])
        b = set(right["terms"])
        similarities.append(len(a & b) / len(a | b))
    return statistics.mean(similarities) if similarities else None


def summarize_condition(
    condition_dir: Path,
    finals: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    summary_dir = condition_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    finals = sorted(finals, key=lambda item: item["run_id"])
    metric_rows = [
        {
            "run_id": item["run_id"],
            "provider": item["provider"],
            "requested_model": item["requested_model"],
            "temperature": item["temperature"],
            "top_p": item["top_p"],
            "qwen_seed": item["qwen_seed"],
            "terms": ";".join(item["terms"]),
            "term_count": item["term_count"],
            "cv_rmse_mean": item["final_cv_rmse_mean"],
            "cv_rmse_std": item["final_cv_rmse_std"],
            "test_rmse": item["test_rmse"],
            "test_mae": item["test_mae"],
            "test_r2": item["test_r2"],
        }
        for item in finals
    ]
    pd.DataFrame(metric_rows).to_csv(
        summary_dir / "repeated_run_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    structure_counts = Counter(tuple(item["terms"]) for item in finals)
    structure_rows = [
        {
            "terms": ";".join(terms),
            "frequency": count,
            "percentage": 100 * count / len(finals),
        }
        for terms, count in structure_counts.most_common()
    ] if finals else []
    pd.DataFrame(structure_rows).to_csv(
        summary_dir / "structure_frequency.csv",
        index=False,
        encoding="utf-8-sig",
    )

    term_rows = []
    for term in TERM_ORDER:
        count = sum(term in item["terms"] for item in finals)
        term_rows.append(
            {
                "term": term,
                "frequency": count,
                "percentage": 100 * count / len(finals) if finals else math.nan,
            }
        )
    pd.DataFrame(term_rows).to_csv(
        summary_dir / "term_frequency.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "completed_runs": len(finals),
        "failed_runs": len(failures),
        "unique_final_structures": len(structure_counts),
        "mean_pairwise_jaccard": mean_pairwise_jaccard(finals),
        "structure_frequencies": structure_rows,
        "cv_rmse": descriptive([item["final_cv_rmse_mean"] for item in finals]),
        "test_rmse": descriptive([item["test_rmse"] for item in finals]),
        "failures": failures,
    }
    write_json(summary_dir / "experiment_summary.json", summary)
    with (summary_dir / "final_models.jsonl").open("w", encoding="utf-8") as handle:
        for item in finals:
            handle.write(json.dumps(item, ensure_ascii=False, allow_nan=False) + "\n")


def descriptive(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def main() -> int:
    args = parse_args()
    provider_config = PROVIDERS[args.provider]
    model = args.model or provider_config["model"]
    base_url = args.base_url or provider_config["base_url"]
    api_key_env = args.api_key_env or provider_config["api_key_env"]

    for temperature in args.temperatures:
        if not 0 <= temperature < 2:
            raise ValueError("each temperature must be in [0, 2)")
    if not 0 < args.top_p <= 1:
        raise ValueError("top_p must be in (0, 1]")
    if args.runs_per_temperature < 1:
        raise ValueError("runs-per-temperature must be positive")

    workspace = Path(__file__).resolve().parent
    args.train = args.train.resolve()
    args.test = args.test.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else workspace / "external_api_runs" / args.provider
    )
    prompts = {
        stage: (workspace / "prompts" / f"{stage}.txt").read_text(encoding="utf-8")
        for stage in STAGES
    }

    manifest = {
        "created_at_utc": utc_now(),
        "provider": args.provider,
        "requested_model": model,
        "base_url": base_url,
        "api_key_environment_variable": api_key_env,
        "temperatures": args.temperatures,
        "top_p": args.top_p,
        "runs_per_temperature": args.runs_per_temperature,
        "max_tokens": args.max_tokens,
        "max_generation_attempts": args.max_generation_attempts,
        "qwen_seed_base": args.qwen_seed_base,
        "cv_seed": args.cv_seed,
        "python_version": platform.python_version(),
        "openai_version": openai.__version__,
        "train_path": str(args.train),
        "train_sha256": sha256(args.train),
        "test_path": str(args.test),
        "test_sha256": sha256(args.test),
        "prompt_sha256": {
            stage: sha256(workspace / "prompts" / f"{stage}.txt")
            for stage in STAGES
        },
        "protocol_note": (
            "Each run is independent. M0-M4 use frozen prompts and inherit only the "
            "same run's preceding selected structure. Candidate coefficients and "
            "selection metrics are computed locally; no data are sent to the LLM."
        ),
    }

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        print("Dry run successful; no API request was made.")
        return 0

    api_key = read_secret_from_environment(api_key_env)
    if not api_key:
        raise RuntimeError(
            f"environment variable {api_key_env} is not set; API keys must not be "
            "stored in source files or command history"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "experiment_manifest.json", manifest)
    evaluator = TrainingEvaluator(args.train, seed=args.cv_seed)
    evaluator.fold_manifest().to_csv(
        output_dir / "fold_manifest.csv",
        index=False,
        encoding="utf-8-sig",
    )
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=args.request_timeout,
        max_retries=3,
    )

    overall_failures = []
    for temperature in args.temperatures:
        condition_dir = output_dir / temperature_label(temperature)
        finals = []
        failures = []
        end_run = args.start_run + args.runs_per_temperature
        for run_id in range(args.start_run, end_run):
            try:
                final = run_one(
                    client=client,
                    provider=args.provider,
                    model=model,
                    temperature=temperature,
                    run_id=run_id,
                    prompts=prompts,
                    evaluator=evaluator,
                    args=args,
                    condition_dir=condition_dir,
                )
                finals.append(final)
                print(
                    f"{args.provider} T={temperature:.2f} run {run_id:03d}: "
                    f"CV={final['final_cv_rmse_mean']:.6f}, "
                    f"test={final['test_rmse']:.6f}",
                    flush=True,
                )
            except Exception as exc:
                failure = {
                    "temperature": temperature,
                    "run_id": run_id,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                failures.append(failure)
                overall_failures.append(failure)
                print(
                    f"{args.provider} T={temperature:.2f} run {run_id:03d} failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        all_finals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(condition_dir.glob("run_*/selected_models/final.json"))
        ]
        summarize_condition(condition_dir, all_finals, failures)

    write_json(output_dir / "failures.json", overall_failures)
    return 1 if overall_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
