"""地方：R1 連対の見込みの直し（検証計画 R1）。nk_r1.py の選んだ見込み（R1b ハービル）に、2021〜2023年で単調な直しを作り、2024〜2026年で確かめる → rentai_calib.json"""
import json, numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression
X = np.load('/tmp/claude-0/-home-claude/780f9162-48d4-5990-b464-1c4db99f5b7c/scratchpad/r1_best.npy')
p, y, yr = X[:, 0], X[:, 1], X[:, 2]
A, B = yr <= 2023, yr >= 2024
ir = IsotonicRegression(out_of_bounds='clip', y_min=0.001, y_max=0.999).fit(p[A], y[A])
grid = np.round(np.arange(0, 1.0001, 0.01), 2); mapped = ir.predict(grid)
q = np.interp(p, grid, mapped)
ll = lambda v, m: float(-(y[m] * np.log(np.clip(v[m], 1e-4, 1 - 1e-4)) + (1 - y[m]) * np.log(np.clip(1 - v[m], 1e-4, 1))).mean())
print(f'連対の当て分け 2024〜2026年：直す前 {ll(p, B):.5f} → 直した後 {ll(q, B):.5f}')
T = pd.DataFrame({'見込み': q[B], '実際': y[B]}); T['帯'] = pd.cut(T['見込み'], [0, .1, .2, .3, .4, .5, .6, .7, .8, 1.0])
T = T.groupby('帯', observed=True).agg(頭=('実際', 'size'), 見込み=('見込み', lambda s: round(s.mean() * 100, 1)), 実際=('実際', lambda s: round(s.mean() * 100, 1)))
T['ずれ'] = (T['実際'] - T['見込み']).round(1); print('■ 直した後、2024〜2026年'); print(T.to_string())
json.dump({'見込み': grid.tolist(), '直した見込み': np.round(mapped, 4).tolist(),
           '作り方': '検証計画 R1。1着の見込みからハービルで出した連対（2着内）の見込みに、2021〜2023年で単調な直しを作った（nk_r1.py・nk_r1cal.py。N3の見込み）'},
          open('rentai_calib.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('rentai_calib.json を書いた')
