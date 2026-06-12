# Reproducibility Guide

The package distributes research data, results, and deterministic analysis
code. Publication documents and their generation sources are excluded. Known
archive conflicts are documented in
[PAPER_AUTHORITY.md](PAPER_AUTHORITY.md).

## 1. Verify the Release

```bash
python run_all.py --mode verify
```

These commands verify immutable inputs and scan the retained release files.

## 2. Reproduce Final M4

```bash
python run_all.py --mode main
```

Expected values, subject only to floating-point rounding:

```text
fixed_cv_rmse          0.0575317728
repeated_cv_rmse       0.0580564366
train_rmse             0.0541077118
test_rmse              0.0606134718
test_r2                0.9765451159
max_vif                15.7863106232
bootstrap_samples      1000
bootstrap_seed         2026
```

For CI or a quick smoke test:

```bash
python scripts/reproduce_main_results.py --bootstrap-samples 100
```

New files are written to `reproduced/main/`.

## 3. Rebuild Figures and Tables

```bash
python scripts/reproduce_figures.py
python scripts/reproduce_tables.py
```

Main figures are written to `figures/main/`, supplementary figures to
`figures/supplementary/`, figure source data to `figures/source_data/`, and CSV
tables to `tables/`.

Equivalent dispatcher commands are `python run_all.py --mode figures` and
`python run_all.py --mode tables`. No manuscript, Supporting Information,
DOCX, or PDF builder is included.

## 4. Group-Aware Sensitivity

Strict closure QC removes 11 invalid training rows without renormalization,
leaving 507 rows.

```bash
python run_all.py --mode group-aware
```

The 92-row same-source test set remains isolated from group-aware model
selection and is used only as a frozen reference.

## 5. External Validation

The source-audited post-snapshot panel is reproduced without refitting:

```bash
python run_all.py --mode external-validation
```

Expected frozen release values:

```text
external_n              20
publication_n            8
external_rmse_eV         0.0416709074
external_mae_eV          0.0326785198
composition_novel_n     16
composition_novel_rmse   0.0452602333
```

Outputs are written to `reproduced/external_validation/`. The default analysis
uses 20,000 bootstrap replicates with seed 20260611. Source PDFs are not
redistributed; provenance and audited file hashes are retained in
`external_validation/source_evidence_manifest.csv`.

## 6. Optional Controls

Archived deterministic and fitted controls are under `baselines/` and
`blackbox_shap/`. The GPLearn rerun is optional:

```bash
python scripts/reproduce_gplearn.py
```

It follows the SI-declared grid and warns when results differ from the archived
paper metrics in `baselines/gplearn/`. Exact GPLearn numerical replay is not
claimed.

PySR outputs are archived in `baselines/pysr/`; a fresh PySR run additionally
requires Julia and is not part of CI.

## 7. LLM Audit Boundary

No API key is needed for deterministic reproduction. `llm_repeated/` retains:

- frozen M0-M4 prompts;
- provider request and response payloads without authorization headers;
- parsed structures and selected models;
- 30 complete workflow summaries and direct M4 candidate archives.

Exact LLM text regeneration is stochastic and is not claimed.

## 8. Data Boundary

- The original random split-generation seed is unavailable.
- Reproducibility relies on checksummed `data/train_518.xlsx` and
  `data/test_92.xlsx`.
- Candidate selection uses training CV and diagnostics.
- The test set is loaded only for post-freeze reporting.
- The independent external panel is post-snapshot, source-audited, and used
  only after model freezing.
- All accepted external records are within the declared applicability domain;
  no unrestricted extrapolation claim is made.

## 9. Bootstrap Audit Note

The canonical rerun uses 1,000 resamples with seed 2026. The retained
raw archive contains 5,000 fits per diagnostic model and matches the published
summary. Both are preserved, but they must not be conflated.
