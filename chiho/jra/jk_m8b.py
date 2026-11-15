"""中央競馬：M8b（検証計画「M8b」）。M8 の E＋V を元にして、V2（相手を先着した・された に分ける）を足す、HGBの3着内と着差のモデルにも材料を足す、の両方を試す。
同じ回・同じ行・同じ木。Y年はY−1年まで（2017年から）。乱数0・1・2の3つの平均。
出力：STORE/jra/exp/m8b_pred_年.csv.gz（p1_・p3_ の EV・EV2、h_・mg_ の EV・EV2。M7 の h・mg は m7_pred から手元で合わせる。jk_m8bcmp.py）。
使い方：python chiho/jra/jk_m8b.py STORE [年…]"""
import os, sys, time, json, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jfeat, jsoft, jk_rel, jk_elo
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF, PEDF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


W3 = json.load(open(f'{HERE}/jra_fix.json', encoding='utf-8'))['1着の付け直し']['木']
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
H = jfeat.build(f'{store}/jra/data', verbose=False, ped=True); log('材料', len(H))
H, EF = jk_elo.add_elo(H, KEY)
H, VF, V2 = jk_elo.add_after(H, KEY, detail=True); log('強さの点数', len(EF), '相手のその後', len(VF), 'くわしい版', len(V2))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF + PEDF if c not in MKT and c in H and H[c].notna().any()]
H, RELF = jk_rel.add_rel(H, KEY)
OUT = ['n', '勝', '3着内', '単勝オッズ', '新馬', '走数']
H = H[[c for c in H.columns if c in set(FE + RELF + EF + VF + V2 + KEY + ['年', '着', '馬番', '差', '距離'] + OUT)]].copy()
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年'] + OUT].copy()
    F = [c for c in FE if tr[c].notna().any()]; R = [c for c in RELF if tr[c].notna().any()]
    for vn, ADD in (('EV', EF + VF), ('EV2', EF + VF + V2)):
        FH = F + ADD; cat = [FH.index(c) for c in CATF if c in FH]
        ps = []
        for sd in (0, 1, 2):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
            m.fit(tr[FH], tr['3着内']); ps.append(m.predict_proba(te[FH])[:, 1])
        o['h_' + vn] = np.mean(ps, axis=0)
        o['mg_' + vn] = jk_rel.margin_fit_predict(tr, te, FH, cat, BIG); log(y, '年', vn, 'HGBの3着内・着差のモデル')
        FF = F + R + ADD
        o['p1_' + vn], o['p3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CATF, wt=(1.0, 0.5, 0.25), params=W3), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['p1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/jra/exp', exist_ok=True)
    o.to_csv(f'{store}/jra/exp/m8b_pred_{y}.csv.gz', index=False)
log('できた')
