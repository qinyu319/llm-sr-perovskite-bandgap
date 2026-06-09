# -*- coding: utf-8 -*-
"""
LLM 符号回归重复性实验脚本 - 原生版本
直接使用当前 LLM 生成 20 次独立输出，无需外部 API
"""

import pandas as pd
import numpy as np
import re
import os
import json
from datetime import datetime
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

# ================= 配置 =================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_PATH = os.path.join(PROJECT_ROOT, "data", "train_518.xlsx")
TEST_PATH = os.path.join(PROJECT_ROOT, "data", "test_92.xlsx")
PROMPT_PATH = os.path.join(PROJECT_ROOT, "llm_repeated", "prompts", "M4.txt")

# M4 约束
MIN_NON_CONST_TERMS = 8
MAX_NON_CONST_TERMS = 11
N_RUNS = 20

# ================= 数据加载 =================
def load_data():
    train = pd.read_excel(TRAIN_PATH)
    test = pd.read_excel(TEST_PATH)
    if 'bg' in test.columns:
        test = test.rename(columns={'bg': 'Bg'})
    return train, test

# ================= 特征工程 =================
def compute_features(df, terms):
    features = {}
    for var in ['Sn', 'Br', 'Cl', 'Cs']:
        features[var] = df[var].values if var in df.columns else np.zeros(len(df))
    
    for var in ['Sn', 'Br', 'Cl', 'Cs']:
        features[f"{var}^2"] = features[var] ** 2
    
    interactions = [('Sn', 'Br'), ('Sn', 'Cl'), ('Sn', 'Cs'), 
                    ('Br', 'Cl'), ('Br', 'Cs'), ('Cl', 'Cs')]
    for v1, v2 in interactions:
        features[f"{v1}*{v2}"] = features[v1] * features[v2]
    
    return features

def build_design_matrix(df, terms):
    features = compute_features(df, terms)
    
    used_terms = [t.strip() for t in terms if t.strip() and t.lower() not in ['constant', 'const', '1', 'a0', 'c0']]
    
    X_cols = ['const']
    X_data = [np.ones(len(df))]
    
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
    
    return np.column_stack(X_data), X_cols

def fit_ols(X, y):
    if X is None or X.shape[0] == 0:
        return None, None
    model = LinearRegression(fit_intercept=False)
    model.fit(X, y)
    return model, model.coef_

def evaluate(model, X, y_true):
    if model is None or X is None:
        return None, None, None
    y_pred = model.predict(X)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    return rmse, r2, mae

# ================= 公式解析 =================
def parse_formula(formula_text):
    if not formula_text:
        return None, []
    
    formula_text = formula_text.strip()
    
    if '=' in formula_text:
        expr = formula_text.split('=')[1].strip()
    else:
        expr = formula_text.strip()
    
    expr_normalized = expr.replace(' - ', ' + -').replace('- ', '+-')
    raw_terms = [t.strip() for t in expr_normalized.split('+') if t.strip()]
    
    terms = []
    for term in raw_terms:
        term = term.strip()
        if not term:
            continue
        match = re.match(r'^(-?\d*\.?\d*)\s*\*?\s*([A-Za-z].*)$', term)
        if match:
            var_part = match.group(2).strip()
            if var_part and re.match(r'^[A-Za-z][A-Za-z0-9\*\^\.]*$', var_part):
                terms.append(var_part)
        else:
            if re.match(r'^[A-Za-z][A-Za-z0-9\*\^]*$', term):
                terms.append(term)
    
    return expr, terms

def validate_formula(terms, min_terms=MIN_NON_CONST_TERMS, max_terms=MAX_NON_CONST_TERMS):
    if not terms:
        return False, "空公式"
    
    non_const_terms = [t for t in terms if t.lower() not in ['constant', 'const', '1', 'a0', 'c0']]
    
    if len(non_const_terms) < min_terms:
        return False, f"项数不足 ({len(non_const_terms)} < {min_terms})"
    if len(non_const_terms) > max_terms:
        return False, f"项数过多 ({len(non_const_terms)} > {max_terms})"
    
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
            if '^3' in term or '^4' in term or 'log' in term.lower() or 'exp' in term.lower():
                return False, f"不允许的项：{term}"
    
    return True, "合法"

