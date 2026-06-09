from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT
from src.group_definitions import GROUP_COLUMNS, assign_group_labels, validate_group_labels


def main() -> None:
    data = pd.read_csv(PROJECT_ROOT / "data" / "curated_dataset.csv")
    labeled = assign_group_labels(data)
    validate_group_labels(labeled)
    cols = [
        "dataset_index",
        "sample_id",
        "id",
        "source_row_index",
        "Eg",
        "FA",
        "MA",
        "Cs",
        "Pb",
        "Sn",
        "Br",
        "Cl",
        "I",
        *GROUP_COLUMNS,
    ]
    out = PROJECT_ROOT / "outputs" / "group_labels" / "group_labels.csv"
    labeled[cols].to_csv(out, index=False, encoding="utf-8-sig")
    counts = []
    for col in GROUP_COLUMNS:
        for value, n in labeled[col].value_counts().items():
            counts.append({"group_column": col, "group_value": value, "n": int(n)})
    pd.DataFrame(counts).to_csv(
        PROJECT_ROOT / "outputs" / "group_labels" / "group_counts.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"Group labels written: {out}")
    print(labeled[GROUP_COLUMNS].nunique().to_string())


if __name__ == "__main__":
    main()
