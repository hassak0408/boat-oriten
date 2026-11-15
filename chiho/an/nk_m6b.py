"""地方：N6b（検証計画「N6b」）：HGBの3着内（h_EV）と着差のモデル（mg_EV）にも E＋V を足し、順を学ぶモデルは base と EV だけ作る。出力は nk_m6b_pred_年。もとは N6（検証計画「N6（地方）：強さの点数と前走の相手のその後」）。今の一覧の作り方（pipe.py の材料づくりをそのまま動かす）を base として、同じ回・同じ行・同じ木で、
順を学ぶモデルの材料に E（強さの点数）だけ・V（前走の相手のその後）だけ・両方を足す。材料は全部の場のレースで作る（hist_all.py、CHIHO_EV=1）。Y年はY−1年まで（2017年から）。
出力：STORE/data/exp/nk_m6_pred_年.csv.gz（pl_1_・pl_3_ の base・E・V・EV）。HGBの3着内と着差のモデルは nk_m5_pred のものを手元で合わせる（nk_m6cmp.py）。
使い方：python chiho/an/nk_m6.py STORE 日付YYYYMMDD 年…（日付は出馬表のある日。材料づくりに使うだけ）"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jsoft, jk_elo, jk_rel
from sklearn.ensemble import HistGradientBoostingClassifier
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
store, day = sys.argv[1], sys.argv[2]
YEARS = [int(v) for v in sys.argv[3:]] or list(range(2021, 2027))
os.environ['CHIHO_EV'] = '1'
src = open(f'{HERE}/pipe.py', encoding='utf-8').read()
head = src[:src.index("Y = int(today[:4])")]
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}
sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H, KEY, log, NFIX, FEATS, NEW, EXTRA3, USE3, BW = (g[k] for k in ('H', 'KEY', 'log', 'NFIX', 'FEATS', 'NEW', 'EXTRA3', 'USE3', 'BW'))
if not g['SOFT']: raise SystemExit('LightGBM が無い')
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW] + list(g['JF']) + ([c for c in g['SF'] if c in H] if NFIX.get('展開の材料') else [])
FE3 = list(dict.fromkeys(c for c in FE3 if c in H))
CAT = ['場c', '馬場c', '天候c', '性c']
W3 = NFIX['木']
H, EF = jk_elo.add_elo_rel(H, KEY, ['E馬', 'E騎'])      # レースの中での差（5場のレースの中で）
VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
H = H[~H['予測'] & (H['年'] >= 2017)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']
H['着'] = pd.to_numeric(H['着'], errors='coerce')
log('材料', len(H), '材料の数', len(FE3), '強さの点数', EF, '点数のある行', round(float(H['E馬'].notna().mean()), 3), '相手のその後のある行', round(float((H['後数3'] > 0).mean()), 3))
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', '五場走数']].copy()
    F = [c for c in FE3 if tr[c].nunique(dropna=True) >= 2]
    FH = F + EF + VF; cat = [FH.index(c) for c in CAT if c in FH]
    ps = []
    for sd in (0, 1, 2):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
        m.fit(tr[FH], tr['3着内']); ps.append(m.predict_proba(te[FH])[:, 1])
    o['h_EV'] = np.mean(ps, axis=0); o['mg_EV'] = jk_rel.margin_fit_predict(tr, te, FH, cat, BIG); log(y, '年 HGBの3着内・着差のモデル（E＋V 入り）')
    for vn, FF in (('base', F), ('EV', F + EF + VF)):
        o['pl_1_' + vn], o['pl_3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CAT, wt=tuple(NFIX['重み']), params=W3), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['pl_1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/data/exp', exist_ok=True)
    o.to_csv(f'{store}/data/exp/nk_m6b_pred_{y}.csv.gz', index=False)
log('できた')
