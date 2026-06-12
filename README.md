# Physics-Constrained LLM Symbolic Regression for Perovskite Band Gaps

Research data and reproducibility package for:

> **Reproducible Physics-Constrained LLM-Assisted Symbolic Regression for
> Interpretable Band-Gap Modeling in Hybrid Perovskites**

Repository: https://github.com/qinyu319/llm-sr-perovskite-bandgap

Manuscript, Supporting Information, response-letter, and submission-file
sources are intentionally excluded. Frozen results and conflict-resolution
rules are documented in [PAPER_AUTHORITY.md](PAPER_AUTHORITY.md).

## Final Model

The frozen M4 model has eight non-constant terms:

```text
Eg = 1.55527 - 1.10253*Sn + 0.34320*Br + 1.61932*Cl
     + 0.12268*Cs + 0.91702*Sn^2 + 0.36607*Br^2
     - 0.22716*Cs*Sn - 0.32528*Cs*Cl
```

| Metric | Paper value |
| --- | ---: |
| Fixed five-fold CV RMSE | 0.057532 eV |
| Repeated five-fold CV RMSE | 0.058056 eV |
| Training RMSE | 0.054108 eV |
| Same-source test RMSE | 0.060613 eV |
| Test R2 | 0.976545 |
| External-panel RMSE | 0.0417 eV |
| External-panel MAE | 0.0327 eV |
| Maximum VIF | 15.7863 |
| Minimum bootstrap sign stability | 0.999 |

The paper-authoritative bootstrap protocol is 1,000 training-row resamples with
seed 2026.

## Quick Start

Python 3.11 is recommended.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run_all.py --mode verify
python run_all.py --mode main
```

Or create the pinned Conda environment:

```bash
conda env create -f environment.yml
conda activate llm-sr-perovskite
```

Rebuild figures, tables, and external-validation results:

```bash
python run_all.py --mode figures
python run_all.py --mode tables
python run_all.py --mode external-validation
```

Model and external-validation reruns are written under `reproduced/`.
Archived evidence is not overwritten.

## Reproduction Levels

1. **Release audit:** verify checksums, security constraints, tables, figures,
   and frozen evidence without fitting or API access.
2. **Final M4 rerun:** recompute coefficients, CV, test metrics, VIF, confidence
   intervals, bootstrap stability, and the `Cl^2` diagnostic.
3. **Figures, tables, controls, and sensitivity:** rebuild publication assets,
   deterministic controls, the 507-row group-aware analysis, and the
   source-audited external validation.
4. **LLM audit:** inspect archived prompts, responses, parsed structures,
   manifests, and repeated-run summaries. API calls are not part of the default
   workflow, and exact text regeneration is not claimed.

See [REPRODUCIBILITY.md](REPRODUCIBILITY.md) for commands and expected values.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `data/` | Frozen 610-row snapshot and immutable 518/92 split |
| `prompts/` | Human-readable prompt and selection notes |
| `llm_repeated/` | Archived prompts and repeated LLM workflows |
| `final_m4/` | Frozen final formula and model comparison |
| `final_m4_diagnostics/` | Coefficients, CI, VIF, and bootstrap evidence |
| `baselines/` | Exhaustive, regularized, GP, GPLearn, and PySR controls |
| `blackbox_shap/` | GBRT, RF, XGBoost, and SHAP outputs |
| `group_aware_sensitivity/` | Strict-QC group-aware workflow and outputs |
| `external_validation/` | Post-snapshot literature panel, audit, metrics, and figure |
| `figures/`, `tables/` | Publication assets and source data |
| `scripts/` | Deterministic reproduction and research-asset builders |
| `archive/` | Historical material retained only for audit |

All tracked path names are ASCII and contain no spaces.

Publication-document builders, manuscript templates, DOCX files, and PDF files
are not distributed in this package.

## Scope and Limitations

The 92-row test split is held out but comes from the same curated source. A
separate source-audited panel of 20 measurements from 8 post-snapshot
publications evaluates independent within-domain transfer without refitting.
No eligible high-Cl or distance-defined out-of-domain record passed the source
audit, so the model remains an interpolation-oriented analytical surrogate
within the represented composition domain.

LLM generation is archived rather than re-called. PySR reruns require Julia.
Exact GPLearn replay remains unresolved and is explicitly separated from the
paper's archived reported values.

## Data, Citation, and License

See [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md), [CITATION.cff](CITATION.cff),
and [MANIFEST.md](MANIFEST.md). Code is MIT licensed. Repository-authored
figures, tables, and result summaries are covered by [LICENSE-DATA](LICENSE-DATA).

For questions about the release, open a GitHub issue.
