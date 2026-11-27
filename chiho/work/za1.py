# ZA1：中央の市場のずれ（Z2 の f）に、AI を足せるか（検証計画 ZA1）。AI は bl1.py と同じ本番の形の1着の見込み
import glob, json, numpy as np, pandas as pd
from scipy.optimize import minimize
rng = np.random.default_rng(85)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
def rd(pat, **kw): return pd.concat([pd.read_csv(f, **kw) for f in sorted(glob.glob(pat))], ignore_index=True)
def fixk(X):
    X['R'] = pd.to_numeric(X['R'], errors='coerce').astype('Int64').astype(str); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['年月日'] = X['年月日'].astype(str); return X
D = fixk(rd(f'{ST}/jra/exp/m8_pred_*.csv.gz', dtype={k: str for k in K}))
M7 = fixk(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz', dtype={k: str for k in K})[K + ['馬番', 'h']])
D = D.merge(M7, on=K + ['馬番'], how='inner'); D = D[D['p1_EV'].notna() & D['h'].notna()]
D['nn'] = D.groupby(K)['馬番'].transform('count'); G = [D[k] for k in K]
hv = D['h'].clip(1e-4, 0.97); hh = (hv * np.minimum(3, D['nn']) / hv.groupby(G).transform('sum')).clip(1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
s1 = A_ * np.log(np.clip(D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum'), 1e-6, 1)).values + B_ * np.log(hh)
s1 = s1 - pd.Series(s1, index=D.index).groupby(G).transform('max').values
x1 = np.exp(s1) * np.where(first, F1, 1.0); D['ai'] = x1 / pd.Series(x1, index=D.index).groupby(G).transform('sum').values
Z = fixk(rd(f'{ST}/jra/exp/z2_pred_*.csv.gz', dtype={k: str for k in K})[K + ['馬番', 'pm', 'f_z2', '勝']])
X = Z.merge(D[K + ['馬番', 'ai']], on=K + ['馬番'], how='inner')
X = X[X['pm'].notna() & X['f_z2'].notna() & X['ai'].notna() & (X['pm'] > 0)]
X = X[(X.groupby(K)['勝'].transform('sum') == 1)]
full = Z.groupby(K)['馬番'].transform('count'); Z['_n'] = full
X = X.merge(Z.drop_duplicates(K)[K + ['_n']], on=K, how='left'); X = X[X.groupby(K)['馬番'].transform('count') == X['_n']]   # レースの全部の馬がそろうレースだけ
for c in ('pm', 'ai'): X[c] = X[c] / X.groupby(K)[c].transform('sum')
X = X.sort_values(K + ['馬番']).reset_index(drop=True); X['_r'] = X.groupby(K).ngroup(); X['期'] = np.where(X['年月日'] <= '20231231', 1, 2)
print('レース', X['_r'].nunique(), '頭', len(X), '（2021〜23', X.loc[X['期'] == 1, '_r'].nunique(), '・2024〜26', X.loc[X['期'] == 2, '_r'].nunique(), '）')
def prep(S, F):
    idx = np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]])
    cols = {'lpm': np.log(S['pm'].clip(1e-6).values), 'f': S['f_z2'].values, 'lai': np.log(S['ai'].clip(1e-6).values)}
    return np.c_[[cols[c] for c in F]].T, idx, S['勝'].values == 1
def lq(th, M, idx):
    u = M @ th; rep = np.diff(np.append(idx, len(u))); mm = np.maximum.reduceat(u, idx); s_ = np.add.reduceat(np.exp(u - np.repeat(mm, rep)), idx); return u - np.repeat(mm + np.log(s_), rep)
def fit(S, F):
    M, idx, y = prep(S, F); return minimize(lambda th: -lq(th, M, idx)[y].sum() / len(idx), np.r_[1.0, np.zeros(len(F) - 1)], method='L-BFGS-B').x
ok = []
for a, b in ((1, 2), (2, 1)):
    S, T = X[X['期'] == a], X[X['期'] == b]
    t0 = fit(S, ['lpm', 'f']); t1 = fit(S, ['lpm', 'f', 'lai'])
    M0, idx, y = prep(T, ['lpm', 'f']); M1, _, _ = prep(T, ['lpm', 'f', 'lai']); Mm, _, _ = prep(T, ['lpm'])
    l0 = -lq(t0, M0, idx)[y]; l1 = -lq(t1, M1, idx)[y]; lm = -lq(np.array([1.0]), Mm, idx)[y]
    dd = T['年月日'].values[idx]; ds = np.sort(np.unique(dd)); ix = np.searchsorted(ds, dd); W = rng.poisson(1.0, (1000, len(ds)))
    diff = (W @ np.bincount(ix, l1 - l0, len(ds))) / (W @ np.bincount(ix, None, len(ds))); ci = np.percentile(diff, [2.5, 97.5])
    print(f'{a}で決めて{b}に当てる：市場だけ {lm.mean():.5f}・市場＋f {l0.mean():.5f}（β {t0[0]:.3f}・γ {t0[1]:.3f}）・市場＋f＋AI {l1.mean():.5f}（β {t1[0]:.3f}・γ {t1[1]:.3f}・α {t1[2]:.3f}）／AIを足した差 {l1.mean() - l0.mean():+.5f}（95%幅 {ci[0]:+.5f}〜{ci[1]:+.5f}）')
    ok.append(l1.mean() < l0.mean() and ci[1] < 0)
    P = X[X['期'] == b].copy(); thr = P['f_z2'].quantile(0.9); top = P[P['f_z2'] >= thr].copy(); top['r'] = top['ai'] / top['pm']
    for nm, g in (('AIも高い（AI÷人気≥1.2）', top[top['r'] >= 1.2]), ('それ以外', top[top['r'] < 1.2])):
        print(f'   数字だけ：f の上位10%・{nm} {len(g)}頭：1着の実際÷人気 {g["勝"].sum() / g["pm"].sum():.3f}')
print('判断：', 'Z2 に AI を足せる' if all(ok) else 'Z2 に AI は足せない')
