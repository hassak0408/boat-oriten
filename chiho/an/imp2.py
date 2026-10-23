"""足した材料のどれが効いたか（2025年で、材料の組ごとに並べ替えて当て分けの下がり方を見る）"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from feat import FEATS
from feat2cols import NEW
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat2.pkl'); FE = FEATS + NEW
cat = [FE.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
tr = H[(H['年'] >= 2017) & (H['年'] <= 2024)]; te = H[H['年'] == 2025].copy()
m = HistGradientBoostingClassifier(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0,
                                   n_iter_no_change=30, early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat).fit(tr[FE], tr['勝'])
base = roc_auc_score(te['勝'], m.predict_proba(te[FE])[:, 1])
G = {'クラス': ['クラス', '前クラス', 'クラス差', '新馬', '交流', '格', '前格'], '全成績の中身（芝・ダート）': ['全連対率', 'ダ走', '芝走', '芝率', 'ダ3率'],
     '初めての馬の目印': ['初データ', '初出走', '外の走数', '外を挟む'], 'タイムの指数': ['指数1', '指数最高3', '指数平均3', '指数最高5', '指数最高3順率', '指数最高3差', '指数1順率'],
     '父・母父': ['父数', '父勝率', '父3率', '母父数', '母父勝率', '母父3率'], '馬主・生産牧場': ['主数', '主勝率', '主3率', '牧数', '牧勝率', '牧3率'],
     '調教師（初めての馬）': ['調初数', '調初勝率', '調初3率']}
rng = np.random.default_rng(0); print('2025年の当て分け', round(base, 4))
for g, cs in G.items():
    X = te[FE].copy(); idx = rng.permutation(len(X))
    for c in cs: X[c] = X[c].values[idx]
    print(f'  {g} を崩すと {roc_auc_score(te["勝"], m.predict_proba(X)[:, 1]) - base:+.4f}')
