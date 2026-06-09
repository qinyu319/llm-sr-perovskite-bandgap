from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score


def rmse(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def safe_r2(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    if len(y_true) < 2 or np.isclose(np.var(y_true), 0.0):
        return float("nan")
    return float(r2_score(y_true, y_pred))


def subgroup_rmse(df: pd.DataFrame, y_true, y_pred, mask) -> float:
    mask = np.asarray(mask, dtype=bool)
    if mask.sum() == 0:
        return float("nan")
    return rmse(np.asarray(y_true)[mask], np.asarray(y_pred)[mask])


def evaluation_metrics(df: pd.DataFrame, y_true, y_pred) -> dict[str, float]:
    abs_err = np.abs(np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float))
    return {
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "r2": safe_r2(y_true, y_pred),
        "median_ae": float(np.median(abs_err)),
        "max_ae": float(np.max(abs_err)),
        "high_Eg_rmse": subgroup_rmse(df, y_true, y_pred, np.asarray(y_true, dtype=float) >= 2.2),
        "Cl_rich_rmse": subgroup_rmse(df, y_true, y_pred, df["Cl"].to_numpy(dtype=float) > 0),
        "MA_rich_rmse": subgroup_rmse(df, y_true, y_pred, df["MA"].to_numpy(dtype=float) >= 0.5),
    }


def jaccard(terms_a: list[str] | tuple[str, ...], terms_b: list[str] | tuple[str, ...]) -> float:
    a = set(terms_a)
    b = set(terms_b)
    if not a and not b:
        return 1.0
    return float(len(a.intersection(b)) / len(a.union(b)))
