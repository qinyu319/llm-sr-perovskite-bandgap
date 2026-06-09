from __future__ import annotations

import numpy as np

from src.metrics import jaccard, mae, rmse


def test_metrics_known_values() -> None:
    y = np.array([1.0, 2.0])
    pred = np.array([1.0, 3.0])
    assert np.isclose(rmse(y, pred), np.sqrt(0.5))
    assert np.isclose(mae(y, pred), 0.5)
    assert np.isclose(jaccard(["Sn", "Br"], ["Sn", "Cl"]), 1 / 3)
