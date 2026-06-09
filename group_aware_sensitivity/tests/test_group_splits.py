from __future__ import annotations

import pandas as pd

from src.config import PROJECT_ROOT


def test_split_manifest_has_expected_strategies() -> None:
    manifest = pd.read_csv(PROJECT_ROOT / "outputs" / "splits" / "split_manifest.csv")
    assert set(manifest["group_strategy"]) == {
        "composition_family_group_shuffle",
        "halide_logo",
        "a_site_logo",
    }
    assert (manifest["n_train"] > 0).all()
    assert (manifest["n_test"] > 0).all()
    assert manifest["no_group_leakage"].all()
