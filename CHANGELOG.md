# Changelog

## 1.1.1 - 2026-06-11

- Removed manuscript and Supporting Information files, document builders,
  document-specific audits, and the retained manuscript source template.
- Removed PDF and DOCX artifacts and disabled PDF generation in retained
  analysis workflows.
- Restored `run_all.py`, `.gitignore`, and `.gitattributes`.
- Moved research-asset scripts directly under `scripts/` and removed
  `scripts/publication/`.
- Removed stale document links, workflow-dispatcher references, checksums, and
  DOCX-only dependencies.
- Retained deterministic model, figure, table, sensitivity, and
  external-validation workflows.

## 1.1.0 - 2026-06-11

- Added the source-audited external validation reported in the revised paper.
- Added 20 measurements from 8 post-snapshot publications, candidate and
  exclusion audit data, DOI-level diagnostics, bootstrap intervals, and SI
  Figure S13.
- Added a deterministic external-validation rerun.
- Updated the authoritative manuscript and Supporting Information.
- Kept publisher source PDFs out of the public package while retaining DOI
  links, source locators, and audited file hashes.

## 1.0.0 - 2026-06-10

- Organized immutable data under stable English paths.
- Added deterministic main-result, figure, table, and checksum entry points.
- Added repository, reproducibility, data-availability, citation, license, manifest, and security documentation.
- Added pinned Python requirements and a Conda environment.
- Locked the supplied final revised manuscript and SI as the repository authority.
- Restored the paper-declared bootstrap method of 1,000 resamples with seed 2026.
- Synchronized the GPLearn narrative with the revised five-refit results.
- Marked GPLearn as an archived-result audit because the current environment does not exactly replay its reported metrics.
- Redirected manuscript builders so they cannot overwrite the authoritative DOCX files.
- Documented retained bootstrap and GPLearn archive discrepancies for audit.
- Removed caches, temporary PID files, and duplicate ZIP archives from the release tree.
