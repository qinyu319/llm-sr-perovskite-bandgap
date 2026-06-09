from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from .config import PROJECT_ROOT


@dataclass(frozen=True)
class SplitRecord:
    split_id: str
    group_strategy: str
    group_column: str
    heldout_groups: tuple[str, ...]
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def _indices_to_tuple(values) -> tuple[int, ...]:
    return tuple(int(v) for v in values)


def validate_no_group_leakage(df: pd.DataFrame, split: SplitRecord) -> None:
    train_groups = set(df.iloc[list(split.train_indices)][split.group_column].astype(str))
    test_groups = set(df.iloc[list(split.test_indices)][split.group_column].astype(str))
    overlap = train_groups.intersection(test_groups)
    if overlap:
        raise ValueError(f"Group leakage in {split.split_id}: {sorted(overlap)}")


def make_composition_family_splits(df: pd.DataFrame, cfg: dict) -> list[SplitRecord]:
    settings = cfg["composition_group_shuffle"]
    splitter = GroupShuffleSplit(
        n_splits=int(settings["n_splits"]),
        test_size=float(settings["test_size"]),
        random_state=int(cfg["random_state"]),
    )
    groups = df["composition_family"].astype(str).to_numpy()
    splits: list[SplitRecord] = []
    for i, (train_idx, test_idx) in enumerate(splitter.split(df, groups=groups)):
        heldout = tuple(sorted(df.iloc[test_idx]["composition_family"].astype(str).unique()))
        rec = SplitRecord(
            split_id=f"composition_gss_{i:02d}",
            group_strategy="composition_family_group_shuffle",
            group_column="composition_family",
            heldout_groups=heldout,
            train_indices=_indices_to_tuple(train_idx),
            test_indices=_indices_to_tuple(test_idx),
        )
        validate_no_group_leakage(df, rec)
        splits.append(rec)
    return splits


def make_leave_one_group_splits(df: pd.DataFrame, group_column: str, strategy_name: str) -> list[SplitRecord]:
    splits: list[SplitRecord] = []
    for group_value in sorted(df[group_column].dropna().astype(str).unique()):
        test_mask = df[group_column].astype(str).eq(group_value).to_numpy()
        train_idx = df.index[~test_mask].to_numpy()
        test_idx = df.index[test_mask].to_numpy()
        if len(train_idx) == 0 or len(test_idx) == 0:
            continue
        rec = SplitRecord(
            split_id=f"{strategy_name}_{group_value}",
            group_strategy=strategy_name,
            group_column=group_column,
            heldout_groups=(group_value,),
            train_indices=_indices_to_tuple(train_idx),
            test_indices=_indices_to_tuple(test_idx),
        )
        validate_no_group_leakage(df, rec)
        splits.append(rec)
    return splits


def make_all_splits(df: pd.DataFrame, cfg: dict) -> list[SplitRecord]:
    return (
        make_composition_family_splits(df, cfg)
        + make_leave_one_group_splits(df, "halide_group", "halide_logo")
        + make_leave_one_group_splits(df, "A_site_group", "a_site_logo")
    )


def save_splits(df: pd.DataFrame, splits: list[SplitRecord]) -> pd.DataFrame:
    rows = []
    for split in splits:
        folder = PROJECT_ROOT / "outputs" / "splits" / split.group_strategy
        folder.mkdir(parents=True, exist_ok=True)
        for part, indices in [("train", split.train_indices), ("test", split.test_indices)]:
            part_df = df.iloc[list(indices)][
                [
                    "dataset_index",
                    "sample_id",
                    "id",
                    "source_row_index",
                    "Eg",
                    "A_group",
                    "B_group",
                    "X_group",
                    "composition_family",
                    "halide_group",
                    "A_site_group",
                ]
            ].copy()
            part_df.to_csv(
                folder / f"{split.split_id}_{part}_indices.csv",
                index=False,
                encoding="utf-8-sig",
            )
        rows.append(
            {
                "split_id": split.split_id,
                "group_strategy": split.group_strategy,
                "group_column": split.group_column,
                "heldout_groups": ";".join(split.heldout_groups),
                "n_train": len(split.train_indices),
                "n_test": len(split.test_indices),
                "train_groups": len(set(df.iloc[list(split.train_indices)][split.group_column])),
                "test_groups": len(set(df.iloc[list(split.test_indices)][split.group_column])),
                "no_group_leakage": True,
                "train_indices_file": (
                    Path("outputs") / "splits" / split.group_strategy / f"{split.split_id}_train_indices.csv"
                ).as_posix(),
                "test_indices_file": (
                    Path("outputs") / "splits" / split.group_strategy / f"{split.split_id}_test_indices.csv"
                ).as_posix(),
            }
        )
    manifest = pd.DataFrame(rows)
    manifest.to_csv(
        PROJECT_ROOT / "outputs" / "splits" / "split_manifest.csv",
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
    )
    return manifest
