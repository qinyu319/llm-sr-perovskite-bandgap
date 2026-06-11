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
- `external_validation/external_panel_audited.csv`: 20 source-audited
  post-snapshot literature measurements with frozen-M4 predictions.
- `external_validation/candidate_audit_log.csv`: included and excluded external
  candidates with source locators and reasons.
- `external_validation/source_evidence_manifest.csv`: DOI links, source
  locators, and hashes of locally audited evidence files.

The archive begins from the frozen local workbook snapshot dated January 28,
2026. The complete upstream export and transformation history before that
snapshot is unavailable.

The 92-row test set is not an independent external validation panel. Independent
transfer is evaluated separately using 20 measurements from 8 publications
released after the snapshot cutoff. All accepted records are within the
declared composition-distance domain.

Publisher PDFs and extracted page images used during the source audit are not
redistributed. The public package retains DOI links, source locators, extracted
numerical records, and hashes of the locally audited evidence files.

Processed tables are provided for reproduction. Reusers should cite the
Perovskite Database Project and comply with its applicable terms. Code is MIT
licensed; repository-authored figures, tables, and result summaries are
licensed under CC BY 4.0 unless an upstream restriction applies.

Public repository:
https://github.com/qinyu319/llm-sr-perovskite-bandgap

The Zenodo DOI should be added after archiving the first GitHub release.
