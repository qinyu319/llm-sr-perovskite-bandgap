from __future__ import annotations

import pandas as pd

from src.config import PROJECT_ROOT, load_config


def test_curated_dataset_passes_strict_closure() -> None:
    cfg = load_config()
    tol = float(cfg["closure_tolerance"])
    df = pd.read_csv(PROJECT_ROOT / "data" / "curated_dataset.csv")
    assert ((df["FA"] + df["MA"] + df["Cs"] - 1).abs() < tol).all()
    assert ((df["Pb"] + df["Sn"] - 1).abs() < tol).all()
    assert ((df["I"] + df["Br"] + df["Cl"] - 1).abs() < tol).all()
