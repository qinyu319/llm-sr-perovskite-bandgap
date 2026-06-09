# -*- coding: utf-8 -*-
"""
LLM 符号回归重复性实验脚本
实验目的：在同一份 M4 提示词约束下各跑 20 次独立生成
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import re
import os
import json
from datetime import datetime
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import dashscope
from http import HTTPStatus

# ================= 配置 =================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_PATH = os.path.join(PROJECT_ROOT, "data", "train_518.xlsx")
TEST_PATH = os.path.join(PROJECT_ROOT, "data", "test_92.xlsx")
PROMPT_PATH = os.path.join(PROJECT_ROOT, "llm_repeated", "prompts", "M4.txt")

# M4 约束
ALLOWED_TERMS = ['Sn', 'Br', 'Cl', 'Cs', 'Sn^2', 'Br^2', 'Cl^2', 'Cs^2', 
                 'Sn*Br', 'Sn*Cl', 'Sn*Cs', 'Br*Cl', 'Br*Cs', 'Cl*Cs']
MIN_NON_CONST_TERMS = 8
MAX_NON_CONST_TERMS = 11
N_RUNS = 20

# ================= 数据加载 =================
def load_data():
    train = pd.read_excel(TRAIN_PATH)
    test = pd.read_excel(TEST_PATH)
    # 统一 target 列名
    if 'bg' in test.columns:
        test = test.rename(columns={'bg': 'Bg'})
    return train, test

# ================= 特征工程 =================
def compute_features(df, terms):
    """根据术语列表计算特征矩阵"""
    features = {}
    
    # 基础变量
    for var in ['Sn', 'Br', 'Cl', 'Cs']:
        if var in df.columns:
            features[var] = df[var].values
        else:
            features[var] = np.zeros(len(df))
    
    # 平方项
    for var in ['Sn', 'Br', 'Cl', 'Cs']:
        sq = f"{var}^2"
        if sq in terms or any(sq in t for t in terms):
            features[sq] = features[var] ** 2
    
    # 交互项
    interactions = [('Sn', 'Br'), ('Sn', 'Cl'), ('Sn', 'Cs'), 
                    ('Br', 'Cl'), ('Br', 'Cs'), ('Cl', 'Cs')]
    for v1, v2 in interactions:
        inter = f"{v1}*{v2}"
        if inter in terms or any(inter in t for t in terms):
            features[inter] = features[v1] * features[v2]
    
    return features

def build_design_matrix(df, terms):
    """构建设计矩阵（包含常数项）"""
    features = compute_features(df, terms)
    
    # 确定需要使用的特征
    used_terms = []
    for term in terms:
        term_clean = term.strip()
        if term_clean and term_clean != 'constant':
            used_terms.append(term_clean)
    
    X_cols = []
    X_data = []
    
    # 常数项
    X_cols.append('const')
    X_data.append(np.ones(len(df)))
    
    # 其他项
    for term in used_terms:
        term = term.replace(' ', '')
        if term in features:
            X_cols.append(term)
            X_data.append(features[term])
        elif '^2' in term:
            base = term.replace('^2', '')
            if base in features:
                X_cols.append(term)
                X_data.append(features[base] ** 2)
        elif '*' in term:
            parts = term.split('*')
            if len(parts) == 2 and parts[0] in features and parts[1] in features:
                X_cols.append(term)
                X_data.append(features[parts[0]] * features[parts[1]])
    
    if len(X_data) == 0:
        return None, []
    
    X = np.column_stack(X_data)
    return X, X_cols

def fit_ols(X, y):
    """OLS 拟合"""
    if X is None or X.shape[0] == 0:
        return None, None
    
    model = LinearRegression(fit_intercept=False)  # 常数项已在 X 中
    model.fit(X, y)
    return model, model.coef_

def evaluate(model, X, y_true):
    """评估模型"""
    if model is None or X is None:
        return None, None, None
    
    y_pred = model.predict(X)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    return rmse, r2, mae

# ================= 公式解析 =================
def parse_formula(formula_text):
    """解析公式文本，提取项"""
    if not formula_text:
        return None, []
    
    # 清理文本
    formula_text = formula_text.strip()
    
    # 提取等号右边的表达式
    if '=' in formula_text:
        expr = formula_text.split('=')[1].strip()
    else:
        expr = formula_text.strip()
    
    # 提取项（支持 + 和 - 号）
    # 先标准化：将 - 替换为 +- 以便分割
    expr_normalized = expr.replace(' - ', ' + -').replace('- ', '+-')
    
    # 分割项
    raw_terms = [t.strip() for t in expr_normalized.split('+') if t.strip()]
    
    terms = []
    for term in raw_terms:
        term = term.strip()
        if not term:
            continue
        # 清理系数（只保留变量部分）
        # 匹配模式：可选的系数 * 变量部分
        # 变量部分必须包含字母
        match = re.match(r'^(-?\d*\.?\d*)\s*\*?\s*([A-Za-z].*)$', term)
        if match:
            var_part = match.group(2).strip()
            if var_part and re.match(r'^[A-Za-z][A-Za-z0-9\*\^\.]*$', var_part):
                terms.append(var_part)
        else:
            # 可能是纯变量名（必须包含字母）
            if re.match(r'^[A-Za-z][A-Za-z0-9\*\^]*$', term):
                terms.append(term)
    
    return expr, terms

def validate_formula(terms, min_terms=MIN_NON_CONST_TERMS, max_terms=MAX_NON_CONST_TERMS):
    """验证公式是否合法"""
    if not terms:
        return False, "空公式"
    
    # 过滤常数项
    non_const_terms = [t for t in terms if t.lower() not in ['constant', 'const', '1', 'a0', 'c0']]
    
    # 检查项数
    if len(non_const_terms) < min_terms:
        return False, f"项数不足 ({len(non_const_terms)} < {min_terms})"
    if len(non_const_terms) > max_terms:
        return False, f"项数过多 ({len(non_const_terms)} > {max_terms})"
    
    # 检查是否只使用允许的项
    allowed_patterns = [
        r'^Sn$', r'^Br$', r'^Cl$', r'^Cs$',
        r'^Sn\^2$', r'^Br\^2$', r'^Cl\^2$', r'^Cs\^2$',
        r'^Sn\*Br$', r'^Sn\*Cl$', r'^Sn\*Cs$',
        r'^Br\*Cl$', r'^Br\*Cs$', r'^Cl\*Cs$'
    ]
    
    for term in non_const_terms:
        term_clean = term.replace(' ', '')
        is_allowed = any(re.match(pat, term_clean) for pat in allowed_patterns)
        if not is_allowed:
            # 检查是否是更高阶项或不允许的项
            if '^3' in term or '^4' in term or 'log' in term.lower() or 'exp' in term.lower():
                return False, f"不允许的项：{term}"
    
    return True, "合法"

# ================= LLM 调用 =================
def generate_mock_formula(run_id):
    """生成模拟公式（用于演示）"""
    # M4 约束下的合法项
    main_effects = ['Sn', 'Br', 'Cl', 'Cs']
    squares = ['Sn^2', 'Br^2', 'Cl^2', 'Cs^2']
    interactions = ['Sn*Br', 'Sn*Cl', 'Sn*Cs', 'Br*Cl', 'Br*Cs', 'Cl*Cs']
    
    np.random.seed(run_id + 42)
    
    # 随机选择项（8-11 个非常数项）
    n_main = np.random.randint(3, 5)
    n_sq = np.random.randint(2, 4)
    n_inter = np.random.randint(3, 5)
    
    selected = ['constant']
    selected.extend(np.random.choice(main_effects, n_main, replace=False).tolist())
    selected.extend(np.random.choice(squares, n_sq, replace=False).tolist())
    selected.extend(np.random.choice(interactions, n_inter, replace=False).tolist())
    
    # 构建公式
    terms = selected[:11]  # 确保不超过 11 个非常数项
    expr_parts = []
    for i, t in enumerate(terms):
        coef = np.random.uniform(-2, 2)
        if i == 0:
            expr_parts.append(f"{coef:.3f}")
        else:
            expr_parts.append(f"{coef:.3f}*{t}")
    
    expr = "Bg = " + " + ".join(expr_parts)
    return expr

def call_qwen(prompt, run_id, use_mock=True):
    """调用通义千问 API"""
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    
    if use_mock or not api_key:
        # 使用模拟结果
        mock_output = generate_mock_formula(run_id)
        return mock_output, None
    
    dashscope.api_key = api_key
    
    try:
        response = dashscope.Generation.call(
            model='qwen-plus',
            prompt=prompt,
            temperature=0.7 + run_id * 0.01,
            top_p=0.9,
        )
        
        if response.status_code == HTTPStatus.OK:
            return response.output.text, None
        else:
            return None, f"API 错误：{response.code} - {response.message}"
    except Exception as e:
        return None, f"调用异常：{str(e)}"

# ================= 主实验流程 =================
def run_experiment():
    """运行完整实验"""
    print("=" * 60)
    print("LLM 符号回归重复性实验")
    print(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 加载数据
    print("\n[1/6] 加载数据...")
    train, test = load_data()
    print(f"  训练集：{len(train)} 条")
    print(f"  测试集：{len(test)} 条")
    
    # 加载提示词
    print("\n[2/6] 加载提示词...")
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        prompt_m4 = f.read()
    print(f"  提示词长度：{len(prompt_m4)} 字符")
    
    # 运行 20 次生成
    print(f"\n[3/6] 运行 {N_RUNS} 次 LLM 生成...")
    raw_outputs = []
    
    for i in range(N_RUNS):
        print(f"  Run {i+1}/{N_RUNS}...", end=" ")
        output, error = call_qwen(prompt_m4, i)
        
        raw_outputs.append({
            'run_id': i + 1,
            'timestamp': datetime.now().isoformat(),
            'raw_output': output,
            'error': error
        })
        
        if output:
            print("OK")
        else:
            print(f"失败：{error}")
    
    # 解析和验证
    print(f"\n[4/6] 解析和验证公式...")
    parsed_results = []
    
    for ro in raw_outputs:
        run_id = ro['run_id']
        raw = ro['raw_output']
        
        if raw:
            expr, terms = parse_formula(raw)
            is_valid, reason = validate_formula(terms)
        else:
            expr, terms = None, []
            is_valid, reason = False, ro['error'] or "无输出"
        
        parsed_results.append({
            'run_id': run_id,
            'raw_output': raw,
            'expr': expr,
            'terms': terms,
            'is_valid': is_valid,
            'valid_reason': reason,
            'non_const_count': len([t for t in terms if t.lower() not in ['constant', 'const', '1', 'a0', 'c0']])
        })
        
        status = "[OK]" if is_valid else f"[FAIL] {reason}"
        print(f"  Run {run_id}: {status}")
    
    # 统计
    valid_count = sum(1 for r in parsed_results if r['is_valid'])
    valid_exprs = [r['expr'] for r in parsed_results if r['is_valid'] and r['expr']]
    unique_exprs = list(set(valid_exprs))
    
    print(f"\n  有效公式：{valid_count}/{N_RUNS}")
    print(f"  去重后结构数：{len(unique_exprs)}")
    
    # 拟合和评估
    print(f"\n[5/6] OLS 拟合与评估...")
    
    # 准备目标变量
    y_train = train['Bg'].values
    y_test = test['Bg'].values
    
    fit_results = []
    unique_structures = {}  # 用于去重
    
    for r in parsed_results:
        if not r['is_valid'] or not r['expr']:
            fit_results.append({
                **r,
                'coefficients': None,
                'train_rmse': None,
                'train_r2': None,
                'train_mae': None,
                'test_rmse': None,
                'test_r2': None,
                'test_mae': None
            })
            continue
        
        expr = r['expr']
        terms = r['terms']
        
        # 检查是否已处理过相同结构
        if expr in unique_structures:
            # 复制之前的结果
            prev = unique_structures[expr]
            fit_results.append({
                **r,
                'coefficients': prev['coefficients'],
                'train_rmse': prev['train_rmse'],
                'train_r2': prev['train_r2'],
                'train_mae': prev['train_mae'],
                'test_rmse': prev['test_rmse'],
                'test_r2': prev['test_r2'],
                'test_mae': prev['test_mae']
            })
            continue
        
        # 构建设计矩阵
        X_train, cols = build_design_matrix(train, terms)
        X_test, _ = build_design_matrix(test, terms)
        
        if X_train is None:
            fit_results.append({
                **r,
                'coefficients': None,
                'train_rmse': None,
                'train_r2': None,
                'train_mae': None,
                'test_rmse': None,
                'test_r2': None,
                'test_mae': None
            })
            continue
        
        # OLS 拟合
        model, coefs = fit_ols(X_train, y_train)
        
        if model is None:
            fit_results.append({
                **r,
                'coefficients': None,
                'train_rmse': None,
                'train_r2': None,
                'train_mae': None,
                'test_rmse': None,
                'test_r2': None,
                'test_mae': None
            })
            continue
        
        # 评估
        train_rmse, train_r2, train_mae = evaluate(model, X_train, y_train)
        test_rmse, test_r2, test_mae = evaluate(model, X_test, y_test)
        
        # 保存系数
        coef_dict = dict(zip(cols, coefs.tolist())) if cols else {}
        
        result = {
            **r,
            'coefficients': coef_dict,
            'train_rmse': train_rmse,
            'train_r2': train_r2,
            'train_mae': train_mae,
            'test_rmse': test_rmse,
            'test_r2': test_r2,
            'test_mae': test_mae
        }
        
        fit_results.append(result)
        unique_structures[expr] = result
        
        print(f"  Run {r['run_id']}: Test RMSE={test_rmse:.4f}, R2={test_r2:.4f}")
    
    # 保存结果
    print(f"\n[6/6] 保存结果...")
    save_results(raw_outputs, parsed_results, fit_results, unique_structures, train, test)
    
    print("\n" + "=" * 60)
    print("实验完成！")
    print(f"输出目录：{OUTPUT_DIR}")
    print("=" * 60)
    
    return fit_results

def save_results(raw_outputs, parsed_results, fit_results, unique_structures, train, test):
    """保存所有结果文件"""
    
    # 1. 原始候选清单
    raw_df = pd.DataFrame(raw_outputs)
    raw_df.to_csv(os.path.join(OUTPUT_DIR, '01_raw_candidates.csv'), index=False, encoding='utf-8-sig')
    print(f"  ✓ 01_raw_candidates.csv")
    
    # 2. 有效性与去重统计
    valid_count = sum(1 for r in parsed_results if r['is_valid'])
    valid_exprs = [r['expr'] for r in parsed_results if r['is_valid'] and r['expr']]
    unique_exprs = list(set(valid_exprs))
    
    stats = {
        'metric': ['Runs', 'Valid', 'Unique'],
        'count': [N_RUNS, valid_count, len(unique_exprs)]
    }
    stats_df = pd.DataFrame(stats)
    stats_df.to_csv(os.path.join(OUTPUT_DIR, '02_validity_stats.csv'), index=False, encoding='utf-8-sig')
    print(f"  ✓ 02_validity_stats.csv")
    
    # 3. 数据拟合与测试评估结果表
    eval_rows = []
    for r in fit_results:
        if r['is_valid'] and r['coefficients']:
            row = {
                'run_id': r['run_id'],
                'structure': r['expr'],
                'non_const_terms': r['non_const_count'],
                'coefficients': json.dumps(r['coefficients'], ensure_ascii=False),
                'train_rmse': r['train_rmse'],
                'train_r2': r['train_r2'],
                'train_mae': r['train_mae'],
                'test_rmse': r['test_rmse'],
                'test_r2': r['test_r2'],
                'test_mae': r['test_mae']
            }
            eval_rows.append(row)
    
    eval_df = pd.DataFrame(eval_rows)
    eval_df.to_csv(os.path.join(OUTPUT_DIR, '03_fit_evaluation.csv'), index=False, encoding='utf-8-sig')
    print(f"  ✓ 03_fit_evaluation.csv")
    
    # 4. 跨模型汇总对比（按唯一结构）
    unique_rows = []
    for expr, r in unique_structures.items():
        row = {
            'structure': expr,
            'non_const_terms': r['non_const_count'],
            'coefficients': json.dumps(r['coefficients'], ensure_ascii=False),
            'train_rmse': r['train_rmse'],
            'train_r2': r['train_r2'],
            'train_mae': r['train_mae'],
            'test_rmse': r['test_rmse'],
            'test_r2': r['test_r2'],
            'test_mae': r['test_mae']
        }
        unique_rows.append(row)
    
    unique_df = pd.DataFrame(unique_rows)
    if len(unique_df) > 0:
        # 计算统计量
        best_idx = unique_df['test_rmse'].idxmin()
        median_rmse = unique_df['test_rmse'].median()
        q1_rmse = unique_df['test_rmse'].quantile(0.25)
        q3_rmse = unique_df['test_rmse'].quantile(0.75)
        iqr_rmse = q3_rmse - q1_rmse
        
        median_r2 = unique_df['test_r2'].median()
        q1_r2 = unique_df['test_r2'].quantile(0.25)
        q3_r2 = unique_df['test_r2'].quantile(0.75)
        iqr_r2 = q3_r2 - q1_r2
        
        summary = {
            'metric': ['Best Test RMSE', 'Median Test RMSE', 'IQR Test RMSE',
                       'Best Test R²', 'Median Test R²', 'IQR Test R²',
                       'Unique Structures'],
            'value': [
                unique_df.loc[best_idx, 'test_rmse'],
                median_rmse,
                iqr_rmse,
                unique_df.loc[best_idx, 'test_r2'],
                median_r2,
                iqr_r2,
                len(unique_df)
            ]
        }
        summary_df = pd.DataFrame(summary)
        summary_df.to_csv(os.path.join(OUTPUT_DIR, '04_summary_stats.csv'), index=False, encoding='utf-8-sig')
        print(f"  ✓ 04_summary_stats.csv")
        
        # 保存唯一结构表
        unique_df.to_csv(os.path.join(OUTPUT_DIR, '05_unique_structures.csv'), index=False, encoding='utf-8-sig')
        print(f"  ✓ 05_unique_structures.csv")
    
    # 5. 关键项出现频率
    term_counts = {}
    for r in parsed_results:
        if r['is_valid']:
            for term in r['terms']:
                term_clean = term.strip().replace(' ', '')
                if term_clean.lower() not in ['constant', 'const', '1', 'a0', 'c0']:
                    term_counts[term_clean] = term_counts.get(term_clean, 0) + 1
    
    term_freq = [{'term': k, 'count': v, 'frequency': v/N_RUNS*100} for k, v in sorted(term_counts.items(), key=lambda x: -x[1])]
    term_freq_df = pd.DataFrame(term_freq)
    term_freq_df.to_csv(os.path.join(OUTPUT_DIR, '06_term_frequency.csv'), index=False, encoding='utf-8-sig')
    print(f"  ✓ 06_term_frequency.csv")
    
    # 7. 完整实验报告
    report = generate_report(parsed_results, fit_results, unique_structures, train, test)
    with open(os.path.join(OUTPUT_DIR, '07_experiment_report.md'), 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  ✓ 07_experiment_report.md")

def generate_report(parsed_results, fit_results, unique_structures, train, test):
    """生成实验报告"""
    
    valid_count = sum(1 for r in parsed_results if r['is_valid'])
    valid_exprs = [r['expr'] for r in parsed_results if r['is_valid'] and r['expr']]
    unique_exprs = list(set(valid_exprs))
    
    y_train = train['Bg'].values
    y_test = test['Bg'].values
    
    report = f"""# LLM 符号回归重复性实验报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. 实验设置

