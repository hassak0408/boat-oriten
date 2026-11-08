"""中央競馬：M3 のくらべ（検証計画 M3）。GitHub の方で作ったソフトマックスの1着の見込み（jra/exp/m3_pred.csv.gz）と、
今のHGBの見込み（jk_up.py の出力、付け直しの前）を、両方がそろうレースでくらべる。
今：exp(a×log HGBの1着 + b×log HGBの3着内)、M3a：exp(a×log ソフトマックス + b×log HGBの3着内)、M3b：exp(a×log ソフトマックス + b×log HGBの3着内 + c×log HGBの1着)。
2021〜2023年で決めて2024〜2026年に当てる、と逆向き。
使い方：python jk_m3cmp.py m3_pred.csv.gz jk_up の出力.pkl"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
S = pd.read_csv(sys.argv[1], dtype={'年月日': str, '場': str, 'R': str})
S['馬番'] = pd.to_numeric(S['馬番'], errors='coerce')
D = pd.read_pickle(sys.argv[2]); D = D.loc[:, ~D.columns.duplicated()].copy(); D['R'] = D['R'].astype(str)
D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D = D.merge(S[KEY + ['馬番', 'p1s']], on=KEY + ['馬番'], how='left')
ok = D.groupby(KEY)['p1s'].transform(lambda s: s.notna().all())
print('レース', D.groupby(KEY).ngroups, 'うち両方そろう', D[ok].groupby(KEY).ngroups, flush=True)
D = D[ok].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup()
D['p1'] = D['p1'] / D.groupby('g')['p1'].transform('sum')
D['p1s'] = D['p1s'] / D.groupby('g')['p1s'].transform('sum')
D['p3'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby('g')['p3'].transform('sum')).clip(1e-4, 0.97)
for c in ('p1', 'p1s', 'p3'): D['l_' + c] = np.log(D[c].clip(1e-6))


def blend(X, cols, w):
    s = sum(wi * X['l_' + c].values for wi, c in zip(w, cols))
    s = s - pd.Series(s).groupby(X['g'].values).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(X['g'].values).transform('sum').values


def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())


def top1(X, p):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
    return X['勝'].values[r == 1].mean() * 100


A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
for X, lab in ((A, '2021〜2023'), (B, '2024〜2026')):
    print(f"{lab}（{X['g'].nunique()}レース）そのまま：HGBの1着 {l1(X, X['p1'].values):.4f}・ソフトマックス {l1(X, X['p1s'].values):.4f}"
          f"／1番手の1着率 {top1(X, X['p1'].values):.2f}%・{top1(X, X['p1s'].values):.2f}%")
MODELS = (('今', ['p1', 'p3']), ('M3a', ['p1s', 'p3']), ('M3b', ['p1s', 'p3', 'p1']))
for fit, test, lab in ((A, B, '2021〜2023年で決めて2024〜2026年に当てる'), (B, A, '2024〜2026年で決めて2021〜2023年に当てる')):
    print('■', lab)
    for nm, cols in MODELS:
        r = minimize(lambda v: l1(fit, blend(fit, cols, v)), [1.0] + [0.0] * (len(cols) - 1), method='Nelder-Mead',
                     options={'xatol': 1e-4, 'fatol': 1e-6, 'maxiter': 2000})
        q = blend(test, cols, r.x)
        print(f"  {nm}：{' '.join(f'{c}={v:.3f}' for c, v in zip(cols, r.x))}　1着の当て分け {l1(test, q):.4f}・1番手の1着率 {top1(test, q):.2f}%", flush=True)
