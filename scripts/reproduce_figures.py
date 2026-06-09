from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = ROOT / "figures" / "source_data"


def run_script(path: Path) -> None:
    subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)


def load_split(name: str, split: str) -> pd.DataFrame:
    frame = pd.read_excel(DATA / name).rename(columns={"Bg": "Eg", "bg": "Eg"})
    frame.insert(0, "split", split)
    return frame


def m4(sn, br, cl, cs):
    return (
        1.5552651680420202
        - 1.1025280815784506 * sn
        + 0.3431953132457202 * br
        + 1.6193177112496755 * cl
        + 0.12267888917628159 * cs
        + 0.9170216432831477 * sn**2
        + 0.36607403560749485 * br**2
        - 0.22715626984385914 * cs * sn
        - 0.3252750459356003 * cs * cl
    )


def export_source_data() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    train = load_split("train_518.xlsx", "train")
    test = load_split("test_92.xlsx", "test")

    pd.concat([train, test], ignore_index=True).to_csv(
        SOURCE / "figure2_dataset_structure.csv", index=False
    )
    pd.read_csv(
        ROOT / "final_m4_diagnostics" / "final_M4_coefficients_CI_bootstrap.csv"
    ).to_csv(SOURCE / "figure3_m4_diagnostics.csv", index=False)

    benchmark = pd.DataFrame(
        {
            "method": [
                "GP",
                "XGBoost",
                "GBRT",
                "Random Forest",
                "Final M4",
                "Exhaustive-6",
                "PySR-P",
            ],
            "cv_rmse": [
                0.051320,
                0.051267,
                0.053247,
                0.059683,
                0.057532,
                0.062853,
                np.nan,
            ],
            "test_rmse": [
                0.048604,
                0.060565,
                0.052021,
                0.055863,
                0.060613,
                0.066711,
                0.0683,
            ],
        }
    )
    shap = pd.read_csv(
        ROOT / "blackbox_shap" / "gbrt" / "shap_global_importance.csv"
    )
    benchmark.insert(0, "record_type", "benchmark")
    shap.insert(0, "record_type", "gbrt_shap")
    pd.concat([benchmark, shap], ignore_index=True, sort=False).to_csv(
        SOURCE / "figure4_benchmark_shap.csv", index=False
    )

    summary = pd.read_csv(
        ROOT
        / "group_aware_sensitivity"
        / "outputs"
        / "summary_tables"
        / "group_aware_summary.csv"
    )
    summary.insert(0, "record_type", "strategy_summary")
    heldout = pd.read_csv(
        ROOT
        / "group_aware_sensitivity"
        / "outputs"
        / "summary_tables"
        / "group_aware_heldout_group_summary.csv"
    )
    heldout.insert(0, "record_type", "heldout_group")
    pd.concat([summary, heldout], ignore_index=True, sort=False).to_csv(
        SOURCE / "figure5_group_aware.csv", index=False
    )

    tree = cKDTree(train[["Sn", "Br", "Cl", "Cs"]].to_numpy(float))
    grid = np.linspace(0, 1, 161)

    sn, br = np.meshgrid(grid, grid)
    cs = np.full_like(sn, 0.10)
    cl = np.zeros_like(sn)
    distance, _ = tree.query(np.c_[sn.ravel(), br.ravel(), cl.ravel(), cs.ravel()])
    first = pd.DataFrame(
        {
            "slice": "Cs=0.10, Cl=0",
            "Sn": sn.ravel(),
            "Br": br.ravel(),
            "Cl": cl.ravel(),
            "Cs": cs.ravel(),
            "predicted_Eg": m4(sn, br, cl, cs).ravel(),
            "nearest_training_distance": distance,
        }
    )

    cl, br = np.meshgrid(grid, grid)
    sn = np.zeros_like(cl)
    cs = np.full_like(cl, 0.10)
    distance, _ = tree.query(np.c_[sn.ravel(), br.ravel(), cl.ravel(), cs.ravel()])
    second = pd.DataFrame(
        {
            "slice": "Cs=0.10, Sn=0",
            "Sn": sn.ravel(),
            "Br": br.ravel(),
            "Cl": cl.ravel(),
            "Cs": cs.ravel(),
            "predicted_Eg": m4(sn, br, cl, cs).ravel(),
            "nearest_training_distance": distance,
        }
    )
    second["site_closure_valid"] = second["Br"] + second["Cl"] <= 1
    first["site_closure_valid"] = True
    design_map = pd.concat([first, second], ignore_index=True)
    design_map["within_distance_0p25"] = (
        design_map["nearest_training_distance"] <= 0.25
    )
    design_map["target_1p60_to_1p80"] = design_map["predicted_Eg"].between(
        1.60, 1.80
    )
    design_map.to_csv(SOURCE / "figure6_design_map.csv", index=False)


def main() -> None:
    run_script(ROOT / "scripts" / "publication" / "build_main_figures.py")
    run_script(ROOT / "scripts" / "publication" / "prepare_si_assets.py")
    export_source_data()
    print(f"Figure source data: {SOURCE}")


if __name__ == "__main__":
    main()
