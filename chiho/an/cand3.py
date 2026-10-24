"""来そうな馬（3着内の見込み）のモデルと、上位の馬の当たり方（検証計画「来そうな馬の候補」）。人気・オッズは使わない。Y年はY−1年まで（2017年〜）。
使い方：python cand3.py 朝|直前|朝3   朝＝馬体重を使わない（朝の一覧用）、直前＝馬体重を使う、朝3＝朝の形にB3の材料（全部の場の前の成績）"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from feat import FEATS
from feat2cols import NEW
KEY = ['競馬場', '競走年月日', 'レース番号']
kind = sys.argv[1] if len(sys.argv) > 1 else '朝'
from feat3 import EXTRA3
H = pd.read_pickle('/tmp/chiho_feat3.pkl' if kind == '朝3' else '/tmp/chiho_feat2.pkl')
FE = [c for c in FEATS + NEW + (EXTRA3 if kind == '朝3' else []) if not (kind in ('朝', '朝3') and c in ('馬体重', '馬体重増減', '馬体重差'))]
cat = [FE.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
P = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
out = []; t0 = time.time()
for Y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] <= Y - 1)]; te = H[H['年'] == Y]
    r = te[KEY + ['馬番']].copy()
    for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **P)
        m.fit(tr[FE], tr[tgt]); r[col] = m.predict_proba(te[FE])[:, 1]
    out.append(r); print(kind, Y, round(time.time() - t0), '秒', flush=True)
pd.concat(out).to_pickle(f'/tmp/chiho_cand3_{kind}.pkl'); print('保存', kind)
