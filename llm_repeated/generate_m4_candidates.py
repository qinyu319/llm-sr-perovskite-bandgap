from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.5-2026-04-23"
DEFAULT_TEMPERATURE = 0.9
DEFAULT_RUNS = 30
DEFAULT_PROMPT = Path("prompts/M4.txt")
DEFAULT_OUTPUT = Path("raw_outputs/candidates_30_M4.jsonl")
SYSTEM_PROMPT = "You are a materials-physics and symbolic-regression expert."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate independent raw M4 symbolic-expression candidates."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum attempts per run for transient API failures.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output instead of resuming missing run IDs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without making API requests.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_existing_run_ids(path: Path) -> set[int]:
    completed: set[int] = set()
    if not path.exists():
        return completed

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number} is not valid JSONL: {exc}"
                ) from exc
            if row.get("status") == "ok":
                completed.add(int(row["run_id"]))
    return completed


def usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()


def generate_one(
    client: OpenAI,
    *,
    run_id: int,
    model: str,
    temperature: float,
    prompt: str,
) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        reasoning_effort="none",
        temperature=temperature,
        seed=run_id,
        max_completion_tokens=300,
        store=False,
    )

    message = response.choices[0].message
    raw = (message.content or "").strip()
    return {
        "run_id": run_id,
        "seed": run_id,
        "status": "ok",
        "requested_model": model,
        "model": response.model,
        "temperature": temperature,
        "reasoning_effort": "none",
        "system_fingerprint": getattr(response, "system_fingerprint", None),
        "request_id": getattr(response, "_request_id", None),
        "response_id": response.id,
        "created": response.created,
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "finish_reason": response.choices[0].finish_reason,
        "refusal": getattr(message, "refusal", None),
        "usage": usage_to_dict(response.usage),
        "raw": raw,
    }


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be at least 1.")
    if not 0 <= args.temperature <= 2:
        raise ValueError("--temperature must be between 0 and 2.")
    if args.max_attempts < 1:
        raise ValueError("--max-attempts must be at least 1.")

    prompt = args.prompt.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty: {args.prompt}")

    if args.overwrite and args.output.exists() and not args.dry_run:
        args.output.unlink()

    completed = set() if args.overwrite else load_existing_run_ids(args.output)
    pending = [run_id for run_id in range(1, args.runs + 1) if run_id not in completed]

    print(f"Model: {args.model}")
    print(f"Temperature: {args.temperature}")
    print(f"Prompt: {args.prompt.resolve()}")
    print(f"Output: {args.output.resolve()}")
    print(f"Completed: {len(completed)}; pending: {len(pending)}")

    if args.dry_run:
        print("Dry run passed; no API requests were made.")
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set. Configure it in the environment before running.",
            file=sys.stderr,
        )
        return 2

    client = OpenAI(max_retries=0, timeout=120.0)
    failed_runs: list[int] = []

    for run_id in pending:
        for attempt in range(1, args.max_attempts + 1):
            try:
                row = generate_one(
                    client,
                    run_id=run_id,
                    model=args.model,
                    temperature=args.temperature,
                    prompt=prompt,
                )
                append_jsonl(args.output, row)
                print(f"[{run_id:02d}/{args.runs}] {row['raw']}")
                break
            except Exception as exc:
                if attempt < args.max_attempts:
                    delay = 2 ** (attempt - 1)
                    print(
                        f"[{run_id:02d}/{args.runs}] attempt {attempt} failed: "
                        f"{type(exc).__name__}: {exc}; retrying in {delay}s",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue

                failed_runs.append(run_id)
                append_jsonl(
                    args.output,
                    {
                        "run_id": run_id,
                        "seed": run_id,
                        "status": "error",
                        "requested_model": args.model,
                        "temperature": args.temperature,
                        "reasoning_effort": "none",
                        "attempts": args.max_attempts,
                        "finished_at_utc": utc_now(),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                print(
                    f"[{run_id:02d}/{args.runs}] failed after "
                    f"{args.max_attempts} attempts: {exc}",
                    file=sys.stderr,
                )

    if failed_runs:
        print(
            f"Completed with failed run IDs: {failed_runs}. Rerun the same command "
            "to retry them without repeating successful calls.",
            file=sys.stderr,
        )
        return 1

    print(f"All {args.runs} runs are present in {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
