# Missing M4 Diagnostics

Training workbook: `data/train_518.xlsx`
CV/OLS basis: training-set design matrix from `repeated_modeling.py`.

## Models

| Model ID | Term count | Train RMSE | Train R2 | Condition number | Max VIF |
| --- | ---: | ---: | ---: | ---: | ---: |
| m4_pruned | 8 | 0.0562607887 | 0.9668970027 | 22.003972 | 15.796717 |
| m4_full_s3 | 11 | 0.0566160778 | 0.9664775890 | 50.216108 | 16.539725 |
| raw_structure_s7 | 10 | 0.0559118159 | 0.9673063896 | 49.694548 | 16.165181 |

## Raw Variable Ranges

| Variable | Min | Mean | Median | Max | Std |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sn | 0.0000000000 | 0.1407915058 | 0.0000000000 | 1.0000000000 | 0.2905575760 |
| Br | 0.0000000000 | 0.2047200772 | 0.1500000000 | 1.0000000000 | 0.2498207342 |
| Cl | 0.0000000000 | 0.0253166023 | 0.0000000000 | 1.0000000000 | 0.1305291720 |
| Cs | 0.0000000000 | 0.1184988417 | 0.0200000000 | 1.0000000000 | 0.2379602518 |

Generated CSV files include coefficient CI + VIF, term-level SHAP, grouped raw-variable SHAP, per-sample SHAP values, and analytic partial-dependence/sensitivity curves for each model.
