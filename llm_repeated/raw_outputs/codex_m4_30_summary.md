# Summary of 30 Independent M4 Codex Runs

Source: `raw_outputs/codex_runs/run_01.txt` through `run_30.txt`; normalized rows are stored in `raw_outputs/candidates_30_M4_codex.jsonl`.

## Overview

- Independent runs: 30
- Output format: one expression line per run
- Runs satisfying M4 non-constant term-count constraint (8-11): 30/30
- Unique raw outputs: 13
- Unique normalized structures: 7
- Method note: runs 01-06 used isolated Codex subagent threads; runs 07-30 used independent ephemeral `codex exec` sessions. Codex CLI did not expose temperature or seed controls for this workflow.

## Structure Frequencies

| Structure ID | Frequency | Percentage | Run IDs | Normalized structure |
| --- | ---: | ---: | --- | --- |
| S1 | 8 | 26.67% | 09, 10, 12, 13, 16, 19, 21, 23 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| S2 | 8 | 26.67% | 04, 11, 20, 25, 26, 27, 29, 30 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| S3 | 7 | 23.33% | 06, 08, 14, 17, 18, 24, 28 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| S4 | 2 | 6.67% | 03, 05 | Sn + Br + Cl + Cs + Sn^2 + Br*Cl + Sn*Br + Sn*Cl + Cs*Sn + Cs*Br |
| S5 | 2 | 6.67% | 02, 15 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| S6 | 2 | 6.67% | 07, 22 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| S7 | 1 | 3.33% | 01 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Sn |

## Non-Constant Term Count Distribution

| Term count | Runs |
| ---: | ---: |
| 10 | 13 |
| 11 | 17 |

## Term Frequencies

| Term | Frequency | Percentage |
| --- | ---: | ---: |
| Sn | 30 | 100.00% |
| Br | 30 | 100.00% |
| Cl | 30 | 100.00% |
| Cs | 30 | 100.00% |
| Sn^2 | 30 | 100.00% |
| Br^2 | 28 | 93.33% |
| Cl^2 | 24 | 80.00% |
| Cs^2 | 12 | 40.00% |
| Sn*Br | 30 | 100.00% |
| Sn*Cl | 30 | 100.00% |
| Br*Cl | 2 | 6.67% |
| Cs*Sn | 3 | 10.00% |
| Cs*Br | 29 | 96.67% |
| Cs*Cl | 9 | 30.00% |

## Per-Run Structure Mapping

| Run | Structure ID | Term count | Normalized structure |
| ---: | --- | ---: | --- |
| 01 | S7 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Sn |
| 02 | S5 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 03 | S4 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br*Cl + Sn*Br + Sn*Cl + Cs*Sn + Cs*Br |
| 04 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 05 | S4 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br*Cl + Sn*Br + Sn*Cl + Cs*Sn + Cs*Br |
| 06 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 07 | S6 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 08 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 09 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 10 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 11 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 12 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 13 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 14 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 15 | S5 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 16 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 17 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 18 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 19 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 20 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 21 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 22 | S6 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 23 | S1 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Cs^2 + Sn*Br + Sn*Cl + Cs*Br |
| 24 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 25 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 26 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 27 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 28 | S3 | 11 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br + Cs*Cl |
| 29 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
| 30 | S2 | 10 | Sn + Br + Cl + Cs + Sn^2 + Br^2 + Cl^2 + Sn*Br + Sn*Cl + Cs*Br |
