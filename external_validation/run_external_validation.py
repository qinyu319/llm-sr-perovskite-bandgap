from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parent
REPO = BASE.parent
OUT = REPO / "reproduced" / "external_validation"

CUTOFF = pd.Timestamp("2026-01-28")
IN_DOMAIN_THRESHOLD = 0.25
COMPOSITION_DUP_THRESHOLD = 0.01
VALUE_DUP_THRESHOLD = 0.01
SAME_SOURCE_RMSE = 0.060613471751538577
CONSISTENCY_THRESHOLD = 2.0 * SAME_SOURCE_RMSE
BOOTSTRAP_SEED = 20260611
BOOTSTRAP_REPS = 20000
EXPECTED_PANEL_N = 20
EXPECTED_DOI_N = 8
EXPECTED_RMSE = 0.04167090742733822
EXPECTED_MAE = 0.03267851978554427
EXPECTED_NOVEL_N = 16
EXPECTED_NOVEL_RMSE = 0.04526023332762144

FEATURES = ["FA", "MA", "Cs", "Pb", "Sn", "I", "Br", "Cl"]
COEFFICIENTS = {
    "Intercept": 1.5552651680420202,
    "Sn": -1.1025280815784506,
    "Br": 0.3431953132457202,
    "Cl": 1.6193177112496755,
    "Cs": 0.12267888917628159,
    "Sn2": 0.9170216432831477,
    "Br2": 0.36607403560749485,
    "CsSn": -0.22715626984385914,
    "CsCl": -0.3252750459356003,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the source-audited external validation."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT,
        help="Output directory (default: reproduced/external_validation).",
    )
    return parser.parse_args()


def predict_m4(frame: pd.DataFrame) -> pd.Series:
    return (
        COEFFICIENTS["Intercept"]
        + COEFFICIENTS["Sn"] * frame["Sn"]
        + COEFFICIENTS["Br"] * frame["Br"]
        + COEFFICIENTS["Cl"] * frame["Cl"]
        + COEFFICIENTS["Cs"] * frame["Cs"]
        + COEFFICIENTS["Sn2"] * frame["Sn"] ** 2
        + COEFFICIENTS["Br2"] * frame["Br"] ** 2
        + COEFFICIENTS["CsSn"] * frame["Cs"] * frame["Sn"]
        + COEFFICIENTS["CsCl"] * frame["Cs"] * frame["Cl"]
    )


