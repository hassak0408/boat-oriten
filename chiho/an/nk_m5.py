"""地方：N5（検証計画「今の評価を上回れるか」）。今の一覧の作り方 N4（pipe.py の材料づくりをそのまま動かす）を base として、同じ回・同じ行で
mg（着差を学ぶモデル）・td（新しいレースを重く学ぶ）・rel（レースの中での差の材料）を作る。Y年はY−1年まで（2017年から）。
出力：STORE/data/exp/nk_m5_pred_年.csv.gz（h＝HGBの3着内、mg＝見込みの着差、pl_1_・pl_3_ の base・td・rel）。手元でくらべる（jra/jk_m6cmp.py nar）。
使い方：python chiho/an/nk_m5.py STORE 日付YYYYMMDD 年…（日付は出馬表のある日。材料づくりに使うだけ）"""
import os, sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jsoft, jk_rel
store, day = sys.argv[1], sys.argv[2]
YEARS = [int(v) for v in sys.argv[3:]] or list(range(2021, 2027))
src = open(f'{HERE}/pipe.py', encoding='utf-8').read()
head = src[:src.index("Y = int(today[:4])")]      # pipe.py の材料づくりの部分（モデルを作る前まで。騎手の格の差・騎手の性能・展開の材料も入っている）
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}
sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H, KEY, log, NFIX, FEATS, NEW, EXTRA3, USE3, BW = (g[k] for k in ('H', 'KEY', 'log', 'NFIX', 'FEATS', 'NEW', 'EXTRA3', 'USE3', 'BW'))
if not g['SOFT']: raise SystemExit('LightGBM が無い')
# 今の一覧（N4）と同じ材料：朝の材料＋騎手の格の差・騎手の性能（JF）＋展開の材料（SF）
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW] + list(g['JF']) + ([c for c in g['SF'] if c in H] if NFIX.get('展開の材料') else [])
FE3 = list(dict.fromkeys(c for c in FE3 if c in H))      # 同じ名前は1つに
CAT = ['場c', '馬場c', '天候c', '性c']
W3 = NFIX['木']
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
H = H[~H['予測'] & (H['年'] >= 2017)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']      # jsoft.py の名前に合わせる
H['着'] = pd.to_numeric(H['着'], errors='coerce')
H, RELF = jk_rel.add_rel(H, KEY)
log('材料', len(H), '材料の数', len(FE3), 'レースの中での差の材料', len(RELF), '着差のある行', round(float(H['差'].notna().mean()), 3))
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', '五場走数']].copy()
    F = [c for c in FE3 if tr[c].nunique(dropna=True) >= 2]; cat = [F.index(c) for c in CAT if c in F]
    ps = []
    for sd in (0, 1, 2):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
        m.fit(tr[F], tr['3着内']); ps.append(m.predict_proba(te[F])[:, 1])
    o['h'] = np.mean(ps, axis=0); log(y, '年 HGBの3着内')
    o['mg'] = jk_rel.margin_fit_predict(tr, te, F, cat, BIG); log(y, '年 着差のモデル')
    rw = 0.5 ** ((y - 1 - tr['年'].values) / 3.0)
    F2 = F + [c for c in RELF if tr[c].nunique(dropna=True) >= 2]
    for vn, FF, kw in (('base', F, {}), ('td', F, {'rw': rw}), ('rel', F2, {})):
        o['pl_1_' + vn], o['pl_3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CAT, wt=tuple(NFIX['重み']), params=W3, **kw), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['pl_1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/data/exp', exist_ok=True)
    o.to_csv(f'{store}/data/exp/nk_m5_pred_{y}.csv.gz', index=False)
log('できた')
