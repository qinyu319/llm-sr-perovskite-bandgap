from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "figures" / "main"
OUT.mkdir(parents=True, exist_ok=True)

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


def load_split(n: int) -> pd.DataFrame:
    for p in DATA.glob("*.xlsx"):
        df = pd.read_excel(p)
        if len(df) == n:
            return df.rename(columns={"Bg": "Eg", "bg": "Eg"})
    raise FileNotFoundError(n)


train = load_split(518)
test = load_split(92)


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# Figure 1: deterministic workflow.
fig, ax = plt.subplots(figsize=(7.2, 4.3))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis("off")
boxes = [
    (0.35, 3.85, 1.7, 1.05, "Curated HOIP\ncomposition data", LIGHT_BLUE),
    (2.35, 3.85, 1.7, 1.05, "Physics-constrained\nprompt", LIGHT_BLUE),
    (4.35, 3.85, 1.7, 1.05, "LLM proposes\nstructures only", "#FFF2CC"),
    (6.35, 3.85, 1.7, 1.05, "OLS coefficient\nfitting", "#E2F0D9"),
    (8.35, 3.85, 1.3, 1.05, "Training\n5-fold CV", "#E2F0D9"),
    (1.3, 1.65, 2.0, 1.0, "Complexity-aware\ncandidate selection", "#E2F0D9"),
    (4.0, 1.65, 2.0, 1.0, "VIF, confidence intervals,\nbootstrap sign stability", "#E2F0D9"),
    (6.7, 1.65, 2.0, 1.0, "Benchmarks, SHAP,\ngroup-aware splits", "#E2F0D9"),
    (4.0, 0.15, 2.0, 0.9, "Freeze Final 8-term M4\nbefore test evaluation", "#DDEBF7"),
]
for x, y, w, h, text, color in boxes:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=1.1,
        edgecolor=BLUE,
        facecolor=color,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        color="#202020",
        fontsize=6.5,
    )

def arrow(x1, y1, x2, y2):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=11,
            linewidth=1.2,
            color=GRAY,
        )
    )

for x1, x2 in [(2.05, 2.35), (4.05, 4.35), (6.05, 6.35), (8.05, 8.35)]:
    arrow(x1, 4.38, x2, 4.38)
arrow(9.0, 3.82, 2.3, 2.75)
arrow(3.35, 2.15, 4.0, 2.15)
arrow(6.0, 2.15, 6.7, 2.15)
arrow(7.7, 1.62, 5.55, 1.05)
arrow(5.0, 1.62, 5.0, 1.07)
ax.text(
    5,
    5.58,
    "LLM stochasticity is isolated to hypothesis generation;\nall fitting, screening, diagnostics, and freezing are deterministic.",
    ha="center",
    va="center",
    fontsize=8.5,
    fontweight="bold",
    color=BLUE,
)
save(fig, "figure1_workflow.png")


# Figure 2: data structure and split representativeness.
fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.8))
bins = np.linspace(1.1, 3.2, 24)
axes[0, 0].hist(train["Eg"], bins=bins, alpha=0.72, label="Train (n=518)", color=BLUE)
axes[0, 0].hist(test["Eg"], bins=bins, alpha=0.62, label="Test (n=92)", color=ORANGE)
axes[0, 0].axvspan(1.5, 1.7, color="#A9D18E", alpha=0.25, label="1.5-1.7 eV")
axes[0, 0].set_xlabel("$E_g$ (eV)")
axes[0, 0].set_ylabel("Count")
axes[0, 0].set_title("(a) Band-gap distribution")
axes[0, 0].legend(frameon=False)

features = ["Sn", "Br", "Cl", "Cs", "MA"]
x = np.arange(len(features))
width = 0.36
axes[0, 1].bar(x - width / 2, train[features].mean(), width, label="Train", color=BLUE)
axes[0, 1].bar(x + width / 2, test[features].mean(), width, label="Test", color=ORANGE)
axes[0, 1].set_xticks(x, features)
axes[0, 1].set_ylabel("Mean site fraction")
axes[0, 1].set_title("(b) Composition means")
axes[0, 1].legend(frameon=False)

corr = train[["Sn", "Br", "Cl", "Cs", "MA"]].corrwith(train["Eg"])
colors = [RED if v < 0 else BLUE for v in corr]
axes[1, 0].barh(corr.index, corr.values, color=colors)
axes[1, 0].axvline(0, color="#333333", linewidth=0.8)
axes[1, 0].set_xlim(-0.5, 0.8)
axes[1, 0].set_xlabel("Pearson correlation with $E_g$")
axes[1, 0].set_title("(c) Marginal composition correlations")

