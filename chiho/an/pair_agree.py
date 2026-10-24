"""モデルの組と人気の組が同じレース・違うレースの当たり方（馬連、2021〜2026年）。見方だけ。"""
import numpy as np, pandas as pd
from itertools import combinations
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '着', '人気', 'n', '年']]; H['馬番'] = H['馬番'].astype(float)
C = pd.read_pickle('/tmp/chiho_cand3_朝3.pkl'); C['馬番'] = C['馬番'].astype(float)
D = H[H['年'] >= 2021].merge(C, on=KEY + ['馬番']); D = D[D['n'] >= 5]
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
rows = []
for k, g in D.groupby(KEY, sort=False):
    fin = g['着'].values
    if (fin <= 2).sum() < 2: continue
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum(); top2 = frozenset(nums[fin <= 2])
    P = {frozenset((nums[i], nums[j])): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    m3 = sorted(P, key=P.get, reverse=True)[:3]
    pr = nums[np.argsort(g['人気'].values)]
    q1 = frozenset(pr[:2]); q3 = [frozenset((pr[0], pr[1])), frozenset((pr[0], pr[2])), frozenset((pr[1], pr[2]))]
    rows.append(dict(年=int(g['年'].iloc[0]), 一致=m3[0] == q1, モデル1点=m3[0] == top2, 人気1点=q1 == top2,
                     重なり=len(set(m3) & set(q3)), 合わせた点=len(set(m3) | set(q3)), 合わせて的中=top2 in (set(m3) | set(q3))))
R = pd.DataFrame(rows)
print('レース', len(R))
t = R.groupby('一致').agg(レース=('年', 'size'), モデル1点の的中=('モデル1点', 'mean'), 人気1点の的中=('人気1点', 'mean'))
t['割合'] = t['レース'] / t['レース'].sum()
print((t * [1, 100, 100, 100]).round(1).to_string())
t = R.groupby('重なり').agg(レース=('年', 'size'), 合わせた点=('合わせた点', 'mean'), 合わせて的中=('合わせて的中', 'mean'))
t['割合'] = t['レース'] / t['レース'].sum()
print('\nモデルの上位3組と人気のBOX3点の重なり'); print((t * [1, 1, 100, 100]).round(1).to_string())
print('全部：合わせた点の平均', round(R['合わせた点'].mean(), 2), '合わせて的中', f"{R['合わせて的中'].mean()*100:.1f}%")
