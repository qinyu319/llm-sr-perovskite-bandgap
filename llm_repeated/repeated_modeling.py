from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold


TERM_ORDER = (
    "Sn",
    "Br",
    "Cl",
    "Cs",
    "Sn^2",
    "Br^2",
    "Cl^2",
    "Cs^2",
    "Sn*Br",
    "Sn*Cl",
    "Br*Cl",
    "Cs*Sn",
    "Cs*Br",
    "Cs*Cl",
)
TERM_INDEX = {term: index for index, term in enumerate(TERM_ORDER)}
MAIN_TERMS = {"Sn", "Br", "Cl", "Cs"}
SQUARE_TERMS = {"Sn^2", "Br^2", "Cl^2", "Cs^2"}
INTERACTION_TERMS = {"Sn*Br", "Sn*Cl", "Br*Cl", "Cs*Sn", "Cs*Br", "Cs*Cl"}

STAGE_RULES: dict[str, dict[str, Any]] = {
    "M0": {
        "allowed": {"Sn", "Br", "Cl"},
        "max_terms": 3,
        "max_interactions": 0,
        "require_square": False,
        "require_cs": False,
        "min_terms": 1,
    },
    "M1": {
        "allowed": {"Sn", "Br", "Cl", "Sn^2", "Br^2", "Cl^2"},
        "max_terms": 6,
        "max_interactions": 0,
        "require_square": True,
        "require_cs": False,
        "min_terms": 2,
    },
    "M2": {
        "allowed": {
            "Sn",
            "Br",
            "Cl",
            "Sn^2",
            "Br^2",
            "Cl^2",
            "Sn*Br",
            "Sn*Cl",
            "Br*Cl",
        },
        "max_terms": 10,
        "max_interactions": 3,
        "require_square": False,
        "require_cs": False,
        "min_terms": 1,
    },
    "M3": {
        "allowed": set(TERM_ORDER),
        "max_terms": 12,
        "max_interactions": 4,
        "require_square": False,
        "require_cs": True,
        "min_terms": 1,
    },
    "M4": {
        "allowed": set(TERM_ORDER),
        "max_terms": 11,
        "max_interactions": 6,
        "require_square": False,
        "require_cs": False,
        "min_terms": 8,
    },
}


@dataclass
class ParsedCandidate:
    candidate_index: int
    raw: str
    valid: bool
    invalid_reasons: list[str]
    has_constant: bool
    terms: list[str]
    canonical_expression: str | None
    duplicate_of: int | None = None


def _normalize_expression(raw: str) -> str:
    text = raw.strip().strip("`")
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", text)
    if "=" in text:
        text = text.split("=", 1)[1]
    text = (
        text.replace("²", "^2")
        .replace("·", "*")
        .replace("×", "*")
        .replace("−", "-")
        .replace("–", "-")
    )
    text = re.sub(r"\s+", "", text)
    return text


def _strip_coefficient(token: str) -> tuple[str, bool]:
    original = token
    token = token.strip("()")
    constant_patterns = (
        r"^(?:a|b|c|beta|β)_?[₀-₉0-9]+$",
        r"^(?:intercept|constant)$",
        r"^1(?:\.0+)?$",
    )
    if any(re.fullmatch(pattern, token, flags=re.IGNORECASE) for pattern in constant_patterns):
        return "", True

    token = re.sub(
        r"^(?:a|b|c|beta|β)_?[₀-₉0-9]+\*?",
        "",
        token,
        flags=re.IGNORECASE,
    )
    token = token.strip("()*")
    return token, token != original