axes[1, 1].scatter(
    train["Br"],
    train["Eg"],
    s=13,
    alpha=0.42,
    color=BLUE,
    edgecolor="none",
    label="Train",
)
cl_mask = train["Cl"] > 0
axes[1, 1].scatter(
    train.loc[cl_mask, "Br"],
    train.loc[cl_mask, "Eg"],
    s=26,
    alpha=0.85,
    color=ORANGE,
    edgecolor="white",
    linewidth=0.3,
    label="Cl-containing",
)
axes[1, 1].set_xlabel("Br fraction")
axes[1, 1].set_ylabel("$E_g$ (eV)")
axes[1, 1].set_title("(d) Sparse high-$E_g$/Cl-containing region")
axes[1, 1].legend(frameon=False)
fig.tight_layout()
save(fig, "figure2_dataset_structure.png")


# Figure 3: coefficient, CI, VIF, sign stability.
coef_path = ROOT / "final_m4_diagnostics" / "final_M4_coefficients_CI_bootstrap.csv"
coef = pd.read_csv(coef_path)
coef = coef[coef["Raw term"].astype(str) != "Intercept"].copy()
terms = coef["Term"].astype(str).str.replace("²", r"$^2$", regex=False).str.replace("·", "×", regex=False)
fig, axes = plt.subplots(1, 3, figsize=(7.3, 3.5), gridspec_kw={"width_ratios": [1.7, 1, 1]})
ypos = np.arange(len(coef))[::-1]
axes[0].errorbar(
    coef["Coefficient"],
    ypos,
    xerr=[
        coef["Coefficient"] - coef["OLS CI low"],
        coef["OLS CI high"] - coef["Coefficient"],
    ],
    fmt="o",
    color=BLUE,
    ecolor="#7F8C8D",
    capsize=3,
)
axes[0].axvline(0, color="#333333", linewidth=0.8)
axes[0].set_yticks(ypos, terms)
axes[0].set_xlabel("OLS coefficient (eV)")
axes[0].set_title("(a) Coefficients and 95% CI")

vif_values = [15.16899, 9.24525, 1.48801, 1.57975, 15.78631, 9.12341, 2.01147, 1.72767]
axes[1].barh(ypos, vif_values, color=MID_BLUE)
axes[1].axvline(10, color=ORANGE, linestyle="--", linewidth=1)
axes[1].set_yticks(ypos, [])
axes[1].set_xlabel("VIF")
axes[1].set_title("(b) Collinearity")

stability = coef["Bootstrap sign stability"].to_numpy(float)
axes[2].barh(ypos, stability, color=GREEN)
axes[2].set_xlim(0.95, 1.002)
axes[2].set_yticks(ypos, [])
axes[2].set_xlabel("Sign stability")
axes[2].set_title("(c) 1000 bootstraps")
fig.tight_layout()
save(fig, "figure3_diagnostics.png")


# Figure 4: benchmark performance and SHAP cross-check.
bench = pd.DataFrame(
    {
        "Method": ["GP", "XGBoost", "GBRT", "RF", "Final M4", "Exhaustive-6", "PySR-P"],
        "CV": [0.051320, 0.051267, 0.053247, 0.059683, 0.057532, 0.062853, np.nan],
        "Test": [0.048604, 0.060565, 0.052021, 0.055863, 0.060613, 0.066711, 0.0683],
    }
)
shap = pd.read_csv(ROOT / "blackbox_shap" / "gbrt" / "shap_global_importance.csv")
fig, axes = plt.subplots(1, 2, figsize=(7.3, 3.6))
x = np.arange(len(bench))
axes[0].bar(x - 0.18, bench["CV"], 0.36, label="Train CV", color=BLUE)
axes[0].bar(x + 0.18, bench["Test"], 0.36, label="Test", color=ORANGE)
axes[0].set_xticks(x, bench["Method"], rotation=38, ha="right")
axes[0].set_ylabel("RMSE (eV)")
axes[0].set_ylim(0, 0.082)
axes[0].set_title("(a) Predictive benchmark")
axes[0].legend(frameon=False)
axes[0].annotate(
    "transparent\n8-term formula",
    xy=(4, 0.0606),
    xytext=(4.7, 0.076),
    arrowprops={"arrowstyle": "->", "color": GRAY},
    ha="center",
    fontsize=8,
)

shap = shap.sort_values("mean_abs_shap")
axes[1].barh(shap["feature"], shap["mean_abs_shap"], color=[LIGHT_GRAY, LIGHT_GRAY, MID_BLUE, MID_BLUE, MID_BLUE])
axes[1].set_xlabel("Mean |SHAP| (eV)")
axes[1].set_title("(b) GBRT global SHAP importance")
axes[1].text(
    0.064,
    0.25,
    "Dominant:\nBr, Sn, Cl",
    color=BLUE,
    fontsize=9,
    fontweight="bold",
)
fig.tight_layout()
save(fig, "figure4_benchmark_shap.png")


