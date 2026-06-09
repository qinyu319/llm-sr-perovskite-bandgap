from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from .config import PROJECT_ROOT
from .cv_selection import select_model_by_cv
from .feature_engineering import formula_string
from .metrics import evaluation_metrics, jaccard, mae, rmse
from .model_terms import FINAL_M4_TERMS
from .ols_fit import fit_ols, predict_ols
from .splitters import SplitRecord


SCREENING_FEATURES = ["FA", "MA", "Cs", "Pb", "Sn", "Br", "Cl", "I"]


def training_only_screening(split: SplitRecord, train_df: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    y = train_df["Eg"].to_numpy(dtype=float)
    for feature in SCREENING_FEATURES:
        x = train_df[feature].to_numpy(dtype=float)
        if np.isclose(np.std(x), 0.0):
            pearson = np.nan
            spearman = np.nan
        else:
            pearson = pearsonr(x, y).statistic
            spearman = spearmanr(x, y).statistic
        rows.append(
            {
                "split_id": split.split_id,
                "group_strategy": split.group_strategy,
                "feature": feature,
                "pearson_r_train_only": float(pearson) if pd.notna(pearson) else np.nan,
                "spearman_r_train_only": float(spearman) if pd.notna(spearman) else np.nan,
                "train_mean": float(np.mean(x)),
                "train_sd": float(np.std(x, ddof=1)),
                "screening_used_test_group": False,
                "external_test_used": False,
            }
        )
    return rows


def run_one_split(df: pd.DataFrame, split: SplitRecord, cfg: dict) -> tuple[dict[str, object], pd.DataFrame, list[dict[str, object]]]:
    train_df = df.iloc[list(split.train_indices)].copy()
    test_df = df.iloc[list(split.test_indices)].copy()

    screening_rows = training_only_screening(split, train_df)
    selection = select_model_by_cv(train_df, split.group_column, cfg, return_candidate_table=True)
    model = fit_ols(train_df, selection.selected_terms)
    train_pred = predict_ols(model, train_df)
    test_pred = predict_ols(model, test_df)

    train_metrics = {
        "train_rmse": rmse(train_df["Eg"], train_pred),
        "train_mae": mae(train_df["Eg"], train_pred),
    }
    test_metrics = evaluation_metrics(test_df, test_df["Eg"], test_pred)
    coefs = model["coefficients"]
    terms = list(selection.selected_terms)
    result = {
        "split_id": split.split_id,
        "group_strategy": split.group_strategy,
        "group_column": split.group_column,
        "heldout_groups": ";".join(split.heldout_groups),
        "n_train": len(train_df),
        "n_test": len(test_df),
        "train_Eg_mean": float(train_df["Eg"].mean()),
        "test_Eg_mean": float(test_df["Eg"].mean()),
        "train_Eg_std": float(train_df["Eg"].std(ddof=1)),
        "test_Eg_std": float(test_df["Eg"].std(ddof=1)),
        "selected_stage": selection.selected_stage,
        "selected_family": selection.selected_family,
        "selected_terms": ",".join(terms),
        "n_terms": selection.n_terms,
        "n_candidates_scored": selection.n_candidates,
        "inner_cv_method": selection.cv_method,
        "cv_rmse_mean": selection.cv_rmse_mean,
        "cv_rmse_std": selection.cv_rmse_std,
        "cv_mae_mean": selection.cv_mae_mean,
        "cv_mae_std": selection.cv_mae_std,
        **train_metrics,
        "test_rmse": test_metrics["rmse"],
        "test_mae": test_metrics["mae"],
        "test_r2": test_metrics["r2"],
        "test_median_ae": test_metrics["median_ae"],
        "test_max_ae": test_metrics["max_ae"],
        "high_Eg_rmse": test_metrics["high_Eg_rmse"],
        "Cl_rich_rmse": test_metrics["Cl_rich_rmse"],
        "MA_rich_rmse": test_metrics["MA_rich_rmse"],
        "formula_jaccard_to_M4": jaccard(terms, FINAL_M4_TERMS),
        "coefficients": json.dumps(coefs, ensure_ascii=False, sort_keys=True),
        "selected_formula_string": formula_string(terms, coefs),
        "screening_cv_pruning_scope": "current_outer_train_only",
        "outer_test_group_used_for_selection": False,
        "external_test_used_for_selection": False,
    }

    candidate_table = selection.candidate_table.copy()
    candidate_table.insert(0, "split_id", split.split_id)
    candidate_table.insert(1, "group_strategy", split.group_strategy)
    return result, candidate_table, screening_rows


def run_full_workflow(df: pd.DataFrame, splits: list[SplitRecord], cfg: dict) -> pd.DataFrame:
    result_rows = []
    candidate_tables = []
    screening_rows = []
    for split in splits:
        result, candidate_table, screening = run_one_split(df, split, cfg)
        result_rows.append(result)
        candidate_tables.append(candidate_table)
        screening_rows.extend(screening)

    out_dir = PROJECT_ROOT / "outputs" / "per_split_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = pd.DataFrame(result_rows)
    results.to_csv(out_dir / "group_aware_full_workflow_results.csv", index=False, encoding="utf-8-sig")
    pd.concat(candidate_tables, ignore_index=True).to_csv(
        out_dir / "group_aware_candidate_cv_audit.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(screening_rows).to_csv(
        out_dir / "training_only_screening.csv", index=False, encoding="utf-8-sig"
    )

    formulas = results[
        ["split_id", "group_strategy", "selected_formula_string", "selected_terms", "coefficients"]
    ].copy()
    formulas.to_csv(
        PROJECT_ROOT / "outputs" / "summary_tables" / "group_aware_selected_formulas.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return results
