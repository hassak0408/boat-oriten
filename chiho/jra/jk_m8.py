"""中央競馬：M8（検証計画「的中率の研究：M8」）。M7（血統＋レースの中での差）と同じ回・同じ行・同じ木で、順を学ぶモデルの材料に
E（強さの点数）だけ・V（前走の相手のその後）だけ・両方を足す。Y年はY−1年まで（2017年から）。乱数0・1・2の3つの平均。
出力：STORE/jra/exp/m8_pred_年.csv.gz（p1_・p3_ の rel（＝M7）・E・V・EV）。HGBの3着内と着差のモデルは m7_pred のものを手元で合わせる（jk_m8cmp.py）。
使い方：python chiho/jra/jk_m8.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, json, numpy as np, pandas as pd
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
H = jfeat.build(f'{store}/jra/data', verbose=False, ped=True); log('材料', len(H))
H, EF = jk_elo.add_elo(H, KEY); log('強さの点数', len(EF))
H, VF = jk_elo.add_after(H, KEY); log('相手のその後', len(VF))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF + PEDF if c not in MKT and c in H and H[c].notna().any()]
H, RELF = jk_rel.add_rel(H, KEY)
OUT = ['n', '勝', '3着内', '単勝オッズ', '新馬', '走数']
H = H[[c for c in H.columns if c in set(FE + RELF + EF + VF + KEY + ['年', '着', '馬番', '差', '距離'] + OUT)]].copy()
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年'] + OUT].copy()
    F2 = [c for c in FE if tr[c].notna().any()] + [c for c in RELF if tr[c].notna().any()]
    for vn, FF in (('rel', F2), ('E', F2 + EF), ('V', F2 + VF), ('EV', F2 + EF + VF)):
        o['p1_' + vn], o['p3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CATF, wt=(1.0, 0.5, 0.25), params=W3), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['p1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/jra/exp', exist_ok=True)
    o.to_csv(f'{store}/jra/exp/m8_pred_{y}.csv.gz', index=False)
log('できた')
