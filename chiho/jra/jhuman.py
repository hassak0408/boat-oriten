"""中央競馬：H1 人が見るならどの材料が効率的か（検証計画 H1）。
(1) 1つの材料だけの力（レースの中で一番いい馬の1着率、上位3頭の3着内の率）。向きは2017〜2020年で決め、2021〜2026年で見る。
(2) 少ない材料でどこまでいけるか（2017〜2020年の単独の力の上位30から1つずつ足す。5つまで）。
使い方：python jhuman.py 材料.pkl 3つの平均の見込み.pkl"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, KEY, EXTRA, PACE, MKT, TROUBLE

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
H = H[(H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H['今日の人気'] = -H['人気'].astype(float)
CAND = [c for c in FEATS + EXTRA + PACE + TROUBLE if c in H and H[c].notna().any()]
CAND = [c for c in CAND if pd.api.types.is_numeric_dtype(H[c])]
# レースの中で同じ値の材料は除く
var = {c: (H.groupby(KEY)[c].transform('nunique') > 1).mean() for c in CAND}
CAND = [c for c in CAND if var[c] > 0.5] + ['今日の人気']
print('材料', len(CAND), round(time.time() - t0), '秒', flush=True)
rng = np.random.default_rng(0); H['_tie'] = rng.random(len(H))
A = H['年'].between(2017, 2020); B = H['年'].between(2021, 2026)


def top_stats(X, c, asc):
    v = X[c] if not asc else -X[c]
    o = X.assign(_v=v.fillna(-np.inf)).sort_values(KEY + ['_v', '_tie'], ascending=[True] * len(KEY) + [False, False])
    rk = o.groupby(KEY, sort=False).cumcount()
    return o.loc[rk.values == 0, '勝'].mean() * 100, o.loc[rk.values < 3, '3着内'].mean() * 100


rows = []
for c in CAND:
    hi = top_stats(H[A], c, False)[0]; lo = top_stats(H[A], c, True)[0]
    asc = lo > hi
    w, t3 = top_stats(H[B], c, asc)
    rows.append(dict(材料=c, 向き='小さいほど良い' if asc else '大きいほど良い', 選ぶ期間の1着率=round(max(hi, lo), 2), 一番の馬の1着率=round(w, 2), 上位3頭の3着内=round(t3, 2),
                     市場の材料='市場' if c in MKT or c == '今日の人気' else ''))
R = pd.DataFrame(rows).sort_values('一番の馬の1着率', ascending=False)
pd.set_option('display.width', 220); pd.set_option('display.max_rows', 200)
print(R.head(40).to_string(index=False), flush=True)
R.to_csv('/tmp/claude-0/-home-claude/780f9162-48d4-5990-b464-1c4db99f5b7c/scratchpad/H1_single.csv', index=False)

# (2) 少ない材料で：2017〜2020年の単独の力の上位30（市場の材料と今日の人気は除く）から1つずつ足す
pool = [r['材料'] for _, r in R.sort_values('選ぶ期間の1着率', ascending=False).iterrows() if not r['市場の材料']][:30]
SM = dict(max_leaf_nodes=31, min_samples_leaf=200, learning_rate=0.1, max_iter=300, n_iter_no_change=20, early_stopping=True, validation_fraction=0.1, random_state=0)
tr = H[A].sample(n=min(200000, int(A.sum())), random_state=0); te = H[H['年'].between(2021, 2023)].copy()


def loss(X, p):
    X = X.assign(_p=p); X['_p'] = X['_p'] / X.groupby(KEY)['_p'].transform('sum')
    return float(-np.log(X.loc[X['勝'] == 1, '_p'].clip(1e-6)).mean())


chosen = []
for step in range(5):
    best = None
    for c in pool:
        if c in chosen: continue
        F = chosen + [c]
        m = HistGradientBoostingClassifier(**SM).fit(tr[F], tr['勝'])
        l = loss(te, m.predict_proba(te[F])[:, 1])
        if best is None or l < best[1]: best = (c, l)
    chosen.append(best[0]); print(f'{step + 1}つ目：{best[0]}（2021〜2023年の1着の当て分け {best[1]:.4f}）', round(time.time() - t0), '秒', flush=True)

# 2024〜2026年で：選んだ組（学習2017〜2023年）、全部の材料のAI（3つの平均）、今日の人気
tr2 = H[H['年'].between(2017, 2023)]; te2 = H[H['年'].between(2024, 2026)].copy()
P = pd.read_pickle(sys.argv[2]); P = P.loc[:, ~P.columns.duplicated()]
te2 = te2.merge(P[KEY + ['馬番', 'p1']].rename(columns={'p1': 'pAI'}), on=KEY + ['馬番'], how='left')
q = 1 / te2['単勝オッズ']; te2['p市場'] = q / q.groupby([te2[k] for k in KEY]).transform('sum')
for k in range(1, 6):
    F = chosen[:k]; m = HistGradientBoostingClassifier(**SM).fit(tr2[F], tr2['勝']); te2[f'p{k}'] = m.predict_proba(te2[F])[:, 1]


def top1(X, c):
    o = X.sort_values(KEY + [c, '_tie'], ascending=[True] * len(KEY) + [False, False]); rk = o.groupby(KEY, sort=False).cumcount()
    return o.loc[rk.values == 0, '勝'].mean() * 100, o.loc[rk.values < 3, '3着内'].mean() * 100


print('\n■ 2024〜2026年', te2.groupby(KEY).ngroups, 'レース')
for nm, c in [(f'{k}つ（' + '・'.join(chosen[:k]) + '）', f'p{k}') for k in range(1, 6)] + [('全部の材料のAI（3つの平均）', 'pAI'), ('今日の人気（オッズ）', 'p市場')]:
    X = te2[te2[c].notna()]
    w, t3 = top1(X, c)
    print(f' {nm}：1着の当て分け {loss(X, X[c].values):.4f}・1番の馬の1着率 {w:.2f}%・上位3頭の3着内 {t3:.2f}%')
print(round(time.time() - t0), '秒')
