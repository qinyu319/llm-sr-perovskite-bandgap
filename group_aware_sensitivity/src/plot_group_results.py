from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import PROJECT_ROOT
from .model_terms import CORE_TERMS


STRATEGY_LABELS = {
    "composition_family_group_shuffle": "Composition-family GSS",
    "halide_logo": "Halide LOGO",
    "a_site_logo": "A-site LOGO",
}


def _save(fig: plt.Figure, stem: str) -> None:
    out = PROJECT_ROOT / "outputs" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_rmse_distribution(results: pd.DataFrame, reference_rmse: float) -> None:
    plot_df = results.copy()
    plot_df["Strategy"] = plot_df["group_strategy"].map(STRATEGY_LABELS)
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    sns.boxplot(data=plot_df, x="Strategy", y="test_rmse", color="#9CC5DA", ax=ax)
    sns.stripplot(data=plot_df, x="Strategy", y="test_rmse", color="#1F4E79", size=4, alpha=0.75, ax=ax)
    ax.axhline(reference_rmse, color="#C00000", linestyle="--", linewidth=1.5, label="Frozen random 85/15 reference")
    ax.set_ylabel("Held-out group RMSE (eV)")
    ax.set_xlabel("")
    ax.set_title("Group-aware test RMSE distribution")
    ax.tick_params(axis="x", rotation=15)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, "group_aware_rmse_distribution")


def plot_term_frequency(frequency: pd.DataFrame) -> None:
    pivot = (
        frequency.loc[frequency["term"].isin(CORE_TERMS)]
        .pivot(index="term", columns="group_strategy", values="frequency_percentage")
        .reindex(index=CORE_TERMS)
        .reindex(columns=list(STRATEGY_LABELS))
        .rename(columns=STRATEGY_LABELS)
    )
    fig, ax = plt.subplots(figsize=(7.8, 5.8))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="Blues", vmin=0, vmax=100, cbar_kws={"label": "Selected (%)"}, ax=ax)
    ax.set_title("Core-term selection frequency")
    ax.set_xlabel("")
    ax.set_ylabel("")
    fig.tight_layout()
    _save(fig, "group_aware_term_frequency_heatmap")


def plot_formula_similarity(results: pd.DataFrame) -> None:
    plot_df = results.copy()
    plot_df["Strategy"] = plot_df["group_strategy"].map(STRATEGY_LABELS)
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    sns.boxplot(data=plot_df, x="Strategy", y="formula_jaccard_to_M4", color="#B7D7A8", ax=ax)
    sns.stripplot(data=plot_df, x="Strategy", y="formula_jaccard_to_M4", color="#38761D", size=4, alpha=0.75, ax=ax)
    ax.set_ylim(-0.02, 1.02)
    ax.set_ylabel("Jaccard similarity to frozen M4")
    ax.set_xlabel("")
    ax.set_title("Selected-formula similarity")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    _save(fig, "group_aware_formula_similarity")


def plot_heldout_group_error(results: pd.DataFrame) -> None:
    logo = results.loc[results["group_strategy"].isin(["halide_logo", "a_site_logo"])].copy()
    logo["Held-out group"] = logo["heldout_groups"]
    logo["Strategy"] = logo["group_strategy"].map(STRATEGY_LABELS)
    logo = logo.sort_values("test_rmse", ascending=False)
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    sns.barplot(data=logo, x="Held-out group", y="test_rmse", hue="Strategy", palette=["#E69138", "#674EA7"], ax=ax)
    ax.set_ylabel("Held-out group RMSE (eV)")
    ax.set_xlabel("")
    ax.set_title("Leave-one-group-out error by held-out regime")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    _save(fig, "group_aware_heldout_group_error")


def generate_all_figures(results: pd.DataFrame, frequency: pd.DataFrame, reference_rmse: float) -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plot_rmse_distribution(results, reference_rmse)
    plot_term_frequency(frequency)
    plot_formula_similarity(results)
    plot_heldout_group_error(results)
