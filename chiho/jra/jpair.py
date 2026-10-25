"""中央競馬：馬連の組の見込みの直し方と、組の当たり方（検証計画「中央競馬」）。
組の見込みは地方と同じ B（1着は1着の見込み、2着は3着内の見込みで割り振る）。2021〜2023年の各レースの上位10組で、見込み→実際の単調な当てはめを作り、
2024〜2026年で確かめる → jra_pair_calib.json。あわせて、上位1組・3組と人気の組（1・2番人気、1〜3番人気のBOX）の当たり方。
使い方：python jpair.py 見込み.pkl（jeval.py の出力）"""
import os, sys, json, numpy as np, pandas as pd
from itertools import combinations
from sklearn.isotonic import IsotonicRegression
KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1] if len(sys.argv) > 1 else '/tmp/jra_pred.pkl')
D = D[D['n'] >= 5].copy()
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
cal, rows = [], []
for k, g in D.groupby(KEY, sort=False):
    fin = g['着'].values
    if (fin <= 2).sum() < 2 or g['人気'].isna().any(): continue
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum(); top2 = set(nums[fin <= 2])
    P = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(P.values()); order = sorted(P, key=P.get, reverse=True)
    hit = lambda o: {nums[o[0]], nums[o[1]]} == top2
    y = int(g['年'].iloc[0])
    for o in order[:10]:
        cal.append((y, P[o] / z, hit(o)))
    r = np.argsort(g['人気'].values)
    pp = lambda a, b: tuple(sorted((a, b)))
    rows.append(dict(年=y, 上位1組=hit(order[0]), 上位3組=any(hit(o) for o in order[:3]), 人気1点=hit(pp(r[0], r[1])),
                     人気BOX3点=any(hit(o) for o in (pp(r[0], r[1]), pp(r[0], r[2]), pp(r[1], r[2]))), 同じ=pp(r[0], r[1]) == order[0]))
CA = pd.DataFrame(cal, columns=['年', '見込み', '的中'])
fit = CA[CA['年'] <= 2023]
ir = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(fit['見込み'], fit['的中'].astype(float))
grid = np.round(np.arange(0, 0.801, 0.005), 3); mapped = ir.predict(grid)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jra_pair_calib.json')
json.dump({'見込み': grid.tolist(), '直した見込み': np.round(mapped, 4).tolist(), '作り方': '中央競馬 2021〜2023年の各レースの上位10組（jpair.py）'},
          open(out, 'w', encoding='utf-8'), ensure_ascii=False)
te = CA[CA['年'] >= 2024].copy(); te['直した'] = np.interp(te['見込み'], grid, mapped)
b = pd.cut(te['直した'], [0, .02, .05, .1, .15, .2, .3, .4, 1])
print('■ 組の見込みの直し：2024〜2026年での確かめ（直した見込みの帯ごと）')
print(te.groupby(b, observed=True).agg(組=('的中', 'size'), 直す前=('見込み', lambda s: round(s.mean() * 100, 1)), 直した後=('直した', lambda s: round(s.mean() * 100, 1)),
                                       実際=('的中', lambda s: round(s.mean() * 100, 1))).to_string())
R = pd.DataFrame(rows)
print('\n■ 馬連の当たり方（的中の率）')
for lab, m in (('2021〜2023年', R['年'] <= 2023), ('2024〜2025年', R['年'].between(2024, 2025)), ('2026年', R['年'] == 2026)):
    X = R[m]
    print(f"{lab}（{len(X)}レース）：上位1組 {X['上位1組'].mean()*100:.1f}%・人気1点 {X['人気1点'].mean()*100:.1f}%／上位3組 {X['上位3組'].mean()*100:.1f}%・"
          f"人気BOX3点 {X['人気BOX3点'].mean()*100:.1f}%／1番の組が人気の組と同じ {X['同じ'].mean()*100:.1f}%")