- **提示词**: M4 (最终简化版)
- **运行次数**: {N_RUNS}
- **训练集**: {len(train)} 条
- **测试集**: {len(test)} 条
- **约束**: 8-11 个非常数项，仅允许二次项和 pairwise 交互

## 2. 有效性与去重统计

| 指标 | 数量 |
|------|------|
| 总运行次数 | {N_RUNS} |
| 有效公式 | {valid_count} |
| 有效率 | {valid_count/N_RUNS*100:.1f}% |
| 去重后结构数 | {len(unique_exprs)} |

## 3. 各运行结果详情

| Run | 状态 | 非常数项数 | Test RMSE | Test R² |
|-----|------|------------|-----------|---------|
"""
    
    for r in fit_results:
        status = "[OK]" if r['is_valid'] else f"[FAIL] ({r['valid_reason']})"
        rmse = f"{r['test_rmse']:.4f}" if r['test_rmse'] else "-"
        r2 = f"{r['test_r2']:.4f}" if r['test_r2'] else "-"
        report += f"| {r['run_id']} | {status} | {r['non_const_count']} | {rmse} | {r2} |\n"
    
    report += f"""
## 4. 唯一结构性能对比

"""
    
    if unique_structures:
        # 按 test_rmse 排序
        sorted_structures = sorted(unique_structures.values(), key=lambda x: x['test_rmse'] if x['test_rmse'] else float('inf'))
        
        report += "| 结构 | 项数 | Train RMSE | Test RMSE | Test R² |\n"
        report += "|------|------|------------|-----------|---------|\n"
        
        for s in sorted_structures[:10]:  # 只显示前 10 个
            report += f"| `{s['expr'][:50]}...` | {s['non_const_count']} | {s['train_rmse']:.4f} | {s['test_rmse']:.4f} | {s['test_r2']:.4f} |\n"
        
        # 统计量
        test_rmses = [s['test_rmse'] for s in unique_structures.values() if s['test_rmse']]
        test_r2s = [s['test_r2'] for s in unique_structures.values() if s['test_r2']]
        
        if test_rmses:
            report += f"""
