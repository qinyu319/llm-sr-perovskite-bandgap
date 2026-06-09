from __future__ import annotations

import pandas as pd


GROUP_COLUMNS = ["A_group", "B_group", "X_group", "composition_family", "halide_group", "A_site_group"]


def a_site_group(row: pd.Series) -> str:
    if row["MA"] >= 0.5:
        return "MA_rich"
    if row["FA"] >= 0.5:
        return "FA_rich"
    if row["Cs"] >= 0.5:
        return "Cs_rich"
    return "mixed_A"


def b_site_group(row: pd.Series) -> str:
    if row["Sn"] < 0.2:
        return "Pb_rich"
    if row["Sn"] > 0.8:
        return "Sn_rich"
    return "mixed_B"


def x_site_group(row: pd.Series) -> str:
    if row["I"] >= 0.8:
        return "I_rich"
    if row["Br"] >= 0.5 and abs(row["Cl"]) <= 1e-12:
        return "Br_rich"
    if row["Cl"] > 0:
        return "Cl_containing"
    return "mixed_halide"


def assign_group_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["A_group"] = out.apply(a_site_group, axis=1)
    out["B_group"] = out.apply(b_site_group, axis=1)
    out["X_group"] = out.apply(x_site_group, axis=1)
    out["composition_family"] = out["A_group"] + "__" + out["B_group"] + "__" + out["X_group"]
    out["halide_group"] = out["X_group"]
    out["A_site_group"] = out["A_group"]
    return out


def validate_group_labels(df: pd.DataFrame) -> None:
    missing = [c for c in GROUP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing group-label columns: {missing}")
    null_counts = df[GROUP_COLUMNS].isna().sum()
    bad = null_counts[null_counts > 0]
    if len(bad):
        raise ValueError(f"Null group labels detected: {bad.to_dict()}")
