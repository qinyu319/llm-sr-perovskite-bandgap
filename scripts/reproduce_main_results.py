from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold
from statsmodels.stats.outliers_influence import variance_inflation_factor


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FINAL_TERMS = ("Sn", "Br", "Cl", "Cs", "Sn2", "Br2", "CsSn", "CsCl")
CL2_TERMS = FINAL_TERMS + ("Cl2",)
CSBR_TERMS = ("Sn", "Br", "Cl", "Cs", "Sn2", "Br2", "CsSn", "CsBr")

EXPECTED = {
    "fixed_cv_rmse": 0.05753177282412343,
    "repeated_cv_rmse": 0.05805643660171057,
    "train_rmse": 0.05410771183819515,
    "test_rmse": 0.060613471751538577,
    "test_r2": 0.9765451159242243,
    "max_vif": 15.786310623222805,
}

INFORMATION_CRITERION_CONVENTION = (
    "Gaussian least-squares criteria without the common n*(log(2*pi)+1) "
    "constant: AIC=n*log(RSS/n)+2*k; BIC=n*log(RSS/n)+log(n)*k, where k "
    "includes the intercept."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute the frozen Final M4 metrics and diagnostics."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reproduced" / "main",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=2026)
    parser.add_argument("--no-verify", action="store_true")
    return parser.parse_args()


