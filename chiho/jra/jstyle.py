"""中央競馬：前に行く馬の予想（検証計画「中央：前に行く馬の予想」）。一覧と同じ作り方（先頭・先行の小さいモデル、各年はその前の年まで）。
使い方：python jstyle.py 材料.pkl"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import CATF, KEY

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
FES = [c for c in ['場c', '芝ダc', '距離', 'n', '馬番', '馬番率', '枠', '齢', '斤量', '走数', '間隔', '距離差', '芝ダ変更', '先頭率5', '先行率5', '終角率1',
                   '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '過去3角', '騎勝率', 'クラス'] if c in H]
SMALL = dict(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500)
cat = [FES.index(c) for c in CATF if c in FES]
P = []
for y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] < y) & H['初角'].notna()]; te = H[H['年'] == y].copy()
    for tgt, col in (('先頭', 'p先頭'), ('先行', 'p先行')):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **SMALL)
        m.fit(tr[FES], tr[tgt]); te[col] = m.predict_proba(te[FES])[:, 1]
    P.append(te[KEY + ['年', 'n', '芝ダ', '初角', '先頭', '先行', '勝', '3着内', '単勝オッズ', 'p先頭', 'p先行']])
    print(y, round(time.time() - t0), '秒', flush=True)
D = pd.concat(P, ignore_index=True)
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
D['逃げ順'] = D.groupby(KEY)['p先頭'].rank(ascending=False, method='first')
D['印'] = np.where((D['逃げ順'] == 1) & (D['p先頭'] >= 0.3), '逃げ', np.where(D['p先行'] >= 0.5, '先行', 'ほか'))
rows = []
for lab, m in (('2021〜2023年', D['年'] <= 2023), ('2024〜2026年', D['年'] >= 2024)):
    for sd in ('芝', 'ダート'):
        X = D[m & (D['芝ダ'] == sd)]
        for mk in ('逃げ', '先行', 'ほか'):
            Z = X[X['印'] == mk]
            rows.append({'期間': lab, '芝ダ': sd, '印': mk, '頭': len(Z), '1角で1番手': f"{Z['先頭'].mean()*100:.1f}%", '1角で3番手以内': f"{Z['先行'].mean()*100:.1f}%",
                         '1着': f"{Z['勝'].mean()*100:.1f}%", '実際÷オッズの見込み': round(Z['勝'].sum() / Z['q'].sum(), 2), '3着内': f"{Z['3着内'].mean()*100:.1f}%",
                         '単勝の回収': f"{(Z['勝'] * Z['単勝オッズ']).mean()*100:.0f}%"})
pd.set_option('display.width', 220)
print(pd.DataFrame(rows).to_string(index=False))
