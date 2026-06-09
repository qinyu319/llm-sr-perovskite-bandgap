from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

from repeated_modeling import TrainingEvaluator


RAW_VARIABLES = ("Sn", "Br", "Cl", "Cs")
GRID_POINTS = 101


def find_train_path() -> Path:
    workbooks = list(Path(".").glob("*.xlsx"))
    if not workbooks:
        raise FileNotFoundError("No .xlsx workbook found in workspace root.")
    return max(workbooks, key=lambda path: path.stat().st_size)


def read_final_pruned_terms() -> list[str]:
    final_path = Path("repeated_runs_30/run_001/selected_models/final.json")
    if final_path.exists():
        final = json.loads(final_path.read_text(encoding="utf-8"))
        terms = final.get("terms")
        if isinstance(terms, list) and all(isinstance(term, str) for term in terms):
            return terms
    return ["Sn", "Br", "Cl", "Cs", "Sn^2", "Br^2", "Cs*Sn", "Cs*Br"]


def terms_for_structure_id(structure_id: str) -> list[str]:
    path = Path("raw_outputs/codex_m4_30_structure_frequencies.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["structure_id"] == structure_id:
                return [
                    term.strip()
                    for term in row["canonical_structure"].split(" + ")
                    if term.strip()
                ]
    raise KeyError(f"Structure ID not found: {structure_id}")


def fit_ols(evaluator: TrainingEvaluator, terms: list[str]) -> dict[str, Any]:
    x = evaluator.feature_columns[terms].to_numpy(dtype=float)
    y = evaluator.y
    design = sm.add_constant(x, has_constant="add")
    model = sm.OLS(y, design).fit()
    ci = model.conf_int(alpha=0.05)
    names = ["Intercept", *terms]
    coefficients = []
    for index, name in enumerate(names):
        coefficients.append(
            {
                "term": name,
                "coefficient": float(model.params[index]),
                "std_error": float(model.bse[index]),
                "ci_95_low": float(ci[index, 0]),
                "ci_95_high": float(ci[index, 1]),
                "p_value": float(model.pvalues[index]),
            }
        )
    prediction = model.predict(design)
    return {
        "model": model,
        "terms": terms,
        "coefficients": coefficients,
        "prediction": np.asarray(prediction, dtype=float),
        "train_rmse": float(math.sqrt(np.mean((evaluator.y - prediction) ** 2))),
        "train_r2": float(model.rsquared),
        "condition_number": float(model.condition_number),
    }


def calculate_vif(evaluator: TrainingEvaluator, terms: list[str]) -> list[dict[str, Any]]:
    x = evaluator.feature_columns[terms].to_numpy(dtype=float)
    design = sm.add_constant(x, has_constant="add")
    rows = []
    for index, term in enumerate(terms, start=1):
        rows.append(
            {
                "term": term,
                "vif": float(variance_inflation_factor(design, index)),
            }
        )
    return rows


def term_owner(term: str) -> tuple[str, ...]:
    if term in RAW_VARIABLES:
        return (term,)
    if term.endswith("^2"):
        return (term[:-2],)
    if "*" in term:
        parts = term.split("*")
        return tuple("Cs" if part == "Cs" else part for part in parts)
    raise ValueError(f"Cannot assign term to raw variable: {term}")


def calculate_shap(
    evaluator: TrainingEvaluator,
    fit: dict[str, Any],
    model_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    terms = fit["terms"]
    coefs = {
        item["term"]: item["coefficient"]
        for item in fit["coefficients"]
        if item["term"] != "Intercept"
    }
    feature_frame = evaluator.feature_columns[terms]
    baselines = feature_frame.mean(axis=0)
    term_shap = pd.DataFrame(index=evaluator.frame.index)
    for term in terms:
        term_shap[term] = coefs[term] * (feature_frame[term] - baselines[term])

    grouped = pd.DataFrame(0.0, index=evaluator.frame.index, columns=list(RAW_VARIABLES))
    for term in terms:
        owners = term_owner(term)
        contribution = term_shap[term] / len(owners)
        for owner in owners:
            grouped[owner] += contribution

    base = float(
        next(item["coefficient"] for item in fit["coefficients"] if item["term"] == "Intercept")
        + sum(coefs[term] * baselines[term] for term in terms)
    )
    reconstructed = base + term_shap.sum(axis=1)
    max_error = float(np.max(np.abs(reconstructed.to_numpy() - fit["prediction"])))

    sample = evaluator.frame[["id", "sn", "br", "cl", "cs", "bg"]].copy()
    sample.columns = ["id", "Sn", "Br", "Cl", "Cs", "Bg"]
    sample.insert(0, "model_id", model_id)
    sample["prediction"] = fit["prediction"]
    sample["shap_base_value"] = base
    for term in terms:
        sample[f"shap_term__{term}"] = term_shap[term].to_numpy()
    sample["shap_reconstruction_error"] = max_error

    grouped_sample = evaluator.frame[["id", "sn", "br", "cl", "cs", "bg"]].copy()
    grouped_sample.columns = ["id", "Sn", "Br", "Cl", "Cs", "Bg"]
    grouped_sample.insert(0, "model_id", model_id)
    grouped_sample["prediction"] = fit["prediction"]
    grouped_sample["shap_base_value"] = base
    for variable in RAW_VARIABLES:
        grouped_sample[f"shap_group__{variable}"] = grouped[variable].to_numpy()
    grouped_sample["allocation_note"] = (
        "Term-level linear SHAP values; pairwise interaction SHAP split equally "
        "between the two raw variables for grouped summaries."
    )

    term_summary = []
    for term in terms:
        values = term_shap[term].to_numpy(dtype=float)
        term_summary.append(
            {
                "model_id": model_id,
                "feature": term,
                "mean_abs_shap": float(np.mean(np.abs(values))),
                "mean_shap": float(np.mean(values)),
                "min_shap": float(np.min(values)),
                "max_shap": float(np.max(values)),
                "coefficient": coefs[term],
            }
        )

    grouped_summary = []
    for variable in RAW_VARIABLES:
        values = grouped[variable].to_numpy(dtype=float)
        grouped_summary.append(
            {
                "model_id": model_id,
                "raw_variable": variable,
                "mean_abs_grouped_shap": float(np.mean(np.abs(values))),
                "mean_grouped_shap": float(np.mean(values)),
                "min_grouped_shap": float(np.min(values)),
                "max_grouped_shap": float(np.max(values)),
                "allocation_note": (
                    "Main and square terms assigned to their raw variable; "
                    "pairwise interaction terms split 50/50."
                ),
            }
        )

    return (
        sample,
        grouped_sample,
        pd.DataFrame(term_summary).sort_values("mean_abs_shap", ascending=False),
        pd.DataFrame(grouped_summary).sort_values(
            "mean_abs_grouped_shap", ascending=False
        ),
    )


def raw_value_summary(evaluator: TrainingEvaluator) -> pd.DataFrame:
    rows = []
    for variable, column in zip(RAW_VARIABLES, ("sn", "br", "cl", "cs"), strict=True):
        values = evaluator.frame[column].astype(float)
        rows.append(
            {
                "variable": variable,
                "n": int(values.count()),
                "min": float(values.min()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "max": float(values.max()),
                "std": float(values.std(ddof=1)),
            }
        )
    return pd.DataFrame(rows)


def feature_value(raw: dict[str, float], term: str) -> float:
    if term in RAW_VARIABLES:
        return raw[term]
    if term.endswith("^2"):
        variable = term[:-2]
        return raw[variable] ** 2
    if "*" in term:
        left, right = term.split("*", 1)
        return raw[left] * raw[right]
    raise ValueError(term)


def predict_from_raw(raw: dict[str, float], fit: dict[str, Any]) -> float:
    total = next(
        item["coefficient"] for item in fit["coefficients"] if item["term"] == "Intercept"
    )
    coefs = {
        item["term"]: item["coefficient"]
        for item in fit["coefficients"]
        if item["term"] != "Intercept"
    }
    for term, coefficient in coefs.items():
        total += coefficient * feature_value(raw, term)
    return float(total)


def derivative(raw: dict[str, float], fit: dict[str, Any], variable: str) -> float:
    coefs = {
        item["term"]: item["coefficient"]
        for item in fit["coefficients"]
        if item["term"] != "Intercept"
    }
    value = 0.0
    main = variable
    square = f"{variable}^2"
    if main in coefs:
        value += coefs[main]
    if square in coefs:
        value += 2.0 * coefs[square] * raw[variable]
    for term, coefficient in coefs.items():
        if "*" not in term:
            continue
        left, right = term.split("*", 1)
        if left == variable:
            value += coefficient * raw[right]
        elif right == variable:
            value += coefficient * raw[left]
    return float(value)


def partial_dependence_and_sensitivity(
    evaluator: TrainingEvaluator,
    fit: dict[str, Any],
    model_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = raw_value_summary(evaluator)
    means = {
        row["variable"]: row["mean"]
        for row in summary.to_dict(orient="records")
    }
    ranges = {
        row["variable"]: (row["min"], row["max"])
        for row in summary.to_dict(orient="records")
    }

    rows = []
    for variable in RAW_VARIABLES:
        low, high = ranges[variable]
        for grid_value in np.linspace(low, high, GRID_POINTS):
            raw = dict(means)
            raw[variable] = float(grid_value)
            rows.append(
                {
                    "model_id": model_id,
                    "variable": variable,
                    "grid_value": float(grid_value),
                    "held_Sn": means["Sn"],
                    "held_Br": means["Br"],
                    "held_Cl": means["Cl"],
                    "held_Cs": means["Cs"],
                    "pdp_prediction_at_means": predict_from_raw(raw, fit),
                    "sensitivity_derivative": derivative(raw, fit, variable),
                    "method_note": (
                        "Analytic curve over observed min-max range with the other "
                        "raw variables held at their training-set means."
                    ),
                }
            )

    curve = pd.DataFrame(rows)
    sign_rows = []
    for (mid, variable), group in curve.groupby(["model_id", "variable"], sort=False):
        values = group["sensitivity_derivative"].to_numpy(dtype=float)
        signs = np.sign(values)
        sign_rows.append(
            {
                "model_id": mid,
                "variable": variable,
                "min_derivative": float(values.min()),
                "max_derivative": float(values.max()),
                "mean_derivative": float(values.mean()),
                "sign_direction": "positive"
                if np.all(signs > 0)
                else "negative"
                if np.all(signs < 0)
                else "mixed",
                "derivative_range_crosses_zero": bool(
                    values.min() <= 0.0 <= values.max()
                ),
                "exact_zero_on_grid": bool(np.any(np.isclose(values, 0.0))),
            }
        )
    return curve, pd.DataFrame(sign_rows)


def write_model_diagnostics(
    out_dir: Path,
    model_id: str,
    evaluator: TrainingEvaluator,
    terms: list[str],
) -> dict[str, Any]:
    fit = fit_ols(evaluator, terms)
    vif = calculate_vif(evaluator, terms)
    coefficient_rows = []
    vif_by_term = {row["term"]: row["vif"] for row in vif}
    for row in fit["coefficients"]:
        copied = {"model_id": model_id, **row}
        copied["vif"] = vif_by_term.get(row["term"])
        copied["condition_number"] = fit["condition_number"]
        copied["train_rmse"] = fit["train_rmse"]
        copied["train_r2"] = fit["train_r2"]
        coefficient_rows.append(copied)

    pd.DataFrame(coefficient_rows).to_csv(
        out_dir / f"{model_id}_coefficients_ci_vif.csv",
        index=False,
        encoding="utf-8-sig",
    )

    (
        term_sample,
        grouped_sample,
        term_summary,
        grouped_summary,
    ) = calculate_shap(evaluator, fit, model_id)
    term_sample.to_csv(
        out_dir / f"{model_id}_term_shap_values.csv",
        index=False,
        encoding="utf-8-sig",
    )
    grouped_sample.to_csv(
        out_dir / f"{model_id}_grouped_raw_variable_shap_values.csv",
        index=False,
        encoding="utf-8-sig",
    )
    term_summary.to_csv(
        out_dir / f"{model_id}_term_shap_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    grouped_summary.to_csv(
        out_dir / f"{model_id}_grouped_raw_variable_shap_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    curve, sign_summary = partial_dependence_and_sensitivity(evaluator, fit, model_id)
    curve.to_csv(
        out_dir / f"{model_id}_partial_dependence_sensitivity_curve.csv",
        index=False,
        encoding="utf-8-sig",
    )
    sign_summary.to_csv(
        out_dir / f"{model_id}_sensitivity_sign_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    return {
        "model_id": model_id,
        "terms": terms,
        "train_rmse": fit["train_rmse"],
        "train_r2": fit["train_r2"],
        "condition_number": fit["condition_number"],
        "max_vif": max(row["vif"] for row in vif),
        "top_term_mean_abs_shap": term_summary.iloc[0].to_dict(),
        "top_grouped_mean_abs_shap": grouped_summary.iloc[0].to_dict(),
    }


def main() -> int:
    out_dir = Path("raw_outputs/missing_m4_diagnostics")
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = find_train_path()
    evaluator = TrainingEvaluator(train_path, seed=20260607)
    variable_summary = raw_value_summary(evaluator)
    variable_summary.to_csv(
        out_dir / "raw_variable_ranges_means.csv",
        index=False,
        encoding="utf-8-sig",
    )

    model_terms = {
        "m4_pruned": read_final_pruned_terms(),
        "m4_full_s3": terms_for_structure_id("S3"),
        "raw_structure_s7": terms_for_structure_id("S7"),
    }
    summaries = [
        write_model_diagnostics(out_dir, model_id, evaluator, terms)
        for model_id, terms in model_terms.items()
    ]
    pd.DataFrame(summaries).to_csv(
        out_dir / "diagnostic_model_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    report_lines = [
        "# Missing M4 Diagnostics",
        "",
        f"Training workbook: `{train_path}`",
        "CV/OLS basis: training-set design matrix from `repeated_modeling.py`.",
        "",
        "## Models",
        "",
        "| Model ID | Term count | Train RMSE | Train R2 | Condition number | Max VIF |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        report_lines.append(
            "| "
            f"{item['model_id']} | {len(item['terms'])} | "
            f"{item['train_rmse']:.10f} | {item['train_r2']:.10f} | "
            f"{item['condition_number']:.6f} | {item['max_vif']:.6f} |"
        )

    report_lines.extend(
        [
            "",
            "## Raw Variable Ranges",
            "",
            "| Variable | Min | Mean | Median | Max | Std |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in variable_summary.to_dict(orient="records"):
        report_lines.append(
            "| "
            f"{row['variable']} | {row['min']:.10f} | {row['mean']:.10f} | "
            f"{row['median']:.10f} | {row['max']:.10f} | {row['std']:.10f} |"
        )

    report_lines.extend(
        [
            "",
            "Generated CSV files include coefficient CI + VIF, term-level SHAP, "
            "grouped raw-variable SHAP, per-sample SHAP values, and analytic "
            "partial-dependence/sensitivity curves for each model.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
