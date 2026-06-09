# Data Availability

The source records were derived from the Perovskite Database Project:

T. J. Jacobsson et al., *Nature Energy* 7, 107-115 (2022),
https://doi.org/10.1038/s41560-021-00941-3.

## Included Data

- `data/dataset_610_snapshot.xlsx`: frozen 610-record snapshot and audit sheets.
- `data/train_518.xlsx`: immutable training split used for fitting and selection.
- `data/test_92.xlsx`: immutable same-source held-out split.
- `group_aware_sensitivity/data/curated_dataset.csv`: strict-QC 507-row training
  table.

The archive begins from the frozen local workbook snapshot dated January 28,
2026. The complete upstream export and transformation history before that
snapshot is unavailable.

The 92-row test set is not an independent external validation panel. No
harmonized external literature-validation panel is included.

Processed tables are provided for reproduction. Reusers should cite the
Perovskite Database Project and comply with its applicable terms. Code is MIT
licensed; repository-authored figures, tables, and result summaries are
licensed under CC BY 4.0 unless an upstream restriction applies.

Public repository:
https://github.com/qinyu319/llm-sr-perovskite-bandgap

The Zenodo DOI should be added after archiving the first GitHub release.