def load_split(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path)
    frame = frame.rename(columns={"Bg": "Eg", "bg": "Eg"})
    required = {"Sn", "Br", "Cl", "Cs", "MA", "Eg"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")
    return frame


def build_design(frame: pd.DataFrame, terms: tuple[str, ...]) -> pd.DataFrame:
    raw = {
        "Sn": frame["Sn"],
        "Br": frame["Br"],
        "Cl": frame["Cl"],
        "Cs": frame["Cs"],
        "Sn2": frame["Sn"] ** 2,
        "Br2": frame["Br"] ** 2,
        "Cl2": frame["Cl"] ** 2,
        "Cs2": frame["Cs"] ** 2,
        "SnBr": frame["Sn"] * frame["Br"],
        "SnCl": frame["Sn"] * frame["Cl"],
        "BrCl": frame["Br"] * frame["Cl"],
        "CsSn": frame["Cs"] * frame["Sn"],
        "CsBr": frame["Cs"] * frame["Br"],
        "CsCl": frame["Cs"] * frame["Cl"],
    }
    return pd.DataFrame({term: raw[term] for term in terms}, index=frame.index)


def fit_ols(frame: pd.DataFrame, terms: tuple[str, ...]):
    design = sm.add_constant(build_design(frame, terms), has_constant="add")
    return sm.OLS(frame["Eg"].to_numpy(float), design).fit()


def reduced_information_criteria(model) -> tuple[float, float]:
    """Match the AIC/BIC scale used by the archived Cl2 diagnostic and SI."""
    n = float(model.nobs)
    k = float(model.df_model + 1)
    deviance = n * np.log(float(model.ssr) / n)
    return float(deviance + 2 * k), float(deviance + np.log(n) * k)


def regression_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    errors = actual - predicted
    return {
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "mae": float(mean_absolute_error(actual, predicted)),
        "median_absolute_error": float(np.median(np.abs(errors))),
        "max_absolute_error": float(np.max(np.abs(errors))),
        "r2": float(r2_score(actual, predicted)),
    }


def cross_validation(
    frame: pd.DataFrame,
    terms: tuple[str, ...],
    seeds: list[int],
) -> tuple[pd.DataFrame, dict[str, float]]:
    x = build_design(frame, terms)
    y = frame["Eg"].to_numpy(float)
    records: list[dict[str, float | int]] = []
    for seed in seeds:
        splitter = KFold(n_splits=5, shuffle=True, random_state=seed)
        for fold, (train_index, valid_index) in enumerate(splitter.split(x), start=1):
            x_train = sm.add_constant(x.iloc[train_index], has_constant="add")
            x_valid = sm.add_constant(x.iloc[valid_index], has_constant="add")
            model = sm.OLS(y[train_index], x_train).fit()
            predicted = np.asarray(model.predict(x_valid), dtype=float)
            records.append(
                {
                    "seed": seed,
                    "fold": fold,
                    "rmse": float(mean_squared_error(y[valid_index], predicted) ** 0.5),
                    "mae": float(mean_absolute_error(y[valid_index], predicted)),
                    "r2": float(r2_score(y[valid_index], predicted)),
                }
            )
    details = pd.DataFrame(records)
    summary = {
        "rmse_mean": float(details["rmse"].mean()),
        "rmse_sd": float(details["rmse"].std(ddof=1)),
        "mae_mean": float(details["mae"].mean()),
        "r2_mean": float(details["r2"].mean()),
    }
    return details, summary


def calculate_vif(frame: pd.DataFrame, terms: tuple[str, ...]) -> dict[str, float]:
    design = sm.add_constant(build_design(frame, terms), has_constant="add").to_numpy()
    return {
        term: float(variance_inflation_factor(design, index + 1))
        for index, term in enumerate(terms)
    }


def bootstrap_coefficients(
    frame: pd.DataFrame,
    terms: tuple[str, ...],
    samples: int,
    seed: int,
    model_name: str,
) -> pd.DataFrame:
    x = sm.add_constant(build_design(frame, terms), has_constant="add").to_numpy(float)
    y = frame["Eg"].to_numpy(float)
    rng = np.random.default_rng(seed)
    values = np.empty((samples, x.shape[1]), dtype=float)
    for bootstrap_id in range(samples):
        indices = rng.integers(0, len(frame), len(frame))
        values[bootstrap_id] = np.linalg.lstsq(x[indices], y[indices], rcond=None)[0]
    result = pd.DataFrame(values, columns=("Intercept",) + terms)
    result.insert(0, "model", model_name)
    result.insert(0, "bootstrap_id", np.arange(1, samples + 1))
    return result


def coefficient_summary(
    model,
    terms: tuple[str, ...],
    bootstrap: pd.DataFrame,
    vif: dict[str, float],
) -> pd.DataFrame:
    rows = []
    full_sign = np.sign(np.asarray(model.params, dtype=float))
    for index, name in enumerate(("Intercept",) + terms):
        samples = bootstrap[name].to_numpy(float)
        ci_low, ci_high = np.quantile(samples, [0.025, 0.975])
        rows.append(
            {
                "term": name,
                "coefficient": float(model.params.iloc[index]),
                "standard_error": float(model.bse.iloc[index]),
                "t": float(model.tvalues.iloc[index]),
                "p_value": float(model.pvalues.iloc[index]),
                "ols_ci_low": float(model.conf_int().iloc[index, 0]),
                "ols_ci_high": float(model.conf_int().iloc[index, 1]),
                "bootstrap_mean": float(samples.mean()),
                "bootstrap_sd": float(samples.std(ddof=1)),
                "bootstrap_ci_low": float(ci_low),
                "bootstrap_ci_high": float(ci_high),
                "bootstrap_sign_stability": float(
                    np.mean(np.sign(samples) == full_sign[index])
                ),
                "vif": np.nan if name == "Intercept" else vif[name],
            }
        )
    return pd.DataFrame(rows)


def evaluate_model(
    name: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    terms: tuple[str, ...],
):
    model = fit_ols(train, terms)
    train_x = sm.add_constant(build_design(train, terms), has_constant="add")
    test_x = sm.add_constant(build_design(test, terms), has_constant="add")
    train_metrics = regression_metrics(
        train["Eg"].to_numpy(float), np.asarray(model.predict(train_x), dtype=float)
    )
    test_predictions = np.asarray(model.predict(test_x), dtype=float)
    test_metrics = regression_metrics(test["Eg"].to_numpy(float), test_predictions)
    fixed_details, fixed = cross_validation(train, terms, [42])
    repeated_details, repeated = cross_validation(train, terms, list(range(100)))
    vif = calculate_vif(train, terms)
    aic, bic = reduced_information_criteria(model)

    cl_mask = test["Cl"].to_numpy(float) > 0
    ma_mask = test["MA"].to_numpy(float) >= 0.5
    result = {
        "model": name,
        "terms": list(terms),
        "n_terms": len(terms),
        "fixed_cv_rmse": fixed["rmse_mean"],
        "fixed_cv_rmse_sd": fixed["rmse_sd"],
        "repeated_cv_rmse": repeated["rmse_mean"],
        "repeated_cv_rmse_sd": repeated["rmse_sd"],
        "train": train_metrics,
        "test": test_metrics,
        "cl_rich_test_rmse": float(
            mean_squared_error(
                test.loc[cl_mask, "Eg"], test_predictions[cl_mask]
            )
            ** 0.5
        ),
        "ma_rich_test_rmse": float(
            mean_squared_error(
                test.loc[ma_mask, "Eg"], test_predictions[ma_mask]
            )
            ** 0.5
        ),
        "max_vif": max(vif.values()),
        "median_vif": float(np.median(list(vif.values()))),
        "aic": aic,
        "bic": bic,
    }
    return result, model, fixed_details, repeated_details, vif


def flatten_model_result(result: dict[str, object]) -> dict[str, object]:
    return {
        "model": result["model"],
        "terms": ", ".join(result["terms"]),
        "n_terms": result["n_terms"],
        "fixed_cv_rmse": result["fixed_cv_rmse"],
        "fixed_cv_rmse_sd": result["fixed_cv_rmse_sd"],
        "repeated_cv_rmse": result["repeated_cv_rmse"],
        "repeated_cv_rmse_sd": result["repeated_cv_rmse_sd"],
        "train_rmse": result["train"]["rmse"],
        "train_mae": result["train"]["mae"],
        "train_r2": result["train"]["r2"],
        "test_rmse": result["test"]["rmse"],
        "test_mae": result["test"]["mae"],
        "test_r2": result["test"]["r2"],
        "cl_rich_test_rmse": result["cl_rich_test_rmse"],
        "ma_rich_test_rmse": result["ma_rich_test_rmse"],
        "max_vif": result["max_vif"],
        "median_vif": result["median_vif"],
        "aic": result["aic"],
        "bic": result["bic"],
    }


def verify_expected(final_result: dict[str, object], coefficients: pd.DataFrame) -> None:
    observed = {
        "fixed_cv_rmse": final_result["fixed_cv_rmse"],
        "repeated_cv_rmse": final_result["repeated_cv_rmse"],
        "train_rmse": final_result["train"]["rmse"],
        "test_rmse": final_result["test"]["rmse"],
        "test_r2": final_result["test"]["r2"],
        "max_vif": final_result["max_vif"],
    }
    failures = []
    for key, expected in EXPECTED.items():
        if not np.isclose(observed[key], expected, rtol=0, atol=1e-11):
            failures.append(f"{key}: observed={observed[key]} expected={expected}")
    archived = pd.read_csv(
        ROOT / "final_m4_diagnostics" / "final_M4_coefficients_CI_bootstrap.csv"
    )
    archived_values = archived["Coefficient"].to_numpy(float)
    reproduced_values = coefficients["coefficient"].to_numpy(float)
    if not np.allclose(archived_values, reproduced_values, rtol=0, atol=1e-11):
        failures.append("Final M4 coefficients differ from the archived coefficient table")
    if failures:
        raise RuntimeError("Verification failed:\n- " + "\n- ".join(failures))


def main() -> None:
    args = parse_args()
    if args.bootstrap_samples < 1:
        raise ValueError("--bootstrap-samples must be positive")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    train = load_split(DATA / "train_518.xlsx")
    test = load_split(DATA / "test_92.xlsx")

    final_result, final_model, fixed_details, repeated_details, final_vif = (
        evaluate_model("Final M4 (CsCl)", train, test, FINAL_TERMS)
    )
    cl2_result, cl2_model, _, _, _ = evaluate_model(
        "Final M4 + Cl2", train, test, CL2_TERMS
    )
    csbr_result, _, _, _, _ = evaluate_model(
        "M4 terminal CsBr", train, test, CSBR_TERMS
    )

    final_bootstrap = bootstrap_coefficients(
        train,
        FINAL_TERMS,
        args.bootstrap_samples,
        args.bootstrap_seed,
        "Final M4",
    )
    cl2_bootstrap = bootstrap_coefficients(
        train,
        CL2_TERMS,
        args.bootstrap_samples,
        args.bootstrap_seed,
        "Final M4 + Cl2",
    )
    coefficients = coefficient_summary(
        final_model, FINAL_TERMS, final_bootstrap, final_vif
    )
    cl2_vif = calculate_vif(train, CL2_TERMS)
    cl2_coefficients = coefficient_summary(
        cl2_model, CL2_TERMS, cl2_bootstrap, cl2_vif
    )

    f_statistic, nested_p_value, df_difference = cl2_model.compare_f_test(final_model)
    cl2_row = cl2_coefficients.loc[cl2_coefficients["term"] == "Cl2"].iloc[0]
    cl2_diagnostic = pd.DataFrame(
        [
            {
                "metric": "fixed_cv_rmse",
                "final_m4": final_result["fixed_cv_rmse"],
                "final_m4_plus_cl2": cl2_result["fixed_cv_rmse"],
            },
            {
                "metric": "test_rmse",
                "final_m4": final_result["test"]["rmse"],
                "final_m4_plus_cl2": cl2_result["test"]["rmse"],
            },
            {
                "metric": "max_vif",
                "final_m4": final_result["max_vif"],
                "final_m4_plus_cl2": cl2_result["max_vif"],
            },
            {
                "metric": "cl2_coefficient",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["coefficient"],
            },
            {
                "metric": "cl2_ols_ci_low",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["ols_ci_low"],
            },
            {
                "metric": "cl2_ols_ci_high",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["ols_ci_high"],
            },
            {
                "metric": "cl2_bootstrap_ci_low",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["bootstrap_ci_low"],
            },
            {
                "metric": "cl2_bootstrap_ci_high",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["bootstrap_ci_high"],
            },
            {
                "metric": "cl2_sign_stability",
                "final_m4": np.nan,
                "final_m4_plus_cl2": cl2_row["bootstrap_sign_stability"],
            },
            {
                "metric": "nested_f_statistic",
                "final_m4": np.nan,
                "final_m4_plus_cl2": float(f_statistic),
            },
            {
                "metric": "nested_f_test_p_value",
                "final_m4": np.nan,
                "final_m4_plus_cl2": float(nested_p_value),
            },
            {
                "metric": "nested_df_difference",
                "final_m4": np.nan,
                "final_m4_plus_cl2": float(df_difference),
            },
        ]
    )
    cl2_diagnostic["delta_plus_cl2_minus_final"] = (
        cl2_diagnostic["final_m4_plus_cl2"] - cl2_diagnostic["final_m4"]
    )

    model_comparison = pd.DataFrame(
        [
            flatten_model_result(final_result),
            flatten_model_result(csbr_result),
            flatten_model_result(cl2_result),
        ]
    )
    all_bootstrap = pd.concat([final_bootstrap, cl2_bootstrap], ignore_index=True)

    coefficients.to_csv(output / "final_m4_coefficients.csv", index=False)
    cl2_coefficients.to_csv(output / "final_m4_plus_cl2_coefficients.csv", index=False)
    model_comparison.to_csv(output / "model_comparison.csv", index=False)
    cl2_diagnostic.to_csv(output / "cl2_diagnostic.csv", index=False)
    fixed_details.to_csv(output / "fixed_cv_folds.csv", index=False)
    repeated_details.to_csv(output / "repeated_cv_folds.csv", index=False)
    all_bootstrap.to_csv(output / "bootstrap_coefficient_samples.csv", index=False)

    summary = {
        "formula": (
            "Eg = 1.55527 - 1.10253*Sn + 0.34320*Br + 1.61932*Cl "
            "+ 0.12268*Cs + 0.91702*Sn^2 + 0.36607*Br^2 "
            "- 0.22716*Cs*Sn - 0.32528*Cs*Cl"
        ),
        "information_criterion_convention": INFORMATION_CRITERION_CONVENTION,
        "bootstrap_samples_per_model": args.bootstrap_samples,
        "bootstrap_seed": args.bootstrap_seed,
        "models": [final_result, csbr_result, cl2_result],
        "minimum_final_m4_sign_stability": float(
            coefficients.loc[
                coefficients["term"] != "Intercept", "bootstrap_sign_stability"
            ].min()
        ),
        "nested_cl2_f_test_p_value": float(nested_p_value),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if not args.no_verify:
        verify_expected(final_result, coefficients)

    print(f"Output: {output}")
    print(f"Fixed CV RMSE: {final_result['fixed_cv_rmse']:.10f} eV")
    print(f"Repeated CV RMSE: {final_result['repeated_cv_rmse']:.10f} eV")
    print(f"Train RMSE: {final_result['train']['rmse']:.10f} eV")
    print(f"Test RMSE: {final_result['test']['rmse']:.10f} eV")
    print(f"Test R2: {final_result['test']['r2']:.10f}")
    print(
        "Minimum sign stability: "
        f"{summary['minimum_final_m4_sign_stability']:.4f}"
    )


if __name__ == "__main__":
    main()
