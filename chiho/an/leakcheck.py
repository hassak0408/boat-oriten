"""漏れの見張り：材料だけで1着を当てる力を、市場（確定の人気）とくらべる。材料の方がずっと上なら漏れを疑う。"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.inspection import permutation_importance
from feat import FEATS
H = pd.read_pickle('/tmp/chiho_feat.pkl')
tr = H[(H['年'] >= 2017) & (H['年'] <= 2022)]; te = H[(H['年'] >= 2023) & (H['年'] <= 2025)].copy()
cat = [FEATS.index(c) for c in ['場c', '馬場c', '天候c', '性c']]
m = HistGradientBoostingClassifier(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500,
                                   early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat)
m.fit(tr[FEATS], tr['勝'])
p = m.predict_proba(te[FEATS])[:, 1]
te['p'] = p
print('木の回数', m.n_iter_)
print('1着のAUC 材料だけ', round(roc_auc_score(te['勝'], p), 4), '／市場（人気）', round(roc_auc_score(te['勝'], -te['人気'].fillna(99)), 4))
te['本命'] = te.groupby(['競馬場', '競走年月日', 'レース番号'])['p'].rank(ascending=False, method='first') == 1
print('材料の本命の1着率', round(te.loc[te['本命'], '勝'].mean() * 100, 1), '%  市場の1番人気', round(te.loc[te['人気'] == 1, '勝'].mean() * 100, 1), '%')
s = te.sample(40000, random_state=0)
pi = permutation_importance(m, s[FEATS], s['勝'], scoring='roc_auc', n_repeats=2, random_state=0)
imp = pd.Series(pi.importances_mean, index=FEATS).sort_values(ascending=False)
print(imp.head(15).round(4).to_string())
