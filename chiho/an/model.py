"""手順3：単勝・複勝の「100円あたりの払戻の見込み」を毎年作り直しで出す。
Y年のモデルは2017年〜Y−2年で作り、線はY−1年の見込みの上位1%・2%・5%、Y年で数える。乱数0・1・2の3本の平均。
出力：/tmp/chiho_pred.pkl（Y年の各馬の見込みと線との比）"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from feat import FEATS
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle(sys.argv[1] if len(sys.argv) > 1 else '/tmp/chiho_feat.pkl')
OUT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/chiho_pred.pkl'
feats = [f for f in FEATS]
cat = [feats.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
QS = (0.01, 0.02, 0.05)
import os
CAP = float(os.environ.get('CAP', '0'))          # 0なら頭打ちなし。学習の答えだけ頭打ちにし、数えるのは本当の払戻
TGTS = tuple(os.environ.get('TGTS', '単払,複払').split(','))
res = []
t0 = time.time()
for Y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] <= Y - 2)]
    va = H[H['年'] == Y - 1]; te = H[H['年'] == Y]
    for tgt in TGTS:
        a = tr[tr[tgt].notna()]; v = va[va[tgt].notna()]; t = te[te[tgt].notna()]
        pv = np.zeros(len(v)); pt = np.zeros(len(t)); iters = []
        for seed in (0, 1, 2):
            m = HistGradientBoostingRegressor(loss='poisson', max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05,
                                              max_iter=500, early_stopping=True, validation_fraction=0.1, random_state=seed,
                                              categorical_features=cat)
            m.fit(a[feats], a[tgt].clip(upper=CAP) if CAP > 0 else a[tgt])
            pv += m.predict(v[feats]) / 3; pt += m.predict(t[feats]) / 3; iters.append(m.n_iter_)
        r = t[KEY + ['馬番', '馬名', '年', '日', '人気', '勝', '3着内', '単払', '複払', 'n']].copy()
        r['券'] = tgt[0]; r['見込み'] = pt; r['ret'] = t[tgt].values
        for q in QS:
            th = np.quantile(pv, 1 - q); r[f'比{int(q*100)}'] = pt / th
        r['Y'] = Y
        res.append(r)
        print(Y, tgt, '学習', len(a), '木', iters, '線1/2/5%', [round(np.quantile(pv, 1 - q), 3) for q in QS],
              '見込み平均', round(pt.mean(), 3), '実際', round(t[tgt].mean(), 3), round(time.time() - t0), '秒', flush=True)
pd.concat(res, ignore_index=True).to_pickle(OUT)
print('保存', OUT)
