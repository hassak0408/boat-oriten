"""中央競馬：P0 馬連の組の見込みの出し方（検証計画 P0）。
今（B式：1着の見込みと3着内の割合）と、ハービル H1（一覧の1着の見込み）・H2（M4b そのままの1着の見込み）を、
実際の1・2着の組の見込みの −log（馬連の当て分け）と、上位1組・上位3組の的中でくらべる（どれも見込みの直しの前）。
使い方：python jk_p0.py 一覧の見込み.pkl（p1・p3、M4b・M4c のあと） m4_pred.csv.gz"""
import sys, numpy as np, pandas as pd
from itertools import combinations

KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1]); D = D.loc[:, ~D.columns.duplicated()].copy(); D['R'] = D['R'].astype(str); D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce')
S = pd.read_csv(sys.argv[2], dtype={'年月日': str, '場': str, 'R': str}); S['馬番'] = pd.to_numeric(S['馬番'], errors='coerce')
if 'p1_b' not in D: D = D.merge(S[KEY + ['馬番', 'p1_b']], on=KEY + ['馬番'], how='left')
D = D[(D['n'] >= 5) & D.groupby(KEY)['p1_b'].transform(lambda s: s.notna().all())].copy()


def pair_probs(p1, p3, mode):
    n = len(p1)
    if mode == 'B':
        a = p1 / p1.sum(); b = p3 / p3.sum()
        P = {(i, j): a[i] * b[j] / (1 - b[i]) + a[j] * b[i] / (1 - b[j]) for i, j in combinations(range(n), 2)}
    else:
        a = p1 / p1.sum()
        P = {(i, j): a[i] * a[j] / (1 - a[i]) + a[j] * a[i] / (1 - a[j]) for i, j in combinations(range(n), 2)}
    z = sum(P.values()); return {k: v / z for k, v in P.items()}


rows = []
for k, g in D.groupby(KEY, sort=False):
    fin = g['着'].values
    if (fin == 1).sum() != 1 or (fin == 2).sum() != 1: continue      # 同着は除く
    nums = g['馬番'].astype(int).values
    i1, i2 = int(np.flatnonzero(fin == 1)[0]), int(np.flatnonzero(fin == 2)[0]); key = tuple(sorted((i1, i2)))
    rec = {'年': int(g['年'].iloc[0])}
    for nm, mode, c1 in (('今（B式）', 'B', 'p1'), ('H1（ハービル・一覧の1着）', 'H', 'p1'), ('H2（ハービル・M4bそのまま）', 'H', 'p1_b')):
        P = pair_probs(g[c1].values.astype(float), g['p3'].values.astype(float), mode)
        order = sorted(P, key=P.get, reverse=True)
        rec[nm] = -np.log(max(P[key], 1e-9)); rec[nm + '1'] = order[0] == key; rec[nm + '3'] = key in order[:3]
    rows.append(rec)
R = pd.DataFrame(rows)
for lab, m in (('2021〜2023年', R['年'] <= 2023), ('2024〜2026年', R['年'] >= 2024)):
    X = R[m]; print(f'■ {lab}（{len(X)}レース）')
    for nm in ('今（B式）', 'H1（ハービル・一覧の1着）', 'H2（ハービル・M4bそのまま）'):
        print(f"  {nm}：馬連の当て分け {X[nm].mean():.4f}・上位1組の的中 {X[nm + '1'].mean() * 100:.2f}%・上位3組 {X[nm + '3'].mean() * 100:.2f}%")
