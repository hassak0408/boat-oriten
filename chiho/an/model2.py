"""1着の見込みのモデルのくらべ（検証計画「市場より劣る所の洗い出しと改善」）。人気・オッズは使わない。Y年はY−1年まで（2017年〜）で作る。
使い方：python model2.py 名前   名前＝B0（前の材料・前の作り方）／B1（前の材料・木を大きく）／B2（足した材料・木を大きく）"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from feat import FEATS
from feat2cols import NEW
KEY = ['競馬場', '競走年月日', 'レース番号']
name = sys.argv[1]
H = pd.read_pickle('/tmp/chiho_feat2.pkl')
FE = FEATS + (NEW if name in ('B2', 'B3') else [])
cat = [FE.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
P = dict(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500) if name == 'B0' else \
    dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
out = []; t0 = time.time()
for Y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] <= Y - 1)]; te = H[H['年'] == Y]
    m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **P)
    m.fit(tr[FE], tr['勝'])
    r = te[KEY + ['馬番']].copy(); r['p'] = m.predict_proba(te[FE])[:, 1]; out.append(r)
    print(name, Y, '回数', m.n_iter_, round(time.time() - t0), '秒', flush=True)
pd.concat(out).to_pickle(f'/tmp/chiho_win_{name}.pkl'); print('保存', name)