def basic_metrics(frame: pd.DataFrame) -> dict[str, float]:
    residual = frame["residual_eV"].to_numpy(float)
    measured = frame["Eg_eV"].to_numpy(float)
    predicted = frame["M4_prediction_eV"].to_numpy(float)
    rmse = float(np.sqrt(np.mean(residual**2)))
    mae = float(np.mean(np.abs(residual)))
    bias = float(np.mean(residual))
    ss_res = float(np.sum((measured - predicted) ** 2))
    ss_tot = float(np.sum((measured - measured.mean()) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    return {"n": len(frame), "rmse_eV": rmse, "mae_eV": mae, "bias_eV": bias, "r2": r2}


def row_bootstrap(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    residual = frame["residual_eV"].to_numpy(float)
    n = len(residual)
    indices = rng.integers(0, n, size=(BOOTSTRAP_REPS, n))
    samples = residual[indices]
    rmse = np.sqrt(np.mean(samples**2, axis=1))
    mae = np.mean(np.abs(samples), axis=1)
    return {
        "rmse_ci_low_eV": float(np.quantile(rmse, 0.025)),
        "rmse_ci_high_eV": float(np.quantile(rmse, 0.975)),
        "mae_ci_low_eV": float(np.quantile(mae, 0.025)),
        "mae_ci_high_eV": float(np.quantile(mae, 0.975)),
    }


def cluster_bootstrap(frame: pd.DataFrame, rng: np.random.Generator) -> dict[str, float]:
    groups = {doi: group["residual_eV"].to_numpy(float) for doi, group in frame.groupby("DOI")}
    dois = np.array(list(groups), dtype=object)
    rmse_values = np.empty(BOOTSTRAP_REPS)
    mae_values = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        sampled_dois = rng.choice(dois, size=len(dois), replace=True)
        residual = np.concatenate([groups[doi] for doi in sampled_dois])
        rmse_values[i] = np.sqrt(np.mean(residual**2))
        mae_values[i] = np.mean(np.abs(residual))
    return {
        "cluster_rmse_ci_low_eV": float(np.quantile(rmse_values, 0.025)),
        "cluster_rmse_ci_high_eV": float(np.quantile(rmse_values, 0.975)),
        "cluster_mae_ci_low_eV": float(np.quantile(mae_values, 0.025)),
        "cluster_mae_ci_high_eV": float(np.quantile(mae_values, 0.975)),
        "n_doi": len(dois),
    }


def publication_balanced_metrics(frame: pd.DataFrame) -> dict[str, float]:
    source_mse = frame.groupby("DOI")["residual_eV"].apply(lambda x: float(np.mean(np.square(x))))
    source_mae = frame.groupby("DOI")["residual_eV"].apply(lambda x: float(np.mean(np.abs(x))))
    source_bias = frame.groupby("DOI")["residual_eV"].mean()
    return {
        "publication_balanced_rmse_eV": float(np.sqrt(source_mse.mean())),
        "publication_balanced_mae_eV": float(source_mae.mean()),
        "publication_balanced_bias_eV": float(source_bias.mean()),
    }


def metric_row(name: str, frame: pd.DataFrame, bootstrap: bool = False) -> dict[str, object]:
    row: dict[str, object] = {"subset": name, **basic_metrics(frame)}
    if bootstrap and len(frame) > 1:
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        row.update(row_bootstrap(frame, rng))
        rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
        row.update(cluster_bootstrap(frame, rng))
        row.update(publication_balanced_metrics(frame))
    return row


def nearest_distance(
    query: np.ndarray, reference: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    delta = query[:, None, :] - reference[None, :, :]
    distance = np.sqrt(np.sum(delta**2, axis=2))
    index = np.argmin(distance, axis=1)
    return distance[np.arange(len(query)), index], index


def create_plot(panel: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
        }
    )
    fig = plt.figure(figsize=(7.4, 3.45), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.3, 0.85])
    ax = fig.add_subplot(grid[0, 0])
    ax_bar = fig.add_subplot(grid[0, 1])

    lo = min(panel["Eg_eV"].min(), panel["M4_prediction_eV"].min()) - 0.04
    hi = max(panel["Eg_eV"].max(), panel["M4_prediction_eV"].max()) + 0.04
    x = np.linspace(lo, hi, 200)
    ax.fill_between(
        x,
        x - CONSISTENCY_THRESHOLD,
        x + CONSISTENCY_THRESHOLD,
        color="#d9e6f2",
        alpha=0.65,
        linewidth=0,
        label=r"$\pm 2\times$ held-out RMSE",
    )
    ax.fill_between(
        x,
        x - SAME_SOURCE_RMSE,
        x + SAME_SOURCE_RMSE,
        color="#9ecae1",
        alpha=0.65,
        linewidth=0,
        label=r"$\pm$ held-out RMSE",
    )
    ax.plot(x, x, color="#222222", linewidth=1.0, zorder=2)

    marker_map = {"Pb_no_Cl": "o", "Pb_low_Cl": "s", "Sn_Pb": "^"}
    color_map = {"Pb_no_Cl": "#2166ac", "Pb_low_Cl": "#b2182b", "Sn_Pb": "#4d9221"}
    label_map = {"Pb_no_Cl": "Pb, Cl = 0", "Pb_low_Cl": "Pb, 0 < Cl < 0.25", "Sn_Pb": "Sn-Pb"}
    for layer in ["Pb_no_Cl", "Pb_low_Cl", "Sn_Pb"]:
        group = panel[panel["layer"] == layer]
        if group.empty:
            continue
        ax.scatter(
            group["Eg_eV"],
            group["M4_prediction_eV"],
            s=34,
            marker=marker_map[layer],
            facecolor=color_map[layer],
            edgecolor="white",
            linewidth=0.55,
            label=label_map[layer],
            zorder=3,
        )

    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(r"Measured $E_g$ (eV)")
    ax.set_ylabel(r"M4-predicted $E_g$ (eV)")
    ax.legend(frameon=False, fontsize=7.4, loc="upper left")
    ax.text(0.98, 0.03, f"n = {len(panel)}", transform=ax.transAxes, ha="right", va="bottom")

    layer_order = ["All", "Pb, Cl=0", "Pb, low Cl", "Sn-Pb"]
    values = [
        basic_metrics(panel)["rmse_eV"],
        basic_metrics(panel[(panel["Sn"] == 0) & (panel["Cl"] == 0)])["rmse_eV"],
        basic_metrics(panel[(panel["Sn"] == 0) & (panel["Cl"] > 0)])["rmse_eV"],
        basic_metrics(panel[panel["Sn"] > 0])["rmse_eV"],
    ]
    colors = ["#4c78a8", "#2166ac", "#b2182b", "#4d9221"]
    bars = ax_bar.bar(layer_order, values, color=colors, width=0.66)
    ax_bar.axhline(SAME_SOURCE_RMSE, color="#555555", linestyle="--", linewidth=1, label="Held-out RMSE")
    ax_bar.axhline(CONSISTENCY_THRESHOLD, color="#999999", linestyle=":", linewidth=1, label="Predeclared limit")
    ax_bar.set_ylabel("RMSE (eV)")
    ax_bar.set_ylim(0, max(CONSISTENCY_THRESHOLD * 1.15, max(values) * 1.25))
    ax_bar.tick_params(axis="x", rotation=28)
    ax_bar.legend(frameon=False, fontsize=7.4, loc="upper right")
    for bar, value in zip(bars, values):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.004,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.savefig(OUT / "Fig_external_validation.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "Fig_external_validation.pdf", bbox_inches="tight")
    plt.close(fig)


def write_report(panel: pd.DataFrame, metrics: pd.DataFrame, exclusions: pd.DataFrame) -> None:
    main = metrics.loc[metrics["subset"] == "In-domain confirmatory"].iloc[0]
    novel = metrics.loc[metrics["subset"] == "Composition-novel (d_snapshot >= 0.01)"].iloc[0]
    sn = metrics.loc[metrics["subset"] == "Sn-containing"].iloc[0]
    exact_retests = int(panel["composition_overlap"].sum())
    value_suspects = int(panel["value_overlap_suspect"].sum())
    criterion = "passed" if main["rmse_eV"] <= CONSISTENCY_THRESHOLD else "not passed"
    ratio = main["rmse_eV"] / SAME_SOURCE_RMSE
    report = f"""# Audited external validation of frozen M4

## Executive result

The reconstructed panel contains **{len(panel)} measurements from {panel['DOI'].nunique()} post-snapshot publications**. All eligible records are inside the declared eight-fraction distance domain (`d_min <= {IN_DOMAIN_THRESHOLD:.2f}`), so the confirmatory result is an in-domain validation only.

The frozen M4 model achieved **RMSE {main['rmse_eV']:.4f} eV**, **MAE {main['mae_eV']:.4f} eV**, and bias {main['bias_eV']:+.4f} eV. The row-bootstrap 95% CI for RMSE is [{main['rmse_ci_low_eV']:.4f}, {main['rmse_ci_high_eV']:.4f}] eV; the DOI-cluster bootstrap CI is [{main['cluster_rmse_ci_low_eV']:.4f}, {main['cluster_rmse_ci_high_eV']:.4f}] eV. The result **{criterion}** the locked consistency criterion of RMSE <= {CONSISTENCY_THRESHOLD:.4f} eV (2 x the same-source held-out RMSE of {SAME_SOURCE_RMSE:.4f} eV). The point estimate is {ratio:.2f} x the same-source held-out RMSE.

The composition-novel sensitivity subset (`d_snapshot >= 0.01`) contains {int(novel['n'])} points and gives RMSE {novel['rmse_eV']:.4f} eV. The Sn-containing subset contains {int(sn['n'])} points and gives RMSE {sn['rmse_eV']:.4f} eV.

## What changed from the ZIP draft

The 21-point draft panel was not used for the final metrics because most records lacked DOI, primary-source locators, measurement method, and verifiable independence. It is omitted from the public package; its exclusion decisions are represented in the candidate audit log.

The replacement panel uses publisher supporting information or the primary paper for every included record. Publication dates are after the archived PDP snapshot date of January 28, 2026. Exact DOI matching could not be run against the local snapshot because the supplied export has no DOI field; post-cutoff publication is therefore the auditable construction rule.

## Deduplication audit

- DOI level: all included papers were published online after January 28, 2026.
- Composition level: {exact_retests} records have `d_snapshot < 0.01` and are marked as independent same-composition retests.
- Value level: {value_suspects} records meet both same-composition and `|delta Eg| < 0.01 eV`; none were silently removed.
- The main metric retains independent retests as specified, while the composition-novel metric reports the stricter sensitivity analysis.

## Dependence and measurement-quality checks

Multiple points come from two composition-scan papers. The DOI-cluster bootstrap and publication-balanced metrics prevent those scans from being interpreted as {len(panel)} fully independent publications. The nominal relative RMSE standard error is approximately `1/sqrt(2n) = {1/math.sqrt(2*len(panel)):.1%}` at the record level and `1/sqrt(2N_DOI) = {1/math.sqrt(2*panel['DOI'].nunique()):.1%}` at the publication level.

The largest coherent offset is the eight-point low-Cl co-evaporated scan from Nature Materials, for which M4 overpredicts by roughly 0.06 eV. This is retained and reported as a likely process/method shift rather than treated as an outlier. A sensitivity analysis excluding the one approximate Sn-Pb absorption-edge digitization is included in `metrics_summary.csv`.

## Applicability limitation

No post-cutoff high-Cl or `d_min > 0.25` thin-film record with an exact allowed composition and recoverable numerical experimental bandgap passed all inclusion criteria. Two high-Cl candidates in the Nature Materials SI lacked numerical bandgaps and were excluded before scoring. Therefore this reconstruction does **not** claim an external out-of-domain performance result. The applicability-domain statement should remain explicit.

## Reproducibility

- Frozen model: eight-term M4 with no refitting.
- Distance: Euclidean L2 distance on `[FA, MA, Cs, Pb, Sn, I, Br, Cl]`.
- Main endpoint: in-domain RMSE and MAE.
- Consistency rule: RMSE <= 0.1212 eV.
- Bootstrap: 20,000 replicates; seed 20260611.
- All passing records are reported.

The rule was supplied before this audited reconstruction and locked in the analysis script before the final metrics run. It is a dated analysis lock, not a public preregistration, and should not be described as blinded.

## Files

- `external_panel_audited.csv`: final point-level results.
- `candidate_audit_log.csv`: included and excluded candidates.
- `metrics_summary.csv`: primary and sensitivity metrics.
- `doi_level_metrics.csv`: per-publication performance.
- `leave_one_doi_out.csv`: source-dependence analysis.
- `Fig_external_validation.png` and `.pdf`: manuscript/SI figure.
- `analysis_metadata.json`: coefficients, thresholds, and run settings.
- `source_evidence_manifest.csv`: DOI links, source locators, and hashes of the locally audited source files. The source PDFs themselves are not redistributed.

## Primary-source links

"""
    for doi, group in panel.groupby("DOI", sort=False):
        report += f"- [{doi}]({group['source_url'].iloc[0]}) - {group['title'].iloc[0]}\n"
    report += f"\n## Exclusion count\n\n{len(exclusions)} candidate rows or candidate groups were excluded with reasons preserved in `candidate_audit_log.csv`.\n"
    (OUT / "external_validation_report.md").write_text(report, encoding="utf-8")


def write_source_manifest(panel: pd.DataFrame) -> None:
    manifest = pd.read_csv(BASE / "source_evidence_manifest.csv")
    if set(manifest["DOI"]) != set(panel["DOI"]):
        raise ValueError("Source manifest DOI set does not match the external panel")
    manifest.to_csv(OUT / "source_evidence_manifest.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    global OUT
    OUT = parse_args().output_dir.resolve()
    OUT.mkdir(parents=True, exist_ok=True)

    candidates = pd.read_csv(BASE / "external_validation_candidates.csv")
    included = candidates[candidates["status"] == "included"].copy()
    exclusions = candidates[candidates["status"] != "included"].copy()

    for column in FEATURES + ["Eg_eV", "Eg_uncertainty_eV"]:
        included[column] = pd.to_numeric(included[column], errors="raise")
    included["published_online"] = pd.to_datetime(included["published_online"], errors="raise")

    included["A_sum"] = included[["FA", "MA", "Cs"]].sum(axis=1)
    included["B_sum"] = included[["Pb", "Sn"]].sum(axis=1)
    included["X_sum"] = included[["I", "Br", "Cl"]].sum(axis=1)
    included["closure_pass"] = (
        (included["A_sum"].sub(1).abs() <= 0.01)
        & (included["B_sum"].sub(1).abs() <= 0.01)
        & (included["X_sum"].sub(1).abs() <= 0.01)
    )
    if not included["closure_pass"].all():
        bad = included.loc[~included["closure_pass"], "record_id"].tolist()
        raise ValueError(f"Site closure failed for {bad}")

    train = pd.read_csv(
        REPO / "group_aware_sensitivity" / "data" / "raw_train_with_qc.csv"
    )
    test = pd.read_csv(
        REPO / "group_aware_sensitivity" / "data" / "raw_external_test_with_qc.csv"
    )
    snapshot = pd.concat([train, test], ignore_index=True)
    if len(train) != 518 or len(snapshot) != 610:
        raise ValueError(f"Unexpected train/snapshot sizes: {len(train)}/{len(snapshot)}")

    query = included[FEATURES].to_numpy(float)
    d_train, nearest_train_index = nearest_distance(query, train[FEATURES].to_numpy(float))
    d_snapshot, nearest_snapshot_index = nearest_distance(query, snapshot[FEATURES].to_numpy(float))
    included["d_min_train"] = d_train
    included["nearest_train_sample_id"] = train.iloc[nearest_train_index]["sample_id"].to_numpy()
    included["d_min_snapshot"] = d_snapshot
    included["nearest_snapshot_sample_id"] = snapshot.iloc[nearest_snapshot_index]["sample_id"].to_numpy()
    included["nearest_snapshot_Eg_eV"] = snapshot.iloc[nearest_snapshot_index]["Eg"].to_numpy(float)
    included["nearest_snapshot_delta_Eg_eV"] = (
        included["Eg_eV"] - included["nearest_snapshot_Eg_eV"]
    ).abs()
    included["doi_dedup"] = np.where(
        included["published_online"] > CUTOFF,
        "PASS_POST_CUTOFF_BY_CONSTRUCTION",
        "REQUIRES_METADATA_MATCH",
    )
    included["composition_overlap"] = included["d_min_snapshot"] < COMPOSITION_DUP_THRESHOLD
    included["value_overlap_suspect"] = (
        included["composition_overlap"]
        & (included["nearest_snapshot_delta_Eg_eV"] < VALUE_DUP_THRESHOLD)
    )
    included["independent_retest"] = included["composition_overlap"] & ~included["value_overlap_suspect"]
    included["in_domain"] = included["d_min_train"] <= IN_DOMAIN_THRESHOLD
    included["M4_prediction_eV"] = predict_m4(included)
    included["residual_eV"] = included["M4_prediction_eV"] - included["Eg_eV"]
    included["absolute_error_eV"] = included["residual_eV"].abs()
    included["squared_error_eV2"] = included["residual_eV"] ** 2
    included["layer"] = np.select(
        [included["Sn"] > 0, included["Cl"] > 0],
        ["Sn_Pb", "Pb_low_Cl"],
        default="Pb_no_Cl",
    )
    included["main_metric_eligible"] = (
        included["closure_pass"]
        & (included["doi_dedup"] == "PASS_POST_CUTOFF_BY_CONSTRUCTION")
        & ~included["value_overlap_suspect"]
        & included["in_domain"]
    )

    panel = included[included["main_metric_eligible"]].copy()
    if len(panel) != len(included):
        raise ValueError("An included record failed the locked main-metric eligibility checks")
    if len(panel) != EXPECTED_PANEL_N or panel["DOI"].nunique() != EXPECTED_DOI_N:
        raise ValueError(
            "External panel no longer matches the paper-authoritative "
            f"{EXPECTED_PANEL_N}-record/{EXPECTED_DOI_N}-publication audit"
        )

    subsets: list[tuple[str, pd.DataFrame, bool]] = [
        ("In-domain confirmatory", panel, True),
        ("Composition-novel (d_snapshot >= 0.01)", panel[panel["d_min_snapshot"] >= 0.01], False),
        ("Independent same-composition retests", panel[panel["independent_retest"]], False),
        ("Pb-only", panel[panel["Sn"] == 0], False),
        ("Sn-containing", panel[panel["Sn"] > 0], False),
        ("Pb, Cl = 0", panel[(panel["Sn"] == 0) & (panel["Cl"] == 0)], False),
        ("Pb, 0 < Cl < 0.25", panel[(panel["Sn"] == 0) & (panel["Cl"] > 0) & (panel["Cl"] < 0.25)], False),
        ("Direct/figure-extracted tier A", panel[panel["quality_tier"].isin(["A", "A_fig"])], False),
        ("Exclude approximate Sn-Pb digitization", panel[panel["record_id"] != "SNPB125"], False),
        ("Author-tabulated/annotated only", panel[~panel["extraction_mode"].isin(["figure_digitized"])], False),
    ]
    metric_rows = [metric_row(name, frame, bootstrap) for name, frame, bootstrap in subsets if len(frame)]
    metrics = pd.DataFrame(metric_rows)
    metrics["same_source_rmse_eV"] = SAME_SOURCE_RMSE
    metrics["consistency_threshold_eV"] = CONSISTENCY_THRESHOLD
    metrics["criterion_pass"] = metrics["rmse_eV"] <= CONSISTENCY_THRESHOLD

    doi_rows = []
    for doi, group in panel.groupby("DOI"):
        row = {"DOI": doi, "title": group["title"].iloc[0], **basic_metrics(group)}
        doi_rows.append(row)
    doi_metrics = pd.DataFrame(doi_rows).sort_values("rmse_eV", ascending=False)

    loo_rows = []
    for doi in panel["DOI"].unique():
        group = panel[panel["DOI"] != doi]
        row = {
            "excluded_DOI": doi,
            "excluded_n": int((panel["DOI"] == doi).sum()),
            **basic_metrics(group),
        }
        loo_rows.append(row)
    loo = pd.DataFrame(loo_rows).sort_values("rmse_eV", ascending=False)

    panel = panel.sort_values(["published_online", "DOI", "record_id"]).reset_index(drop=True)
    panel["published_online"] = panel["published_online"].dt.strftime("%Y-%m-%d")
    candidates.to_csv(OUT / "candidate_audit_log.csv", index=False, encoding="utf-8-sig")
    panel.to_csv(OUT / "external_panel_audited.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUT / "metrics_summary.csv", index=False, encoding="utf-8-sig")
    doi_metrics.to_csv(OUT / "doi_level_metrics.csv", index=False, encoding="utf-8-sig")
    loo.to_csv(OUT / "leave_one_doi_out.csv", index=False, encoding="utf-8-sig")

    metadata = {
        "snapshot_cutoff": str(CUTOFF.date()),
        "analysis_lock_date": "2026-06-11",
        "model": "M4 frozen eight-term expression",
        "coefficients": COEFFICIENTS,
        "feature_order": FEATURES,
        "train_n": len(train),
        "snapshot_n": len(snapshot),
        "distance": "Euclidean L2 on eight site fractions",
        "in_domain_threshold": IN_DOMAIN_THRESHOLD,
        "composition_duplicate_threshold": COMPOSITION_DUP_THRESHOLD,
        "value_duplicate_threshold_eV": VALUE_DUP_THRESHOLD,
        "same_source_heldout_rmse_eV": SAME_SOURCE_RMSE,
        "consistency_threshold_eV": CONSISTENCY_THRESHOLD,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPS,
        "confirmatory_n": len(panel),
        "confirmatory_doi_n": panel["DOI"].nunique(),
        "out_of_domain_n": int((~panel["in_domain"]).sum()),
        "warning": "The analysis lock is not a public or blinded preregistration.",
    }
    (OUT / "analysis_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    create_plot(panel)
    write_report(panel, metrics, exclusions)
    write_source_manifest(panel)

    main_result = metrics.loc[metrics["subset"] == "In-domain confirmatory"].iloc[0]
    novel_result = metrics.loc[
        metrics["subset"] == "Composition-novel (d_snapshot >= 0.01)"
    ].iloc[0]
    locked_checks = {
        "external RMSE": (main_result["rmse_eV"], EXPECTED_RMSE),
        "external MAE": (main_result["mae_eV"], EXPECTED_MAE),
        "composition-novel n": (novel_result["n"], EXPECTED_NOVEL_N),
        "composition-novel RMSE": (novel_result["rmse_eV"], EXPECTED_NOVEL_RMSE),
    }
    for label, (observed, expected) in locked_checks.items():
        if not np.isclose(observed, expected, rtol=0.0, atol=1e-12):
            raise ValueError(f"{label} drifted: observed {observed}, expected {expected}")

    print(
        json.dumps(
            {
                "n": int(main_result["n"]),
                "n_doi": int(main_result["n_doi"]),
                "rmse_eV": float(main_result["rmse_eV"]),
                "mae_eV": float(main_result["mae_eV"]),
                "bias_eV": float(main_result["bias_eV"]),
                "cluster_rmse_ci": [
                    float(main_result["cluster_rmse_ci_low_eV"]),
                    float(main_result["cluster_rmse_ci_high_eV"]),
                ],
                "criterion_pass": bool(main_result["criterion_pass"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
