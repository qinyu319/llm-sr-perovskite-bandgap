from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[2]
INPUT_DATA = ROOT / "data"
BUILD = ROOT / "archive" / "publication_build" / "si"
FIG = ROOT / "figures" / "supplementary"
DATA = BUILD / "data"
FIG.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

BLUE = "#1F4E79"
MID_BLUE = "#5B9BD5"
LIGHT_BLUE = "#D9EAF7"
ORANGE = "#E67E22"
RED = "#B03A2E"
GREEN = "#2E7D32"
GRAY = "#606060"
LIGHT_GRAY = "#E8E8E8"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "figure.dpi": 160,
        "savefig.dpi": 300,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def load_split(n: int) -> tuple[Path, pd.DataFrame]:
    required = {"FA", "MA", "Cs", "Pb", "Sn", "Br", "Cl", "I"}
    for path in INPUT_DATA.glob("*.xlsx"):
        try:
            frame = pd.read_excel(path)
        except Exception:
            continue
        frame = frame.rename(columns={"Bg": "Eg", "bg": "Eg"})
        if len(frame) == n and required | {"Eg"} <= set(frame.columns):
            return path, frame
    raise FileNotFoundError(f"No root workbook with {n} rows")


def find_file(name: str) -> Path:
    matches = list(ROOT.rglob(name))
    if not matches:
        raise FileNotFoundError(name)
    return matches[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIG / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def composition_key(row: pd.Series) -> str:
    return (
        f"FA{row.FA:.4g} MA{row.MA:.4g} Cs{row.Cs:.4g} | "
        f"Pb{row.Pb:.4g} Sn{row.Sn:.4g} | "
        f"I{row.I:.4g} Br{row.Br:.4g} Cl{row.Cl:.4g}"
    )


train_path, train = load_split(518)
test_path, test = load_split(92)
dataset_path = INPUT_DATA / "dataset_610_snapshot.xlsx"
raw = pd.read_excel(dataset_path, sheet_name="merged_raw").rename(columns={"Bg": "Eg"})
processed = pd.read_excel(dataset_path, sheet_name="processed").rename(
    columns={"Bg_mean": "Eg_mean"}
)

fractions = ["FA", "MA", "Cs", "Pb", "Sn", "Br", "Cl", "I"]
full_cols = fractions + ["Eg"]


def row_counter(frame: pd.DataFrame) -> Counter:
    return Counter(
        tuple(round(float(value), 10) for value in row)
        for row in frame[full_cols].to_numpy()
    )


split_multiset_equal = row_counter(raw) == row_counter(
    pd.concat([train, test], ignore_index=True)
)

dups = (
    raw.groupby(fractions, dropna=False)["Eg"]
    .agg(["count", "min", "max", "mean", "std"])
    .reset_index()
)
dups = dups[dups["count"] > 1].copy()
dups["composition"] = dups.apply(composition_key, axis=1)
dups["Eg range"] = dups.apply(lambda r: f'{r["min"]:.3f}-{r["max"]:.3f}', axis=1)
dups["decision"] = "Retained as separate records; no averaging in primary analysis"
dups = dups.sort_values(["count", "composition"], ascending=[False, True])
dups[
    ["composition", "count", "min", "max", "mean", "std", "decision"]
].to_csv(DATA / "duplicate_composition_audit.csv", index=False)

closure_rows = []
for label, frame in [("Training", train), ("Held-out test", test)]:
    a = frame[["FA", "MA", "Cs"]].sum(axis=1)
    b = frame[["Pb", "Sn"]].sum(axis=1)
    x = frame[["I", "Br", "Cl"]].sum(axis=1)
    bad = (a.sub(1).abs() > 1e-6) | (b.sub(1).abs() > 1e-6) | (x.sub(1).abs() > 1e-6)
    closure_rows.append(
        {
            "cohort": label,
            "n": len(frame),
            "closure_pass": int((~bad).sum()),
            "closure_issue": int(bad.sum()),
            "max_abs_A_error": float(a.sub(1).abs().max()),
            "max_abs_B_error": float(b.sub(1).abs().max()),
            "max_abs_X_error": float(x.sub(1).abs().max()),
        }
    )
pd.DataFrame(closure_rows).to_csv(DATA / "closure_audit.csv", index=False)

feature_stats = []
for label, frame in [("Training", train), ("Held-out test", test)]:
    for feature in ["Eg", "Sn", "Br", "Cl", "Cs", "MA", "FA"]:
        series = frame[feature].astype(float)
        feature_stats.append(
            {
                "cohort": label,
                "variable": feature,
                "n": len(series),
                "mean": series.mean(),
                "sd": series.std(ddof=1),
                "median": series.median(),
                "min": series.min(),
                "max": series.max(),
            }
        )
pd.DataFrame(feature_stats).to_csv(DATA / "train_test_summary.csv", index=False)

train_compositions = Counter(
    tuple(round(float(value), 10) for value in row)
    for row in train[fractions].to_numpy()
)
test_compositions = Counter(
    tuple(round(float(value), 10) for value in row)
    for row in test[fractions].to_numpy()
)
shared_compositions = set(train_compositions) & set(test_compositions)
train_full_rows = Counter(
    tuple(round(float(value), 10) for value in row)
    for row in train[full_cols].to_numpy()
)
test_full_rows = Counter(
    tuple(round(float(value), 10) for value in row)
    for row in test[full_cols].to_numpy()
)
shared_full_rows = set(train_full_rows) & set(test_full_rows)
model_features = ["Sn", "Br", "Cl", "Cs"]
train_model_keys = {
    tuple(round(float(value), 10) for value in row)
    for row in train[model_features].to_numpy()
}
test_model_keys = [
    tuple(round(float(value), 10) for value in row)
    for row in test[model_features].to_numpy()
]
shared_model_mask = np.array([key in train_model_keys for key in test_model_keys])


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


test_pred = m4(
    test["Sn"].to_numpy(float),
    test["Br"].to_numpy(float),
    test["Cl"].to_numpy(float),
    test["Cs"].to_numpy(float),
)
test_error = test["Eg"].to_numpy(float) - test_pred
shared_rmse = float(np.sqrt(np.mean(test_error[shared_model_mask] ** 2)))
unseen_rmse = float(np.sqrt(np.mean(test_error[~shared_model_mask] ** 2)))

# Figure S1: evidence-aware curation flow.
fig, ax = plt.subplots(figsize=(7.2, 4.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 7)
ax.axis("off")
boxes = [
    (0.5, 5.35, 2.3, 0.95, "Perovskite Database\nProject source", LIGHT_BLUE),
    (3.85, 5.35, 2.3, 0.95, "Upstream extraction and\nscope filtering", "#FFF2CC"),
    (7.2, 5.35, 2.3, 0.95, "Archived record-level\nsnapshot: 610 rows", "#E2F0D9"),
    (0.5, 3.25, 2.3, 0.95, "No IF/JCR filter;\nno target rebalancing", LIGHT_BLUE),
    (3.85, 3.25, 2.3, 0.95, "Duplicate measurements\nretained as records", LIGHT_BLUE),
    (7.2, 3.25, 2.3, 0.95, "Immutable split files:\n518 train / 92 test", "#E2F0D9"),
    (0.5, 1.15, 2.3, 0.95, "Primary final M4:\n518-row training file", "#DDEBF7"),
    (3.85, 1.15, 2.3, 0.95, "Strict closure sensitivity:\n507 valid training rows", "#DDEBF7"),
    (7.2, 1.15, 2.3, 0.95, "Held-out post hoc report:\n92-row test file", "#DDEBF7"),
]
for x, y, w, h, text, color in boxes:
    patch = plt.Rectangle((x, y), w, h, facecolor=color, edgecolor=BLUE, linewidth=1.1)
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)
arrows = [
    ((2.8, 5.82), (3.85, 5.82)),
    ((6.15, 5.82), (7.2, 5.82)),
    ((8.35, 5.35), (8.35, 4.2)),
    ((2.8, 3.72), (3.85, 3.72)),
    ((6.15, 3.72), (7.2, 3.72)),
    ((8.35, 3.25), (8.35, 2.1)),
    ((7.2, 3.72), (2.8, 1.62)),
    ((7.2, 3.72), (6.15, 1.62)),
]
for start, end in arrows:
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "color": GRAY})
ax.text(
    5,
    6.75,
    "The pre-610 source-export log is not present in the local archive;\nall downstream counts and files are directly auditable.",
    ha="center",
    va="center",
    color=RED,
    fontsize=8.5,
    fontweight="bold",
)
save(fig, "figure_s1_curation_flow.png")