def _canonical_term(token: str) -> str | None:
    token = token.strip("()")
    aliases = {
        "Sn": "Sn",
        "Br": "Br",
        "Cl": "Cl",
        "Cs": "Cs",
        "Sn^2": "Sn^2",
        "Br^2": "Br^2",
        "Cl^2": "Cl^2",
        "Cs^2": "Cs^2",
        "Sn*Br": "Sn*Br",
        "Br*Sn": "Sn*Br",
        "SnBr": "Sn*Br",
        "Sn*Cl": "Sn*Cl",
        "Cl*Sn": "Sn*Cl",
        "SnCl": "Sn*Cl",
        "Br*Cl": "Br*Cl",
        "Cl*Br": "Br*Cl",
        "BrCl": "Br*Cl",
        "Cs*Sn": "Cs*Sn",
        "Sn*Cs": "Cs*Sn",
        "CsSn": "Cs*Sn",
        "Cs*Br": "Cs*Br",
        "Br*Cs": "Cs*Br",
        "CsBr": "Cs*Br",
        "Cs*Cl": "Cs*Cl",
        "Cl*Cs": "Cs*Cl",
        "CsCl": "Cs*Cl",
    }
    return aliases.get(token)


def parse_candidate(raw: str, stage: str, candidate_index: int) -> ParsedCandidate:
    rules = STAGE_RULES[stage]
    normalized = _normalize_expression(raw)
    reasons: list[str] = []

    lowered = normalized.lower()
    if any(name in lowered for name in ("log", "exp", "sqrt", "sin", "cos", "tan")):
        reasons.append("contains forbidden function")
    if "/" in normalized:
        reasons.append("contains division")
    if re.search(r"\^[3-9]|\^\d{2,}", normalized):
        reasons.append("contains power above two")

    additive = normalized.replace("-", "+-").split("+")
    terms: list[str] = []
    has_constant = False
    unknown_tokens: list[str] = []
    for segment in additive:
        token = segment.strip()
        if not token:
            continue
        token = token.lstrip("-")
        stripped, coefficient_or_constant = _strip_coefficient(token)
        if stripped == "":
            has_constant = True
            continue
        canonical = _canonical_term(stripped)
        if canonical is None:
            unknown_tokens.append(token)
        else:
            terms.append(canonical)

    if unknown_tokens:
        reasons.append("unrecognized term(s): " + ", ".join(unknown_tokens))
    if not has_constant:
        reasons.append("missing constant term")
    if not terms:
        reasons.append("contains no recognized non-constant terms")
    if len(terms) != len(set(terms)):
        reasons.append("contains duplicate term")

    unique_terms = sorted(set(terms), key=TERM_INDEX.get)
    disallowed = [term for term in unique_terms if term not in rules["allowed"]]
    if disallowed:
        reasons.append("disallowed term(s): " + ", ".join(disallowed))
    if len(unique_terms) < rules["min_terms"]:
        reasons.append(f"fewer than {rules['min_terms']} non-constant terms")
    if len(unique_terms) > rules["max_terms"]:
        reasons.append(f"more than {rules['max_terms']} non-constant terms")
    interaction_count = sum(term in INTERACTION_TERMS for term in unique_terms)
    if interaction_count > rules["max_interactions"]:
        reasons.append(f"more than {rules['max_interactions']} interaction terms")
    if rules["require_square"] and not any(term in SQUARE_TERMS for term in unique_terms):
        reasons.append("missing required quadratic curvature term")
    if rules["require_cs"] and "Cs" not in unique_terms:
        reasons.append("missing required Cs main effect")

    canonical_expression = None
    if not reasons:
        canonical_expression = "Eg = a0"
        for index, term in enumerate(unique_terms, start=1):
            canonical_expression += f" + a{index}*{term}"

    return ParsedCandidate(
        candidate_index=candidate_index,
        raw=raw,
        valid=not reasons,
        invalid_reasons=reasons,
        has_constant=has_constant,
        terms=unique_terms,
        canonical_expression=canonical_expression,
    )


