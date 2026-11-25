"""NP1 のくらべ（検証計画「地方の血統を足す（NP1）」）。nk_np1.py の見込み（base＝今の一覧（EV）・ped＝今＋血統）に、nk_m5_pred の HGBの3着内（h）と着差のモデル（mg）を合わせ、
今の一覧と同じ形（1着 ∝ 順を学ぶモデルの1着^a × HGBの3着内^b × exp(−e×着差)、3着内 ∝（順を学ぶモデルの3着内。5場で初めて走る馬だけ HGB）^c × exp(−f×着差)）で、
2021〜2023年で決めて2024〜2026年に当てる、と逆向き。使い方：python nk_m6cmp.py STORE"""
import sys, glob, numpy as np, pandas as pd
from scipy.optimize import minimize

ST = sys.argv[1]
KEY = ['競馬場', '競走年月日', 'レース番号']
rd = lambda pat: pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(pat))], ignore_index=True)
D = rd(f'{ST}/data/exp/nk_np1_pred_*.csv.gz')
V = [c[5:] for c in D.columns if c.startswith('pl_1_')]
M5 = rd(f'{ST}/data/exp/nk_m5_pred_*.csv.gz')[KEY + ['馬番', 'h', 'mg', 'pl_1_base']].rename(columns={'pl_1_base': '_b5'})
n0 = len(D); D = D.merge(M5, on=KEY + ['馬番'], how='inner')
print('行', n0, '→ N5 と合う行', len(D), '／base の1着の見込みが N5 と同じか（差の一番大きい所）', round(float((D['pl_1_base'] - D['_b5']).abs().max()), 6))
D = D[(D['n'] >= 5) & (D.groupby(KEY)['勝'].transform('sum') >= 1) & (D.groupby(KEY)['馬番'].transform('size') == D['n'])]
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
gsum = lambda v, g: pd.Series(v).groupby(g).transform('sum').values
n3 = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / gsum(v, X['g'].values), 1e-4, 0.97)
first = (D['五場走数'] == 0).values
D['hh'] = n3(D, D['h'].values); D['lh'] = np.log(D['hh'])
D['m'] = D['mg'] - D.groupby('g')['mg'].transform('mean')
for v in V:
    p = D[f'pl_1_{v}'].values; D['l1_' + v] = np.log(np.clip(p / gsum(p, G), 1e-6, 1))
    D['m3_' + v] = n3(D, np.where(first, D['hh'].values, n3(D, D[f'pl_3_{v}'].values)))
print('レース', D['g'].nunique(), '（2021〜23', D.loc[D['年'] <= 2023, 'g'].nunique(), '・2024〜26', D.loc[D['年'] >= 2024, 'g'].nunique(), '）')


def p1of(X, v, w):
    s = w[0] * X['l1_' + v].values + w[1] * X['lh'].values - w[2] * X['m'].values
    g = X['g'].values; s = s - pd.Series(s).groupby(g).transform('max').values
    x = np.exp(s); return x / gsum(x, g)


def p3of(X, v, c, f): return n3(X, X['m3_' + v].values ** c * np.exp(-f * X['m'].values))
def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
def rk(X, p): return pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
def top1(X, p): return X['勝'].values[rk(X, p) == 1].mean() * 100
def top3(X, p): return X['3着内'].values[rk(X, p) <= 3].mean() * 100


NMo = dict(method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7, 'maxiter': 3000})
A = D[D['年'] <= 2023].reset_index(drop=True); B = D[D['年'] >= 2024].reset_index(drop=True)
LABS = ('→24〜26', '→21〜23'); res = {}
for fit, test, lab in ((A, B, LABS[0]), (B, A, LABS[1])):
    for v in V:
        r1 = minimize(lambda w: l1(fit, p1of(fit, v, w)), [1.0, 0.2, 0.0], **NMo)
        r3 = minimize(lambda c: l3(fit, p3of(fit, v, c[0], c[1])), [1.0, 0.0], **NMo)
        q1 = p1of(test, v, r1.x); q3 = p3of(test, v, r3.x[0], r3.x[1])
        res[(v, lab)] = (l1(test, q1), l3(test, q3), top1(test, q1), top3(test, q3), ' '.join(f'{x:.3f}' for x in list(r1.x) + list(r3.x)))
print('| | 1着の当て分け →24〜26／→21〜23 | 3着内の当て分け | 1番手の1着率 | 上位3頭の3着内 | 決めた値（a b e c f）|'); print('|---|---|---|---|---|---|')
for v in V:
    a, b = res[(v, LABS[0])], res[(v, LABS[1])]
    print(f'| {v} | {a[0]:.5f}／{b[0]:.5f} | {a[1]:.5f}／{b[1]:.5f} | {a[2]:.2f}%／{b[2]:.2f}% | {a[3]:.2f}%／{b[3]:.2f}% | {a[4]} ／ {b[4]} |')
base = V[0]; ok = []
for v in V[1:]:
    d1 = [res[(v, k)][0] - res[(base, k)][0] for k in LABS]; d3 = [res[(v, k)][1] - res[(base, k)][1] for k in LABS]
    good = all(x <= -0.001 for x in d1) and all(x <= 0.0005 for x in d3)      # NP1 の決めごと：1着は両方で 0.001 以上下がる・3着内は 0.0005 より悪くならない
    print(f'{v}：1着の差 {d1[0]:+.5f}・{d1[1]:+.5f}、3着内の差 {d3[0]:+.5f}・{d3[1]:+.5f} →', '条件を満たす' if good else '届かない')
    if good: ok.append((sum(res[(v, k)][0] for k in LABS), v))
print('通ったもの', [v for _, v in sorted(ok)] or 'なし')
for lab, X in (('2021〜23', A), ('2024〜26', B)):
    r = X['人気'].values; print('1番人気', lab, '1着率', round(X['勝'].values[r == 1].mean() * 100, 2), '1〜3番人気の3着内', round(X['3着内'].values[r <= 3].mean() * 100, 2))

# 数字だけ：このデータで初めて走る馬・2走目の馬だけの1着の当て分け（その馬が勝ったレースだけで数える）
for fit, test, lab in ((A, B, LABS[0]), (B, A, LABS[1])):
    for nm, mk in (('初めて走る馬', test['走数'].values == 0), ('2走目の馬', test['走数'].values == 1)):
        out = []
        for v in V:
            r1 = minimize(lambda w: l1(fit, p1of(fit, v, w)), [1.0, 0.2, 0.0], **NMo); q1 = p1of(test, v, r1.x)
            w = (test['勝'].values == 1) & mk; out.append(float(-np.log(np.clip(q1[w], 1e-6, 1)).mean()))
        print(lab, nm, '勝った', int(((test['勝'].values == 1) & mk).sum()), '｜', '・'.join(f'{v} {x:.4f}' for v, x in zip(V, out)))
