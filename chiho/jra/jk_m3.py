"""中央競馬：M3 レースの中で比べる学び方（1着をレースごとのソフトマックスで学ぶ。検証計画 M3）。
LightGBM に自分で書いた目的関数（レースごとのソフトマックスの当て分け）を渡す。材料は今の一覧と同じ（jpipe.py の FE）。
Y年はY−1年まで（2017年から）。乱数0・1・2の3つの平均（早く止めるための確かめに使うレース（学ぶ年の1割）の選び方が変わる）。
出力：STORE/jra/exp/m3_pred.csv.gz（年月日・場・R・馬番・年・p1s）。手元で今の見込みとくらべる（jk_m3cmp.py）。
使い方：python chiho/jra/jk_m3.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


H = jfeat.build(f'{store}/jra/data', verbose=False); log('材料', len(H))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
H = H[[c for c in H.columns if c in set(FE + KEY + ['年', '勝', '馬番'])]].copy()
H['Ri'] = pd.to_numeric(H['R'], errors='coerce'); H['馬番'] = pd.to_numeric(H['馬番'], errors='coerce')
H = H.sort_values(['年月日', '場', 'Ri', '馬番']).reset_index(drop=True)
H['g'] = H.groupby(KEY, sort=False).ngroup()
w = H.groupby('g')['勝'].transform('sum'); n = H.groupby('g')['勝'].transform('size')
H = H[(w > 0) & (n >= 2)].reset_index(drop=True)
H['y'] = H['勝'] / H.groupby('g')['勝'].transform('sum')      # 同着は分ける（レースの中で足して1）
cat = [c for c in CATF if c in FE]
log('学ぶ行', len(H), 'レース', H['g'].nunique(), '材料', len(FE))


def groups(gid):
    st = np.r_[0, np.flatnonzero(np.diff(gid)) + 1]
    return st, np.diff(np.r_[st, len(gid)])


def softmax(s, st, sz):
    m = np.maximum.reduceat(s, st); e = np.exp(s - np.repeat(m, sz))
    return e / np.repeat(np.add.reduceat(e, st), sz)


def obj(preds, data):
    st, sz = data.gs; p = softmax(preds, st, sz)
    return p - data.get_label(), np.maximum(p * (1 - p), 1e-6)


def feval(preds, data):
    st, sz = data.gs; y = data.get_label()
    m = np.maximum.reduceat(preds, st); s = preds - np.repeat(m, sz)
    ll = np.log(np.add.reduceat(np.exp(s), st)) - np.add.reduceat(y * s, st)
    return 'race_ll', float(ll.mean()), False


def dataset(X):
    d = lgb.Dataset(X[FE], label=X['y'].values, categorical_feature=cat, free_raw_data=False)
    d.gs = groups(X['g'].values)
    return d


out = []
for y in YEARS:
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y]
    if not len(te): continue
    races = tr['g'].unique(); ps = []
    for sd in (0, 1, 2):
        va_r = set(races[np.random.default_rng(sd).random(len(races)) < 0.1])
        mv = tr['g'].isin(va_r).values
        dtr, dva = dataset(tr[~mv]), dataset(tr[mv])
        P = dict(objective=obj, learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, lambda_l2=1.0, max_bin=255, seed=sd,
                 num_threads=os.cpu_count() or 4, verbose=-1, metric='None', feature_pre_filter=False)
        b = lgb.train(P, dtr, num_boost_round=3000, valid_sets=[dva], feval=feval, callbacks=[lgb.early_stopping(30, verbose=False)])
        st, sz = groups(te['g'].values)
        ps.append(softmax(b.predict(te[FE], num_iteration=b.best_iteration, raw_score=True), st, sz))
        log(y, '年 乱数', sd, '回数', b.best_iteration, '確かめの当て分け', round(b.best_score['valid_0']['race_ll'], 4))
    o = te[KEY + ['馬番', '年']].copy(); o['p1s'] = np.mean(ps, axis=0)
    wn = te['y'].values > 0
    log(y, '年の1着の当て分け（ソフトマックス、全部のレース）', round(float(-np.log(np.clip(o['p1s'].values[wn], 1e-9, 1)).mean()), 4))
    out.append(o)
os.makedirs(f'{store}/jra/exp', exist_ok=True)
pd.concat(out, ignore_index=True).to_csv(f'{store}/jra/exp/m3_pred.csv.gz', index=False)
log('できた')
