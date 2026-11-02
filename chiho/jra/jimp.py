"""中央競馬：直してみる材料（EXTRA）を足すと良くなるか（検証計画「中央：直してみること」）。
2021〜2023年（各年はその前の年まで、2017年から）で、今の材料と EXTRA を足したものをくらべる。PERIOD=check で2024年から。
使い方：python jimp.py 材料.pkl"""
import os, sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, EXTRA, KEY

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
YEARS = [2024, 2025, 2026] if os.environ.get('PERIOD') == 'check' else [2021, 2022, 2023]
res = {}
for lab, FE in (('今の材料', FEATS), ('EXTRAを足す', FEATS + EXTRA)):
    FE = [c for c in FE if c in H and H[c].notna().any()]; cat = [FE.index(c) for c in CATF if c in FE]
    P = []
    for y in YEARS:
        tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
        for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG)
            m.fit(tr[FE], tr[tgt]); te[col] = m.predict_proba(te[FE])[:, 1]
        P.append(te[KEY + ['年', 'n', '勝', '新馬', 'p1', 'p3', '単勝オッズ']])
        print(lab, y, round(time.time() - t0), '秒', flush=True)
    res[lab] = pd.concat(P, ignore_index=True)
rows = []
for lab, D in res.items():
    D = D[D['n'] >= 5].copy()
    D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
    D['r3'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first')
    for seg, X in (('全部', D), ('新馬', D[D['新馬'] == 1]), ('新馬でない', D[D['新馬'] == 0])):
        w = X[X['勝'] == 1]
        cap = X[(X['r3'] <= 3)].groupby(KEY)['勝'].max().mean()
        rows.append({'材料': lab, '区分': seg, 'レース': len(w), '損失': round(float(-np.log(w['p1'].clip(1e-6)).mean()), 4), '上位3頭に1着': f'{cap*100:.1f}%'})
    for y in YEARS:
        X = D[D['年'] == y]; w = X[X['勝'] == 1]
        rows.append({'材料': lab, '区分': f'{y}年', 'レース': len(w), '損失': round(float(-np.log(w['p1'].clip(1e-6)).mean()), 4),
                     '上位3頭に1着': f"{X[X['r3'] <= 3].groupby(KEY)['勝'].max().mean()*100:.1f}%"})
pd.set_option('display.width', 200)
print(pd.DataFrame(rows).to_string(index=False))
print(round(time.time() - t0), '秒')