# Figure 5: group-aware applicability domain.
group = pd.read_csv(
    ROOT
    / "group_aware_sensitivity"
    / "outputs"
    / "summary_tables"
    / "group_aware_heldout_group_summary.csv"
)
specific = group[group["group_strategy"].isin(["halide_logo", "a_site_logo"])].copy()
specific["label"] = specific["heldout_groups"].astype(str).str.replace("_", " ")
specific = specific.sort_values("mean_test_rmse")
fig, axes = plt.subplots(1, 2, figsize=(7.3, 3.8), gridspec_kw={"width_ratios": [1.45, 1]})
colors = [RED if "Cl containing" in label else (ORANGE if "Cs rich" in label else BLUE) for label in specific["label"]]
axes[0].barh(specific["label"], specific["mean_test_rmse"], color=colors)
axes[0].axvline(0.060613, color="#222222", linestyle="--", linewidth=1, label="Random split M4")
axes[0].set_xlabel("Held-out-group RMSE (eV)")
axes[0].set_title("(a) Leave-one-group-out error")
axes[0].legend(frameon=False, loc="lower right")

summary = pd.read_csv(
    ROOT
    / "group_aware_sensitivity"
    / "outputs"
    / "summary_tables"
    / "group_aware_summary.csv"
)
axes[1].errorbar(
    np.arange(len(summary)),
    summary["mean_test_rmse"],
    yerr=summary["sd_test_rmse"],
    fmt="o",
    capsize=4,
    color=BLUE,
)
axes[1].axhline(0.060613, color="#222222", linestyle="--", linewidth=1)
axes[1].set_xticks(
    np.arange(len(summary)),
    ["Composition\nfamily", "Halide\nLOGO", "A-site\nLOGO"],
)
axes[1].set_ylabel("RMSE (eV)")
axes[1].set_title("(b) Strategy-level sensitivity")
axes[1].set_ylim(0, 0.75)
axes[1].annotate(
    "Cl-containing\nboundary",
    xy=(1, 0.60),
    xytext=(1.45, 0.68),
    arrowprops={"arrowstyle": "->", "color": RED},
    color=RED,
    ha="center",
)
fig.tight_layout()
save(fig, "figure5_group_aware.png")


# Figure 6: composition-guided design maps with distance-to-training mask.
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

tree = cKDTree(train[["Sn", "Br", "Cl", "Cs"]].to_numpy(float))
grid = np.linspace(0, 1, 161)
sn, br = np.meshgrid(grid, grid)
cs = np.full_like(sn, 0.10)
cl = np.zeros_like(sn)
z1 = m4(sn, br, cl, cs)
d1, _ = tree.query(np.c_[sn.ravel(), br.ravel(), cl.ravel(), cs.ravel()])
d1 = d1.reshape(sn.shape)

cl2, br2 = np.meshgrid(grid, grid)
sn2 = np.zeros_like(cl2)
cs2 = np.full_like(sn2, 0.10)
valid = br2 + cl2 <= 1
z2 = m4(sn2, br2, cl2, cs2)
d2, _ = tree.query(np.c_[sn2.ravel(), br2.ravel(), cl2.ravel(), cs2.ravel()])
d2 = d2.reshape(sn2.shape)

fig, axes = plt.subplots(1, 2, figsize=(7.3, 3.45))
levels = np.linspace(1.15, 3.0, 19)
for ax, xx, yy, zz, dist, title, xlabel, ylabel in [
    (axes[0], br, sn, z1, d1, "(a) Cs=0.10, Cl=0", "Br fraction", "Sn fraction"),
    (axes[1], cl2, br2, z2, d2, "(b) Cs=0.10, Sn=0", "Cl fraction", "Br fraction"),
]:
    mask = (dist > 0.25) | (~valid if ax is axes[1] else False)
    shown = np.ma.masked_where(mask, zz)
    cf = ax.contourf(xx, yy, shown, levels=levels, cmap="viridis", extend="both")
    ax.contour(xx, yy, shown, levels=[1.6, 1.7, 1.8], colors="white", linewidths=0.8)
    target = np.ma.masked_where(mask | (zz < 1.6) | (zz > 1.8), zz)
    ax.contourf(xx, yy, target, levels=[1.6, 1.8], colors=["none"], hatches=["////"])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
cax = fig.add_axes([0.87, 0.22, 0.022, 0.62])
cbar = fig.colorbar(cf, cax=cax)
cbar.set_ticks(np.linspace(1.15, 3.0, 7))
cbar.set_label("Predicted $E_g$ (eV)")
fig.text(
    0.5,
    -0.01,
    "Colored regions are within Euclidean distance 0.25 of at least one training composition;\nhatching marks the illustrative 1.60-1.80 eV screening window.",
    ha="center",
    fontsize=8,
    color=GRAY,
)
fig.subplots_adjust(bottom=0.22, wspace=0.22, right=0.84)
save(fig, "figure6_design_map.png")

print(f"Created figures in {OUT}")
