"""中央競馬：Z1 市場のずれを学ぶ（検証計画 Z1）。1着 ∝ 市場の見込み × exp(f)。f は今の一覧と同じ材料（オッズ・人気は入れない）の木のモデルで、
市場の見込みの対数を出発点（init_score）にして、勝ち馬を当てる形（レースの中のソフトマックス）で学ぶ。Y年はY−1年まで（2017年から）。乱数0・1・2の平均。
出力：STORE/jra/exp/z1_pred_年.csv.gz（f・pm＝市場の見込み・勝・単勝オッズ・人気など）。手元でくらべる（jk_z1cmp.py）。
使い方：python chiho/jra/jk_z1.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jfeat, jsoft
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))
PRM = dict(learning_rate=0.02, num_leaves=15, min_data_in_leaf=1000, lambda_l2=50.0, feature_fraction=0.7)


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


def fit_resid(X, FE, cat, seeds=(0, 1, 2)):
    """jsoft.fit と同じ並べ方・分け方で、出発点を市場の見込みの対数にして1着だけを学ぶ"""
    import lightgbm as lgb
    idx, g = jsoft._sorted(X); Y = X.loc[idx]
    w = pd.Series(Y['勝'].values).groupby(g).transform('sum').values; n = pd.Series(g).groupby(g).transform('size').values
    keep = (w > 0) & (n >= 2); Y = Y[keep]; g = g[keep]; y = Y['勝'].values / w[keep]; ini = np.log(Y['pm'].values)
    od = pd.DataFrame({'g': g, 'f': pd.to_numeric(Y['着'], errors='coerce').fillna(99).values, 'b': pd.to_numeric(Y['馬番'], errors='coerce').values})
    order = (od.sort_values(['g', 'f', 'b']).groupby('g').cumcount() + 1).reindex(od.index).values
    races = np.unique(g); models = []
    for sd in seeds:
        va = np.isin(g, races[np.random.default_rng(sd).random(len(races)) < 0.1])

        def ds(m):
            d = lgb.Dataset(Y.loc[m, FE], label=y[m], init_score=ini[m], categorical_feature=[c for c in cat if c in FE], free_raw_data=False)
            d.gs = jsoft.groups(g[m]); d.order = order[m]; return d
        b = lgb.train(dict(jsoft.P, **PRM, objective=jsoft.make_obj((1.0,)), seed=sd, num_threads=os.cpu_count() or 4), ds(~va), num_boost_round=2000,
                      valid_sets=[ds(va)], feval=jsoft._feval, callbacks=[lgb.early_stopping(50, verbose=False)])
        models.append(b); log('  乱数', sd, '回数', b.best_iteration, '確かめの当て分け', round(b.best_score['valid_0']['race_ll'], 5))
    return models


H = jfeat.build(f'{store}/jra/data', verbose=False); log('材料', len(H))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
o_ = pd.to_numeric(H['単勝オッズ'], errors='coerce'); gk = [H[k] for k in KEY]
H = H[o_.groupby(gk).transform(lambda s: s.notna().all()) & (H['n'] >= 5)].copy()
q = 1 / pd.to_numeric(H['単勝オッズ'], errors='coerce'); H['pm'] = q / q.groupby([H[k] for k in KEY]).transform('sum')
OUT = ['n', '勝', '3着内', '単勝オッズ', '人気', 'pm', '新馬', '走数']
H = H[[c for c in H.columns if c in set(FE + KEY + ['年', '着', '馬番'] + OUT)]].copy()
log('オッズのそろったレースの馬', len(H), '材料', len(FE))
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    F = [c for c in FE if tr[c].notna().any()]
    ms = fit_resid(tr, F, CATF)
    o = te[KEY + ['馬番', '年'] + [c for c in OUT if c in te]].copy()
    o['f'] = np.mean([b.predict(te[F], num_iteration=b.best_iteration, raw_score=True) for b in ms], axis=0)
    log(y, '年 f の散らばり（標準偏差）', round(float(o['f'].std()), 4))
    os.makedirs(f'{store}/jra/exp', exist_ok=True)
    o.to_csv(f'{store}/jra/exp/z1_pred_{y}.csv.gz', index=False)
log('できた')
