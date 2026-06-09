# LLM符号表达式重复运行项目说明

## 1. 项目目的

本项目用于检验LLM提出的钙钛矿带隙解析表达式是否具有稳定性，而不是某一次随机生成的偶然结果。

研究目标是使用组成分数变量：

- `Sn`：B位Sn比例
- `Br`：X位Br比例
- `Cl`：X位Cl比例
- `Cs`：A位Cs比例

构建光学带隙 `Eg` 的低阶、可解释多项式模型。LLM只负责提出表达式结构，所有数值系数均由训练集上的普通最小二乘法（OLS）确定。

## 2. 数据文件

| 文件 | 内容 |
| --- | --- |
| `../data/train_518.xlsx` | 518条训练数据，用于OLS拟合和五折交叉验证 |
| `../data/test_92.xlsx` | 92条测试数据，仅在最终M4结构确定后使用 |

训练集和测试集在全部重复运行中保持固定，不重新划分。

目标列为 `Bg/bg`。建模只使用 `Sn`、`Br`、`Cl`、`Cs`，不重复引入与其存在组成闭合关系的 `Pb`、`I`、`FA`、`MA`。

## 3. 提示词迭代流程

冻结的提示词位于 `prompts/`：

| 阶段 | 作用 |
| --- | --- |
| `M0.txt` | 只允许Sn、Br、Cl线性主效应 |
| `M1.txt` | 加入Sn、Br、Cl平方项，不允许交互项 |
| `M2.txt` | 加入Sn/Br/Cl之间的二阶交互项 |
| `M3.txt` | 引入Cs及Cs相关交互项 |
| `M4.txt` | 在8–11个非恒定项约束下生成最终简化结构 |

每一次完整run均使用一个全新的Codex会话，并在同一会话中依次执行：

```text
M0 -> 训练集CV筛选
   -> M1 -> 训练集CV筛选
   -> M2 -> 训练集CV筛选
   -> M3 -> 训练集CV筛选
   -> M4 -> 训练集CV筛选
   -> 测试集事后评估
```

下一阶段会收到同一run上一阶段选中的结构和训练集CV指标，但不会收到其他run的结果。

## 4. 候选生成与合法性检查

每个阶段由Codex生成16个候选，因此：

```text
30 runs × 5 stages × 16 candidates = 2400 candidates
```

程序对每个候选检查：

1. 是否包含恒定项；
2. 是否只使用当前阶段允许的变量和项；
3. 是否仅包含线性项、平方项或二元交互项；
4. 是否包含高阶幂、除法、log、exp等禁止运算；
5. 是否超过阶段项数或交互项数量限制；
6. 是否包含重复项；
7. M3是否包含Cs主效应；
8. M4是否包含8–11个非恒定项。

非法候选不会被修改或删除，其原始内容和失败原因都会保存。

## 5. OLS和五折交叉验证

所有合法候选均使用训练集进行OLS拟合。五折划分固定使用：

```text
CV seed = 20260607
KFold(n_splits=5, shuffle=True, random_state=20260607)
```

每个候选记录：

- 五折CV RMSE均值和标准差；
- 五折out-of-fold R²；
- 训练集RMSE、MAE和R²；
- OLS系数及95%置信区间；
- 设计矩阵condition number。

固定折叠记录保存在：

```text
repeated_runs_30/fold_manifest.csv
```

## 6. 阶段内筛选规则

每个阶段按以下规则选择结构：

1. 找到训练集五折CV RMSE最低值；
2. 将RMSE不高于最优值`1.05倍`的候选视为精度等价；
3. 在精度等价候选中选择非恒定项最少的结构；
4. 如果项数相同，选择CV RMSE更低者；
5. 如果仍相同，按候选原始编号决定，避免人工选择。

测试集不参与候选筛选、剪枝或模型选择。

## 7. 30次实验结果

30次运行使用30个不同的Codex thread ID，全部成功完成。

最终结构在30次运行中完全一致：

```text
Eg = a0 + a1*Sn + a2*Br + a3*Cl + a4*Cs
   + a5*Sn^2 + a6*Br^2 + a7*Cs*Sn + a8*Cs*Br
```

训练集OLS拟合结果为：

```text
Eg = 1.55271644
   - 1.10243968*Sn
   + 0.36371509*Br
   + 1.52306437*Cl
   + 0.14762472*Cs
   + 0.91790459*Sn^2
   + 0.36879104*Br^2
   - 0.27025553*Cs*Sn
   - 0.13556005*Cs*Br
```

性能结果：

