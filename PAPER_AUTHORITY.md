# Evidence Authority and Conflict Policy

## Distribution Boundary

This package does not distribute manuscript, Supporting Information,
response-letter, or submission-file sources. It also excludes scripts and
templates that generate those documents.

When artifacts disagree, use this order:

1. frozen final-model files and checksummed inputs;
2. final tables, figures, and external-validation evidence;
3. deterministic reproduction scripts;
4. archived intermediate and historical outputs.

## Locked Claims

- Final terms: `Sn`, `Br`, `Cl`, `Cs`, `Sn^2`, `Br^2`, `Cs*Sn`, `Cs*Cl`.
- Data sizes: 610 total, 518 training, 92 same-source held-out test.
- Fixed CV: five folds, shuffled, seed 42, RMSE 0.057532 eV.
- Repeated CV: 100 five-fold partitions, seeds 0-99, RMSE 0.058056 eV.
- Test RMSE and R2: 0.060613 eV and 0.976545.
- Bootstrap: 1,000 training-row resamples, seed 2026.
- Group-aware strict-QC training size: 507.
- External validation: 20 measurements from 8 post-snapshot publications.
- External RMSE and MAE: 0.0417 eV and 0.0327 eV.
- Composition-novel external subset: 16 measurements, RMSE 0.0453 eV.
- GPLearn report: CV RMSE 0.145284 eV and five-refit test RMSE
  0.177322 +/- 0.022785 eV.

## Retained Discrepancies

**Bootstrap:** the frozen release protocol declares 1,000 resamples, while
`final_m4_diagnostics/bootstrap_coefficient_samples.csv` contains 5,000 fits
per diagnostic model and matches the archived summary table. Canonical reruns
follow the 1,000-resample method; the larger archive remains audit
evidence.

**GPLearn:** `scripts/reproduce_gplearn.py` and the archived CV output use the
parsimony grid `0.0005, 0.001, 0.003, 0.01`. Pinned package versions do not
guarantee bit-for-bit replay, so the frozen values remain archived results
rather than an exact deterministic replay claim.

## Public Path Mapping

Historical manuscript labels were normalized for portability:

| Historical label | Public path |
| --- | --- |
| final M4 folder | `final_m4/` |
| VIF/CI/bootstrap folder | `final_m4_diagnostics/` |
| group-aware split folder | `group_aware_sensitivity/` |
| repeated LLM folder | `llm_repeated/` |

The retained scripts rebuild research figures and data assets only. They do
not generate manuscript, SI, response-letter, submission, DOCX, or PDF files.
