# JK2 の追記：本番と同じ形の見込み（jk_m8cmp.py の形、値は jra_fix.json）とくらべて、騎手ごとの直しをもう一度確かめる
import glob, json, sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/boat-oriten/chiho/jra'); import jfeat
rng = np.random.default_rng(80)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
C_ = FX['3着内の付け直し']['c']; FM = FX['着差のモデル']['f']
print('本番の値 a', A_, 'b', B_, '初めて', F1, 'c', C_, 'f', FM)
rd = lambda pat: pd.concat([pd.read_csv(f, dtype={k: str for k in K}) for f in sorted(glob.glob(pat))], ignore_index=True)
D = rd(f'{ST}/jra/exp/m8_pred_*.csv.gz'); M7 = rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz')[K + ['馬番', 'h', 'mg']]
D = D.merge(M7, on=K + ['馬番'], how='inner')
J = pd.concat([pd.read_csv(f, dtype=str, usecols=['年月日', '場', 'R', '馬番', '騎手']) for f in sorted(glob.glob(f'{ST}/jra/data/202[1-6]/*_horses.csv.gz'))])
J['R'] = pd.to_numeric(J['R'], errors='coerce').astype('Int64').astype(str); J['馬番'] = pd.to_numeric(J['馬番'], errors='coerce')
J['騎手'] = J['騎手'].map(jfeat.clean_person)
D['R'] = pd.to_numeric(D['R'], errors='coerce').astype('Int64').astype(str); D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
D = D.merge(J.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['h'].notna() & D['騎手'].notna() & (D['騎手'] != '')]
D = D[D.groupby(K)['勝'].transform('sum') == 1].sort_values(K + ['馬番']).reset_index(drop=True)
D['n'] = D.groupby(K)['馬番'].transform('count')
G = [D[k] for k in K]
def n3(v): v = pd.Series(v, index=D.index); return np.clip(v * np.minimum(3, D['n']) / v.groupby(G).transform('sum'), 1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
hh = n3(D['h'].values); m = (D['mg'] - D.groupby(K)['mg'].transform('mean')).values
s1 = A_ * np.log(np.clip(D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum'), 1e-6, 1)).values + B_ * np.log(hh)
s1 = s1 - pd.Series(s1, index=D.index).groupby(G).transform('max').values
x1 = np.exp(s1) * np.where(first, F1, 1.0); D['p1'] = x1 / pd.Series(x1, index=D.index).groupby(G).transform('sum').values
m3 = n3(np.where(first, hh, n3(D['p3_EV'].values))); D['p3'] = n3(m3 ** C_ * np.exp(-FM * m))
D['pm'] = (1 / D['単勝オッズ']).where(D['単勝オッズ'] > 0); D['pm'] = D['pm'] / D.groupby(K)['pm'].transform('sum')
D['期'] = np.where(D['年月日'] <= '20231231', 1, 2)
print('馬', len(D), 'レース', D.groupby(K).ngroups, '騎手', D['騎手'].nunique())
def theta(S, a1, a3):
    g = S.groupby('騎手'); return np.log((g['勝'].sum() + a1) / (g['p1'].sum() + a1)), np.log((g['3着内'].sum() + a3) / (g['p3'].sum() + a3))
def apply(T, t1, t3):
    gg = [T[k] for k in K]
    q1 = T['p1'].values * np.exp(T['騎手'].map(t1).fillna(0.0).values); q1 = q1 / pd.Series(q1, index=T.index).groupby(gg).transform('sum').values
    lo = np.log(T['p3'] / (1 - T['p3'])).values + T['騎手'].map(t3).fillna(0.0).values; q3 = 1 / (1 + np.exp(-lo))
    q3 = np.clip(q3 * np.minimum(3, T['n'].values) / pd.Series(q3, index=T.index).groupby(gg).transform('sum').values, 1e-4, 0.97)
    return q1, q3
def evaluate(a1, a3):
    out = []
    for fit, test in ((1, 2), (2, 1)):
        S = D[D['期'] == fit]; T = D[D['期'] == test].copy(); t1, t3 = theta(S, a1, a3); q1, q3 = apply(T, t1, t3)
        w = (T['勝'] == 1).values; y = T['3着内'].values; p3 = T['p3'].values
        l1a = -np.log(T['p1'].values[w]); l1b = -np.log(q1[w])
        l3a = -(y * np.log(p3) + (1 - y) * np.log(1 - p3)); l3b = -(y * np.log(q3) + (1 - y) * np.log(1 - q3))
        days = T['年月日'].values; ds = np.sort(np.unique(days)); Wt = rng.poisson(1.0, (1000, len(ds)))
        def bd(a, b, dd): ix = np.searchsorted(ds, dd); return (Wt @ np.bincount(ix, a - b, len(ds))) / (Wt @ np.bincount(ix, None, len(ds)))
        b1 = np.percentile(bd(l1b, l1a, days[w]), [2.5, 97.5]); b3 = np.percentile(bd(l3b, l3a, days), [2.5, 97.5])
        gg = [T[k] for k in K]
        ra = pd.Series(p3, index=T.index).groupby(gg).rank(ascending=False, method='first').values; rb = pd.Series(q3, index=T.index).groupby(gg).rank(ascending=False, method='first').values
        out.append(dict(fit=fit, d1=l1b.mean() - l1a.mean(), b1=b1, d3=l3b.mean() - l3a.mean(), b3=b3,
                        top3a=y[ra <= 3].mean() * 100, top3b=y[rb <= 3].mean() * 100, one3a=y[ra == 1].mean() * 100, one3b=y[rb == 1].mean() * 100,
                        mv=float(np.abs(q3 - p3).mean() * 100), mx=float(np.abs(q3 - p3).max() * 100)))
    for r in out:
        print(f"  {r['fit']}で当てはめて{3 - r['fit']}に当てる：1着 {r['d1']:+.5f}（{r['b1'][0]:+.5f}〜{r['b1'][1]:+.5f}）・3着内 {r['d3']:+.5f}（{r['b3'][0]:+.5f}〜{r['b3'][1]:+.5f}）"
              f"・上位3頭の3着内 {r['top3a']:.2f}→{r['top3b']:.2f}%・1番手の3着内 {r['one3a']:.2f}→{r['one3b']:.2f}%・3着内の見込みの動き 平均{r['mv']:.2f}・最大{r['mx']:.1f}ポイント")
    return out
print('本番の形・決めた値（20・50）'); R = evaluate(20, 50)
print('判断：3着内', '効く' if all(r['d3'] < 0 and r['b3'][1] < 0 for r in R) else '効かない', '／1着（入れない。数字だけ）', '0より下' if all(r['d1'] < 0 and r['b1'][1] < 0 for r in R) else '0をまたぐ')
print('数字だけ（100・200）'); evaluate(100, 200)
t1, t3 = theta(D[D['期'] == 2], 20, 50); n = D[D['期'] == 2].groupby('騎手').size()
# 付け直しの前の値（jk2.py の形）で当てはめた θ3 とのくらべ
D2 = D[D['期'] == 2].copy(); D2['p3r'] = np.clip(D2['p3_EV'], 1e-4, 0.97); D2['p3r'] = D2['p3r'] * np.minimum(3, D2['n']) / D2.groupby(K)['p3r'].transform('sum')
g = D2.groupby('騎手'); t3r = np.log((g['3着内'].sum() + 50) / (g['p3r'].sum() + 50))
big = n[n >= 300].index
print('θ3（本番の形）と θ3（付け直しの前）の相関（300騎乗以上）', round(float(np.corrcoef(t3[big], t3r[big])[0, 1]), 3), '・人数', len(big))
lead = n.sort_values(ascending=False).head(8).index
print('騎乗の多い8人の3着内の掛ける値（本番の形／付け直しの前）', {k: (round(float(np.exp(t3[k])), 3), round(float(np.exp(t3r[k])), 3)) for k in lead})
pd.DataFrame({'騎手': t3.index, 'θ3': t3.values, 'θ1': t1.reindex(t3.index).values, '騎乗': n.reindex(t3.index).fillna(0).astype(int).values}).to_csv('/home/claude/work/jk2b_theta_2024_26.csv', index=False)
