# EM2：中央の昼の見直し（E1 当日の馬体重の増減＋E2 その日の内の有利さ）（検証計画 EM2）
import glob, json, sys, numpy as np, pandas as pd
from scipy.optimize import minimize
sys.path.insert(0, '/home/claude/boat-oriten/chiho/jra')
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
C_ = FX['3着内の付け直し']['c']; FM = FX['着差のモデル']['f']
def rd(pat, **kw): return pd.concat([pd.read_csv(f, **kw) for f in sorted(glob.glob(pat))], ignore_index=True)
def fixk(X):
    X['R'] = pd.to_numeric(X['R'], errors='coerce').astype('Int64').astype(str); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['年月日'] = X['年月日'].astype(str); return X
# 本番の形の見込み（JK2 の追記と同じ）
D = fixk(rd(f'{ST}/jra/exp/m8_pred_*.csv.gz', dtype={k: str for k in K}))
M7 = fixk(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz', dtype={k: str for k in K})[K + ['馬番', 'h', 'mg']])
D = D.merge(M7, on=K + ['馬番'], how='inner')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['h'].notna()]
D = D[D.groupby(K)['勝'].transform('sum') == 1].sort_values(K + ['馬番']).reset_index(drop=True)
D['nn'] = D.groupby(K)['馬番'].transform('count'); G = [D[k] for k in K]
def n3(v): v = pd.Series(v, index=D.index); return np.clip(v * np.minimum(3, D['nn']) / v.groupby(G).transform('sum'), 1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
hh = n3(D['h'].values); m = (D['mg'] - D.groupby(K)['mg'].transform('mean')).values
s1 = A_ * np.log(np.clip(D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum'), 1e-6, 1)).values + B_ * np.log(hh)
s1 = s1 - pd.Series(s1, index=D.index).groupby(G).transform('max').values
x1 = np.exp(s1) * np.where(first, F1, 1.0); D['p1'] = x1 / pd.Series(x1, index=D.index).groupby(G).transform('sum').values
m3 = n3(np.where(first, hh, n3(D['p3_EV'].values))); D['p3'] = n3(m3 ** C_ * np.exp(-FM * m))
# 当日の馬体重・増減、芝ダ
W = fixk(rd(f'{ST}/jra/data/202[1-6]/*_horses.csv.gz', dtype=str, usecols=K + ['馬番', '馬体重', '増減']))
W['z'] = pd.to_numeric(W['増減'].astype(str).str.replace('+', '', regex=False), errors='coerce'); W['体重あり'] = pd.to_numeric(W['馬体重'], errors='coerce').notna()
Hd = fixk(rd(f'{ST}/jra/exp/hdump_20*.csv.gz', dtype={k: str for k in K}, usecols=K + ['馬番', '芝ダ']))
D = D.merge(W[K + ['馬番', 'z', '体重あり']].drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left').merge(Hd.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D = D[D['芝ダ'].isin(['芝', 'ダート'])].copy()   # 過去の表の書き方は「芝」「ダート」（最初は「ダ」と取り違えて芝だけになっていた）
print('芝ダ', D.drop_duplicates(K)['芝ダ'].value_counts().to_dict())
D['期'] = np.where(D['年月日'] <= '20231231', 1, 2)
z = D['z']
D['e_m10'] = (z <= -10).astype(float); D['e_m4'] = ((z >= -9) & (z <= -4)).astype(float); D['e_p4'] = ((z >= 4) & (z <= 9)).astype(float); D['e_p10'] = (z >= 10).astype(float)
D['e_none'] = (D['体重あり'].fillna(False).astype(bool) & z.isna()).astype(float)
# E2：同じ日・同じ場・同じ芝ダの前のレースの、内の有利さ
D['nn'] = D.groupby(K)['馬番'].transform('count')
D['内'] = (D['馬番'] <= D['nn'] / 3).astype(float); D['外'] = (D['馬番'] > D['nn'] * 2 / 3).astype(float)
D['resid'] = D['3着内'] - D['p3']
gi = D[D['内'] == 1].groupby(K)['resid'].mean(); go = D[D['外'] == 1].groupby(K)['resid'].mean()
R = pd.DataFrame({'内差': gi - go}).reset_index().merge(D.drop_duplicates(K)[K + ['芝ダ']], on=K, how='left')
R['Rn'] = pd.to_numeric(R['R'], errors='coerce'); R = R.sort_values(['場', '年月日', '芝ダ', 'Rn'])
g = R.groupby(['場', '年月日', '芝ダ'])
R['累'] = g['内差'].transform(lambda x: x.fillna(0).shift(1).expanding().sum()); R['数'] = g['内差'].transform(lambda x: x.notna().astype(float).shift(1).expanding().sum())
R['m'] = g.cumcount()
R['内の有利さ'] = np.where(R['数'] > 0, R['累'] / R['数'].clip(lower=1), 0.0) * R['m'] / (R['m'] + 3)
D = D.merge(R[K + ['内の有利さ']], on=K, how='left').fillna({'内の有利さ': 0.0})
D['x_in'] = D['内'] * D['内の有利さ']
D = D.sort_values(K + ['馬番']).reset_index(drop=True); D['_r'] = D.groupby(K).ngroup()
def nll(th, X, idx, lp, y):
    u = lp + X @ th; mm = np.maximum.reduceat(u, idx); rep = np.diff(np.append(idx, len(u)))
    s_ = np.add.reduceat(np.exp(u - np.repeat(mm, rep)), idx); return -np.sum((u - np.repeat(mm + np.log(s_), rep))[y]) / len(idx)
def prep(S, F):
    S = S.sort_values(['_r', '馬番']); idx = np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]])
    return S[F].values.astype(float), idx, np.log(S['p1'].clip(1e-6).values), (S['勝'].values == 1)
def fit(S, F): X, idx, lp, y = prep(S, F); return minimize(nll, np.zeros(len(F)), args=(X, idx, lp, y), method='L-BFGS-B').x
def score(S, th, F): X, idx, lp, y = prep(S, F); return nll(np.zeros(len(F)), X, idx, lp, y), nll(th, X, idx, lp, y)
def ll3(S, th, F):
    p3 = S['p3'].clip(1e-4, 0.97).values; lo = np.log(p3 / (1 - p3)) + S[F].values @ th; q = 1 / (1 + np.exp(-lo)); gg = [S[k] for k in K]
    q = np.clip(q * np.minimum(3, S['nn'].values) / pd.Series(q, index=S.index).groupby(gg).transform('sum').values, 1e-4, 0.97); y = S['3着内'].values
    f_ = lambda v: -np.mean(y * np.log(v) + (1 - y) * np.log(1 - v)); return f_(p3), f_(q)
F_all = ['e_m10', 'e_m4', 'e_p4', 'e_p10', 'e_none', 'x_in']
print('馬', len(D), 'レース', D['_r'].nunique(), '／体重の帯', {c: int(D[c].sum()) for c in F_all[:5]}, '／内の有利さが0でない', round(float((D['内の有利さ'] != 0).mean()), 3), '／増減なし（体重もなし）', int((D['z'].isna() & ~D['体重あり'].fillna(False).astype(bool)).sum()))
res = {}
for nm, F in (('全部', F_all), ('E1だけ', F_all[:5]), ('E2だけ', ['x_in'])):
    for a, b in ((1, 2), (2, 1)):
        th = fit(D[D['期'] == a], F); b0, b1 = score(D[D['期'] == b], th, F); c0, c1 = ll3(D[D['期'] == b], th, F)
        res[(nm, a)] = b1 - b0
        print(f'{nm}：{a}で決めて{b}に当てる θ', dict(zip(F, np.round(th, 3))), f'／1着 {b0:.5f}→{b1:.5f}（{b1 - b0:+.5f}）／3着内 {c0:.5f}→{c1:.5f}（{c1 - c0:+.5f}）')
ok = res[('全部', 1)] <= -0.001 and res[('全部', 2)] <= -0.001
print('判断：', '入れる' if ok else '入れない')
th = fit(D, F_all); print('全部の期間で決めた θ', dict(zip(F_all, np.round(th, 4))), '／体重の帯の掛ける値', {c: round(float(np.exp(t)), 3) for c, t in zip(F_all[:5], th[:5])})
json.dump({'θ': dict(zip(F_all, [round(float(t), 5) for t in th]))}, open('/home/claude/work/em2_theta.json', 'w'), ensure_ascii=False)