# Figure S2: record-level vs auxiliary composition-averaged distribution.
fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25))
bins = np.linspace(1.1, 3.2, 25)
axes[0].hist(raw["Eg"], bins=bins, color=BLUE, alpha=0.82)
axes[0].set_title("(a) Archived record-level data (n=610)")
axes[0].set_xlabel("$E_g$ (eV)")
axes[0].set_ylabel("Count")
axes[1].hist(processed["Eg_mean"], bins=bins, color=ORANGE, alpha=0.82)
axes[1].set_title("(b) Auxiliary Cl-free composition means (n=519)")
axes[1].set_xlabel("Mean $E_g$ per composition (eV)")
fig.text(
    0.5,
    -0.02,
    "The composition-averaged sheet was not used for the primary 610-record split or Final M4.",
    ha="center",
    fontsize=8,
    color=GRAY,
)
fig.tight_layout()
save(fig, "figure_s2_archived_distributions.png")

# Figure S3: train/test distribution comparison.
plot_vars = ["Eg", "Sn", "Br", "Cl", "Cs", "MA"]
fig, axes = plt.subplots(2, 3, figsize=(7.3, 5.0))
for ax, variable in zip(axes.ravel(), plot_vars):
    low = min(train[variable].min(), test[variable].min())
    high = max(train[variable].max(), test[variable].max())
    bins = np.linspace(low, high if high > low else low + 1, 20)
    ax.hist(train[variable], bins=bins, density=True, alpha=0.65, color=BLUE, label="Train")
    ax.hist(test[variable], bins=bins, density=True, alpha=0.55, color=ORANGE, label="Test")
    ax.set_title(variable if variable != "Eg" else "$E_g$")
    ax.set_ylabel("Density")
