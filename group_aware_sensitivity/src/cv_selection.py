from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, KFold

from .feature_engineering import add_engineered_terms
from .metrics import mae, rmse
from .model_terms import ALL_TERMS, generate_candidate_terms


@dataclass(frozen=True)
class CVSelectionResult:
    selected_terms: tuple[str, ...]
    selected_stage: str
    selected_family: str
    cv_rmse_mean: float
    cv_rmse_std: float
    cv_mae_mean: float
    cv_mae_std: float
    n_terms: int
    n_candidates: int
    cv_method: str
    candidate_table: pd.DataFrame


def _make_inner_splits(df: pd.DataFrame, group_column: str, n_splits: int, random_state: int):
    groups = df[group_column].astype(str)
    if groups.nunique() >= n_splits:
        splitter = GroupKFold(n_splits=n_splits)
        return list(splitter.split(df, groups=groups)), f"GroupKFold({group_column})"
    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    return list(splitter.split(df)), "KFold_fallback"


def _fit_predict(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(x_train, y_train, rcond=None)
    return x_val @ beta


def select_model_by_cv(
    train_df: pd.DataFrame,
    group_column: str,
    cfg: dict,
    return_candidate_table: bool = True,
) -> CVSelectionResult:
    n_splits = int(cfg["inner_cv"]["n_splits"])
    random_state = int(cfg["random_state"])
    margin = float(cfg["inner_cv"]["equivalence_margin"])
    max_terms = int(cfg["candidate_terms"]["max_terms"])
    enforce_hierarchy = bool(cfg["candidate_terms"].get("enforce_hierarchy", True))

    candidates = generate_candidate_terms(max_terms=max_terms, enforce_hierarchy=enforce_hierarchy)
    folds, cv_method = _make_inner_splits(train_df, group_column, n_splits, random_state)
    enriched = add_engineered_terms(train_df)
    y = enriched["Eg"].to_numpy(dtype=float)
    term_to_index = {term: i for i, term in enumerate(ALL_TERMS)}
    term_values = enriched[ALL_TERMS].to_numpy(dtype=float)

    rows = []
    for stage, terms, family in candidates:
        col_indices = [term_to_index[t] for t in terms]
        fold_rmses = []
        fold_maes = []
        for tr_idx, val_idx in folds:
            if col_indices:
                x_train = np.column_stack([np.ones(len(tr_idx)), term_values[tr_idx][:, col_indices]])
                x_val = np.column_stack([np.ones(len(val_idx)), term_values[val_idx][:, col_indices]])
            else:
                x_train = np.ones((len(tr_idx), 1))
                x_val = np.ones((len(val_idx), 1))
            pred = _fit_predict(x_train, y[tr_idx], x_val)
            fold_rmses.append(rmse(y[val_idx], pred))
            fold_maes.append(mae(y[val_idx], pred))
        rows.append(
            {
                "stage": stage,
                "candidate_family": family,
                "selected_terms": ",".join(terms),
                "n_terms": len(terms),
                "cv_rmse_mean": float(np.mean(fold_rmses)),
                "cv_rmse_std": float(np.std(fold_rmses, ddof=1)) if len(fold_rmses) > 1 else 0.0,
                "cv_mae_mean": float(np.mean(fold_maes)),
                "cv_mae_std": float(np.std(fold_maes, ddof=1)) if len(fold_maes) > 1 else 0.0,
            }
        )
    table = pd.DataFrame(rows)
    best_rmse = table["cv_rmse_mean"].min()
    equivalent = table.loc[table["cv_rmse_mean"] <= best_rmse * (1.0 + margin)].copy()
    equivalent = equivalent.sort_values(["n_terms", "cv_rmse_mean", "selected_terms"], kind="mergesort")
    selected = equivalent.iloc[0]
    selected_terms = tuple(t for t in str(selected["selected_terms"]).split(",") if t)
    if return_candidate_table:
        table = table.sort_values(["cv_rmse_mean", "n_terms", "selected_terms"], kind="mergesort")
        table["best_cv_rmse"] = best_rmse
        table["within_5pct_best"] = table["cv_rmse_mean"] <= best_rmse * (1.0 + margin)
        table["selected_by_rule"] = table["selected_terms"].eq(",".join(selected_terms))
    else:
        table = pd.DataFrame()
    return CVSelectionResult(
        selected_terms=selected_terms,
        selected_stage=str(selected["stage"]),
        selected_family=str(selected["candidate_family"]),
        cv_rmse_mean=float(selected["cv_rmse_mean"]),
        cv_rmse_std=float(selected["cv_rmse_std"]),
        cv_mae_mean=float(selected["cv_mae_mean"]),
        cv_mae_std=float(selected["cv_mae_std"]),
        n_terms=int(selected["n_terms"]),
        n_candidates=len(candidates),
        cv_method=cv_method,
        candidate_table=table,
    )
