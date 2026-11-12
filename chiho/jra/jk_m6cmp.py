"""N5（地方）・M6（中央）のくらべ（検証計画「今の評価を上回れるか」）。nk_m5.py・jk_m6.py の見込みで、base（今の作り方）と
mg（着差のモデルを足す）・td（新しいレースを重く学ぶ）・rel（レースの中での差の材料）を、2021〜2023年で決めて2024〜2026年に当てる、と逆向き。
1着 ∝ 順を学ぶモデルの1着^a × HGBの3着内^b（mg は × exp(−e×m)）、3着内 ∝（順を学ぶモデルの3着内。初めて走る馬だけ HGB）^c（mg は × exp(−f×m)）。
使い方：python jk_m6cmp.py nar "…/nk_m5_pred_*.csv.gz" ／ python jk_m6cmp.py jra "…/m6_pred_*.csv.gz" [出力.pkl（決めた値で作った見込みを残す）]"""
import sys, glob, numpy as np, pandas as pd
from scipy.optimize import minimize

mode = sys.argv[1]
NAR = mode == 'nar'
KEY = ['競馬場', '競走年月日', 'レース番号'] if NAR else ['年月日', '場', 'R']
D = pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(sys.argv[2]))], ignore_index=True)
pre = 'pl_' if NAR else 'p'
if NAR:
    D = D[(D['n'] >= 5) & (D.groupby(KEY)['勝'].transform('sum') >= 1) & (D.groupby(KEY)['馬番'].transform('size') == D['n'])]
    first = lambda X: (X['五場走数'] == 0).values
else:
    D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())]
    first = lambda X: ((X['走数'] == 0) & (X['新馬'] == 0)).values
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True)
D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
gsum = lambda v, g: pd.Series(v).groupby(g).transform('sum').values
n3 = lambda X, v: np.clip(v * np.minimum(3, X['n'].values) / gsum(v, X['g'].values), 1e-4, 0.97)
D['hh'] = n3(D, D['h'].values); D['lh'] = np.log(D['hh'])
D['m'] = D['mg'] - D.groupby('g')['mg'].transform('mean')      # 見込みの着差（レースの平均との差。小さいほど良い）
V = ('base', 'td', 'rel')
for v in V:
    p = D[f'{pre}1_{v}'].values; D['l1_' + v] = np.log(np.clip(p / gsum(p, G), 1e-6, 1))
    D['m3_' + v] = n3(D, np.where(first(D), D['hh'].values, n3(D, D[f'{pre}3_{v}'].values)))
print(mode, 'レース', D['g'].nunique(), '（2021〜2023年', D.loc[D['年'] <= 2023, 'g'].nunique(), '・2024〜2026年', D.loc[D['年'] >= 2024, 'g'].nunique(), '）', flush=True)


def p1of(X, v, w, e=0.0):
    s = w[0] * X['l1_' + v].values + w[1] * X['lh'].values - e * X['m'].values
    g = X['g'].values; s = s - pd.Series(s).groupby(g).transform('max').values
    x = np.exp(s); return x / gsum(x, g)


def p3of(X, v, c, f=0.0): return n3(X, X['m3_' + v].values ** c * np.exp(-f * X['m'].values))
def l1(X, p): return float(-np.log(np.clip(p[X['勝'].values == 1], 1e-6, 1)).mean())
def l3(X, p): y = X['3着内'].values; return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def top1(X, p):
    r = pd.Series(p).groupby(X['g'].values).rank(ascending=False, method='first').values
    return X['勝'].values[r == 1].mean() * 100


NM = dict(method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7, 'maxiter': 2000})
A = D[D['年'].between(2021, 2023)].reset_index(drop=True); B = D[D['年'].between(2024, 2026)].reset_index(drop=True)
res, keep = {}, {}
for fit, test, lab in ((A, B, '→24〜26'), (B, A, '→21〜23')):
    for nm in ('base', 'mg', 'td', 'rel'):
        v = 'base' if nm == 'mg' else nm
        if nm == 'mg':
            r1 = minimize(lambda w: l1(fit, p1of(fit, v, w[:2], w[2])), [1.0, 0.2, 0.0], **NM)
            r3 = minimize(lambda c: l3(fit, p3of(fit, v, c[0], c[1])), [1.0, 0.0], **NM)
            q1 = p1of(test, v, r1.x[:2], r1.x[2]); q3 = p3of(test, v, r3.x[0], r3.x[1])
        else:
            r1 = minimize(lambda w: l1(fit, p1of(fit, v, w)), [1.0, 0.2], **NM)
            r3 = minimize(lambda c: l3(fit, p3of(fit, v, c[0])), [1.0], **NM)
            q1 = p1of(test, v, r1.x); q3 = p3of(test, v, r3.x[0])
        res[(nm, lab)] = (l1(test, q1), l3(test, q3), top1(test, q1), ' '.join(f'{x:.3f}' for x in list(r1.x) + list(r3.x)))
        keep[(nm, lab)] = (q1, q3)
print('| | 1着の当て分け →24〜26／→21〜23 | 3着内の当て分け | 1番手の1着率 | 決めた値（a b [e] c [f]）|')
for nm in ('base', 'mg', 'td', 'rel'):
    a, b = res[(nm, '→24〜26')], res[(nm, '→21〜23')]
    print(f'| {nm} | {a[0]:.5f}／{b[0]:.5f} | {a[1]:.5f}／{b[1]:.5f} | {a[2]:.1f}%／{b[2]:.1f}% | {a[3]} ／ {b[3]} |')
LABS = ('→24〜26', '→21〜23'); ok = []
for nm in ('mg', 'td', 'rel'):
    d1 = [res[(nm, k)][0] - res[('base', k)][0] for k in LABS]; d3 = [res[(nm, k)][1] - res[('base', k)][1] for k in LABS]
    good = all(x < 0 for x in d1) and all(x <= 0.00005 for x in d3)
    print(f'{nm}：1着の差 {d1[0]:+.5f}・{d1[1]:+.5f}、3着内の差 {d3[0]:+.5f}・{d3[1]:+.5f} →', '条件を満たす' if good else '届かない')
    if good: ok.append(nm)
print('通ったもの', ok or 'なし')
if not NAR:
    pm = (1 / D['単勝オッズ']) / gsum((1 / D['単勝オッズ']).values, G)
    for lab, X in (('2021〜23', D['年'] <= 2023), ('2024〜26', D['年'] >= 2024)):
        print('市場の1着の当て分け', lab, round(l1(D[X], pm[X].values), 5))
if len(sys.argv) > 3:
    pd.to_pickle({'D': D, 'res': res}, sys.argv[3])
