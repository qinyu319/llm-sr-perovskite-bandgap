from __future__ import annotations

import json
import platform
from pathlib import Path

import gplearn
import numpy as np
import pandas as pd
import sklearn
from gplearn.genetic import SymbolicRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "reproduced" / "gplearn"
OUT.mkdir(parents=True, exist_ok=True)


def load_split(row_count: int) -> pd.DataFrame:
    paths = {
        518: DATA / "train_518.xlsx",
        92: DATA / "test_92.xlsx",
    }
    try:
        path = paths[row_count]
    except KeyError as exc:
        raise ValueError(f"Unsupported split size: {row_count}") from exc
    return pd.read_excel(path).rename(columns={"Bg": "Eg", "bg": "Eg"})


def make_model(parsimony: float, seed: int) -> SymbolicRegressor:
    return SymbolicRegressor(
        population_size=300,
        generations=12,
        tournament_size=20,
        stopping_criteria=1e-5,
        const_range=(-2.0, 2.0),
        init_depth=(2, 5),
        init_method="half and half",
        function_set=("add", "sub", "mul"),
        metric="mse",
        parsimony_coefficient=parsimony,
        p_crossover=0.70,
        p_subtree_mutation=0.10,
        p_hoist_mutation=0.05,
        p_point_mutation=0.10,
        p_point_replace=0.05,
        max_samples=0.90,
        feature_names=["Sn", "Br", "Cl", "Cs", "MA"],
        warm_start=False,
        low_memory=True,
        n_jobs=-1,
        verbose=0,
        random_state=seed,
    )


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


train = load_split(518)
test = load_split(92)
features = ["Sn", "Br", "Cl", "Cs", "MA"]
X = train[features].to_numpy(float)
y = train["Eg"].to_numpy(float)
X_test = test[features].to_numpy(float)
y_test = test["Eg"].to_numpy(float)

folds = list(KFold(n_splits=5, shuffle=True, random_state=42).split(X))
# Archived search grid used to produce baselines/gplearn/gplearn_cv.csv.
grid = [0.0005, 0.001, 0.003, 0.01]
cv_rows: list[dict[str, object]] = []

for parsimony in grid:
    fold_scores: list[float] = []
    fold_lengths: list[int] = []
    fold_programs: list[str] = []
    for fold_id, (fit_idx, val_idx) in enumerate(folds, start=1):
        model = make_model(parsimony, seed=4200 + fold_id)
        model.fit(X[fit_idx], y[fit_idx])
        pred = model.predict(X[val_idx])
        fold_scores.append(rmse(y[val_idx], pred))
        fold_lengths.append(int(model._program.length_))
        fold_programs.append(str(model._program))
    cv_rows.append(
        {
            "parsimony": parsimony,
            "cv_rmse": float(np.mean(fold_scores)),
            "cv_sd": float(np.std(fold_scores, ddof=1)),
            "mean_length": float(np.mean(fold_lengths)),
            "fold_rmse": json.dumps(fold_scores),
            "fold_lengths": json.dumps(fold_lengths),
            "fold_programs": json.dumps(fold_programs),
        }
    )

cv = pd.DataFrame(cv_rows).sort_values(["cv_rmse", "mean_length"]).reset_index(drop=True)
best_parsimony = float(cv.iloc[0]["parsimony"])

seed_rows: list[dict[str, object]] = []
for seed in range(5):
    model = make_model(best_parsimony, seed=20260 + seed)
    model.fit(X, y)
    pred_train = model.predict(X)
    pred_test = model.predict(X_test)
    seed_rows.append(
        {
            "seed": seed,
            "program": str(model._program),
            "length": int(model._program.length_),
            "depth": int(model._program.depth_),
            "train_rmse": rmse(y, pred_train),
            "test_rmse": rmse(y_test, pred_test),
            "test_mae": float(mean_absolute_error(y_test, pred_test)),
            "test_r2": float(r2_score(y_test, pred_test)),
        }
    )

seeds = pd.DataFrame(seed_rows).sort_values("test_rmse").reset_index(drop=True)
cv.to_csv(OUT / "gplearn_cv.csv", index=False)
seeds.to_csv(OUT / "gplearn_seed_results.csv", index=False)

summary = {
    "environment": {
        "python": platform.python_version(),
        "gplearn": gplearn.__version__,
        "scikit_learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
    },
    "features": features,
    "function_set": ["add", "sub", "mul"],
    "selection": "minimum mean five-fold training CV RMSE; test used post hoc only",
    "best_parsimony": best_parsimony,
    "cv_rmse": float(cv.iloc[0]["cv_rmse"]),
    "cv_sd": float(cv.iloc[0]["cv_sd"]),
    "mean_program_length_cv": float(cv.iloc[0]["mean_length"]),
    "n_refit_seeds": 5,
    "unique_programs": int(seeds["program"].nunique()),
    "test_rmse_mean": float(seeds["test_rmse"].mean()),
    "test_rmse_sd": float(seeds["test_rmse"].std(ddof=1)),
    "test_rmse_min": float(seeds["test_rmse"].min()),
    "test_rmse_max": float(seeds["test_rmse"].max()),
    "best_posthoc_program": str(seeds.iloc[0]["program"]),
    "paper_reported": {
        "cv_rmse": 0.1452841619953396,
        "cv_sd": 0.03271318667464909,
        "test_rmse_mean": 0.1773217636473249,
        "test_rmse_sd": 0.02278517916474288,
    },
}
summary["matches_paper_reported_metrics"] = bool(
    np.isclose(summary["cv_rmse"], summary["paper_reported"]["cv_rmse"])
    and np.isclose(
        summary["test_rmse_mean"],
        summary["paper_reported"]["test_rmse_mean"],
    )
)
(OUT / "gplearn_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(json.dumps(summary, indent=2, ensure_ascii=False))
if not summary["matches_paper_reported_metrics"]:
    print(
        "WARNING: This environment did not reproduce the archived paper metrics. "
        "Use baselines/gplearn/ for publication-result audit."
    )