class TrainingEvaluator:
    def __init__(self, train_path: Path, seed: int = 20260607) -> None:
        frame = pd.read_excel(train_path)
        frame.columns = [str(column).strip().lower() for column in frame.columns]
        required = {"id", "sn", "br", "cl", "cs", "bg"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Training data missing columns: {sorted(missing)}")
        self.frame = frame.dropna(subset=sorted(required)).copy()
        self.seed = seed
        self.y = self.frame["bg"].to_numpy(dtype=float)
        self.feature_columns = self._feature_frame(self.frame)
        self.kfold = KFold(n_splits=5, shuffle=True, random_state=seed)
        self.splits = list(self.kfold.split(self.frame))

    @staticmethod
    def _feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
        sn = frame["sn"].astype(float)
        br = frame["br"].astype(float)
        cl = frame["cl"].astype(float)
        cs = frame["cs"].astype(float)
        return pd.DataFrame(
            {
                "Sn": sn,
                "Br": br,
                "Cl": cl,
                "Cs": cs,
                "Sn^2": sn**2,
                "Br^2": br**2,
                "Cl^2": cl**2,
                "Cs^2": cs**2,
                "Sn*Br": sn * br,
                "Sn*Cl": sn * cl,
                "Br*Cl": br * cl,
                "Cs*Sn": cs * sn,
                "Cs*Br": cs * br,
                "Cs*Cl": cs * cl,
            }
        )

    def fold_manifest(self) -> pd.DataFrame:
        rows: list[dict[str, int]] = []
        ids = self.frame["id"].astype(int).to_numpy()
        for fold, (_, validation_indices) in enumerate(self.splits, start=1):
            for row_index in validation_indices:
                rows.append(
                    {
                        "row_index": int(row_index),
                        "id": int(ids[row_index]),
                        "validation_fold": fold,
                    }
                )
        return pd.DataFrame(rows).sort_values("row_index")

    def evaluate(self, terms: list[str]) -> dict[str, Any]:
        x = self.feature_columns[terms].to_numpy(dtype=float)
        fold_rmse: list[float] = []
        oof = np.empty(len(self.y), dtype=float)

        for train_indices, validation_indices in self.splits:
            model = LinearRegression(fit_intercept=True)
            model.fit(x[train_indices], self.y[train_indices])
            prediction = model.predict(x[validation_indices])
            oof[validation_indices] = prediction
            fold_rmse.append(
                float(math.sqrt(mean_squared_error(self.y[validation_indices], prediction)))
            )

        design = sm.add_constant(x, has_constant="add")
        full_model = sm.OLS(self.y, design).fit()
        confidence = full_model.conf_int(alpha=0.05)
        coefficient_names = ["Intercept", *terms]
        coefficients = [
            {
                "term": name,
                "coefficient": float(full_model.params[index]),
                "ci_95_low": float(confidence[index, 0]),
                "ci_95_high": float(confidence[index, 1]),
            }
            for index, name in enumerate(coefficient_names)
        ]

        return {
            "term_count": len(terms),
            "cv_rmse_mean": float(np.mean(fold_rmse)),
            "cv_rmse_std": float(np.std(fold_rmse, ddof=1)),
            "cv_r2": float(r2_score(self.y, oof)),
            "fold_rmse": fold_rmse,
            "train_rmse": float(math.sqrt(mean_squared_error(self.y, full_model.predict(design)))),
            "train_mae": float(mean_absolute_error(self.y, full_model.predict(design))),
            "train_r2": float(r2_score(self.y, full_model.predict(design))),
            "condition_number": float(full_model.condition_number),
            "coefficients": coefficients,
        }

    def evaluate_stage(
        self, raw_candidates: Iterable[str], stage: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        parsed = [
            parse_candidate(raw, stage, candidate_index)
            for candidate_index, raw in enumerate(raw_candidates, start=1)
        ]
        first_by_terms: dict[tuple[str, ...], int] = {}
        rows: list[dict[str, Any]] = []
        for candidate in parsed:
            key = tuple(candidate.terms)
            if candidate.valid and key in first_by_terms:
                candidate.duplicate_of = first_by_terms[key]
            elif candidate.valid:
                first_by_terms[key] = candidate.candidate_index

            row = asdict(candidate)
            if candidate.valid:
                row.update(self.evaluate(candidate.terms))
            rows.append(row)

        legal = [row for row in rows if row["valid"]]
        if not legal:
            raise ValueError(f"{stage} produced no legal candidates")

        best_rmse = min(row["cv_rmse_mean"] for row in legal)
        threshold = best_rmse * 1.05
        equivalent = [row for row in legal if row["cv_rmse_mean"] <= threshold + 1e-12]
        selected = min(
            equivalent,
            key=lambda row: (
                row["term_count"],
                row["cv_rmse_mean"],
                row["candidate_index"],
            ),
        )
        selection = {
            "stage": stage,
            "raw_candidate_count": len(rows),
            "valid_candidate_count": len(legal),
            "unique_valid_structure_count": len(first_by_terms),
            "best_cv_rmse": best_rmse,
            "five_percent_threshold": threshold,
            "selected_candidate_index": selected["candidate_index"],
            "selected_expression": selected["canonical_expression"],
            "selected_terms": selected["terms"],
            "selected_term_count": selected["term_count"],
            "selected_cv_rmse_mean": selected["cv_rmse_mean"],
            "selected_cv_rmse_std": selected["cv_rmse_std"],
            "selected_cv_r2": selected["cv_r2"],
            "selected_coefficients": selected["coefficients"],
            "selected_condition_number": selected["condition_number"],
        }
        return rows, selection


def evaluate_final_test(
    train_evaluator: TrainingEvaluator,
    test_path: Path,
    terms: list[str],
) -> dict[str, Any]:
    test = pd.read_excel(test_path)
    test.columns = [str(column).strip().lower() for column in test.columns]
    required = {"id", "sn", "br", "cl", "cs", "bg"}
    missing = required - set(test.columns)
    if missing:
        raise ValueError(f"Test data missing columns: {sorted(missing)}")
    test = test.dropna(subset=sorted(required)).copy()

    x_train = train_evaluator.feature_columns[terms].to_numpy(dtype=float)
    y_train = train_evaluator.y
    x_test = TrainingEvaluator._feature_frame(test)[terms].to_numpy(dtype=float)
    y_test = test["bg"].to_numpy(dtype=float)

    model = LinearRegression(fit_intercept=True)
    model.fit(x_train, y_train)
    train_prediction = model.predict(x_train)
    test_prediction = model.predict(x_test)
    coefficients = [
        {"term": "Intercept", "coefficient": float(model.intercept_)},
        *[
            {"term": term, "coefficient": float(coefficient)}
            for term, coefficient in zip(terms, model.coef_, strict=True)
        ],
    ]

    expression = f"Eg = {model.intercept_:.8f}"
    for term, coefficient in zip(terms, model.coef_, strict=True):
        operator = "+" if coefficient >= 0 else "-"
        expression += f" {operator} {abs(coefficient):.8f}*{term}"

    return {
        "terms": terms,
        "term_count": len(terms),
        "symbolic_expression": "Eg = a0"
        + "".join(f" + a{index}*{term}" for index, term in enumerate(terms, start=1)),
        "fitted_expression": expression,
        "coefficients": coefficients,
        "train_rows": len(y_train),
        "test_rows": len(y_test),
        "train_rmse": float(math.sqrt(mean_squared_error(y_train, train_prediction))),
        "train_mae": float(mean_absolute_error(y_train, train_prediction)),
        "train_r2": float(r2_score(y_train, train_prediction)),
        "test_rmse": float(math.sqrt(mean_squared_error(y_test, test_prediction))),
        "test_mae": float(mean_absolute_error(y_test, test_prediction)),
        "test_r2": float(r2_score(y_test, test_prediction)),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
