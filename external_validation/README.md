# Source-Audited External Validation

This directory contains the independent post-snapshot literature validation
reported in the revised manuscript and Supporting Information.

The frozen eight-term M4 equation was applied without refitting to 20
measurements from 8 publications released after the January 28, 2026 dataset
snapshot. All accepted records are within the declared composition-distance
domain.

## Paper-Authoritative Results

| Result | Value |
| --- | ---: |
| External measurements | 20 |
| Publications | 8 |
| RMSE | 0.0417 eV |
| MAE | 0.0327 eV |
| Mean signed error | +0.0215 eV |
| Record-bootstrap RMSE 95% CI | 0.0307-0.0507 eV |
| DOI-cluster-bootstrap RMSE 95% CI | 0.0116-0.0559 eV |
| Composition-novel subset | 16 records |
| Composition-novel RMSE | 0.0453 eV |

These results support within-domain post-snapshot transfer only. They do not
establish accuracy for high-Cl, strongly Cs-rich, or distance-defined
out-of-domain compositions.

## Reproduce

From the repository root:

```bash
python external_validation/run_external_validation.py
```

Outputs are written to `reproduced/external_validation/`. The default run uses
20,000 bootstrap replicates with seed 20260611.

## File Mapping

| Path | Paper role |
| --- | --- |
| `external_panel_audited.csv` | Table S25 source data |
| `metrics_summary.csv` | Table S26 source data |
| `leave_one_doi_out.csv` | Table S27 source data |
| `Fig_external_validation.pdf` | Figure S13 |
| `candidate_audit_log.csv` | Inclusion and exclusion audit |
| `source_evidence_manifest.csv` | DOI links, locators, and audited file hashes |
| `external_validation_candidates.csv` | Script input |

Publisher PDFs and extracted page images used during source auditing are not
redistributed. Their filenames, hashes, source locators, and public DOI links
are retained in `source_evidence_manifest.csv`.
