"""中央競馬：M4c 中央で初めて走る馬（新馬以外）の3着内だけ HGB を使う（検証計画 M4c）。
使い方：python jk_m4c.py m4_pred.csv.gz jk_up の出力.pkl"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
S = pd.read_csv(sys.argv[1], dtype={'年月日': str, '場': str, 'R': str}); S['馬番'] = pd.to_numeric(S['馬番'], errors='coerce')
D = pd.read_pickle(sys.argv[2]); D = D.loc[:, ~D.columns.duplicated()].copy(); D['R'] = D['R'].astype(str); D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D = D.merge(S[KEY + ['馬番', 'p3_b']], on=KEY + ['馬番'], how='left')
D = D[D.groupby(KEY)['p3_b'].transform(lambda s: s.notna().all())].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup()
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
print('レース', D['g'].nunique(), '中央で初めて走る馬（新馬以外）', int(first.sum()), flush=True)
norm = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / pd.Series(v).groupby(X['g'].values).transform('sum').values, 1e-4, 0.97)
D['h'] = norm(D, D['p3'].values); D['b'] = norm(D, D['p3_b'].values); D['m'] = norm(D, np.where(first, D['h'].values, D['b'].values))


def pow3(X, col, c): return norm(X, X[col].values ** c)
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
for fit, test, lab in ((A, B, '2021〜2023年で決めて2024〜2026年に当てる'), (B, A, '2024〜2026年で決めて2021〜2023年に当てる')):
    print('■', lab)
    f2 = ((test['走数'] == 0) & (test['新馬'] == 0)).values
    for nm, col in (('今（M4bの3着内）', 'b'), ('M4c（初めて走る馬だけHGB）', 'm')):
        r = minimize(lambda v: l3(fit, pow3(fit, col, v[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
        q = pow3(test, col, r.x[0])
        print(f"  {nm}：c={r.x[0]:.3f}　3着内の当て分け {l3(test, q):.5f}／初めて走る馬の実際÷見込み {test['3着内'].values[f2].sum() / q[f2].sum():.3f}"
              f"・ほかの馬 {test['3着内'].values[~f2].sum() / q[~f2].sum():.3f}", flush=True)
