"""中央競馬：M5 のくらべ（検証計画 M5）。くらべるものごとに、M4b・M4c と同じ使い方
（1着 ∝ そのモデルの1着^a×HGBの3着内^b、3着内 ∝ そのモデルの3着内（中央で初めて走る馬（新馬以外）だけHGB）^c）で、
2021〜2023年で決めて2024〜2026年に当てる、と逆向き。
使い方：python jk_m5cmp.py m5_pred.csv.gz jk_up の出力.pkl"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
S = pd.read_csv(sys.argv[1], dtype={'年月日': str, '場': str, 'R': str}); S['馬番'] = pd.to_numeric(S['馬番'], errors='coerce')
V = [c[3:] for c in S.columns if c.startswith('p1_')]
D = pd.read_pickle(sys.argv[2]); D = D.loc[:, ~D.columns.duplicated()].copy(); D['R'] = D['R'].astype(str); D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D = D.merge(S[KEY + ['馬番'] + [f'p{k}_{v}' for v in V for k in (1, 3)]], on=KEY + ['馬番'], how='left')
D = D[D.groupby(KEY)['p1_base'].transform(lambda s: s.notna().all())].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
norm3 = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / pd.Series(v).groupby(X['g'].values).transform('sum').values, 1e-4, 0.97)
D['h'] = norm3(D, D['p3'].values); D['l_h'] = np.log(D['h'])
for v in V:
    D['p1_' + v] = D['p1_' + v] / D.groupby('g')['p1_' + v].transform('sum'); D['l_' + v] = np.log(D['p1_' + v].clip(1e-6))
    D['m_' + v] = norm3(D, np.where(first, D['h'].values, norm3(D, D['p3_' + v].values)))
print('レース', D['g'].nunique(), 'くらべるもの', V, flush=True)


def blend(X, v, w):
    s = w[0] * X['l_' + v].values + w[1] * X['l_h'].values
    s = s - pd.Series(s).groupby(X['g'].values).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(X['g'].values).transform('sum').values


def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
res = {}
for fit, test, lab in ((A, B, '→2024〜26'), (B, A, '→2021〜23')):
    for v in V:
        r1 = minimize(lambda w: l1(fit, blend(fit, v, w)), [1.0, 0.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6})
        r3 = minimize(lambda c: l3(fit, norm3(fit, fit['m_' + v].values ** c[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
        res[(v, lab)] = (l1(test, blend(test, v, r1.x)), l3(test, norm3(test, test['m_' + v].values ** r3.x[0])), r1.x, r3.x[0])
print('| | 1着 →2024〜26 | 1着 →2021〜23 | 3着内 →2024〜26 | 3着内 →2021〜23 |')
for v in V:
    a, b = res[(v, '→2024〜26')], res[(v, '→2021〜23')]
    print(f'| {v} | {a[0]:.4f} | {b[0]:.4f} | {a[1]:.5f} | {b[1]:.5f} |　a={a[2][0]:.3f} b={a[2][1]:.3f} c={a[3]:.3f}')
ok = [v for v in V if v != 'base' and all(res[(v, k)][0] < res[('base', k)][0] for k in ('→2024〜26', '→2021〜23'))
      and all(res[(v, k)][1] <= res[('base', k)][1] + 0.00005 for k in ('→2024〜26', '→2021〜23'))]
print('条件を満たすもの', ok, '→ 採用', min(ok, key=lambda v: res[(v, '→2024〜26')][0] + res[(v, '→2021〜23')][0]) if ok else 'なし（今のまま）')
