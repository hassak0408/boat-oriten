"""中央競馬：M6（検証計画「今の評価を上回れるか」）。今の一覧の作り方（HGBの3着内＋1〜3着の順を学ぶ M5b）を base として、同じ回・同じ行で
mg（着差を学ぶモデル）・td（新しいレースを重く学ぶ）・rel（レースの中での差の材料）を作る。Y年はY−1年まで（2017年から）。乱数0・1・2の3つの平均。
出力：STORE/jra/exp/m6_pred_年.csv.gz（h＝HGBの3着内、mg＝見込みの着差、p1_・p3_ の base・td・rel）。手元でくらべる（jk_m6cmp.py）。
使い方：python chiho/jra/jk_m6.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, json, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jfeat, jsoft, jk_rel
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


W3 = json.load(open(f'{HERE}/jra_fix.json', encoding='utf-8'))['1着の付け直し']['木']
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
H = jfeat.build(f'{store}/jra/data', verbose=False); log('材料', len(H))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
H, RELF = jk_rel.add_rel(H, KEY); log('レースの中での差の材料', len(RELF))
OUT = ['n', '勝', '3着内', '単勝オッズ', '新馬', '走数']
H = H[[c for c in H.columns if c in set(FE + RELF + KEY + ['年', '着', '馬番', '差', '距離'] + OUT)]].copy()
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年'] + OUT].copy()
    F = [c for c in FE if tr[c].notna().any()]; cat = [F.index(c) for c in CATF if c in F]
    ps = []
    for sd in (0, 1, 2):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
        m.fit(tr[F], tr['3着内']); ps.append(m.predict_proba(te[F])[:, 1])
    o['h'] = np.mean(ps, axis=0); log(y, '年 HGBの3着内')
    o['mg'] = jk_rel.margin_fit_predict(tr, te, F, cat, BIG); log(y, '年 着差のモデル')
    rw = 0.5 ** ((y - 1 - tr['年'].values) / 3.0)
    F2 = F + [c for c in RELF if tr[c].notna().any()]
    for vn, FF, kw in (('base', F, {}), ('td', F, {'rw': rw}), ('rel', F2, {})):
        o['p1_' + vn], o['p3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CATF, wt=(1.0, 0.5, 0.25), params=W3, **kw), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['p1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/jra/exp', exist_ok=True)
    o.to_csv(f'{store}/jra/exp/m6_pred_{y}.csv.gz', index=False)
log('できた')
