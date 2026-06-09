# Core File Manifest

## Immutable Inputs

| Path | Purpose |
| --- | --- |
| `data/dataset_610_snapshot.xlsx` | Frozen 610-record snapshot |
| `data/train_518.xlsx` | Immutable 518-row training split |
| `data/test_92.xlsx` | Immutable 92-row same-source test split |
| `group_aware_sensitivity/data/curated_dataset.csv` | Strict-QC 507-row table |

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
| `run_all.py` | Workflow dispatcher |
| `scripts/reproduce_main_results.py` | Final M4 deterministic rerun |
| `scripts/reproduce_figures.py` | Figures and source-data export |
| `scripts/reproduce_tables.py` | Main and supplementary tables |
| `scripts/verify_checksums.py` | SHA-256 verification |
| `scripts/security_scan.py` | Secret, private-path, and filename scan |

## Audit Evidence

| Path | Purpose |
| --- | --- |
| `llm_repeated/prompts/` | Frozen M0-M4 prompt templates |
| `llm_repeated/repeated_runs_30/` | Thirty archived full workflows |
| `llm_repeated/external_api_runs/` | Sanitized provider request/response records |
| `baselines/` | Exhaustive, regularized, GP, GPLearn, and PySR controls |
| `blackbox_shap/` | Tree benchmarks and SHAP artifacts |
| `group_aware_sensitivity/` | Group-aware scripts, tests, splits, and outputs |
| `archive/` | Historical, non-authoritative material |

## Publication Artifacts

| Path | Purpose |
| --- | --- |
| `paper/main_REVISED.docx` | Authoritative revised manuscript |
| `paper/si_REVISED.docx` | Authoritative revised Supporting Information |
| `figures/main/` | Main-text figures |
| `figures/supplementary/` | Supplementary figures |
| `figures/source_data/` | Figure source CSV files |
| `tables/main/` | Main-text source tables |
| `tables/supplementary/` | Supplementary source tables |