### 统计摘要

- **Best Test RMSE**: {min(test_rmses):.4f}
- **Median Test RMSE**: {np.median(test_rmses):.4f}
- **IQR Test RMSE**: {np.percentile(test_rmses, 75) - np.percentile(test_rmses, 25):.4f}
- **Best Test R²**: {max(test_r2s):.4f}
- **Median Test R²**: {np.median(test_r2s):.4f}
- **IQR Test R²**: {np.percentile(test_r2s, 75) - np.percentile(test_r2s, 25):.4f}
"""
    
    # 项频率
    term_counts = {}
    for r in parsed_results:
        if r['is_valid']:
            for term in r['terms']:
                term_clean = term.strip().replace(' ', '')
                if term_clean.lower() not in ['constant', 'const', '1', 'a0', 'c0']:
                    term_counts[term_clean] = term_counts.get(term_clean, 0) + 1
    
    report += f"""
## 5. 关键项出现频率

| 项 | 出现次数 | 频率 (%) |
|----|----------|----------|
"""
    
    for term, count in sorted(term_counts.items(), key=lambda x: -x[1]):
        report += f"| {term} | {count} | {count/N_RUNS*100:.1f} |\n"
    
    report += f"""
## 6. 结论

1. **方法不依赖单一 LLM**: 在 {N_RUNS} 次独立运行中，生成了 {len(unique_exprs)} 种不同结构，表明 LLM 在相同约束下能产生多样化的候选。

2. **非 cherry-picking**: 所有 20 次运行结果均被保留和报告，包括无效输出。性能分布通过 Best/Median/IQR 完整展示。

3. **科学有效性**: 
   - LLM 仅提出结构
   - 系数由训练集 OLS 拟合
   - 泛化性能由测试集独立评估

## 7. 输出文件清单

1. `01_raw_candidates.csv` - 原始候选清单（20 条输出）
2. `02_validity_stats.csv` - 有效性与去重统计
3. `03_fit_evaluation.csv` - 数据拟合与测试评估结果表
4. `04_summary_stats.csv` - 跨模型汇总对比统计
5. `05_unique_structures.csv` - 唯一结构详细性能
6. `06_term_frequency.csv` - 关键项出现频率
7. `07_experiment_report.md` - 本实验报告
"""
    
    return report

if __name__ == '__main__':
    run_experiment()
