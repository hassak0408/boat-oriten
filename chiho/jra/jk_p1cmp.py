"""中央競馬：P1 のくらべ（検証計画「中央：血統」P1）。base（今の材料）と ped（血統を足した）を、今の一覧と同じ使い方
（1着 ∝ M4bの1着^a×HGBの3着内^b、3着内 ∝ M4bの3着内（中央で初めて走る馬（新馬以外）だけHGB）^c）で、
2021〜2023年で決めて2024〜2026年に当てる、と逆向き。あわせて、新馬戦・初めての芝ダ・初めての距離の帯での1着の当て分けと1番手の1着率。
使い方：python jk_p1cmp.py p1_pred.csv.gz"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
D = pd.read_csv(sys.argv[1], dtype={'年月日': str, '場': str, 'R': str})
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
norm3 = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / pd.Series(v).groupby(X['g'].values).transform('sum').values, 1e-4, 0.97)
V = ('base', 'ped')
for v in V:
    D['hh_' + v] = norm3(D, D['h_' + v].values); D['lh_' + v] = np.log(D['hh_' + v])
    D['p1_' + v] = D['p1_' + v] / D.groupby('g')['p1_' + v].transform('sum'); D['l_' + v] = np.log(D['p1_' + v].clip(1e-6))
    D['m_' + v] = norm3(D, np.where(first, D['hh_' + v].values, norm3(D, D['p3_' + v].values)))
print('レース', D['g'].nunique(), flush=True)


def blend(X, v, w):
    s = w[0] * X['l_' + v].values + w[1] * X['lh_' + v].values
    s = s - pd.Series(s).groupby(X['g'].values).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(X['g'].values).transform('sum').values


def l1(X, p, m=None):
    w = X['勝'].values == 1
    if m is not None: w = w & m
    return float(-np.log(np.clip(p[w], 1e-6, 1)).mean())


def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def top1(X, p, races=None):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values == 1
    if races is not None: r = r & races
    return X['勝'].values[r].mean() * 100


A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
for fit, test, lab in ((A, B, '2021〜2023年で決めて2024〜2026年に当てる'), (B, A, '2024〜2026年で決めて2021〜2023年に当てる')):
    print('■', lab)
    shin = (test['新馬'] == 1).values
    for v in V:
        r1 = minimize(lambda w: l1(fit, blend(fit, v, w)), [1.0, 0.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6})
        r3 = minimize(lambda c: l3(fit, norm3(fit, fit['m_' + v].values ** c[0])), [1.0], method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7})
        q1 = blend(test, v, r1.x); q3 = norm3(test, test['m_' + v].values ** r3.x[0])
        print(f"  {v}：a={r1.x[0]:.3f} b={r1.x[1]:.3f} c={r3.x[0]:.3f}　1着の当て分け {l1(test, q1):.4f}・3着内の当て分け {l3(test, q3):.5f}・1番手の1着率 {top1(test, q1):.2f}%")
        print(f"     新馬戦 {l1(test, q1, shin):.4f}（1番手の1着率 {top1(test, q1, shin):.1f}%）・初めての芝ダ {l1(test, q1, (test['初芝ダ'] == 1).values):.4f}"
              f"・初めての距離の帯 {l1(test, q1, (test['初距'] == 1).values):.4f}", flush=True)
    m = ~np.isnan(test['単勝オッズ'].values)
    q = 1 / test['単勝オッズ'].values; q = q / pd.Series(q).groupby(test['g'].values).transform('sum').values
    print(f"  （市場）1着の当て分け {l1(test, q):.4f}・新馬戦 {l1(test, q, shin):.4f}（1番手の1着率 {top1(test, q, shin):.1f}%）")
