"""脚質：前に行ける馬（検証計画「脚質：前に行ける馬」）
1) 前提：実際に前で回った馬の成績（結果から分かる数字）
2) 前に行くかをレース前に当てるモデル（Y年はY−1年までで作る）
3) 買い方 F1・F2・F3"""
import re, sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from load import _read
from feat import FEATS, corner_pos
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl')
R = _read('race', 'racelist').drop_duplicates(KEY)
cc = [f'コーナー通過順{i}' for i in range(1, 9)]
last = R[cc].replace('', np.nan).ffill(axis=1).iloc[:, -1]
lastpos = dict(zip(map(tuple, R[KEY].values), last.map(lambda s: corner_pos(s) if isinstance(s, str) else {})))
H['終角'] = [lastpos.get(tuple(k), {}).get(int(b)) for k, b in zip(H[KEY].values, H['馬番'])]
H['終角'] = pd.to_numeric(H['終角'], errors='coerce'); H['終角率'] = H['終角'] / H['n']
H['先頭'] = (H['初角'] == 1).astype(float).where(H['初角'].notna())
H['先行'] = (H['初角'] <= 3).astype(float).where(H['初角'].notna())
H['上げ'] = H['終角'] - H['着x']             # 最後のコーナーから着順までに上げた数
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
g = H.groupby('馬', sort=False)
for c in ['先頭', '先行']:
    H[c + '率5'] = g[c].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
H['終角率1'] = g['終角率'].shift(1); H['上げ1'] = g['上げ'].shift(1)
H['上げ3'] = g['上げ'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
# 相手の顔ぶれ
H['逃げ型'] = (H['先頭率5'] >= 0.4).astype(int)
H['他の逃げ型'] = H.groupby(KEY)['逃げ型'].transform('sum') - H['逃げ型']
H['先頭率5順'] = H.groupby(KEY)['先頭率5'].rank(ascending=False, method='min')
H['過去3角順'] = H.groupby(KEY)['過去3角'].rank(method='min')
mx = H.groupby(KEY)['先頭率5'].transform(lambda s: s.nlargest(2).iloc[-1] if s.notna().sum() >= 2 else np.nan)
top = H.groupby(KEY)['先頭率5'].transform('max')
H['他の最大先頭率'] = np.where(H['先頭率5'] >= top, mx, top)
SF = ['先頭率5', '先行率5', '終角率1', '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '他の最大先頭率']
FE = FEATS + SF
cat = [FE.index(c) for c in ['場c', '馬場c', '天候c', '性c']]

# 1) 前提
pd.set_option('display.width', 250)
A = H[(H['年'] >= 2016) & (H['年'] <= 2025) & H['初角'].notna() & H['人気'].notna()].copy()
A['人気帯'] = pd.cut(A['人気'], [0, 3, 6, 16], labels=['1〜3番人気', '4〜6番人気', '7番人気以下'])
def tab(D, by):
    t = D.groupby(by, observed=True).agg(頭=('勝', 'size'), 一着=('勝', 'mean'), 三着内=('3着内', 'mean'), 単勝=('単払', 'mean'), 複勝=('複払', 'mean'))
    for c in ['一着', '三着内', '単勝', '複勝']: t[c] = (t[c] * 100).round(1)
    return t
print('■ 前提：実際に最初のコーナーを先頭で回った馬（2016〜2025年、結果から分かる数字）')
print(tab(A[A['先頭'] == 1], '人気帯').to_string())
print('  場ごと'); print(tab(A[A['先頭'] == 1], '競馬場').to_string())
print('■ 実際に3番手以内で回った馬'); print(tab(A[A['先行'] == 1], '人気帯').to_string())
print('■ 実際に後ろ半分で回った馬'); print(tab(A[A['初角率'] > 0.5], '人気帯').to_string())

# 2) 前に行くかを当てるモデル
pred = []
for Y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] <= Y - 1) & H['初角'].notna()]; te = H[H['年'] == Y].copy()
    for tgt in ('先頭', '先行'):
        m = HistGradientBoostingClassifier(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500,
                                           early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat)
        m.fit(tr[FE], tr[tgt]); te['p' + tgt] = m.predict_proba(te[FE])[:, 1]
    pred.append(te); print(Y, 'できた', flush=True)
T = pd.concat(pred, ignore_index=True)
T.to_pickle('/tmp/chiho_style.pkl')
ok = T['初角'].notna()
print('\n■ 当てる力（2021〜2026年）')
print('  先頭のAUC', round(roc_auc_score(T.loc[ok, '先頭'], T.loc[ok, 'p先頭']), 3), '／3番手以内のAUC', round(roc_auc_score(T.loc[ok, '先行'], T.loc[ok, 'p先行']), 3))
T['逃げ予想'] = T.groupby(KEY)['p先頭'].rank(ascending=False, method='first') == 1
T['単純'] = T.groupby(KEY)['過去3角'].rank(method='first') == 1   # 過去3走の最初のコーナーの平均が一番前（中央で試した形）
for lab, c in (('モデルの逃げ予想', '逃げ予想'), ('過去3走の位置が一番前', '単純')):
    S = T[T[c] & ok]
    print(f'  {lab}：実際に先頭 {S["先頭"].mean()*100:.1f}%  3番手以内 {S["先行"].mean()*100:.1f}%')
