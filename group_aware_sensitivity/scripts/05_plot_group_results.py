from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT, load_config
from src.plot_group_results import generate_all_figures


def main() -> None:
    cfg = load_config()
    results = pd.read_csv(
        PROJECT_ROOT / "outputs" / "per_split_results" / "group_aware_full_workflow_results.csv"
    )
    frequency = pd.read_csv(
        PROJECT_ROOT / "outputs" / "summary_tables" / "group_aware_term_frequency.csv"
    )
    generate_all_figures(results, frequency, float(cfg["reference"]["frozen_m4_test_rmse"]))
    print(f"Figures written to {PROJECT_ROOT / 'outputs' / 'figures'}")


if __name__ == "__main__":
    main()
