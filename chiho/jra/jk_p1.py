"""中央競馬：P1 血統の材料をモデルに足す（検証計画「中央：血統」P1）。
今の一覧の作り方（HGBの3着内＋1〜3着の順を学ぶモデル M4b。jsoft.py）で、材料に血統（PEDF）を足したもの（ped）と足さないもの（base）を、
同じ回・同じ行で作る。Y年はY−1年まで（2017年から）。乱数0・1・2の3つの平均。
出力：STORE/jra/exp/p1_pred.csv.gz（年月日・場・R・馬番・年・n・勝・3着内・単勝オッズ・新馬・走数・初芝ダ・初距と、h_・p1_・p3_の base・ped）。
手元でくらべる（jk_p1cmp.py）。
使い方：python chiho/jra/jk_p1.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat, jsoft
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF, PEDF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


H = jfeat.build(f'{store}/jra/data', verbose=False, ped=True); log('材料', len(H), '血統のある行', round(float(H['父数'].notna().mean()), 3))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE0 = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
FE1 = FE0 + [c for c in PEDF if c in H and H[c].notna().any()]
H['初芝ダ'] = ((H['芝ダ走'] == 0) & (H['走数'] > 0)).astype(int); H['初距'] = ((H['当距走'] == 0) & (H['走数'] > 0)).astype(int)
OUT = ['n', '勝', '3着内', '単勝オッズ', '新馬', '走数', '初芝ダ', '初距']
H = H[[c for c in H.columns if c in set(FE1 + KEY + ['年', '着', '馬番'] + OUT)]].copy()
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
out = []
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年'] + OUT].copy()
    for vn, FE in (('base', FE0), ('ped', FE1)):
        F = [c for c in FE if tr[c].notna().any()]; cat = [F.index(c) for c in CATF if c in F]
        ps = []
        for sd in (0, 1, 2):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
            m.fit(tr[F], tr['3着内']); ps.append(m.predict_proba(te[F])[:, 1])
        o['h_' + vn] = np.mean(ps, axis=0)
        o['p1_' + vn], o['p3_' + vn] = jsoft.predict(jsoft.fit(tr, F, CATF, wt=(1.0, 0.5, 0.25)), te, F)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(F), '1着の当て分け（M4bそのまま）', round(float(-np.log(np.clip(o['p1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    out.append(o)
os.makedirs(f'{store}/jra/exp', exist_ok=True)
pd.concat(out, ignore_index=True).to_csv(f'{store}/jra/exp/p1_pred.csv.gz', index=False)
log('できた')
