from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic reproduction tasks.")
    parser.add_argument(
        "--mode",
        choices=(
            "main",
            "figures",
            "tables",
            "group-aware",
            "external-validation",
            "all",
        ),
        default="main",
    )
    return parser.parse_args()


def run(command: list[str], cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def run_main() -> None:
    run([sys.executable, "scripts/reproduce_main_results.py"])


def run_figures() -> None:
    run([sys.executable, "scripts/reproduce_figures.py"])


def run_tables() -> None:
    run([sys.executable, "scripts/reproduce_tables.py"])


def run_group_aware() -> None:
    project = ROOT / "group_aware_sensitivity"
    for script in (
        "01_validate_data.py",
        "02_make_group_labels.py",
        "03_make_and_validate_splits.py",
        "03_run_group_aware_workflow.py",
        "04_summarize_group_results.py",
        "05_plot_group_results.py",
        "06_make_excel_report.py",
    ):
        run([sys.executable, f"scripts/{script}"], cwd=project)
    run([sys.executable, "-m", "pytest", "tests"], cwd=project)


def run_external_validation() -> None:
    run([sys.executable, "external_validation/run_external_validation.py"])


def main() -> None:
    mode = parse_args().mode
    if mode in {"main", "all"}:
        run_main()
    if mode in {"figures", "all"}:
        run_figures()
    if mode in {"tables", "all"}:
        run_tables()
    if mode in {"group-aware", "all"}:
        run_group_aware()
    if mode in {"external-validation", "all"}:
        run_external_validation()


if __name__ == "__main__":
    main()