axes[0, 0].legend(frameon=False)
fig.tight_layout()
save(fig, "figure_s3_train_test_distributions.png")

# Figure S4: stage-wise accuracy and complexity.
stage = pd.DataFrame(
    {
        "Model": ["M0", "M1", "M2", "M3-full", "Historical M4", "Final M4"],
        "Terms": [3, 6, 9, 14, 13, 8],
        "CV": [0.087733, 0.063939, 0.066548, 0.058333, 0.059460, 0.057532],
        "Test": [0.085887, 0.071660, 0.066416, 0.054620, 0.053835, 0.060613],
    }
)
fig, ax = plt.subplots(figsize=(7.2, 3.8))
ax.plot(stage["Terms"], stage["CV"], "o-", color=BLUE, label="Training five-fold CV")
ax.plot(stage["Terms"], stage["Test"], "s--", color=ORANGE, label="Held-out test (post hoc)")
for _, row in stage.iterrows():
    ax.annotate(
        row["Model"],
        (row["Terms"], row["CV"]),
        xytext=(3, 5),
        textcoords="offset points",
        fontsize=7.5,
    )
ax.axhline(0.06, color=RED, linestyle=":", linewidth=1.2, label="Late-stage CV gate")
ax.set_xlabel("Number of non-constant terms")
ax.set_ylabel("RMSE (eV)")
ax.set_ylim(0.048, 0.093)
ax.legend(frameon=False, ncol=3, loc="upper right")
save(fig, "figure_s4_stage_performance.png")

