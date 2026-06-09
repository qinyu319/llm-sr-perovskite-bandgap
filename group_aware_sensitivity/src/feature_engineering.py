from __future__ import annotations

import numpy as np
import pandas as pd


TERM_FUNCTIONS = {
    "Sn": lambda d: d["Sn"],
    "Br": lambda d: d["Br"],
    "Cl": lambda d: d["Cl"],
    "Cs": lambda d: d["Cs"],
    "Sn2": lambda d: d["Sn"] ** 2,
    "Br2": lambda d: d["Br"] ** 2,
    "Cl2": lambda d: d["Cl"] ** 2,
    "Cs2": lambda d: d["Cs"] ** 2,
    "SnBr": lambda d: d["Sn"] * d["Br"],
    "SnCl": lambda d: d["Sn"] * d["Cl"],
    "BrCl": lambda d: d["Br"] * d["Cl"],
    "CsSn": lambda d: d["Cs"] * d["Sn"],
    "CsBr": lambda d: d["Cs"] * d["Br"],
    "CsCl": lambda d: d["Cs"] * d["Cl"],
}


TERM_LABELS = {
    "Sn": "Sn",
    "Br": "Br",
    "Cl": "Cl",
    "Cs": "Cs",
    "Sn2": "Sn^2",
    "Br2": "Br^2",
    "Cl2": "Cl^2",
    "Cs2": "Cs^2",
    "SnBr": "Sn*Br",
    "SnCl": "Sn*Cl",
    "BrCl": "Br*Cl",
    "CsSn": "Cs*Sn",
    "CsBr": "Cs*Br",
    "CsCl": "Cs*Cl",
}


def add_engineered_terms(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for term, func in TERM_FUNCTIONS.items():
        out[term] = func(out)
    return out


def term_matrix(df: pd.DataFrame, terms: list[str]) -> np.ndarray:
    enriched = add_engineered_terms(df)
    if not terms:
        return np.empty((len(df), 0))
    return enriched[terms].to_numpy(dtype=float)


def design_matrix(df: pd.DataFrame, terms: list[str], include_intercept: bool = True) -> np.ndarray:
    x_terms = term_matrix(df, terms)
    if include_intercept:
        return np.column_stack([np.ones(len(df)), x_terms])
    return x_terms


def formula_string(terms: list[str], coefficients: dict[str, float]) -> str:
    pieces = [f"{coefficients.get('Intercept', 0.0):.6g}"]
    for term in terms:
        coef = coefficients[term]
        label = TERM_LABELS.get(term, term)
        sign = "+" if coef >= 0 else "-"
        pieces.append(f" {sign} {abs(coef):.6g}*{label}")
    return "Eg = " + "".join(pieces)
