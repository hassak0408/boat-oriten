"""中央競馬：モデルの確かめ（検証計画「中央競馬」）。各年の見込みは、その年より前の年（2017年から）だけで作る。
物差し：①見込みの上位3頭に1着が入る率、②上位3頭のBOXの馬連の的中、③見込みと実際の合い方、④1着の当て分け（対数の損失）を確定オッズの見込みとくらべる、
⑤見込みと確定オッズの見込みを混ぜて良くなるか（混ぜ方は2021〜2023年で決め、2024年からで確かめる）。
使い方：python jeval.py 材料.pkl 出力の見込み.pkl"""
import sys, time, json, numpy as np, pandas as pd
from itertools import combinations
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from jfeat import FEATS, CATF, KEY

t0 = time.time()
H = pd.read_pickle(sys.argv[1])
H = H[~H['予測']].copy()
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
FE = [c for c in FEATS if c in H and H[c].notna().any()]
cat = [FE.index(c) for c in CATF if c in FE]
YEARS = [y for y in range(2021, 2027) if (H['年'] == y).any()]
P = []
for y in YEARS:
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
    for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG)
        m.fit(tr[FE], tr[tgt]); te[col] = m.predict_proba(te[FE])[:, 1]
        print(y, tgt, '学習', len(tr), '回数', m.n_iter_, round(time.time() - t0), '秒', flush=True)
    P.append(te[KEY + ['馬番', '馬名', '年', '日', 'n', '着', '勝', '3着内', '人気', '単勝オッズ', '芝ダ', '条件', '場', 'p1', 'p3']])
D = pd.concat(P, ignore_index=True)
D.to_pickle(sys.argv[2] if len(sys.argv) > 2 else '/tmp/jra_pred.pkl')

# レースの中でそろえる
ok = D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())
D = D[ok & (D['n'] >= 5)].copy()
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')


def race_ll(X, col):
    w = X[X['勝'] == 1]
    return float(-np.log(np.clip(w[col], 1e-6, 1)).mean())


# ⑤ 混ぜ方（2021〜2023年で決める）：logit(混ぜ) = a·log(モデル) + b·log(市場) をレースの中でそろえる（条件付きロジットの近似として、勝ち馬の見込みの対数が最大になる a, b を格子で探す）
def mix(X, a, b):
    z = a * np.log(np.clip(X['p1'], 1e-6, 1)) + b * np.log(np.clip(X['q'], 1e-6, 1))
    e = np.exp(z - z.groupby([X[k] for k in KEY]).transform('max'))
    return e / e.groupby([X[k] for k in KEY]).transform('sum')


SEL = D[D['年'] <= 2023]
best = None
for a in np.arange(0, 1.01, 0.05):
    for b in np.arange(0.6, 1.41, 0.05):
        v = race_ll(SEL.assign(m=mix(SEL, a, b)), 'm')
        if best is None or v < best[0]: best = (v, round(a, 2), round(b, 2))
_, A_, B_ = best
D['mix'] = mix(D, A_, B_)
bq = min(((race_ll(SEL.assign(m=mix(SEL, 0, b)), 'm'), round(b, 2)) for b in np.arange(0.6, 1.41, 0.05)))
D['qb'] = mix(D, 0, bq[1])      # 市場だけ（強さの直しだけ）

rows = []
for lab, m in (('2021〜2023年（選ぶ期間）', D['年'] <= 2023), ('2024〜2025年（確かめ）', D['年'].between(2024, 2025)), ('2026年（確かめ）', D['年'] == 2026)):
    X = D[m]
    if not len(X): continue
    nr = X.groupby(KEY).ngroups
    t3 = X.assign(r=X.groupby(KEY)['p3'].rank(ascending=False, method='first')).query('r <= 3')
    q3 = X.assign(r=X.groupby(KEY)['人気'].rank(method='first')).query('r <= 3')
    w_in = t3.groupby(KEY)['勝'].sum().mean(); w_in_q = q3.groupby(KEY)['勝'].sum().mean()
    box = (t3.groupby(KEY)['着'].apply(lambda s: (s <= 2).sum() == 2)).mean()
    boxq = (q3.groupby(KEY)['着'].apply(lambda s: (s <= 2).sum() == 2)).mean()
    top1 = X.loc[X.groupby(KEY)['p1'].idxmax()]; fav = X.loc[X.groupby(KEY)['q'].idxmax()]
    rows.append({'期間': lab, 'レース': nr, '上位3頭に1着': f'{w_in*100:.1f}%', '人気1〜3番に1着': f'{w_in_q*100:.1f}%', '上位3頭BOX馬連': f'{box*100:.1f}%',
                 '人気1〜3番BOX馬連': f'{boxq*100:.1f}%', '一番手の1着': f"{top1['勝'].mean()*100:.1f}%", '1番人気の1着': f"{fav['勝'].mean()*100:.1f}%",
                 '損失_モデル': round(race_ll(X, 'p1'), 4), '損失_市場': round(race_ll(X, 'qb'), 4), '損失_混ぜ': round(race_ll(X, 'mix'), 4)})
pd.set_option('display.width', 250)
print(pd.DataFrame(rows).to_string(index=False))
print(f'混ぜ方（2021〜2023年で決めた）：モデル {A_}、市場 {B_}（市場だけの強さの直し {bq[1]}）')
for col, tgt in (('p3', '3着内'), ('p1', '勝')):
    A = D[D['年'] >= 2024]
    t = A.groupby(pd.cut(A[col], [0, .02, .05, .1, .2, .3, .4, .5, .6, .8, 1]), observed=True).agg(頭=(tgt, 'size'), 見込み=(col, 'mean'), 実際=(tgt, 'mean'))
    t['見込み'] = (t['見込み'] * 100).round(1); t['実際'] = (t['実際'] * 100).round(1)
    print(f'\n■ {col}（{tgt}）の見込みと実際（2024年から）'); print(t.to_string())
print(round(time.time() - t0), '秒')
