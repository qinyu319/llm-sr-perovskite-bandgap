from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAIN = ROOT / "tables" / "main"
SUPP = ROOT / "tables" / "supplementary"


def load_split(name: str) -> pd.DataFrame:
    return pd.read_excel(DATA / name).rename(columns={"Bg": "Eg", "bg": "Eg"})


def dataset_summary(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for split_name, frame in (("Train", train), ("Test", test)):
        for variable in ("Eg", "Sn", "Br", "Cl", "Cs", "MA"):
            rows.append(
                {
                    "split": split_name,
                    "variable": variable,
                    "n": int(frame[variable].notna().sum()),
                    "mean": float(frame[variable].mean()),
                    "sd": float(frame[variable].std(ddof=1)),
                    "min": float(frame[variable].min()),
                    "median": float(frame[variable].median()),
                    "max": float(frame[variable].max()),
                }
            )
    return pd.DataFrame(rows)


def model_performance() -> pd.DataFrame:
    rows = [
        {
            "method": "Final M4",
            "category": "Analytical model",
            "cv_rmse": 0.05753177282412343,
            "test_rmse": 0.060613471751538577,
            "test_r2": 0.9765451159242243,
        },
        {
            "method": "Exhaustive-6",
            "category": "Analytical model",
            "cv_rmse": 0.06285301689084975,
            "test_rmse": 0.06671115624633457,
            "test_r2": 0.971588647580994,
        },
    ]

    gp = pd.read_csv(ROOT / "baselines/gp_learning" / "gp_model_selection.csv").iloc[0]
    gp_predictions = pd.read_csv(ROOT / "baselines/gp_learning" / "gp_test_predictions.csv")
    actual = gp_predictions["Bg actual"].to_numpy(float)
    predicted = gp_predictions["GP mean"].to_numpy(float)
    rows.append(
        {
            "method": "Gaussian Process",
            "category": "Black-box benchmark",
            "cv_rmse": float(gp["CV RMSE"]),
            "test_rmse": float(np.mean((actual - predicted) ** 2) ** 0.5),
            "test_r2": float(
                1
                - np.sum((actual - predicted) ** 2)
                / np.sum((actual - actual.mean()) ** 2)
            ),
        }
    )

    tree = pd.read_csv(
        ROOT / "blackbox_shap/rf_xgboost" / "rf_xgboost_model_performance.csv"
    )
    for _, row in tree.iterrows():
        rows.append(
            {
                "method": row["Model"],
                "category": "Black-box benchmark",
                "cv_rmse": row["CV RMSE"],
                "test_rmse": row["Test RMSE"],
                "test_r2": row["Test R2"],
            }
        )

    gbrt_selection = pd.read_csv(ROOT / "blackbox_shap/gbrt" / "gbrt_model_selection.csv")
    best_gbrt = gbrt_selection.sort_values("mean_cv_rmse").iloc[0]
    gbrt_predictions = pd.read_csv(ROOT / "blackbox_shap/gbrt" / "gbrt_test_predictions.csv")
    actual = gbrt_predictions["Bg actual"].to_numpy(float)
    predicted = gbrt_predictions["GBRT pred"].to_numpy(float)
    rows.append(
        {
            "method": "GBRT",
            "category": "Black-box benchmark",
            "cv_rmse": float(best_gbrt["mean_cv_rmse"]),
            "test_rmse": float(np.mean((actual - predicted) ** 2) ** 0.5),
            "test_r2": float(
                1
                - np.sum((actual - predicted) ** 2)
                / np.sum((actual - actual.mean()) ** 2)
            ),
        }
    )

    pysr = json.loads(
        (ROOT / "baselines/pysr" / "pysr_summary.json").read_text(encoding="utf-8")
    )
    rows.append(
        {
            "method": "PySR polynomial (seed mean)",
            "category": "Symbolic benchmark",
            "cv_rmse": np.nan,
            "test_rmse": pysr["P_polynomial"]["best_test_rmse_mean"],
            "test_r2": np.nan,
        }
    )
    return pd.DataFrame(rows).sort_values("test_rmse")


def symbolic_controls() -> pd.DataFrame:
    gplearn = json.loads(
        (ROOT / "baselines" / "gplearn" / "gplearn_summary.json").read_text(
            encoding="utf-8"
        )
    )
    pysr = json.loads(
        (ROOT / "baselines" / "pysr" / "pysr_summary.json").read_text(
            encoding="utf-8"
        )
    )
    return pd.DataFrame(
        [
            {
                "method": "Final M4",
                "selection": "Physics-constrained LLM symbolic regression",
                "complexity": 8,
                "cv_rmse": 0.05753177282412343,
                "test_rmse": 0.060613471751538577,
                "test_rmse_sd": np.nan,
            },
            {
                "method": "Exhaustive-6",
                "selection": "Best six-term exhaustive polynomial control",
                "complexity": 6,
                "cv_rmse": 0.06285301689084975,
                "test_rmse": 0.06671115624633457,
                "test_rmse_sd": np.nan,
            },
            {
                "method": "PySR-P",
                "selection": "Five-seed polynomial symbolic control",
                "complexity": np.nan,
                "cv_rmse": np.nan,
                "test_rmse": pysr["P_polynomial"]["best_test_rmse_mean"],
                "test_rmse_sd": pysr["P_polynomial"]["best_test_rmse_std"],
            },
            {
                "method": "GPLearn",
                "selection": gplearn["selection"],
                "complexity": gplearn["mean_program_length_cv"],
                "cv_rmse": gplearn["cv_rmse"],
                "test_rmse": gplearn["test_rmse_mean"],
                "test_rmse_sd": gplearn["test_rmse_sd"],
            },
        ]
    )


def main() -> None:
    MAIN.mkdir(parents=True, exist_ok=True)
    SUPP.mkdir(parents=True, exist_ok=True)

    train = load_split("train_518.xlsx")
    test = load_split("test_92.xlsx")
    dataset_summary(train, test).to_csv(
        MAIN / "table1_dataset_summary.csv", index=False
    )
    symbolic_controls().to_csv(
        MAIN / "table2_symbolic_controls.csv", index=False, lineterminator="\n"
    )

    reproduced_comparison = ROOT / "reproduced" / "main" / "model_comparison.csv"
    s10a_target = SUPP / "table_s10a_csbr_vs_cscl.csv"
    if reproduced_comparison.exists():
        pd.read_csv(reproduced_comparison).to_csv(s10a_target, index=False)
    elif not s10a_target.exists():
        raise FileNotFoundError(
            "Run scripts/reproduce_main_results.py before rebuilding Table S10a."
        )

    coefficients = pd.read_csv(
        ROOT / "final_m4_diagnostics" / "final_M4_coefficients_CI_bootstrap.csv"
    )
    coefficients.to_csv(SUPP / "table_s11a_final_m4_ols_vif.csv", index=False)
    coefficients[
        [
            "Term",
            "Bootstrap mean",
            "Bootstrap SD",
            "Bootstrap CI low",
            "Bootstrap CI high",
            "Bootstrap sign stability",
        ]
    ].to_csv(SUPP / "table_s11b_bootstrap.csv", index=False)
    pd.read_csv(
        ROOT / "final_m4_diagnostics" / "Cl2_retention_diagnostic.csv"
    ).to_csv(SUPP / "table_s12_cl2_diagnostic.csv", index=False)

    model_performance().to_csv(
        SUPP / "table_s21_blackbox_benchmarks.csv", index=False
    )
    gbrt_shap = pd.read_csv(ROOT / "blackbox_shap/gbrt" / "shap_global_importance.csv")
    gbrt_shap.insert(0, "model", "GBRT")
    tree_shap = pd.read_csv(
        ROOT / "blackbox_shap/rf_xgboost" / "rf_xgboost_shap_global_importance.csv"
    )
    tree_shap = tree_shap.rename(
        columns={
            "Model": "model",
            "Feature": "feature",
            "Mean |SHAP|": "mean_abs_shap",
        }
    )
    pd.concat([gbrt_shap, tree_shap], ignore_index=True, sort=False).to_csv(
        SUPP / "table_s22_shap_importance.csv", index=False
    )
    pd.read_csv(
        ROOT
        / "group_aware_sensitivity"
        / "outputs"
        / "group_labels"
        / "group_counts.csv"
    ).to_csv(SUPP / "table_s24a_logo_group_counts.csv", index=False)

    print(f"Main tables: {MAIN}")
    print(f"Supplementary tables: {SUPP}")


if __name__ == "__main__":
    main()