# Figure S5: final coefficient diagnostics (copied from audited main-paper asset).
shutil.copy2(
    ROOT / "figures" / "main" / "figure3_diagnostics.png",
    FIG / "figure_s5_final_diagnostics.png",
)

# Figure S6: direct M4 repeated-run heatmap plus cross-provider summary.
direct = [
    json.loads(line)
    for line in (ROOT / "llm_repeated" / "raw_outputs" / "candidates_30_M4_codex.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]
term_order = [
    "Sn",
    "Br",
    "Cl",
    "Cs",
    "Sn^2",
    "Br^2",
    "Cl^2",
    "Cs^2",
    "Sn*Br",
    "Sn*Cl",
    "Br*Cl",
    "Cs*Sn",
    "Cs*Br",
    "Cs*Cl",
]
matrix = np.zeros((len(term_order), len(direct)), dtype=int)
for col, item in enumerate(direct):
    canonical = item.get("canonical_for_validation", "")
    terms = {term.strip() for term in canonical.split("+") if term.strip()}
    for row, term in enumerate(term_order):
        matrix[row, col] = int(term in terms)

external = pd.read_csv(
    ROOT / "llm_repeated" / "external_api_runs" / "external_api_summary_with_median_iqr.csv"
)
fig, axes = plt.subplots(2, 1, figsize=(7.3, 6.1), gridspec_kw={"height_ratios": [1.8, 1]})
axes[0].imshow(matrix, aspect="auto", interpolation="nearest", cmap="Blues", vmin=0, vmax=1)
axes[0].set_yticks(np.arange(len(term_order)), term_order)
axes[0].set_xticks(np.arange(0, 30, 2), [str(i) for i in range(1, 31, 2)])
axes[0].set_xlabel("Independent direct M4 run")
axes[0].set_title("(a) Term occurrence in 30 direct M4 prompt outputs")
labels = [f"{r.provider}, T={r.T:g}" for r in external.itertuples()]
axes[1].bar(
    np.arange(len(external)),
    external["test_median"],
    yerr=external["test_iqr"] / 2,
    color=[MID_BLUE if p == "qwen" else ORANGE for p in external["provider"]],
    capsize=3,
)
axes[1].axhline(0.060613, color=RED, linestyle="--", linewidth=1, label="Final M4 test RMSE")
axes[1].set_xticks(np.arange(len(external)), labels, rotation=25, ha="right")
axes[1].set_ylabel("Median test RMSE (eV)")
axes[1].set_title("(b) Cross-provider repeated workflow summary")
axes[1].set_ylim(0.054, 0.068)
axes[1].legend(frameon=False, loc="upper right")
fig.tight_layout()
save(fig, "figure_s6_llm_stochasticity.png")

# Figure S7: symbolic baseline performance/complexity.
pysr = json.loads((ROOT / "baselines/pysr" / "pysr_summary.json").read_text(encoding="utf-8"))
gplearn = json.loads(
    (ROOT / "baselines" / "gplearn" / "gplearn_summary.json").read_text(
        encoding="utf-8"
    )
)
points = [
    ("Final M4", 8, 0.060613, BLUE),
    ("Exhaustive-6", 6, 0.066711, GREEN),
    ("PySR polynomial", np.mean([r["best_complexity"] for r in pysr["P_polynomial"]["per_seed"]]), pysr["P_polynomial"]["best_test_rmse_mean"], ORANGE),
    ("PySR rich", np.mean([r["best_complexity"] for r in pysr["R_rich"]["per_seed"]]), pysr["R_rich"]["best_test_rmse_mean"], RED),
    ("GPLearn", gplearn["mean_program_length_cv"], gplearn["test_rmse_mean"], GRAY),
]
fig, ax = plt.subplots(figsize=(7.2, 3.8))
for label, complexity, error, color in points:
    ax.scatter(complexity, error, s=65, color=color)
    ax.annotate(label, (complexity, error), xytext=(5, 4), textcoords="offset points", fontsize=8)
ax.set_xlabel("Reported term/program complexity")
ax.set_ylabel("Post hoc test RMSE (eV)")
ax.set_xlim(3, max(p[1] for p in points) + 5)
ax.set_ylim(0.05, max(p[2] for p in points) + 0.025)
ax.set_title("Accuracy-complexity reference for symbolic approaches")
save(fig, "figure_s7_symbolic_baselines.png")

# Figures S8-S10: existing SHAP outputs and composites.
shutil.copy2(
    ROOT / "blackbox_shap/gbrt" / "figures" / "shap_beeswarm.png",
    FIG / "figure_s8_gbrt_shap_beeswarm.png",
)


def horizontal_composite(paths: list[Path], output: Path, labels: list[str]) -> None:
    fig, axes = plt.subplots(1, len(paths), figsize=(7.3, 3.6))
    if len(paths) == 1:
        axes = [axes]
    for ax, path, label in zip(axes, paths, labels):
        ax.imshow(Image.open(path))
        ax.axis("off")
        ax.set_title(label, fontweight="bold", fontsize=10)
    fig.tight_layout()
    save(fig, output.name)


horizontal_composite(
    [
        ROOT / "blackbox_shap/rf_xgboost" / "figures" / "RF_shap_beeswarm.png",
        ROOT / "blackbox_shap/rf_xgboost" / "figures" / "XGBoost_shap_beeswarm.png",
    ],
    FIG / "figure_s9_rf_xgb_shap_beeswarm.png",
    ["(a) Random forest", "(b) XGBoost"],
)
shutil.copy2(
    ROOT / "blackbox_shap/gbrt" / "figures" / "shap_interaction_heatmap.png",
    FIG / "figure_s10_shap_interactions.png",
)

shutil.copy2(
    ROOT
    / "group_aware_sensitivity"
    / "outputs"
    / "figures"
    / "group_aware_term_frequency_heatmap.png",
    FIG / "figure_s11_group_term_frequency.png",
)
shutil.copy2(
    ROOT
    / "group_aware_sensitivity"
    / "outputs"
    / "figures"
    / "group_aware_heldout_group_error.png",
    FIG / "figure_s12_group_heldout_error.png",
)
shutil.copy2(
    ROOT / "figures" / "main" / "figure6_design_map.png",
    FIG / "figure_s13_design_maps.png",
)

# Design demonstration: 100,000 local perturbations around archived training rows.
rng = np.random.default_rng(20260609)
n_screen = 100_000
base_idx = rng.integers(0, len(train), size=n_screen)
base = train.iloc[base_idx].reset_index(drop=True)

sn = np.clip(base["Sn"].to_numpy(float) + rng.normal(0, 0.04, n_screen), 0, 1)

def perturb_simplex(values: np.ndarray, concentration: float = 120.0) -> np.ndarray:
    alpha = np.maximum(values * concentration, 0.25)
    draws = np.empty_like(values, dtype=float)
    for i in range(len(values)):
        draws[i] = rng.dirichlet(alpha[i])
    return draws


a_draw = perturb_simplex(base[["FA", "MA", "Cs"]].to_numpy(float))
x_draw = perturb_simplex(base[["I", "Br", "Cl"]].to_numpy(float))
screen = pd.DataFrame(
    {
        "FA": a_draw[:, 0],
        "MA": a_draw[:, 1],
        "Cs": a_draw[:, 2],
        "Pb": 1 - sn,
        "Sn": sn,
        "I": x_draw[:, 0],
        "Br": x_draw[:, 1],
        "Cl": x_draw[:, 2],
    }
)
screen["Eg_pred"] = m4(screen["Sn"], screen["Br"], screen["Cl"], screen["Cs"])
tree = cKDTree(train[["Sn", "Br", "Cl", "Cs", "MA"]].to_numpy(float))
screen["nearest_train_distance"] = tree.query(
    screen[["Sn", "Br", "Cl", "Cs", "MA"]].to_numpy(float)
)[0]
eligible = screen[
    screen["Eg_pred"].between(1.60, 1.80)
    & (screen["nearest_train_distance"] <= 0.15)
    & (screen["Cs"] <= 0.50)
    & (screen["Cl"] <= 0.15)
].copy()
selected_rows = []
targets = [1.62, 1.66, 1.70, 1.74, 1.78]
quotas = [2, 2, 3, 2, 3]
for target, quota in zip(targets, quotas):
    ranked = eligible.assign(
        target_distance=(eligible["Eg_pred"] - target).abs()
    ).sort_values(["target_distance", "nearest_train_distance"])
    picked = 0
    for _, row in ranked.iterrows():
        vector = row[["Sn", "Br", "Cl", "Cs", "MA"]].to_numpy(float)
        distances = [
            np.linalg.norm(
                vector
                - selected[["Sn", "Br", "Cl", "Cs", "MA"]].to_numpy(float)
            )
            for selected in selected_rows
        ]
        if not distances or min(distances) >= 0.08:
            selected_rows.append(row)
            picked += 1
        if picked == quota:
            break
selected = pd.DataFrame(selected_rows)
selected.insert(0, "Candidate", [f"C{i:02d}" for i in range(1, len(selected) + 1)])
selected.to_csv(DATA / "design_candidates.csv", index=False)

summary = {
    "dataset": {
        "raw_rows": int(len(raw)),
        "processed_composition_means": int(len(processed)),
        "unique_full_rows": int(len(row_counter(raw))),
        "exact_duplicate_row_excess": int(len(raw) - len(row_counter(raw))),
        "unique_compositions": int(
            raw.groupby(fractions, dropna=False).ngroups
        ),
        "duplicate_composition_groups": int(len(dups)),
        "duplicate_composition_excess": int(dups["count"].sum() - len(dups)),
        "split_multiset_equal": bool(split_multiset_equal),
    },
    "split": {
        "train_n": int(len(train)),
        "test_n": int(len(test)),
        "shared_full_composition_groups": int(len(shared_compositions)),
        "test_rows_in_shared_full_compositions": int(
            sum(test_compositions[key] for key in shared_compositions)
        ),
        "shared_exact_full_rows": int(len(shared_full_rows)),
        "test_rows_exactly_repeated_from_training": int(
            sum(test_full_rows[key] for key in shared_full_rows)
        ),
        "shared_model_feature_combinations": int(
            len(set(test_model_keys) & train_model_keys)
        ),
        "test_rows_shared_model_features": int(shared_model_mask.sum()),
        "test_rows_unseen_model_features": int((~shared_model_mask).sum()),
        "shared_feature_rmse": shared_rmse,
        "unseen_feature_rmse": unseen_rmse,
        "generation_seed_status": "Not present in the archive and not recovered from seeds 0-199999 under sklearn train_test_split(test_size=0.15).",
    },
    "checksums": {
        "data/dataset_610_snapshot.xlsx": sha256(dataset_path),
        "data/train_518.xlsx": sha256(train_path),
        "data/test_92.xlsx": sha256(test_path),
    },
    "design_screen": {
        "seed": 20260609,
        "generated": n_screen,
        "target_window_eV": [1.60, 1.80],
        "distance_features": ["Sn", "Br", "Cl", "Cs", "MA"],
        "distance_threshold": 0.15,
        "additional_domain_filters": {"Cs_max": 0.50, "Cl_max": 0.15},
        "eligible": int(len(eligible)),
        "reported_candidates": int(len(selected)),
    },
}
(DATA / "si_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(json.dumps(summary, indent=2, ensure_ascii=False))
