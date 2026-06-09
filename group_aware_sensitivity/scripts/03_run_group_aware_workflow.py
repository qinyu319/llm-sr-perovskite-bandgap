from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT, load_config
from src.splitters import make_all_splits, validate_no_group_leakage
from src.workflow_rerun import run_full_workflow


def main() -> None:
    cfg = load_config()
    df = pd.read_csv(PROJECT_ROOT / "outputs" / "group_labels" / "group_labels.csv")
    splits = make_all_splits(df, cfg)
    for split in splits:
        validate_no_group_leakage(df, split)
    results = run_full_workflow(df, splits, cfg)
    print(results.groupby("group_strategy")["test_rmse"].agg(["count", "mean", "std", "max"]).to_string())


if __name__ == "__main__":
    main()
