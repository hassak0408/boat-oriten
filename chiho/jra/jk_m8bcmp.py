"""M8b のくらべ（h・mg の出どころも替える。名前は「順を学ぶモデル:HGBと着差」。例 EV:m7 EV2:m7 EV:EV EV2:EV2）。もとは M8 のくらべ（検証計画「的中率の研究：M8」）。jk_m8.py の見込み（rel＝M7・E・V・EV）に、m7_pred の HGBの3着内（h）と着差のモデル（mg）を合わせ、
今の一覧と同じ形（1着 ∝ 順を学ぶモデルの1着^a × HGBの3着内^b、3着内 ∝（順を学ぶモデルの3着内。中央で初めて走る馬だけ HGB）^c × exp(−f×着差)）で、
2021〜2023年で決めて2024〜2026年に当てる、と逆向き。使い方：python jk_m8cmp.py STORE [m8（見込みの名前）] [くらべる名前…]"""
import sys, glob, numpy as np, pandas as pd
from scipy.optimize import minimize

ST = sys.argv[1]; NM = sys.argv[2] if len(sys.argv) > 2 else 'm8'
KEY = ['年月日', '場', 'R']
rd = lambda pat: pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(pat))], ignore_index=True)
D = rd(f'{ST}/jra/exp/{NM}_pred_*.csv.gz')
V = sys.argv[3:] or ['EV:m7', 'EV2:m7', 'EV:EV', 'EV2:EV2']
M7 = rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz')[KEY + ['馬番', 'h', 'mg']].rename(columns={'h': 'h_m7', 'mg': 'mg_m7'})
n0 = len(D); D = D.merge(M7, on=KEY + ['馬番'], how='inner'); print('行', n0, '→ M7 と合う行', len(D))
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())]
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
gsum = lambda v, g: pd.Series(v).groupby(g).transform('sum').values
n3 = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / gsum(v, X['g'].values), 1e-4, 0.97)
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
for v in V:
    pv, hv = v.split(':')
    hh = n3(D, D['h_' + hv].values); D['lh_' + v] = np.log(hh)
    D['m_' + v] = D['mg_' + hv] - D.groupby('g')['mg_' + hv].transform('mean')
    p = D[f'p1_{pv}'].values; D['l1_' + v] = np.log(np.clip(p / gsum(p, G), 1e-6, 1))
    D['m3_' + v] = n3(D, np.where(first, hh, n3(D, D[f'p3_{pv}'].values)))
print('レース', D['g'].nunique(), '（2021〜23', D.loc[D['年'] <= 2023, 'g'].nunique(), '・2024〜26', D.loc[D['年'] >= 2024, 'g'].nunique(), '）')


def p1of(X, v, w):
    s = w[0] * X['l1_' + v].values + w[1] * X['lh_' + v].values
    g = X['g'].values; s = s - pd.Series(s).groupby(g).transform('max').values
    x = np.exp(s); return x / gsum(x, g)


def p3of(X, v, c, f): return n3(X, X['m3_' + v].values ** c * np.exp(-f * X['m_' + v].values))
def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
def rk(X, p): return pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
def top1(X, p): return X['勝'].values[rk(X, p) == 1].mean() * 100
def top3(X, p): return X['3着内'].values[rk(X, p) <= 3].mean() * 100


NMo = dict(method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7, 'maxiter': 2000})
A = D[D['年'] <= 2023].reset_index(drop=True); B = D[D['年'] >= 2024].reset_index(drop=True)
LABS = ('→24〜26', '→21〜23'); res = {}
for fit, test, lab in ((A, B, LABS[0]), (B, A, LABS[1])):
    for v in V:
        r1 = minimize(lambda w: l1(fit, p1of(fit, v, w)), [1.0, 0.2], **NMo)
        r3 = minimize(lambda c: l3(fit, p3of(fit, v, c[0], c[1])), [1.0, 0.3], **NMo)
        q1 = p1of(test, v, r1.x); q3 = p3of(test, v, r3.x[0], r3.x[1])
        res[(v, lab)] = (l1(test, q1), l3(test, q3), top1(test, q1), top3(test, q3), ' '.join(f'{x:.3f}' for x in list(r1.x) + list(r3.x)))
print('| | 1着の当て分け →24〜26／→21〜23 | 3着内の当て分け | 1番手の1着率 | 上位3頭の3着内 | 決めた値（a b c f）|'); print('|---|---|---|---|---|---|')
for v in V:
    a, b = res[(v, LABS[0])], res[(v, LABS[1])]
    print(f'| {v} | {a[0]:.5f}／{b[0]:.5f} | {a[1]:.5f}／{b[1]:.5f} | {a[2]:.2f}%／{b[2]:.2f}% | {a[3]:.2f}%／{b[3]:.2f}% | {a[4]} ／ {b[4]} |')
base = V[0]; ok = []
for v in V[1:]:
    d1 = [res[(v, k)][0] - res[(base, k)][0] for k in LABS]; d3 = [res[(v, k)][1] - res[(base, k)][1] for k in LABS]
    good = all(x < 0 for x in d1) and all(x <= 0.00005 for x in d3)
    print(f'{v}：1着の差 {d1[0]:+.5f}・{d1[1]:+.5f}、3着内の差 {d3[0]:+.5f}・{d3[1]:+.5f} →', '条件を満たす' if good else '届かない')
    if good: ok.append((sum(res[(v, k)][0] for k in LABS), v))
print('通ったもの', [v for _, v in sorted(ok)] or 'なし')
pm = (1 / D['単勝オッズ']) / gsum((1 / D['単勝オッズ']).values, G)
for lab, X in (('2021〜23', D['年'] <= 2023), ('2024〜26', D['年'] >= 2024)):
    Y = D[X].reset_index(drop=True); print('市場', lab, '1着の当て分け', round(l1(Y, pm[X].values), 5), '1番人気の1着率', round(top1(Y, pm[X].values), 2), '上位3頭の3着内', round(top3(Y, pm[X].values), 2))
