"""中央競馬：M5b M5で採用した v2（葉127・葉の最小400）に、v4（材料7割）・v6（L2 10）を組み合わせる（検証計画 M5b）。
jsoft.py（毎日の一覧と同じ作り方）に、木の大きさなどを替えて渡す。重み1・0.5・0.25、乱数0・1・2の3つの平均、Y年はY−1年まで（2017年から）。
出力：STORE/jra/exp/m5b_pred.csv.gz（年月日・場・R・馬番・年と、くらべるものごとの p1_名前・p3_名前）。手元でくらべる（jk_m5cmp.py）。
使い方：python chiho/jra/jk_m5b.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat, jsoft
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))
V2 = {'num_leaves': 127, 'min_data_in_leaf': 400}
VARIANTS = {'base': V2, 'w1': dict(V2, feature_fraction=0.7), 'w2': dict(V2, lambda_l2=10.0), 'w3': dict(V2, feature_fraction=0.7, lambda_l2=10.0)}


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


H = jfeat.build(f'{store}/jra/data', verbose=False); log('材料', len(H))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
H = H[[c for c in H.columns if c in set(FE + KEY + ['年', '勝', '着', '馬番'])]].copy()
out = []
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    F = [c for c in FE if tr[c].notna().any()]
    o = te[KEY + ['馬番', '年']].copy()
    for vn, pv in VARIANTS.items():
        its = []
        ms = jsoft.fit(tr, F, CATF, wt=(1.0, 0.5, 0.25), params=pv, log=lambda *a: its.append(a[-1]))
        o['p1_' + vn], o['p3_' + vn] = jsoft.predict(ms, te, F)
        w = te['勝'].values == 1
        log(y, '年', vn, pv, '回数', its, '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['p1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    out.append(o)
os.makedirs(f'{store}/jra/exp', exist_ok=True)
pd.concat(out, ignore_index=True).to_csv(f'{store}/jra/exp/m5b_pred.csv.gz', index=False)
log('できた')
