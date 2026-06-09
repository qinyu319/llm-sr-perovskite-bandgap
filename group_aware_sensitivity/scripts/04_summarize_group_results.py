from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT
from src.summarize_group_results import decision_interpretation, summarize_results


def main() -> None:
    results = pd.read_csv(
        PROJECT_ROOT / "outputs" / "per_split_results" / "group_aware_full_workflow_results.csv"
    )
    summary, frequency, heldout = summarize_results(results)
    decision = decision_interpretation(summary, frequency)
    (PROJECT_ROOT / "outputs" / "summary_tables" / "group_aware_decision.txt").write_text(
        decision + "\n", encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(decision)


if __name__ == "__main__":
    main()
