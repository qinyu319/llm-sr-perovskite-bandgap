from __future__ import annotations

import numpy as np
import pandas as pd

from .feature_engineering import design_matrix


def fit_ols(df: pd.DataFrame, terms: list[str] | tuple[str, ...]) -> dict[str, object]:
    term_list = list(terms)
    x = design_matrix(df, term_list, include_intercept=True)
    y = df["Eg"].to_numpy(dtype=float)
    beta, residuals, rank, singular_values = np.linalg.lstsq(x, y, rcond=None)
    coefs = {"Intercept": float(beta[0])}
    coefs.update({term: float(value) for term, value in zip(term_list, beta[1:])})
    return {
        "terms": term_list,
        "coefficients": coefs,
        "rank": int(rank),
        "singular_values": [float(v) for v in singular_values],
    }


def predict_ols(model: dict[str, object], df: pd.DataFrame) -> np.ndarray:
    terms = list(model["terms"])
    coefs = model["coefficients"]
    x = design_matrix(df, terms, include_intercept=True)
    beta = np.array([coefs["Intercept"], *[coefs[t] for t in terms]], dtype=float)
    return x @ beta
