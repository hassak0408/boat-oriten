# EM1：地方の昼の見直し（E1 当日の馬体重＋E2 その日の内・前の有利さ）の値を決め直す（検証計画 EM1）
import glob, json, numpy as np, pandas as pd
from scipy.optimize import minimize
ST = '/home/claude/chiho-keiba'
K = ['競馬場', '競走年月日', 'レース番号']
def s(v): return pd.to_numeric(v, errors='coerce').astype('Int64').astype(str)
# 元の見込み（N6：pl_1_EV・pl_3_EV）
B = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_m6_pred_*.csv.gz'))])
for c in ('レース番号', '馬番'): B[c] = s(B[c])
for c in ('pl_1_EV', 'pl_3_EV', '勝', '3着内', 'n'): B[c] = pd.to_numeric(B[c], errors='coerce')
B = B.dropna(subset=['pl_1_EV', 'pl_3_EV']).drop_duplicates(K + ['馬番'])
# 馬体重の増減（月ごとの出馬表）
W = pd.concat([pd.read_csv(f, dtype=str, usecols=['競馬場', '競走年月日', 'レース番号', '馬番', '馬体重', '馬体重増減']) for f in sorted(glob.glob(f'{ST}/data/race/202[1-6]*/02_*horselist*.csv.gz'))])
for c in ('レース番号', '馬番'): W[c] = s(W[c])
W['増減'] = pd.to_numeric(W['馬体重増減'].astype(str).str.replace('+', '', regex=False), errors='coerce'); W['体重あり'] = pd.to_numeric(W['馬体重'], errors='coerce').notna()
# 先行率5（過去の表の書き出し）
Hd = pd.concat([pd.read_csv(f, dtype=str, usecols=K + ['馬番', '先行率5']) for f in sorted(glob.glob(f'{ST}/data/exp/nk_hdump_*.csv.gz'))])
for c in ('レース番号', '馬番'): Hd[c] = s(Hd[c])
Hd['先行率5'] = pd.to_numeric(Hd['先行率5'], errors='coerce')
D = B.merge(W[K + ['馬番', '増減', '体重あり']].drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left').merge(Hd.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D = D[D.groupby(K)['勝'].transform('sum') == 1].copy()
D['p1'] = D['pl_1_EV'] / D.groupby(K)['pl_1_EV'].transform('sum')
D['p3'] = D['pl_3_EV']
D['期'] = np.where(D['競走年月日'] <= '20231231', 1, 2)
# E1 の帯
z = D['増減']
D['e_m10'] = ((z <= -10)).astype(float); D['e_m4'] = ((z >= -9) & (z <= -4)).astype(float); D['e_p4'] = ((z >= 4) & (z <= 9)).astype(float); D['e_p10'] = ((z >= 10)).astype(float)
D['e_none'] = (D['体重あり'] & z.isna()).astype(float)
# E2：内・前の馬（今のレースの中で）
D['馬番n'] = pd.to_numeric(D['馬番'], errors='coerce'); D['nn'] = D.groupby(K)['馬番n'].transform('count')
D['内'] = (D['馬番n'] <= D['nn'] / 3).astype(float); D['外'] = (D['馬番n'] > D['nn'] * 2 / 3).astype(float)
D['先行順'] = D.groupby(K)['先行率5'].rank(ascending=False, method='first'); D['前'] = (D['先行順'] <= D['nn'] / 3).astype(float)
D['resid'] = D['3着内'] - D['p3']
R = D.groupby(K).apply(lambda X: pd.Series({'内差': X.loc[X['内'] == 1, 'resid'].mean() - X.loc[X['外'] == 1, 'resid'].mean(), '前差': X.loc[X['前'] == 1, 'resid'].mean() - X.loc[X['前'] == 0, 'resid'].mean()})).reset_index()
R['Rn'] = pd.to_numeric(R['レース番号'], errors='coerce'); R = R.sort_values(['競馬場', '競走年月日', 'Rn'])
g = R.groupby(['競馬場', '競走年月日'])
for c in ('内差', '前差'):
    R[c + '累'] = g[c].transform(lambda x: x.fillna(0).shift(1).expanding().sum()); R[c + '数'] = g[c].transform(lambda x: x.notna().astype(float).shift(1).expanding().sum())
R['m'] = g.cumcount()
for c in ('内差', '前差'): R[c.replace('差', 'の有利さ')] = np.where(R[c + '数'] > 0, R[c + '累'] / R[c + '数'].clip(lower=1), 0.0) * R['m'] / (R['m'] + 3)
D = D.merge(R[K + ['内の有利さ', '前の有利さ']], on=K, how='left').fillna({'内の有利さ': 0.0, '前の有利さ': 0.0})
D['x_in'] = D['内'] * D['内の有利さ']; D['x_fr'] = D['前'] * D['前の有利さ']
F = ['e_m10', 'e_m4', 'e_p4', 'e_p10', 'e_none', 'x_in', 'x_fr']
D = D.sort_values(K + ['馬番n']).reset_index(drop=True); D['_r'] = D.groupby(K).ngroup()
def nll(th, X, idx, lp, y):
    u = lp + X @ th; m = np.maximum.reduceat(u, idx); e = np.exp(u - np.repeat(m, np.diff(np.append(idx, len(u)))))
    s_ = np.add.reduceat(e, idx); return -(u[y] - m - np.log(s_)).mean() if False else -np.sum((u - np.repeat(m + np.log(s_), np.diff(np.append(idx, len(u)))))[y]) / len(idx)
def prep(S):
    S = S.sort_values(['_r', '馬番n']); idx = np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]])
    return S[F].values.astype(float), idx, np.log(S['p1'].clip(1e-6).values), (S['勝'].values == 1)
