"""中央競馬：M2a 出てきた見込みを、レースの中のくらべで付け直す（検証計画 M2a）。
1着：p1' ∝ exp(a×log p1 + b×log p3)。3着内：p3' ∝ p3^c（足して3、0.97で止める）。2021〜2023年で決めて2024〜2026年に当てる、と逆向き。
使い方：python jk_m2a.py 見込み.pkl（jk_lap.py の出力）"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1]); D = D.loc[:, ~D.columns.duplicated()]
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True)
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(1e-4, 0.97)
D['g'] = D.groupby(KEY, sort=False).ngroup()


def p1_new(X, a, b):
    s = a * np.log(X['p1'].clip(1e-6).values) + b * np.log(X['p3'].clip(1e-6).values)
    s = s - pd.Series(s).groupby(X['g'].values).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(X['g'].values).transform('sum').values


def p3_new(X, c):
    e = X['p3'].values ** c
    q = e * np.minimum(3, X['n'].values) / pd.Series(e).groupby(X['g'].values).transform('sum').values
    return np.clip(q, 1e-4, 0.97)


def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def top1(X, p):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
    return X['勝'].values[r == 1].mean() * 100


def top3(X, p):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
    return X['3着内'].values[r <= 3].mean() * 100


A = D[D['年'].between(2021, 2023)]; B = D[D['年'].between(2024, 2026)]
for fit, test, lab in ((A, B, '2021〜2023年で決めて2024〜2026年に当てる'), (B, A, '2024〜2026年で決めて2021〜2023年に当てる')):
    r1 = minimize(lambda v: l1(fit, p1_new(fit, v[0], v[1])), [1.0, 0.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6})
    r3 = minimize(lambda v: l3(fit, p3_new(fit, v[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
    a, b = r1.x; c = r3.x[0]
    q1 = p1_new(test, a, b); q3 = p3_new(test, c)
    print(f'■ {lab}：a={a:.3f} b={b:.3f} c={c:.3f}')
    print(f'  1着の当て分け {l1(test, test["p1"].values):.4f} → {l1(test, q1):.4f}／1番手（1着の見込み）の1着率 {top1(test, test["p1"].values):.2f}% → {top1(test, q1):.2f}%')
    print(f'  3着内の当て分け {l3(test, test["p3"].values):.6f} → {l3(test, q3):.6f}／上位3頭の3着内 {top3(test, test["p3"].values):.2f}% → {top3(test, q3):.2f}%')
