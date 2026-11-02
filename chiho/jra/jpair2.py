"""中央競馬：馬連の組をモデルで足すと、人気だけで組を増やすより当たるか（検証計画の同じ名前の節）。
A：人気の1〜3番人気のBOX（3点）＋モデルの上位3組（重なりを除いて k 点）。B：同じ k 点を、単勝オッズのハービル式の組の見込みの上位から。
使い方：python jpair2.py 見込み.pkl STORE/jra/data"""
import sys, glob, json, numpy as np, pandas as pd
from itertools import combinations
KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1]); D = D.loc[:, ~D.columns.duplicated()]
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: v = json.loads(p).get('馬連') if p else None
        except ValueError: v = None
        if isinstance(v, list) and len(v) == 1: pays[(a, b, int(c))] = v[0] / 100
D = D[D['n'] >= 5].copy()
ok = D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all()) & D.groupby(KEY)['人気'].transform(lambda s: s.notna().all())
D = D[ok]
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
rows = []
for k, g in D.groupby(KEY, sort=False):
    fin = g['着'].values
    if (fin <= 2).sum() != 2: continue
    nums = g['馬番'].astype(int).values; idx = range(len(nums))
    top2 = tuple(sorted(int(x) for x in nums[fin <= 2]))
    p1 = g['p1'].values; p3 = g['p3'].values / g['p3'].sum(); q = g['q'].values
    PM = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(idx, 2)}
    PQ = {(i, j): q[i] * q[j] / (1 - q[i]) + q[j] * q[i] / (1 - q[j]) for i, j in combinations(idx, 2)}
    pr = np.argsort(g['人気'].values, kind='stable')
    pp = lambda a, b: tuple(sorted((a, b)))
    box = {pp(pr[0], pr[1]), pp(pr[0], pr[2]), pp(pr[1], pr[2])}
    A = box | set(sorted(PM, key=PM.get, reverse=True)[:3])
    B = set(sorted(PQ, key=PQ.get, reverse=True)[:len(A)])
    hit = lambda S: any(tuple(sorted((int(nums[a]), int(nums[b])))) == top2 for a, b in S)
    pay = pays.get((k[0], k[1], int(k[2])), np.nan)
    rows.append(dict(年=int(g['年'].iloc[0]), 点=len(A), A的中=hit(A), B的中=hit(B), 箱的中=hit(box), 払=pay))
R = pd.DataFrame(rows)
pd.set_option('display.width', 200)
for lab, m in (('2021〜2023年', R['年'] <= 2023), ('2024〜2026年', R['年'] >= 2024)):
    X = R[m]
    pa = (X['A的中'] * X['払'].fillna(0)).sum() / X['点'].sum() * 100; pb = (X['B的中'] * X['払'].fillna(0)).sum() / X['点'].sum() * 100
    print(f"{lab}（{len(X)}レース、平均{X['点'].mean():.2f}点）：A（人気BOX＋モデルの組）{X['A的中'].mean()*100:.1f}%（回収{pa:.0f}%）／"
          f"B（人気だけで同じ点数）{X['B的中'].mean()*100:.1f}%（回収{pb:.0f}%）／人気BOX3点だけ {X['箱的中'].mean()*100:.1f}%")
    print('  点数ごと：', X.groupby('点').agg(レース=('A的中', 'size'), A=('A的中', 'mean'), B=('B的中', 'mean')).round(3).to_dict('index'))
