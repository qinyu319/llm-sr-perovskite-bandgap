from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT
from .model_terms import ALL_TERMS


def _split_terms(value: str) -> set[str]:
    if pd.isna(value) or not str(value).strip():
        return set()
    return {v for v in str(value).split(",") if v}


def summarize_results(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    frequency_rows = []
    heldout_rows = []

    for strategy, group in results.groupby("group_strategy", sort=False):
        heldout_summary = (
            group.groupby("heldout_groups", dropna=False)
            .agg(
                n_splits=("split_id", "count"),
                mean_test_rmse=("test_rmse", "mean"),
                sd_test_rmse=("test_rmse", "std"),
                mean_test_mae=("test_mae", "mean"),
                mean_jaccard_to_M4=("formula_jaccard_to_M4", "mean"),
            )
            .reset_index()
        )
        heldout_summary.insert(0, "group_strategy", strategy)
        heldout_rows.append(heldout_summary)
        failure = heldout_summary.sort_values("mean_test_rmse", ascending=False).iloc[0]["heldout_groups"]
        summary_rows.append(
            {
                "group_strategy": strategy,
                "n_splits": len(group),
                "mean_test_rmse": group["test_rmse"].mean(),
                "sd_test_rmse": group["test_rmse"].std(ddof=1),
                "median_test_rmse": group["test_rmse"].median(),
                "worst_test_rmse": group["test_rmse"].max(),
                "mean_test_mae": group["test_mae"].mean(),
                "sd_test_mae": group["test_mae"].std(ddof=1),
                "mean_jaccard_to_M4": group["formula_jaccard_to_M4"].mean(),
                "median_jaccard_to_M4": group["formula_jaccard_to_M4"].median(),
                "mean_n_terms": group["n_terms"].mean(),
                "median_n_terms": group["n_terms"].median(),
                "main_failure_regime": failure,
            }
        )
        term_sets = group["selected_terms"].map(_split_terms)
        for term in ALL_TERMS:
            count = int(term_sets.map(lambda s: term in s).sum())
            frequency_rows.append(
                {
                    "group_strategy": strategy,
                    "term": term,
                    "count_selected": count,
                    "frequency_percentage": 100.0 * count / len(group),
                }
            )

    summary = pd.DataFrame(summary_rows)
    frequency = pd.DataFrame(frequency_rows)
    heldout = pd.concat(heldout_rows, ignore_index=True)
    out = PROJECT_ROOT / "outputs" / "summary_tables"
    summary.to_csv(out / "group_aware_summary.csv", index=False, encoding="utf-8-sig")
    frequency.to_csv(out / "group_aware_term_frequency.csv", index=False, encoding="utf-8-sig")
    heldout.to_csv(out / "group_aware_heldout_group_summary.csv", index=False, encoding="utf-8-sig")
    return summary, frequency, heldout


def decision_interpretation(summary: pd.DataFrame, frequency: pd.DataFrame) -> str:
    composition = summary.loc[summary["group_strategy"].eq("composition_family_group_shuffle")]
    if composition.empty:
        return "Decision C: insufficient composition-family results."
    comp = composition.iloc[0]
    freq = frequency.loc[frequency["group_strategy"].eq("composition_family_group_shuffle")]
    main_freq = freq.set_index("term").reindex(["Sn", "Br", "Cl"])["frequency_percentage"].fillna(0)
    mean_main = float(main_freq.mean())
    mean_j = float(comp["mean_jaccard_to_M4"])
    mean_rmse = float(comp["mean_test_rmse"])
    halide = summary.loc[summary["group_strategy"].eq("halide_logo")]
    worst_halide = float(halide["worst_test_rmse"].iloc[0]) if not halide.empty else np.nan
    if mean_main >= 90 and mean_j >= 0.60 and mean_rmse <= 0.10 and (np.isnan(worst_halide) or worst_halide <= 0.20):
        return "Decision A: strong robustness."
    if mean_main >= 70 and mean_j >= 0.40 and mean_rmse <= 0.16:
        if pd.notna(worst_halide) and worst_halide > 0.20:
            return "Decision B: moderate robustness; strict halide leave-one-group-out identifies Cl-containing compositions as an applicability-domain boundary."
        return "Decision B: moderate robustness."
    return "Decision C: weak robustness."
