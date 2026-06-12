# Core File Manifest

## Immutable Inputs

| Path | Purpose |
| --- | --- |
| `data/dataset_610_snapshot.xlsx` | Frozen 610-record snapshot |
| `data/train_518.xlsx` | Immutable 518-row training split |
| `data/test_92.xlsx` | Immutable 92-row same-source test split |
| `group_aware_sensitivity/data/curated_dataset.csv` | Strict-QC 507-row table |
| `external_validation/external_validation_candidates.csv` | Audited external-panel input and exclusion log |

## Final Model

| Path | Purpose |
| --- | --- |
| `final_m4/final_M4_formula.txt` | Frozen equation and headline metrics |
| `final_m4/final_M4_model_comparison.csv` | Final and alternative model audit |
| `final_m4_diagnostics/final_M4_coefficients_CI_bootstrap.csv` | OLS, CI, bootstrap, and VIF |
| `final_m4_diagnostics/bootstrap_coefficient_samples.csv` | Retained 5,000-fit audit archive |
| `final_m4_diagnostics/Cl2_retention_diagnostic.csv` | Nested `Cl^2` evidence |

## Reproduction

| Path | Purpose |
| --- | --- |
| `run_all.py` | Deterministic workflow dispatcher |
| `scripts/reproduce_main_results.py` | Final M4 deterministic rerun |
| `scripts/reproduce_figures.py` | Figures and source-data export |
| `scripts/reproduce_tables.py` | Main and supplementary tables |
| `scripts/verify_checksums.py` | SHA-256 verification |
| `scripts/security_scan.py` | Secret, private-path, and filename scan |
| `external_validation/run_external_validation.py` | External-panel metrics, bootstrap, and figure rerun |

## Audit Evidence

| Path | Purpose |
| --- | --- |
| `llm_repeated/prompts/` | Frozen M0-M4 prompt templates |
| `llm_repeated/repeated_runs_30/` | Thirty archived full workflows |
| `llm_repeated/external_api_runs/` | Sanitized provider request/response records |
| `baselines/` | Exhaustive, regularized, GP, GPLearn, and PySR controls |
| `blackbox_shap/` | Tree benchmarks and SHAP artifacts |
| `group_aware_sensitivity/` | Group-aware scripts, tests, splits, and outputs |
| `external_validation/` | Source-audited post-snapshot panel and transfer analysis |
| `archive/` | Historical, non-authoritative material |

## Figures and Tables

| Path | Purpose |
| --- | --- |
| `figures/main/` | Main-text figures |
| `figures/supplementary/` | Supplementary figures |
| `figures/supplementary/figure_s6_symbolic_baselines.png` | SI Figure S6: symbolic baselines |
| `figures/supplementary/figure_s7_llm_stochasticity.png` | SI Figure S7: LLM stochasticity |
| `figures/supplementary/figure_s13_external_validation.png` | SI Figure S13: copy of the external-validation figure |
| `figures/supplementary/figure_s14_design_maps.png` | SI Figure S14: design maps |
| `figures/source_data/` | Figure source CSV files |
| `tables/main/` | Main-text source tables |
| `tables/supplementary/` | Supplementary source tables |
| `external_validation/Fig_external_validation.png` | External-validation figure |
| `external_validation/external_panel_audited.csv` | SI Table S25 source data |
| `external_validation/metrics_summary.csv` | SI Table S26 source data |
| `external_validation/leave_one_doi_out.csv` | SI Table S27 source data |

Manuscripts, Supporting Information documents, response letters, submission
files, PDF/DOCX files, document-generation scripts, and document templates are
intentionally excluded.