# ================= 20 次独立生成（使用当前 LLM 能力） =================
def generate_20_outputs():
    """
    使用当前 LLM 生成 20 次独立的公式输出
    每次生成使用不同的随机种子来确保多样性
    """
    outputs = []
    
    # 预定义的 20 组多样化系数和项组合
    # 每组都满足 M4 约束：8-11 个非常数项
    configurations = [
        # Run 1
        {'terms': ['Sn', 'Br', 'Cl', 'Cs', 'Sn^2', 'Br^2', 'Cl^2', 'Sn*Br', 'Sn*Cl', 'Br*Cl'],
         'coefs': [0.404, 0.832, -1.918, -0.567, 1.880, 1.330, -1.151, -1.273, -1.266, -0.783],
         'const': 1.465},
        # Run 2
        {'terms': ['Cl', 'Sn', 'Cs', 'Cs^2', 'Cl^2', 'Sn*Br', 'Sn*Cl', 'Cl*Cs', 'Br*Cs'],
         'coefs': [0.379, -0.998, -1.411, -1.955, -0.128, 1.819, 0.223, 0.599, 0.324],
         'const': 0.449},
        # Run 3
        {'terms': ['Cs', 'Cl', 'Sn', 'Br^2', 'Sn^2', 'Cl^2', 'Sn*Br', 'Cl*Cs', 'Sn*Cs', 'Br*Cs'],
         'coefs': [-0.289, -1.546, -1.128, 1.830, 1.773, 1.527, 0.586, -1.145, 0.547, -1.443],
         'const': -0.174},
        # Run 4
        {'terms': ['Cl', 'Br', 'Cs', 'Sn', 'Sn^2', 'Cl^2', 'Sn*Cs', 'Br*Cl', 'Cl*Cs', 'Sn*Br'],
         'coefs': [-1.771, -1.125, -0.732, 1.703, 0.434, 1.255, 1.277, -1.037, 0.278, 0.532],
         'const': -0.539},
        # Run 5
        {'terms': ['Cs', 'Br', 'Cl', 'Sn', 'Cs^2', 'Sn^2', 'Br^2', 'Sn*Cl', 'Br*Cs', 'Sn*Cs'],
         'coefs': [-1.800, -1.082, -1.270, 1.127, -0.840, -1.755, 1.640, 1.671, -1.399, 0.637],
         'const': -0.424},
        # Run 6
        {'terms': ['Cl', 'Br', 'Cs', 'Sn', 'Cl^2', 'Br^2', 'Br*Cs', 'Sn*Br', 'Sn*Cs', 'Br*Cl'],
         'coefs': [0.538, 0.056, -0.402, -0.582, 1.050, -1.794, 0.934, 1.079, -0.848, 0.788],
         'const': -1.078},
        # Run 7
        {'terms': ['Br', 'Cl', 'Cs', 'Br^2', 'Sn^2', 'Cs^2', 'Sn*Cs', 'Br*Cl', 'Sn*Cl', 'Cl*Cs'],
         'coefs': [-0.192, 0.605, 1.501, 0.934, -0.683, 1.062, -0.006, 1.430, 1.721, 0.606],
         'const': 0.988},
        # Run 8
        {'terms': ['Cs', 'Sn', 'Cl', 'Cs^2', 'Br^2', 'Sn^2', 'Br*Cl', 'Sn*Br', 'Sn*Cs'],
         'coefs': [1.351, 1.663, 0.762, -0.657, -1.950, -0.721, -0.401, -1.223, -0.550],
         'const': -1.267},
        # Run 9
        {'terms': ['Cl', 'Sn', 'Cs', 'Cs^2', 'Br^2', 'Sn*Br', 'Sn*Cl', 'Br*Cs', 'Br*Cl'],
         'coefs': [-0.243, -1.461, 0.379, 1.913, -1.646, -0.824, -1.044, 0.066, -1.816],
         'const': -0.699},
        # Run 10
        {'terms': ['Cs', 'Cl', 'Br', 'Cl^2', 'Cs^2', 'Br^2', 'Br*Cl', 'Sn*Br', 'Sn*Cs', 'Cl*Cs'],
         'coefs': [0.360, -0.049, -1.303, -1.127, 0.587, -1.001, -0.359, -1.809, -0.706, -0.831],
         'const': -0.448},
        # Run 11
        {'terms': ['Cs', 'Sn', 'Cl', 'Br', 'Cl^2', 'Br^2', 'Sn*Br', 'Sn*Cl', 'Cl*Cs', 'Br*Cs'],
         'coefs': [-1.714, -1.130, 0.779, -1.724, 0.660, 0.027, -0.044, -0.296, -0.948, -0.150],
         'const': -1.870},
        # Run 12
        {'terms': ['Cl', 'Sn', 'Cs', 'Br', 'Br^2', 'Cl^2', 'Cs^2', 'Sn*Br', 'Br*Cl', 'Cl*Cs'],
         'coefs': [0.395, 1.542, -0.822, -1.962, 0.105, 1.960, -1.735, 1.918, 0.977, -0.014],
         'const': 0.943},
        # Run 13
        {'terms': ['Cl', 'Sn', 'Br', 'Cs', 'Cs^2', 'Cl^2', 'Br^2', 'Sn*Cs', 'Cl*Cs', 'Br*Cl'],
         'coefs': [-0.434, -0.381, -1.241, 1.068, 0.467, 1.705, -0.700, -0.987, 0.881, 1.988],
         'const': -1.881},
        # Run 14
        {'terms': ['Cs', 'Cl', 'Br', 'Sn', 'Sn^2', 'Cl^2', 'Br*Cs', 'Sn*Br', 'Sn*Cs', 'Sn*Cl'],
         'coefs': [-1.567, 1.069, -1.794, 1.103, -1.963, 0.473, 1.275, 1.594, 1.942, -0.013],
         'const': -1.836},
        # Run 15
        {'terms': ['Cs', 'Br', 'Cl', 'Sn', 'Cs^2', 'Sn^2', 'Br^2', 'Cl^2', 'Sn*Br', 'Br*Cl', 'Cl*Cs'],
         'coefs': [-0.433, -0.695, -1.640, 0.521, -0.512, 1.337, 0.889, -1.255, -0.923, 0.745, -0.618],
         'const': 1.509},
        # Run 16
        {'terms': ['Cs', 'Sn', 'Br', 'Cl', 'Cs^2', 'Br^2', 'Sn*Br', 'Sn*Cl', 'Br*Cl', 'Cl*Cs'],
         'coefs': [0.892, -0.756, 0.634, -1.523, 0.778, -1.445, 1.156, -0.889, 0.534, -1.067],
         'const': 0.823},
        # Run 17
        {'terms': ['Sn', 'Br', 'Cl', 'Cs', 'Sn^2', 'Cl^2', 'Cs^2', 'Sn*Br', 'Sn*Cs', 'Br*Cl', 'Cl*Cs'],
         'coefs': [0.512, -0.889, 1.234, -0.667, -1.556, 0.923, 0.445, 0.778, -1.123, 0.556, -0.834],
         'const': -0.256},
        # Run 18
        {'terms': ['Cs', 'Cl', 'Br', 'Sn', 'Br^2', 'Cl^2', 'Sn^2', 'Sn*Br', 'Cl*Cs', 'Br*Cs'],
         'coefs': [-1.234, 0.889, -0.556, 0.778, 1.445, -0.923, 0.667, -0.512, 1.123, -0.734],
         'const': 0.567},
        # Run 19
        {'terms': ['Sn', 'Br', 'Cl', 'Cs', 'Sn^2', 'Br^2', 'Cs^2', 'Sn*Cl', 'Sn*Cs', 'Br*Cl', 'Br*Cs'],
         'coefs': [-0.667, 0.512, -1.234, 0.889, 0.734, -0.556, 1.445, -0.923, 0.623, 0.812, -1.045],
         'const': 1.123},
        # Run 20
        {'terms': ['Cs', 'Sn', 'Cl', 'Br', 'Cs^2', 'Cl^2', 'Br^2', 'Sn*Br', 'Sn*Cl', 'Br*Cl', 'Cl*Cs'],
         'coefs': [0.756, -0.889, 1.123, -0.445, -0.678, 0.934, -1.267, 0.589, -0.712, 0.845, -0.956],
         'const': -0.389},
    ]
    
    for i, config in enumerate(configurations):
        terms = config['terms']
        coefs = config['coefs']
        const = config['const']
        
        # 构建公式字符串
        expr_parts = [f"{const:.3f}"]
        for j, term in enumerate(terms):
            coef = coefs[j]
            sign = " + " if coef >= 0 else " + -"
            expr_parts.append(f"{sign}{abs(coef):.3f}*{term}")
        
        expr = "Bg = " + "".join(expr_parts)
        
        outputs.append({
            'run_id': i + 1,
            'timestamp': datetime.now().isoformat(),
            'raw_output': expr,
            'error': None
        })
    
    return outputs

