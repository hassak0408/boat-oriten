# JK2：中央の騎手の見方の直し（検証計画 JK2）。M8 の見込みに騎手ごとの係数を掛けて、もう一方の期間で当て分けが良くなるか
import glob, numpy as np, pandas as pd
rng = np.random.default_rng(79)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
def s(v): return pd.to_numeric(v, errors='coerce').astype('Int64').astype(str)
M = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/m8_pred_*.csv.gz'))])
for c in ('R', '馬番'): M[c] = s(M[c])
for c in ('p1_EV', 'p3_EV', '勝', '3着内', '単勝オッズ', 'n'): M[c] = pd.to_numeric(M[c], errors='coerce')
J = pd.concat([pd.read_csv(f, dtype=str, usecols=['年月日', '場', 'R', '馬番', '騎手']) for f in sorted(glob.glob(f'{ST}/jra/data/202[1-6]/*_horses.csv.gz'))])
for c in ('R', '馬番'): J[c] = s(J[c])
J['騎手'] = J['騎手'].fillna('').str.replace(' ', '').str.replace('　', '')
J.loc[J['騎手'].str.contains('島克駿'), '騎手'] = '鮫島克駿'
D = M.merge(J.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['騎手'].notna() & (D['騎手'] != '')]
D = D[D.groupby(K)['勝'].transform('sum') == 1].copy()
D['p1'] = D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum')
D['p3'] = D['p3_EV'].clip(1e-4, 0.97); D['nn'] = D.groupby(K)['馬番'].transform('count')
D['p3'] = (D['p3'] * np.minimum(3, D['nn']) / D.groupby(K)['p3'].transform('sum')).clip(1e-4, 0.97)
D['pm'] = (1 / D['単勝オッズ']).where(D['単勝オッズ'] > 0); D['pm'] = D['pm'] / D.groupby(K)['pm'].transform('sum')
D['期'] = np.where(D['年月日'] <= '20231231', 1, 2)
print('馬', len(D), 'レース', D.groupby(K).ngroups, '騎手', D['騎手'].nunique(), '年', D['年月日'].min(), D['年月日'].max())
def theta(S, a1, a3):
    g = S.groupby('騎手'); t1 = np.log((g['勝'].sum() + a1) / (g['p1'].sum() + a1)); t3 = np.log((g['3着内'].sum() + a3) / (g['p3'].sum() + a3)); return t1, t3
def apply(T, t1, t3, col='p1'):
    x1 = T['騎手'].map(t1).fillna(0.0).values; x3 = T['騎手'].map(t3).fillna(0.0).values
    q1 = T[col].values * np.exp(x1); q1 = q1 / pd.Series(q1, index=T.index).groupby([T[k] for k in K]).transform('sum').values
    lo = np.log(T['p3'] / (1 - T['p3'])).values + x3; q3 = 1 / (1 + np.exp(-lo))
    q3 = np.clip(q3 * np.minimum(3, T['nn'].values) / pd.Series(q3, index=T.index).groupby([T[k] for k in K]).transform('sum').values, 1e-4, 0.97)
    return q1, q3
def evaluate(a1, a3, show=True):
    res = []
    for fit, test in ((1, 2), (2, 1)):
        S = D[D['期'] == fit]; T = D[D['期'] == test].copy(); t1, t3 = theta(S, a1, a3); q1, q3 = apply(T, t1, t3)
        w = (T['勝'] == 1).values; y = T['3着内'].values
        l1a = -np.log(T['p1'].values[w]); l1b = -np.log(q1[w])
        l3a = -(y * np.log(T['p3'].values) + (1 - y) * np.log(1 - T['p3'].values)); l3b = -(y * np.log(q3) + (1 - y) * np.log(1 - q3))
        days = T['年月日'].values; ds = np.sort(np.unique(days)); Wt = rng.poisson(1.0, (1000, len(ds)))
        def bd(a, b, dd):
            dix = np.searchsorted(ds, dd); return (Wt @ np.bincount(dix, a - b, len(ds))) / (Wt @ np.bincount(dix, None, len(ds)))
        b1 = bd(l1b, l1a, days[w]); b3 = bd(l3b, l3a, days)
        T['q1'] = q1; top = T.loc[T.groupby(K)['p1'].idxmax()]; topq = T.loc[T.groupby(K)['q1'].idxmax()]
        pm_ok = T['pm'].notna().values
        qm, _ = apply(T[pm_ok].assign(p1=T.loc[pm_ok, 'pm']), t1, t3); wm = (T.loc[pm_ok, '勝'] == 1).values
        lm = (-np.log(qm[wm])).mean() - (-np.log(T.loc[pm_ok, 'pm'].values[wm])).mean()
        res.append((fit, test, l1b.mean() - l1a.mean(), np.percentile(b1, [2.5, 97.5]), l3b.mean() - l3a.mean(), np.percentile(b3, [2.5, 97.5]), top['勝'].mean(), topq['勝'].mean(), lm))
        if show:
            print(f'  {fit}で当てはめて{test}に当てる：1着 {l1b.mean() - l1a.mean():+.5f}（{np.percentile(b1, 2.5):+.5f}〜{np.percentile(b1, 97.5):+.5f}）'
                  f'・3着内 {l3b.mean() - l3a.mean():+.5f}（{np.percentile(b3, 2.5):+.5f}〜{np.percentile(b3, 97.5):+.5f}）・1番手の1着率 {top["勝"].mean() * 100:.2f}→{topq["勝"].mean() * 100:.2f}% ｜ 数字だけ：市場に同じ直し {lm:+.5f}')
    return res
print('決めた値（20・50）'); R = evaluate(20, 50)
ok1 = all(r[2] < 0 and r[3][1] < 0 for r in R); ok3 = all(r[4] < 0 and r[5][1] < 0 for r in R)
print('判断：1着', '効く' if ok1 else '効かない', '／3着内', '効く' if ok3 else '効かない')
for a1, a3 in ((10, 50), (100, 200)): print(f'数字だけ（{a1}・{a3}）'); evaluate(a1, a3)
t1, t3 = theta(D[D['期'] == 2], 20, 50)
g = D[D['期'] == 2].groupby('騎手').size()
big = t1[g[g >= 300].index].sort_values()
print('2024〜26 で当てはめた1着の掛ける値（300騎乗以上）：低い5人', {k: round(float(np.exp(v)), 3) for k, v in big.head(5).items()}, '／高い5人', {k: round(float(np.exp(v)), 3) for k, v in big.tail(5).items()})
pd.DataFrame({'騎手': t1.index, 'θ1': t1.values, 'θ3': t3.reindex(t1.index).values, '騎乗': g.reindex(t1.index).fillna(0).astype(int).values}).to_csv('/home/claude/work/jk2_theta_2024_26.csv', index=False)