def fit(S):
    X, idx, lp, y = prep(S); r = minimize(nll, np.zeros(len(F)), args=(X, idx, lp, y), method='L-BFGS-B'); return r.x
def score(S, th):
    X, idx, lp, y = prep(S); return nll(np.zeros(len(F)), X, idx, lp, y), nll(th, X, idx, lp, y)
def ll3(S, th):
    p3 = S['p3'].clip(1e-4, 0.97).values; lo = np.log(p3 / (1 - p3)) + S[F].values @ th; q = 1 / (1 + np.exp(-lo))
    q = q * np.minimum(3, S['nn'].values) / pd.Series(q, index=S.index).groupby([S[k] for k in K]).transform('sum').values; q = np.clip(q, 1e-4, 0.97); y = S['3着内'].values
    b = np.clip(p3 * np.minimum(3, S['nn'].values) / pd.Series(p3, index=S.index).groupby([S[k] for k in K]).transform('sum').values, 1e-4, 0.97)
    f_ = lambda v: -np.mean(y * np.log(v) + (1 - y) * np.log(1 - v)); return f_(b), f_(q)
print('馬', len(D), 'レース', D['_r'].nunique(), '／体重の帯', {c: int(D[c].sum()) for c in F[:5]}, '／内の有利さが0でない', round(float((D['内の有利さ'] != 0).mean()), 3))
out = {}
for a, b in ((1, 2), (2, 1)):
    th = fit(D[D['期'] == a]); b0, b1 = score(D[D['期'] == b], th); c0, c1 = ll3(D[D['期'] == b], th)
    out[f'{a}→{b}'] = th
    print(f'{a}で決めて{b}に当てる：θ', dict(zip(F, np.round(th, 3))), f'／1着の当て分け {b0:.5f}→{b1:.5f}（{b1 - b0:+.5f}）／3着内 {c0:.5f}→{c1:.5f}（{c1 - c0:+.5f}）')
th = fit(D); print('全部で決めた θ', dict(zip(F, np.round(th, 4))), '／掛ける値（体重の帯）', {c: round(float(np.exp(t)), 3) for c, t in zip(F[:5], th[:5])})
json.dump({'θ': dict(zip(F, [round(float(t), 5) for t in th])), '1→2': dict(zip(F, [round(float(t), 5) for t in out['1→2']])), '2→1': dict(zip(F, [round(float(t), 5) for t in out['2→1']]))}, open('/home/claude/work/em1_theta.json', 'w'), ensure_ascii=False)
