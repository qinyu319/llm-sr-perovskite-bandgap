# Audited external validation of frozen M4

## Executive result

The reconstructed panel contains **20 measurements from 8 post-snapshot publications**. All eligible records are inside the declared eight-fraction distance domain (`d_min <= 0.25`), so the confirmatory result is an in-domain validation only.

The frozen M4 model achieved **RMSE 0.0417 eV**, **MAE 0.0327 eV**, and bias +0.0215 eV. The row-bootstrap 95% CI for RMSE is [0.0307, 0.0507] eV; the DOI-cluster bootstrap CI is [0.0116, 0.0559] eV. The result **passed** the locked consistency criterion of RMSE <= 0.1212 eV (2 x the same-source held-out RMSE of 0.0606 eV). The point estimate is 0.69 x the same-source held-out RMSE.

The composition-novel sensitivity subset (`d_snapshot >= 0.01`) contains 16 points and gives RMSE 0.0453 eV. The Sn-containing subset contains 3 points and gives RMSE 0.0262 eV.

## What changed from the ZIP draft

The 21-point draft panel was not used for the final metrics because most records lacked DOI, primary-source locators, measurement method, and verifiable independence. It is omitted from the public package; its exclusion decisions are represented in the candidate audit log.

The replacement panel uses publisher supporting information or the primary paper for every included record. Publication dates are after the archived PDP snapshot date of January 28, 2026. Exact DOI matching could not be run against the local snapshot because the supplied export has no DOI field; post-cutoff publication is therefore the auditable construction rule.

## Deduplication audit

- DOI level: all included papers were published online after January 28, 2026.
- Composition level: 4 records have `d_snapshot < 0.01` and are marked as independent same-composition retests.
- Value level: 0 records meet both same-composition and `|delta Eg| < 0.01 eV`; none were silently removed.
- The main metric retains independent retests as specified, while the composition-novel metric reports the stricter sensitivity analysis.

## Dependence and measurement-quality checks

Multiple points come from two composition-scan papers. The DOI-cluster bootstrap and publication-balanced metrics prevent those scans from being interpreted as 20 fully independent publications. The nominal relative RMSE standard error is approximately `1/sqrt(2n) = 15.8%` at the record level and `1/sqrt(2N_DOI) = 25.0%` at the publication level.

The largest coherent offset is the eight-point low-Cl co-evaporated scan from Nature Materials, for which M4 overpredicts by roughly 0.06 eV. This is retained and reported as a likely process/method shift rather than treated as an outlier. A sensitivity analysis excluding the one approximate Sn-Pb absorption-edge digitization is included in `metrics_summary.csv`.

## Applicability limitation

No post-cutoff high-Cl or `d_min > 0.25` thin-film record with an exact allowed composition and recoverable numerical experimental bandgap passed all inclusion criteria. Two high-Cl candidates in the Nature Materials SI lacked numerical bandgaps and were excluded before scoring. Therefore this reconstruction does **not** claim an external out-of-domain performance result. The applicability-domain statement should remain explicit.

## Reproducibility

- Frozen model: eight-term M4 with no refitting.
- Distance: Euclidean L2 distance on `[FA, MA, Cs, Pb, Sn, I, Br, Cl]`.
- Main endpoint: in-domain RMSE and MAE.
- Consistency rule: RMSE <= 0.1212 eV.
- Bootstrap: 20,000 replicates; seed 20260611.
- All passing records are reported.

The rule was supplied before this audited reconstruction and locked in the analysis script before the final metrics run. It is a dated analysis lock, not a public preregistration, and should not be described as blinded.

## Files

- `external_panel_audited.csv`: final point-level results.
- `candidate_audit_log.csv`: included and excluded candidates.
- `metrics_summary.csv`: primary and sensitivity metrics.
- `doi_level_metrics.csv`: per-publication performance.
- `leave_one_doi_out.csv`: source-dependence analysis.
- `Fig_external_validation.png`: external-validation figure.
- `analysis_metadata.json`: coefficients, thresholds, and run settings.
- `source_evidence_manifest.csv`: DOI links, source locators, and hashes of the locally audited source files. The source PDFs themselves are not redistributed.

## Primary-source links

- [10.1038/s41563-026-02494-w](https://www.nature.com/articles/s41563-026-02494-w) - Crystal-facet-directed all-vacuum-deposited perovskite solar cells
- [10.1021/acsenergylett.6c00156](https://pubs.acs.org/doi/10.1021/acsenergylett.6c00156) - Bandgap Tunable Two-Step Vapor-Deposited Perovskite Absorbers for Perovskite-Based Tandem Solar Cells
- [10.1021/acsenergylett.6c00210](https://pubs.acs.org/doi/10.1021/acsenergylett.6c00210) - Codeposition Strategy Enables Stable Built-In Electric Field in Sn-Pb Perovskite Solar Cells
- [10.1021/acsenergylett.6c00617](https://pubs.acs.org/doi/10.1021/acsenergylett.6c00617) - Suppressing Sn-Rich Phase Precipitation Enables Controlled Crystallization in Sn-Pb Perovskite Solar Cells
- [10.1021/acsenergylett.6c01038](https://pubs.acs.org/doi/10.1021/acsenergylett.6c01038) - Photochemical Iodine Immobilization for Stabilizing Wide-Bandgap Perovskite Solar Cells
- [10.1021/acsenergylett.6c00227](https://pubs.acs.org/doi/10.1021/acsenergylett.6c00227) - Solution-Processed SnOx Nanoparticles for Efficient Perovskite Solar Cells and All-Perovskite Tandems
- [10.1021/acsaelm.6c00264](https://pubs.acs.org/doi/10.1021/acsaelm.6c00264) - CsBr-Buffered Self-Assembled Monolayers for Efficient and Stable Inverted Wide-Bandgap Cs0.7FA0.3PbI2Br Perovskite Solar Cells
- [10.1021/acsenergylett.6c00771](https://pubs.acs.org/doi/10.1021/acsenergylett.6c00771) - Redox-Active Flavonoid Interlayers Enable Strain-Relieved and Efficient Sn-Pb Perovskite Solar Cells

## Exclusion count

10 candidate rows or candidate groups were excluded with reasons preserved in `candidate_audit_log.csv`.
