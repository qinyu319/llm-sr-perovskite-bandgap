from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


RUN_DIR = Path("raw_outputs/codex_runs")
OUTPUT = Path("raw_outputs/candidates_30_M4_codex.jsonl")
SUMMARY = Path("raw_outputs/candidates_30_M4_codex_summary.json")


def canonicalize(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^[A-Za-z]+\s*=\s*", "", text)
    text = re.sub(r"β[₀₁₂₃₄₅₆₇₈₉0-9]+", "", text)
    text = text.replace("²", "^2").replace("·", "*")
    text = text.replace("(", "").replace(")", "")
    replacements = {
        "SnBr": "Sn*Br",
        "SnCl": "Sn*Cl",
        "BrCl": "Br*Cl",
        "CsSn": "Cs*Sn",
        "CsBr": "Cs*Br",
        "CsCl": "Cs*Cl",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    terms = [term.strip() for term in text.split("+") if term.strip() not in {"", "1"}]
    return " + ".join(terms)


def main() -> None:
    rows: list[dict[str, object]] = []
    for run_id in range(1, 31):
        path = RUN_DIR / f"run_{run_id:02d}.txt"
        if not path.exists():
            raise FileNotFoundError(path)
        raw = path.read_text(encoding="utf-8").strip()
        if not raw or "\n" in raw or "\r" in raw:
            raise ValueError(f"Run {run_id:02d} is not one non-empty line.")

        canonical = canonicalize(raw)
        term_count = len([term for term in canonical.split(" + ") if term])
        rows.append(
            {
                "run_id": run_id,
                "source": "codex_subagent" if run_id <= 6 else "codex_exec",
                "model": "gpt-5.5",
                "reasoning_effort": None if run_id <= 6 else ("high" if run_id == 7 else "low"),
                "independent_context": True,
                "raw": raw,
                "canonical_for_validation": canonical,
                "non_constant_term_count": term_count,
                "m4_term_count_valid": 8 <= term_count <= 11,
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    canonical_counts = Counter(str(row["canonical_for_validation"]) for row in rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_count": len(rows),
        "all_single_line": True,
        "m4_term_count_valid_runs": sum(bool(row["m4_term_count_valid"]) for row in rows),
        "unique_raw_outputs": len({str(row["raw"]) for row in rows}),
        "unique_canonical_structures": len(canonical_counts),
        "canonical_structure_frequencies": [
            {"structure": structure, "frequency": frequency}
            for structure, frequency in canonical_counts.most_common()
        ],
        "method_note": (
            "Runs 1-6 used isolated Codex subagent threads. Runs 7-30 used "
            "independent ephemeral codex exec sessions. Codex does not expose "
            "temperature or seed controls for this workflow."
        ),
    }
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
