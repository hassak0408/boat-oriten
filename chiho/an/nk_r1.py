"""地方：R1 連対（2着内）の見込みの出し方（検証計画 R1）。N3の見込み（nk_m4b.py）で、R1a（馬連の組の見込みを足す）と R1b（ハービル）をくらべる。
使い方：python nk_r1.py nk_m4b_pred.csv.gz STORE"""
import sys, glob, numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
a, b, c = 0.978, 0.222, 0.884      # nar_fix.json（N3）の値
D = pd.read_csv(sys.argv[1], dtype={'競馬場': str, '競走年月日': str, 'レース番号': str}); D = D[D['n'] >= 5].copy()
R = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['馬番', '着順']) for f in glob.glob(f'{sys.argv[2]}/data/race/*/*horselist*.csv.gz')],
              ignore_index=True).drop_duplicates(KEY + ['馬番'], keep='last')
R['馬番'] = pd.to_numeric(R['馬番'], errors='coerce'); R['着'] = pd.to_numeric(R['着順'], errors='coerce')
D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce'); D = D.merge(R[KEY + ['馬番', '着']], on=KEY + ['馬番'], how='left')
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True); G = D.groupby(KEY, sort=False).ngroup().values
ok = pd.Series((D['着'] <= 2).astype(int)).groupby(G).transform('sum').values == 2      # 1・2着がはっきりしているレース（同着は除く）
D, G = D[ok].reset_index(drop=True), G[ok]; G = pd.factorize(G)[0]
s1 = lambda x: x / pd.Series(x).groupby(G).transform('sum').values
s3 = lambda x: np.clip(x * np.minimum(3, D['n'].values) / pd.Series(x).groupby(G).transform('sum').values, 1e-4, 0.97)
h3 = s3(D['h_3_k'].values); pl1 = s1(D['pl_1_k'].values)
z = a * np.log(np.clip(pl1, 1e-6, 1)) + b * np.log(h3); z = z - pd.Series(z).groupby(G).transform('max').values
p1 = s1(np.exp(z)); m3 = s3(np.where((D['五場走数'] == 0).values, h3, s3(D['pl_3_k'].values))); p3 = s3(m3 ** c)
y2 = (D['着'] <= 2).astype(int).values
r2a = np.zeros(len(D)); r2b = np.zeros(len(D))
st = np.r_[0, np.flatnonzero(np.diff(G)) + 1]; en = np.r_[st[1:], len(G)]
for s, e in zip(st, en):
    q1 = p1[s:e] / p1[s:e].sum(); q3 = p3[s:e] / p3[s:e].sum()
    P = q1[:, None] * q3[None, :] / (1 - q3[:, None]); np.fill_diagonal(P, 0); P = P + P.T      # 馬連の組（B式、i→j と j→i の和）
    P = P / P[np.triu_indices(e - s, 1)].sum()
    r2a[s:e] = P.sum(1)
    r = q1 / np.clip(1 - q1, 1e-9, None); r2b[s:e] = q1 + q1 * (r.sum() - r)      # ハービル
r2a, r2b = np.clip(r2a, 1e-4, 0.999), np.clip(r2b, 1e-4, 0.999)
ll = lambda p, m: float(-(y2[m] * np.log(p[m]) + (1 - y2[m]) * np.log(1 - p[m])).mean())
yr = D['年'].values; A, B = yr <= 2023, yr >= 2024
print(f'レース {G.max() + 1}（2021〜2023年 {len(set(G[A]))}・2024〜2026年 {len(set(G[B]))}）')
for nm, p in (('R1a 馬連の組を足す', r2a), ('R1b ハービル', r2b)):
    print(f'{nm}：連対の当て分け 2021〜2023年 {ll(p, A):.5f}・2024〜2026年 {ll(p, B):.5f}')
best = r2a if ll(r2a, A) <= ll(r2b, A) else r2b
print('選んだもの：', 'R1a' if best is r2a else 'R1b')
X = pd.DataFrame({'見込み': best, '実際': y2, '年': yr})
X['帯'] = pd.cut(X['見込み'], [0, .1, .2, .3, .4, .5, .6, .7, .8, 1.0])
for lab, m in (('2021〜2023年', A), ('2024〜2026年', B)):
    T = X[m].groupby('帯', observed=True).agg(頭=('実際', 'size'), 見込み=('見込み', lambda s: round(s.mean() * 100, 1)), 実際=('実際', lambda s: round(s.mean() * 100, 1)))
    T['ずれ'] = (T['実際'] - T['見込み']).round(1); print('■', lab); print(T.to_string())
np.save('/tmp/claude-0/-home-claude/780f9162-48d4-5990-b464-1c4db99f5b7c/scratchpad/r1_best.npy', np.c_[best, y2, yr])
