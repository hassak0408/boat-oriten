"""地方：N1・N2 のくらべ（検証計画「地方：精度を上げる」）。nk_m4.py の見込みで、5頭以上のレースを、
今（HGB 乱数0、そのまま）・N1（順を学ぶモデル＋HGB 3つの平均）・N2（N1＋騎手の格の差）で、2021〜2023年で決めて2024〜2026年に当てる、と逆向き。
使い方：python nk_m4cmp.py nk_m4_pred.csv.gz"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['競馬場', '競走年月日', 'レース番号']
D = pd.read_csv(sys.argv[1], dtype={'競馬場': str, '競走年月日': str, 'レース番号': str})
D = D[(D['n'] >= 5) & (D.groupby(KEY)['勝'].transform('sum') >= 1)].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
first = (D['五場走数'] == 0).values
s1 = lambda v: v / pd.Series(v).groupby(G).transform('sum').values
s3 = lambda v, g=G, n=None: np.clip(v * np.minimum(3, D['n'].values if n is None else n) / pd.Series(v).groupby(g).transform('sum').values, 1e-4, 0.97)
D['今1'] = s1(D['h0_1'].values); D['今3'] = s3(D['h0_3'].values)
for v in ('', '_j'):
    D['h3' + v] = s3(D['h_3' + v].values); D['l_h3' + v] = np.log(D['h3' + v])
    D['pl1' + v] = s1(D['pl_1' + v].values); D['l_pl1' + v] = np.log(np.clip(D['pl1' + v], 1e-6, 1))
    D['m3' + v] = s3(np.where(first, D['h3' + v].values, s3(D['pl_3' + v].values)))      # 5場で初めて走る馬だけ HGB の3着内
print('レース', D['g'].nunique(), '（2021〜2023年', D.loc[D['年'] <= 2023, 'g'].nunique(), '・2024〜2026年', D.loc[D['年'] >= 2024, 'g'].nunique(), '）', flush=True)


def blend(X, v, w):
    s = w[0] * X['l_pl1' + v].values + w[1] * X['l_h3' + v].values
    s = s - pd.Series(s).groupby(X['g'].values).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(X['g'].values).transform('sum').values


def pow3(X, col, c):
    e = X[col].values ** c
    return np.clip(e * np.minimum(3, X['n'].values) / pd.Series(e).groupby(X['g'].values).transform('sum').values, 1e-4, 0.97)


def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def top(X, p, k, col):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
    return X[col].values[r <= k].mean() * 100


A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
res = {}
for fit, test, lab in ((A, B, '→2024〜26'), (B, A, '→2021〜23')):
    res[('今', lab)] = (l1(test, test['今1'].values), l3(test, test['今3'].values), top(test, test['今1'].values, 1, '勝'), top(test, test['今3'].values, 3, '3着内'), '')
    for nm, v in (('N1', ''), ('N2', '_j')):
        r1 = minimize(lambda w: l1(fit, blend(fit, v, w)), [1.0, 0.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6})
        r3 = minimize(lambda c: l3(fit, pow3(fit, 'm3' + v, c[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
        q1 = blend(test, v, r1.x); q3 = pow3(test, 'm3' + v, r3.x[0])
        res[(nm, lab)] = (l1(test, q1), l3(test, q3), top(test, q1, 1, '勝'), top(test, q3, 3, '3着内'), f'a={r1.x[0]:.3f} b={r1.x[1]:.3f} c={r3.x[0]:.3f}')
    pop = pd.to_numeric(test['人気'], errors='coerce')
    res[('市場', lab)] = (np.nan, np.nan, test.loc[pop == 1, '勝'].mean() * 100, test.loc[pop <= 3, '3着内'].mean() * 100, '')
print('| | 1着の当て分け →24〜26／→21〜23 | 3着内の当て分け | AIの1番手の1着率 | 上位3頭の3着内 |')
for nm in ('今', 'N1', 'N2', '市場'):
    a, b = res[(nm, '→2024〜26')], res[(nm, '→2021〜23')]
    print(f'| {nm} | {a[0]:.4f}／{b[0]:.4f} | {a[1]:.5f}／{b[1]:.5f} | {a[2]:.1f}%／{b[2]:.1f}% | {a[3]:.1f}%／{b[3]:.1f}% |　{a[4]}')
ok1 = all(res[('N1', k)][0] < res[('今', k)][0] and res[('N1', k)][1] < res[('今', k)][1] for k in ('→2024〜26', '→2021〜23'))
ok2 = ok1 and all(res[('N2', k)][0] < res[('N1', k)][0] and res[('N2', k)][1] <= res[('N1', k)][1] + 0.00005 for k in ('→2024〜26', '→2021〜23'))
print('N1 採用' if ok1 else 'N1 届かない', '／', 'N2 採用' if ok2 else 'N2 届かない')
