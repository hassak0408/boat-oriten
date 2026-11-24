# BL1：AIと人気を合わせた1着の見込み（検証計画 BL1）。D の作り方は ex1.py と同じ
import glob, json, sys, numpy as np, pandas as pd
from scipy.optimize import minimize
sys.path.insert(0, '/home/claude/boat-oriten/chiho/jra'); import jk_wide
rng = np.random.default_rng(83)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8')); CAL = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_wide_calib.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
C_ = FX['3着内の付け直し']['c']; FM = FX['着差のモデル']['f']
def rd(pat, **kw): return pd.concat([pd.read_csv(f, **kw) for f in sorted(glob.glob(pat))], ignore_index=True)
def fixk(X):
    X['R'] = pd.to_numeric(X['R'], errors='coerce').astype('Int64').astype(str); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['年月日'] = X['年月日'].astype(str); return X
D = fixk(rd(f'{ST}/jra/exp/m8_pred_*.csv.gz', dtype={k: str for k in K}))
M7 = fixk(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz', dtype={k: str for k in K})[K + ['馬番', 'h', 'mg']])
D = D.merge(M7, on=K + ['馬番'], how='inner')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['h'].notna() & (D['単勝オッズ'] > 0)]
D = D[D.groupby(K)['勝'].transform('sum') == 1].sort_values(K + ['馬番']).reset_index(drop=True)
D['nn'] = D.groupby(K)['馬番'].transform('count'); G = [D[k] for k in K]
def n3(v): v = pd.Series(v, index=D.index); return np.clip(v * np.minimum(3, D['nn']) / v.groupby(G).transform('sum'), 1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
hh = n3(D['h'].values)
s1 = A_ * np.log(np.clip(D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum'), 1e-6, 1)).values + B_ * np.log(hh)
s1 = s1 - pd.Series(s1, index=D.index).groupby(G).transform('max').values
x1 = np.exp(s1) * np.where(first, F1, 1.0); D['p1'] = x1 / pd.Series(x1, index=D.index).groupby(G).transform('sum').values
D['pm'] = 1 / D['単勝オッズ']; D['pm'] = D['pm'] / D.groupby(K)['pm'].transform('sum')
Hd = fixk(rd(f'{ST}/jra/exp/hdump_20*.csv.gz', dtype={k: str for k in K}, usecols=K + ['馬番', '前走数']))
D = D.merge(Hd.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D['浅いレース'] = D.groupby(K)['前走数'].transform(lambda s: (s <= 1).mean() >= 0.5)
D['期'] = np.where(D['年月日'] <= '20231231', 1, 2)
D = D.sort_values(K + ['馬番']).reset_index(drop=True); D['_r'] = D.groupby(K).ngroup()
def prep(S):
    idx = np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]])
    X = np.c_[np.log(S['p1'].clip(1e-6).values), np.log(S['pm'].clip(1e-6).values)]; return X, idx, (S['勝'].values == 1)
def per_race(th, X, idx):
    u = X @ th; rep = np.diff(np.append(idx, len(u))); mm = np.maximum.reduceat(u, idx); s_ = np.add.reduceat(np.exp(u - np.repeat(mm, rep)), idx)
    return u - np.repeat(mm + np.log(s_), rep)   # 各馬の log q
def nll(th, X, idx, y): return -per_race(th, X, idx)[y].sum() / len(idx)
def fit(S): X, idx, y = prep(S); return minimize(nll, np.array([0.5, 0.5]), args=(X, idx, y), method='L-BFGS-B').x
def evaluate(S, th):
    X, idx, y = prep(S); days = S['年月日'].values[idx]
    lb = -per_race(th, X, idx)[y]; lm = -per_race(np.array([0.0, 1.0]), X, idx)[y]; la = -per_race(np.array([1.0, 0.0]), X, idx)[y]
    ds = np.sort(np.unique(days)); ix = np.searchsorted(ds, days); W = rng.poisson(1.0, (1000, len(ds)))
    d = (W @ np.bincount(ix, lb - lm, len(ds))) / (W @ np.bincount(ix, None, len(ds)))
    return la.mean(), lm.mean(), lb.mean(), np.percentile(d, [2.5, 97.5])
def p3_from_p1(S, col):
    out = np.empty(len(S)); v = S[col].values; idx = np.r_[np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]]), len(S)]
    for a, b in zip(idx[:-1], idx[1:]):
        p = v[a:b] / v[a:b].sum(); M = jk_wide.pairprob(p, CAL['λ2'], CAL['λ3']); out[a:b] = np.clip(M.sum(1) / 2, 1e-4, 0.97)
    return out
ok = []
for a, b in ((1, 2), (2, 1)):
    th = fit(D[D['期'] == a]); T = D[D['期'] == b].copy(); la, lm, lb, ci = evaluate(T, th)
    print(f'{a}で決めて{b}に当てる：α {th[0]:.3f}・β {th[1]:.3f}／1着の当て分け AIだけ {la:.5f}・人気だけ {lm:.5f}・合わせて {lb:.5f}（人気だけとの差 {lb - lm:+.5f}、95%幅 {ci[0]:+.5f}〜{ci[1]:+.5f}）')
    ok.append(lb < lm and ci[1] < 0)
    th2 = fit(D[(D['期'] == a) & D['浅いレース']]); T2 = T[T['浅いレース']]; la2, lm2, lb2, ci2 = evaluate(T2, th2)
    print(f'   数字だけ（浅いレース {T2["_r"].nunique()}）：α {th2[0]:.3f}・β {th2[1]:.3f}／AIだけ {la2:.5f}・人気だけ {lm2:.5f}・合わせて {lb2:.5f}（{lb2 - lm2:+.5f}、{ci2[0]:+.5f}〜{ci2[1]:+.5f}）')
    X, idx, y = prep(T); T['q'] = np.exp(per_race(th, X, idx))
    y3 = T['3着内'].values; f_ = lambda v: -np.mean(y3 * np.log(v) + (1 - y3) * np.log(1 - v))
    print(f'   数字だけ（3着内、ハービル型）：AIだけ {f_(p3_from_p1(T, "p1")):.5f}・人気だけ {f_(p3_from_p1(T, "pm")):.5f}・合わせて {f_(p3_from_p1(T, "q")):.5f}')
print('判断：', 'AIは人気に足せる情報を持っている' if all(ok) else '1着については、AIは人気に足せる情報がない')
th = fit(D); print('全部の期間で決めた α・β', np.round(th, 4))
json.dump({'α': round(float(th[0]), 5), 'β': round(float(th[1]), 5)}, open('/home/claude/work/bl1_theta.json', 'w'), ensure_ascii=False)
