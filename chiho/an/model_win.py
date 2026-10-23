"""材料だけで1着の見込みを出す（毎年作り直し：Y年は2017年〜Y−2年で作る）。人気・オッズは使わない。相手選び用。"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from feat import FEATS
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl')
cat = [FEATS.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
out = []; t0 = time.time()
for Y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] <= Y - 2)]; te = H[H['年'] == Y]
    m = HistGradientBoostingClassifier(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500,
                                       early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat)
    m.fit(tr[FEATS], tr['勝'])
    r = te[KEY + ['馬番']].copy(); r['p勝'] = m.predict_proba(te[FEATS])[:, 1]; out.append(r)
    print(Y, m.n_iter_, round(time.time() - t0), '秒', flush=True)
pd.concat(out).to_pickle('/tmp/chiho_win.pkl'); print('保存')
