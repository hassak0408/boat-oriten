"""中央競馬：M4 レースの中で1〜3着の順を学ぶ（プラケット・ルース。検証計画 M4）。
1着はレースの全部の馬のソフトマックス、2着は1着の馬を除いた残り、3着はさらに残りのソフトマックス。重みは M4a 1・1・1、M4b 1・0.5・0.25。
LightGBM に自分で書いた目的関数を渡す。材料・木の大きさ・早く止め方（1着の当て分け）・乱数0・1・2の3つの平均は jk_m3.py と同じ。
3着内の見込みは、同じ点数から1着・2着・3着になる見込みを足したもの（ハービル）。
出力：STORE/jra/exp/m4_pred.csv.gz（年月日・場・R・馬番・年・p1_a・p3_a・p1_b・p3_b）。手元でくらべる（jk_m4cmp.py）。
使い方：python chiho/jra/jk_m4.py STORE [年…（空なら2021〜2026）]"""
import os, sys, time, numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF

t0 = time.time()
store = sys.argv[1]
YEARS = [int(v) for v in sys.argv[2:]] or list(range(2021, 2027))
VARIANTS = {'a': (1.0, 1.0, 1.0), 'b': (1.0, 0.5, 0.25)}


def log(*a):
    print(f'[{time.time() - t0:6.0f}秒]', *a, flush=True)


H = jfeat.build(f'{store}/jra/data', verbose=False); log('材料', len(H))
H = H[~H['予測'] & (H['合わない'] == 0) & (H['年'] >= 2017)].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H and H[c].notna().any()]
H = H[[c for c in H.columns if c in set(FE + KEY + ['年', '勝', '着', '馬番'])]].copy()
H['Ri'] = pd.to_numeric(H['R'], errors='coerce'); H['馬番'] = pd.to_numeric(H['馬番'], errors='coerce')
H['着n'] = pd.to_numeric(H['着'], errors='coerce').fillna(99)
H = H.sort_values(['年月日', '場', 'Ri', '馬番']).reset_index(drop=True)
H['g'] = H.groupby(KEY, sort=False).ngroup()
w = H.groupby('g')['勝'].transform('sum'); n = H.groupby('g')['勝'].transform('size')
H = H[(w > 0) & (n >= 2)].reset_index(drop=True)
H['順'] = H.sort_values(['g', '着n', '馬番']).groupby('g').cumcount().reindex(H.index) + 1      # 着の順（同着は馬番の順）
H['y'] = H['勝'] / H.groupby('g')['勝'].transform('sum')      # 早く止めるときの1着の当て分け（同着は分ける）
cat = [c for c in CATF if c in FE]
log('学ぶ行', len(H), 'レース', H['g'].nunique(), '材料', len(FE))


def groups(gid):
    st = np.r_[0, np.flatnonzero(np.diff(gid)) + 1]
    return st, np.diff(np.r_[st, len(gid)])


def softmax_masked(s, m, st, sz):
    mx = np.maximum.reduceat(np.where(m > 0, s, -np.inf), st); mx = np.where(np.isfinite(mx), mx, 0)
    e = np.exp(s - np.repeat(mx, sz)) * m; z = np.add.reduceat(e, st)
    return e / np.repeat(np.where(z > 0, z, 1), sz), z > 0


def make_obj(wt):
    def obj(preds, data):
        st, sz = data.gs; o = data.order; grad = np.zeros_like(preds); hess = np.zeros_like(preds)
        m = np.ones_like(preds)
        for k, wk in enumerate(wt, start=1):
            p, has = softmax_masked(preds, m, st, sz)
            tgt = (o == k).astype(float)
            ok = np.repeat(has & (np.add.reduceat(tgt, st) > 0), sz)      # その着の馬がいるレースだけ
            grad += np.where(ok, wk * (p - tgt), 0); hess += np.where(ok, wk * p * (1 - p), 0)
            m = m * (o != k)
        return grad, np.maximum(hess, 1e-6)
    return obj


def feval(preds, data):
    st, sz = data.gs; y = data.get_label()
    mx = np.maximum.reduceat(preds, st); s = preds - np.repeat(mx, sz)
    ll = np.log(np.add.reduceat(np.exp(s), st)) - np.add.reduceat(y * s, st)
    return 'race_ll', float(ll.mean()), False


def dataset(X):
    d = lgb.Dataset(X[FE], label=X['y'].values, categorical_feature=cat, free_raw_data=False)
    d.gs = groups(X['g'].values); d.order = X['順'].values
    return d


def harville3(p, st, sz):
    """1着の見込み p（レースの中で足して1）から、1〜3着に入る見込み（ハービル）"""
    out = np.empty_like(p)
    for a, b in zip(st, sz):
        q = p[a:a + b].astype(float)
        if b <= 3: out[a:a + b] = 1.0; continue
        r = q / np.clip(1 - q, 1e-12, None)
        p2 = q * (r.sum() - r)
        A = np.outer(q, q) / np.clip(1 - q, 1e-12, None)[:, None]; np.fill_diagonal(A, 0)
        den = np.clip(1 - q[:, None] - q[None, :], 1e-12, None); B = A / den; np.fill_diagonal(B, 0)
        p3 = q * (B.sum() - B.sum(0) - B.sum(1))
        out[a:a + b] = np.clip(q + p2 + p3, 0, 1)
    return out


out = []
for y in YEARS:
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y]
    if not len(te): continue
    races = tr['g'].unique(); o = te[KEY + ['馬番', '年']].copy(); st, sz = groups(te['g'].values)
    for vn, wt in VARIANTS.items():
        ps = []
        for sd in (0, 1, 2):
            va_r = set(races[np.random.default_rng(sd).random(len(races)) < 0.1])
            mv = tr['g'].isin(va_r).values
            dtr, dva = dataset(tr[~mv]), dataset(tr[mv])
            P = dict(objective=make_obj(wt), learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, lambda_l2=1.0, max_bin=255, seed=sd,
                     num_threads=os.cpu_count() or 4, verbose=-1, metric='None', feature_pre_filter=False)
            b = lgb.train(P, dtr, num_boost_round=3000, valid_sets=[dva], feval=feval, callbacks=[lgb.early_stopping(30, verbose=False)])
            s = b.predict(te[FE], num_iteration=b.best_iteration, raw_score=True)
            ps.append(softmax_masked(s, np.ones_like(s), st, sz)[0])
            log(y, '年', 'M4' + vn, '乱数', sd, '回数', b.best_iteration, '確かめの1着の当て分け', round(b.best_score['valid_0']['race_ll'], 4))
        p1 = np.mean(ps, axis=0); p1 = p1 / np.repeat(np.add.reduceat(p1, st), sz)
        o['p1_' + vn] = p1; o['p3_' + vn] = harville3(p1, st, sz)
        wn = te['y'].values > 0
        log(y, '年 M4' + vn, '1着の当て分け', round(float(-np.log(np.clip(p1[wn], 1e-9, 1)).mean()), 4))
    out.append(o)
os.makedirs(f'{store}/jra/exp', exist_ok=True)
pd.concat(out, ignore_index=True).to_csv(f'{store}/jra/exp/m4_pred.csv.gz', index=False)
log('できた')
