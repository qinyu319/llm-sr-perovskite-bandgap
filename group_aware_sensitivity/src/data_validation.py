from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, ensure_output_dirs, resolve_from_root


COMPOSITION_COLUMNS = ["FA", "MA", "Cs", "Pb", "Sn", "Br", "Cl", "I"]
REQUIRED_COLUMNS = ["id", *COMPOSITION_COLUMNS]


@dataclass(frozen=True)
class ValidationResult:
    train_raw: pd.DataFrame
    test_raw: pd.DataFrame
    curated: pd.DataFrame
    train_invalid: pd.DataFrame
    test_invalid: pd.DataFrame


def _standardize_columns(df: pd.DataFrame, target_column: str, split_label: str) -> pd.DataFrame:
    out = df.copy()
    if target_column not in out.columns:
        raise ValueError(f"Missing target column {target_column!r} for {split_label}.")
    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"Missing required columns for {split_label}: {missing}")
    out = out.rename(columns={target_column: "Eg"})
    out["source_row_index"] = np.arange(len(out), dtype=int)
    out["sample_id"] = out["id"].map(lambda x: f"{split_label}_{int(x)}" if pd.notna(x) else None)
    out["original_split"] = split_label
    for col in COMPOSITION_COLUMNS + ["Eg"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _add_closure_qc(df: pd.DataFrame, tol: float) -> pd.DataFrame:
    out = df.copy()
    out["A_sum"] = out["FA"] + out["MA"] + out["Cs"]
    out["B_sum"] = out["Pb"] + out["Sn"]
    out["X_sum"] = out["I"] + out["Br"] + out["Cl"]
    out["A_closure_error"] = out["A_sum"] - 1.0
    out["B_closure_error"] = out["B_sum"] - 1.0
    out["X_closure_error"] = out["X_sum"] - 1.0
    numeric_complete = out[COMPOSITION_COLUMNS + ["Eg"]].notna().all(axis=1)
    within_bounds = out[COMPOSITION_COLUMNS].ge(0.0).all(axis=1) & out[COMPOSITION_COLUMNS].le(1.0).all(axis=1)
    closure_ok = (
        out[["A_closure_error", "B_closure_error", "X_closure_error"]].abs().lt(tol).all(axis=1)
    )
    out["numeric_complete"] = numeric_complete
    out["fractions_within_0_1"] = within_bounds
    out["closure_pass"] = numeric_complete & within_bounds & closure_ok
    return out


def load_and_validate(cfg: dict) -> ValidationResult:
    ensure_output_dirs()
    tol = float(cfg.get("closure_tolerance", 1e-6))
    train_path = resolve_from_root(cfg["training_excel"])
    test_path = resolve_from_root(cfg["external_test_excel"])

    train_raw = pd.read_excel(train_path)
    test_raw = pd.read_excel(test_path)
    train = _add_closure_qc(
        _standardize_columns(train_raw, cfg.get("target_column_train", "Bg"), "train"), tol
    )
    test = _add_closure_qc(
        _standardize_columns(test_raw, cfg.get("target_column_test", "bg"), "external_test"), tol
    )

    curated = train.loc[train["closure_pass"]].copy().reset_index(drop=True)
    curated["dataset_index"] = np.arange(len(curated), dtype=int)
    train_invalid = train.loc[~train["closure_pass"]].copy()
    test_invalid = test.loc[~test["closure_pass"]].copy()

    data_dir = PROJECT_ROOT / "data"
    train.to_csv(data_dir / "raw_train_with_qc.csv", index=False, encoding="utf-8-sig")
    test.to_csv(data_dir / "raw_external_test_with_qc.csv", index=False, encoding="utf-8-sig")
    curated.to_csv(data_dir / "curated_dataset.csv", index=False, encoding="utf-8-sig")
    train_invalid.to_csv(data_dir / "excluded_closure_violations_train.csv", index=False, encoding="utf-8-sig")
    test_invalid.to_csv(data_dir / "external_test_closure_violations_reference_only.csv", index=False, encoding="utf-8-sig")

    report = make_validation_report(train, test, curated, train_invalid, test_invalid, tol)
    (PROJECT_ROOT / "outputs" / "summary_tables" / "task1_data_check_report.txt").write_text(
        report, encoding="utf-8"
    )
    task1_rows = [
        {
            "dataset": "training_raw",
            "n_rows": len(train),
            "target_column": "Eg",
            "closure_invalid_rows": len(train_invalid),
            "used_for_group_aware_workflow": False,
            "note": "Raw source; valid subset is used after strict closure QC.",
        },
        {
            "dataset": "training_valid_curated",
            "n_rows": len(curated),
            "target_column": "Eg",
            "closure_invalid_rows": 0,
            "used_for_group_aware_workflow": True,
            "note": "Only these original-training rows enter group labels, splits, screening, CV, and selection.",
        },
        {
            "dataset": "external_test",
            "n_rows": len(test),
            "target_column": "Eg",
            "closure_invalid_rows": len(test_invalid),
            "used_for_group_aware_workflow": False,
            "note": "Excluded from all selection/pruning/final choice; retained only as frozen random-split reference.",
        },
    ]
    pd.DataFrame(task1_rows).to_csv(
        PROJECT_ROOT / "outputs" / "summary_tables" / "task1_data_check.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return ValidationResult(train, test, curated, train_invalid, test_invalid)


def make_validation_report(
    train: pd.DataFrame,
    test: pd.DataFrame,
    curated: pd.DataFrame,
    train_invalid: pd.DataFrame,
    test_invalid: pd.DataFrame,
    tol: float,
) -> str:
    lines = [
        "Task 1 data inspection and QC report",
        f"Closure tolerance: {tol:g}",
        "Policy: exclude invalid original-training rows without renormalization; original external test is not used for model selection.",
        "",
        f"Training raw rows: {len(train)}",
        f"Training valid rows used for group-aware workflow: {len(curated)}",
        f"Training closure/QC excluded rows: {len(train_invalid)}",
        f"External test rows: {len(test)}",
        f"External test closure/QC issues, reference only: {len(test_invalid)}",
        "",
        "Available columns after standardization:",
        ", ".join(train.columns.astype(str)),
        "",
        "Training target Eg summary:",
        train["Eg"].describe().to_string(),
        "",
        "Curated training target Eg summary:",
        curated["Eg"].describe().to_string(),
    ]
    if len(train_invalid):
        lines += ["", "Excluded training source_row_index/id and closure errors:"]
        cols = ["source_row_index", "id", "A_closure_error", "B_closure_error", "X_closure_error"]
        lines.append(train_invalid[cols].to_string(index=False))
    return "\n".join(lines) + "\n"