| 指标 | 结果 |
| --- | ---: |
| 五折CV RMSE | 0.05812724 eV |
| 测试集RMSE | 0.06175816 eV |
| 测试集MAE | 0.04660800 eV |
| 测试集R² | 0.97565086 |
| 最终结构数量 | 1 |
| 平均两两Jaccard | 1.0 |

最终8个非恒定项在30次运行中的出现频率均为100%。

## 8. 项目文件结构

```text
llm_repeated/
├── README.md
├── 修改目的.txt
├── 提示语.txt
├── 标准.txt
├── ../data/train_518.xlsx
├── ../data/test_92.xlsx
├── prompts/
│   ├── M0.txt
│   ├── M1.txt
│   ├── M2.txt
│   ├── M3.txt
│   └── M4.txt
├── candidate_batch.schema.json
├── repeated_modeling.py
├── run_full_repeated_experiment.py
└── repeated_runs_30/
    ├── experiment_manifest.json
    ├── fold_manifest.csv
    ├── failures.json
    ├── run_001/ ... run_030/
    └── summary/
```

每个 `run_XXX/` 包含：

```text
raw_outputs/        Codex每阶段原始候选
prompts/            实际发送给Codex的完整提示词
parsed_structures/  候选解析和合法性结果
cv_results/         每个候选的OLS和CV指标
selected_models/    M0-M4阶段选中结构及最终模型
logs/               Codex标准输出和错误日志
session.json        thread ID、阶段和调用记录
```

汇总文件位于 `repeated_runs_30/summary/`：

| 文件 | 内容 |
| --- | --- |
| `experiment_report.md` | 30次实验的中文报告 |
| `experiment_summary.json` | 实验配置和总体统计 |
| `repeated_run_metrics.csv` | 每次run的CV和测试指标 |
| `stage_selections.csv` | 150个阶段的选中结构 |
| `term_frequency.csv` | 最终项出现频率 |
| `jaccard_similarity.csv` | 30个模型两两Jaccard相似度 |
| `coefficient_sign_stability.csv` | 系数符号稳定性 |
| `final_models.jsonl` | 30个最终模型的完整JSON记录 |

## 9. 重新运行

完整重新运行30次：

```powershell
python .\run_full_repeated_experiment.py `
  --runs 30 `
  --parallelism 6 `
  --output-dir repeated_runs_30_new
```

重新运行时建议使用新的输出目录，以免覆盖现有实验记录。

脚本支持从已有结果继续：如果某个run已经存在
`selected_models/final.json`，在未指定`--overwrite`时会直接读取该结果。

## 10. 复现性边界

本项目可以固定并复现：

- 训练集和测试集；
- M0–M4提示词；
- 每阶段候选数量；
- 五折CV划分；
- OLS拟合方法；
- 合法性检查；
- 阶段筛选规则；
- 输出文件组织和统计方法。

Codex CLI目前不开放`temperature`和`seed`参数，因此再次运行时不能保证逐字生成相同的2400条原始候选。可以复现实验方法和后处理过程，但生成结果属于独立随机采样。

本次30次运行最终结构完全一致，说明该结构在当前模型、提示词、数据和选择规则下具有很强的经验稳定性，但不应表述为seed控制下的数学确定性。

## 11. 真实跨LLM与采样温度实验

`qianwen/` 和 `deepseek/` 中原有的模拟或匿名候选文件不能作为论文中的真实跨LLM证据。真实API实验统一使用：

```text
run_external_api_experiment.py
```

脚本对Qwen或DeepSeek执行完整的`M0 -> M4`流程，并保存每次API请求参数、原始响应、response ID、返回模型、system fingerprint、token usage、候选合法性、CV筛选及最终测试指标。API Key只从环境变量读取，不会写入实验目录。

建议固定`top_p=1.0`，只改变temperature，以避免同时改变两个采样参数：

```powershell
$env:DASHSCOPE_API_KEY = "你的Qwen API Key"
python .\run_external_api_experiment.py `
  --provider qwen `
  --temperatures 0.2 0.7 1.0 `
  --runs-per-temperature 10 `
  --qwen-seed-base 2026060701 `
  --output-dir .\external_api_runs\qwen
```

```powershell
$env:DEEPSEEK_API_KEY = "你的DeepSeek API Key"
python .\run_external_api_experiment.py `
  --provider deepseek `
  --temperatures 0.2 0.7 1.0 `
  --runs-per-temperature 10 `
  --output-dir .\external_api_runs\deepseek
```

正式运行前可使用`--dry-run`检查模型、数据哈希、提示词哈希和参数，dry run不会发起API请求。为保证跨模型比较公平，两家模型应使用完全相同的temperature、top_p、重复次数、数据、CV折叠和筛选规则。
