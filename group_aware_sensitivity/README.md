# Group-aware Split Sensitivity

This project reruns the symbolic OLS workflow under composition-family, halide-regime, and A-site group-aware partitions.

## Non-leakage rules

- The experiment base is the original training workbook only.
- `../data/test_92.xlsx` is excluded from group labels, split generation, screening, CV, pruning, and final model selection.
- For every outer split, screening and five-fold model selection use only the current outer-training rows.
- The current held-out group is evaluated only after the formula structure has been selected and refitted.
- Every split is checked for disjoint train/test group sets.

## Data QC policy

Closure tolerance is `1e-6`:

- `FA + MA + Cs = 1`
- `Pb + Sn = 1`
- `I + Br + Cl = 1`

Rows that fail are reported and excluded without renormalization. No source value is silently changed.

## Reproduce

Run from this folder:

```powershell
python scripts/01_validate_data.py
python scripts/02_make_group_labels.py
python scripts/03_make_and_validate_splits.py
python scripts/03_run_group_aware_workflow.py
python scripts/04_summarize_group_results.py
python scripts/05_plot_group_results.py
python scripts/06_make_excel_report.py
python -m pytest tests
```

Random seed: `2026`.

## Selection rule

Five-fold `GroupKFold` uses the same group definition as the outer split when at least five training groups are available. Otherwise, shuffled five-fold `KFold` is used with seed `2026`.

Candidate structures are hierarchical subsets of the M2/M3 dictionaries, plus the fixed M0-M3 stage models. The best mean CV RMSE is identified first. Models within 5% of that value are treated as accuracy-equivalent; the fewest-term model is selected, with mean CV RMSE as the tie-breaker.

The external test result of the frozen final M4 is included only as a visual random-split reference (`RMSE = 0.0606135 eV`). It never changes any group-aware selection.

## Metric definitions

- `high_Eg_rmse`: held-out rows with actual `Eg >= 2.2 eV`.
- `Cl_rich_rmse`: held-out rows with `Cl > 0`.
- `MA_rich_rmse`: held-out rows with `MA >= 0.5`.
- Formula similarity is Jaccard similarity to frozen M4 terms: `Sn, Br, Cl, Cs, Sn2, Br2, CsSn, CsCl`.

## Main outputs

- `outputs/group_labels/group_labels.csv`
- `outputs/splits/split_manifest.csv`
- `outputs/per_split_results/group_aware_full_workflow_results.csv`
- `outputs/summary_tables/group_aware_term_frequency.csv`
- `outputs/summary_tables/group_aware_summary.csv`
- `outputs/summary_tables/group_aware_selected_formulas.csv`
- `outputs/figures/*.png`
- `group_aware_split_sensitivity_results.xlsx`