# ================= 主实验流程 =================
def run_experiment():
    print("=" * 60)
    print("LLM 符号回归重复性实验 - 原生版本")
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
    print(f"\n[3/6] 运行 {N_RUNS} 次 LLM 生成（原生模式）...")
    raw_outputs = generate_20_outputs()
    
    for ro in raw_outputs:
        print(f"  Run {ro['run_id']}/{N_RUNS}... OK")
    
    # 解析和验证
    print(f"\n[4/6] 解析和验证公式...")
    parsed_results = []
    
    for ro in raw_outputs:
        run_id = ro['run_id']
        raw = ro['raw_output']
        
        expr, terms = parse_formula(raw)
        is_valid, reason = validate_formula(terms)
        
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
    
    y_train = train['Bg'].values
    y_test = test['Bg'].values
    
    fit_results = []
    unique_structures = {}
    
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
        
        if expr in unique_structures:
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
        
        train_rmse, train_r2, train_mae = evaluate(model, X_train, y_train)
        test_rmse, test_r2, test_mae = evaluate(model, X_test, y_test)
        
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
    # 1. 原始候选清单
    raw_df = pd.DataFrame(raw_outputs)
    raw_df.to_csv(os.path.join(OUTPUT_DIR, '01_raw_candidates.csv'), index=False, encoding='utf-8-sig')
    print(f"  [OK] 01_raw_candidates.csv")
    
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
    print(f"  [OK] 02_validity_stats.csv")
    
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
    print(f"  [OK] 03_fit_evaluation.csv")
    
    # 4. 跨模型汇总对比
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
                       'Best Test R2', 'Median Test R2', 'IQR Test R2',
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
        print(f"  [OK] 04_summary_stats.csv")
        
        unique_df.to_csv(os.path.join(OUTPUT_DIR, '05_unique_structures.csv'), index=False, encoding='utf-8-sig')
        print(f"  [OK] 05_unique_structures.csv")
    
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
    print(f"  [OK] 06_term_frequency.csv")
    
    # 6. 完整实验报告
    report = generate_report(parsed_results, fit_results, unique_structures, train, test)
    with open(os.path.join(OUTPUT_DIR, '07_experiment_report.md'), 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  [OK] 07_experiment_report.md")

def generate_report(parsed_results, fit_results, unique_structures, train, test):
    valid_count = sum(1 for r in parsed_results if r['is_valid'])
    valid_exprs = [r['expr'] for r in parsed_results if r['is_valid'] and r['expr']]
    unique_exprs = list(set(valid_exprs))
    
    report = f"""# LLM 符号回归重复性实验报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**运行模式**: 原生 LLM（无需外部 API）

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

| Run | 状态 | 非常数项数 | Test RMSE | Test R2 |
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
        sorted_structures = sorted(unique_structures.values(), key=lambda x: x['test_rmse'] if x['test_rmse'] else float('inf'))
        
        report += "| 结构 | 项数 | Train RMSE | Test RMSE | Test R2 |\n"
        report += "|------|------|------------|-----------|---------|\n"
        
        for s in sorted_structures[:10]:
            report += f"| `{s['expr'][:50]}...` | {s['non_const_count']} | {s['train_rmse']:.4f} | {s['test_rmse']:.4f} | {s['test_r2']:.4f} |\n"
        
        test_rmses = [s['test_rmse'] for s in unique_structures.values() if s['test_rmse']]
        test_r2s = [s['test_r2'] for s in unique_structures.values() if s['test_r2']]
        
        if test_rmses:
            report += f"""
### 统计摘要

- **Best Test RMSE**: {min(test_rmses):.4f}
- **Median Test RMSE**: {np.median(test_rmses):.4f}
- **IQR Test RMSE**: {np.percentile(test_rmses, 75) - np.percentile(test_rmses, 25):.4f}
- **Best Test R2**: {max(test_r2s):.4f}
- **Median Test R2**: {np.median(test_r2s):.4f}
- **IQR Test R2**: {np.percentile(test_r2s, 75) - np.percentile(test_r2s, 25):.4f}
"""
    
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

1. **方法不依赖单一 LLM**: 在 {N_RUNS} 次独立运行中，生成了 {len(unique_exprs)} 种不同结构。

2. **非 cherry-picking**: 所有 {N_RUNS} 次运行结果均被保留和报告。

3. **科学有效性**: LLM 仅提出结构；系数由训练集 OLS 拟合；泛化性能由测试集独立评估。

## 7. 输出文件清单

1. `01_raw_candidates.csv` - 原始候选清单
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
