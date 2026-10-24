"""馬連の組の見込み（B）の直し方：2021〜2023年の各レースの上位10組で、見込み→実際の当たりの単調な当てはめを作り、2024〜2026年で確かめる。→ pair_calib.json"""
import json, numpy as np, pandas as pd
from itertools import combinations
from sklearn.isotonic import IsotonicRegression
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '着', '人気', 'n', '年']]; H['馬番'] = H['馬番'].astype(float)
C = pd.read_pickle('/tmp/chiho_cand3_朝3.pkl'); C['馬番'] = C['馬番'].astype(float)
D = H[H['年'] >= 2021].merge(C, on=KEY + ['馬番']); D = D[D['n'] >= 5]
cal = []
for k, g in D.groupby(KEY, sort=False):
    fin = g['着'].values
    if (fin <= 2).sum() < 2: continue
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum(); top2 = set(nums[fin <= 2])
    P = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(P.values())
    for o in sorted(P, key=P.get, reverse=True)[:10]:
        cal.append((int(g['年'].iloc[0]), P[o] / z, {nums[o[0]], nums[o[1]]} == top2))
CA = pd.DataFrame(cal, columns=['年', '見込み', '的中'])
fit = CA[CA['年'] <= 2023]; ir = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(fit['見込み'], fit['的中'].astype(float))
grid = np.round(np.arange(0, 0.801, 0.005), 3); mapped = ir.predict(grid)
json.dump({'見込み': grid.tolist(), '直した見込み': np.round(mapped, 4).tolist(), '作り方': '2021〜2023年の各レースの上位10組（pair_calib.py）'}, open('pair_calib.json', 'w', encoding='utf-8'), ensure_ascii=False)
te = CA[CA['年'] >= 2024].copy(); te['直した'] = np.interp(te['見込み'], grid, mapped)
b = pd.cut(te['直した'], [0, .02, .05, .1, .15, .2, .3, .4, 1])
print('■ 2024〜2026年での確かめ（直した見込みの帯ごと）')
print(te.groupby(b, observed=True).agg(組=('的中', 'size'), 直す前=('見込み', lambda s: round(s.mean() * 100, 1)), 直した後=('直した', lambda s: round(s.mean() * 100, 1)), 実際=('的中', lambda s: round(s.mean() * 100, 1))).to_string())
