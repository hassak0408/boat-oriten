"""中央競馬：M4 のくらべ（検証計画 M4）。両方の見込みがそろうレースで、
1着：今（M3a：exp(a×log ソフトマックス + b×log HGBの3着内)）と M4a・M4b（exp(a×log M4の1着 + b×log HGBの3着内)）、
3着内：今（HGBの3着内^c、足して3）と M4a・M4b の3着内^c を、2021〜2023年で決めて2024〜2026年に当てる、と逆向きでくらべる。
使い方：python jk_m4cmp.py m4_pred.csv.gz m3_pred.csv.gz jk_up の出力.pkl"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']


def rd(f):
    X = pd.read_csv(f, dtype={'年月日': str, '場': str, 'R': str}); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); return X


S4, S3 = rd(sys.argv[1]), rd(sys.argv[2])
D = pd.read_pickle(sys.argv[3]); D = D.loc[:, ~D.columns.duplicated()].copy(); D['R'] = D['R'].astype(str)
D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D = D.merge(S3[KEY + ['馬番', 'p1s']], on=KEY + ['馬番'], how='left').merge(S4[KEY + ['馬番', 'p1_a', 'p3_a', 'p1_b', 'p3_b']], on=KEY + ['馬番'], how='left')
C = ['p1s', 'p1_a', 'p3_a', 'p1_b', 'p3_b']
ok = D.groupby(KEY)[C].transform(lambda s: s.notna().all()).all(axis=1)
print('レース', D.groupby(KEY).ngroups, 'うち全部そろう', D[ok].groupby(KEY).ngroups, flush=True)
D = D[ok].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
for c in ('p1s', 'p1_a', 'p1_b'): D[c] = D[c] / D.groupby('g')[c].transform('sum')
for c in ('p3', 'p3_a', 'p3_b'): D[c] = (D[c] * np.minimum(3, D['n']) / D.groupby('g')[c].transform('sum')).clip(1e-4, 0.97)
for c in ('p1s', 'p1_a', 'p1_b', 'p3'): D['l_' + c] = np.log(D[c].clip(1e-6))


def blend(X, cols, w):
    s = sum(wi * X['l_' + c].values for wi, c in zip(w, cols))
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
for X, lab in ((A, '2021〜2023'), (B, '2024〜2026')):
    print(f"{lab}（{X['g'].nunique()}レース）そのまま：1着 ソフトマックス {l1(X, X['p1s'].values):.4f}・M4a {l1(X, X['p1_a'].values):.4f}・M4b {l1(X, X['p1_b'].values):.4f}"
          f"／3着内 HGB {l3(X, X['p3'].values):.5f}・M4a {l3(X, X['p3_a'].values):.5f}・M4b {l3(X, X['p3_b'].values):.5f}")
M1 = (('今（M3a）', ['p1s', 'p3']), ('M4a', ['p1_a', 'p3']), ('M4b', ['p1_b', 'p3']), ('M4a（混ぜない）', ['p1_a']), ('M4b（混ぜない）', ['p1_b']))
M3 = (('今（HGB）', 'p3'), ('M4a', 'p3_a'), ('M4b', 'p3_b'))
for fit, test, lab in ((A, B, '2021〜2023年で決めて2024〜2026年に当てる'), (B, A, '2024〜2026年で決めて2021〜2023年に当てる')):
    print('■', lab)
    for nm, cols in M1:
        if len(cols) == 1: q = test[cols[0]].values; ws = ''
        else:
            r = minimize(lambda v: l1(fit, blend(fit, cols, v)), [1.0] + [0.0] * (len(cols) - 1), method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6})
            q = blend(test, cols, r.x); ws = ' '.join(f'{c}={v:.3f}' for c, v in zip(cols, r.x))
        print(f"  1着 {nm}：{ws}　当て分け {l1(test, q):.4f}・1番手の1着率 {top(test, q, 1, '勝'):.2f}%", flush=True)
    for nm, col in M3:
        r = minimize(lambda v: l3(fit, pow3(fit, col, v[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
        q = pow3(test, col, r.x[0])
        print(f"  3着内 {nm}：c={r.x[0]:.3f}　当て分け {l3(test, q):.5f}・上位3頭の3着内 {top(test, q, 3, '3着内'):.2f}%", flush=True)
