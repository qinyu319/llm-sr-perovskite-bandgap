# Paper Authority and Conflict Policy

## Canonical Documents

| Document | SHA-256 |
| --- | --- |
| `paper/main_REVISED.docx` | `3a34c77b5adb24e06ff817af4afbb1da61a8a86ff4944c2ce1d712f9f13b2788` |
| `paper/si_REVISED.docx` | `e7a91927251d59cfadaa68a4a8c5c37167234c65f842fb18714c4548ace00460` |

When artifacts disagree, use this order:

1. revised main manuscript;
2. revised Supporting Information;
3. final publication tables and frozen model evidence;
4. deterministic reproduction scripts;
5. archived intermediate and historical outputs.

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

**Bootstrap:** the paper declares 1,000 resamples, while
`final_m4_diagnostics/bootstrap_coefficient_samples.csv` contains 5,000 fits
per diagnostic model and matches the archived summary table. Canonical reruns
follow the paper's 1,000-resample method; the larger archive remains audit
evidence.

**GPLearn:** SI Table S14 prints a parsimony grid of `1e-6, 1e-5, 1e-4`, while
the archived CV output associated with the reported values uses
`0.0005, 0.001, 0.003, 0.01`. Current pinned packages do not exactly reproduce
the archived metrics. The paper values are therefore treated as archived
publication results, not an exact deterministic replay claim.

## Public Path Mapping

Historical manuscript labels were normalized for portability:

| Historical label | Public path |
| --- | --- |
| final M4 folder | `final_m4/` |
| VIF/CI/bootstrap folder | `final_m4_diagnostics/` |
| group-aware split folder | `group_aware_sensitivity/` |
| repeated LLM folder | `llm_repeated/` |
| paper/SI build folders | `scripts/publication/` and `archive/publication_build/` |

Publication builders write review copies under `reproduced/` and never
overwrite the canonical DOCX files.
