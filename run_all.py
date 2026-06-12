from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GROUP_AWARE = ROOT / "group_aware_sensitivity"


def run(relative: str, *, cwd: Path = ROOT, args: tuple[str, ...] = ()) -> None:
    command = [sys.executable, relative, *args]
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def verify() -> None:
    run("scripts/verify_checksums.py")
    run("scripts/security_scan.py")


def main_results() -> None:
    run("scripts/reproduce_main_results.py")


def figures() -> None:
    run("scripts/reproduce_figures.py")


def tables() -> None:
    run("scripts/reproduce_tables.py")


def group_aware() -> None:
    for script in (
        "scripts/01_validate_data.py",
        "scripts/02_make_group_labels.py",
        "scripts/03_make_and_validate_splits.py",
        "scripts/03_run_group_aware_workflow.py",
        "scripts/04_summarize_group_results.py",
        "scripts/05_plot_group_results.py",
        "scripts/06_make_excel_report.py",
    ):
        run(script, cwd=GROUP_AWARE)
    run("-m", cwd=GROUP_AWARE, args=("pytest", "-p", "no:cacheprovider", "tests"))


def external_validation() -> None:
    run("external_validation/run_external_validation.py")


WORKFLOWS = {
    "verify": verify,
    "main": main_results,
    "figures": figures,
    "tables": tables,
    "group-aware": group_aware,
    "external-validation": external_validation,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic project workflows.")
    parser.add_argument(
        "--mode",
        choices=(*WORKFLOWS, "all"),
        default="verify",
        help="Workflow to run (default: verify).",
    )
    return parser.parse_args()


def main() -> None:
    mode = parse_args().mode
    if mode == "all":
        for workflow in WORKFLOWS.values():
            workflow()
        return
    WORKFLOWS[mode]()


if __name__ == "__main__":
    main()
