"""中央競馬：レースの中で1〜3着の順を学ぶ（プラケット・ルース。検証計画 M3・M4。jpipe.py が使う）。
1着はレースの全部の馬のソフトマックス、2着は1着の馬を除いた残り、3着はさらに残り。着ごとの重み wt（M4b は 1・0.5・0.25。wt=(1,) なら1着だけ＝M3）。
LightGBM に自分で書いた目的関数を渡す。作り方は jk_m4.py と同じ（葉63・葉の最小200・学びの速さ0.05・L2 1.0、学ぶレースの1割で1着の当て分けを見て早く止める、
乱数0・1・2の3つの平均）。着の順は着順（同着は馬番の順）。3着内の見込みは、同じ点数から1着・2着・3着になる見込みを足したもの（ハービル）。"""
import os, numpy as np, pandas as pd

P = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, lambda_l2=1.0, max_bin=255, verbose=-1, metric='None', feature_pre_filter=False)


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
        rw = getattr(data, 'rw', None)      # レースの重み（検証計画 N5・M6 の td。無ければ全部1）
        if rw is not None: grad *= rw; hess *= rw
        return grad, np.maximum(hess, 1e-6)
    return obj


def _feval(preds, data):
    st, sz = data.gs; y = data.get_label()
    mx = np.maximum.reduceat(preds, st); s = preds - np.repeat(mx, sz)
    ll = np.log(np.add.reduceat(np.exp(s), st)) - np.add.reduceat(y * s, st)
    return 'race_ll', float(ll.mean()), False


def harville3(p, st, sz):
    """1着の見込み p（レースの中で足して1）から、1〜3着に入る見込み（ハービル）"""
    out = np.empty_like(p, dtype=float)
    for a, b in zip(st, sz):
        q = p[a:a + b].astype(float)
        if b <= 3: out[a:a + b] = 1.0; continue
        r = q / np.clip(1 - q, 1e-12, None)
        p2 = q * (r.sum() - r)
        A = np.outer(q, q) / np.clip(1 - q, 1e-12, None)[:, None]; np.fill_diagonal(A, 0)
        B = A / np.clip(1 - q[:, None] - q[None, :], 1e-12, None); np.fill_diagonal(B, 0)
        p3 = q * (B.sum() - B.sum(0) - B.sum(1))
        out[a:a + b] = np.clip(q + p2 + p3, 0, 1)
    return out


def _sorted(X):
    """レースごとにまとまるように並べる（元の行の番号は index に残る）"""
    o = pd.DataFrame({'d': X['年月日'].astype(str).values, 'p': X['場'].astype(str).values, 'r': pd.to_numeric(X['R'], errors='coerce').values,
                      'b': pd.to_numeric(X['馬番'], errors='coerce').values}, index=X.index).sort_values(['d', 'p', 'r', 'b'])
    g = o.groupby(['d', 'p', 'r'], sort=False).ngroup().values
    return o.index, g


def fit(X, FE, cat, wt=(1.0, 0.5, 0.25), seeds=(0, 1, 2), log=None, params=None, rw=None):
    """X：学ぶ行（勝・着・年月日・場・R・馬番と材料）。勝ち馬のいないレースと1頭のレースは除く。params で木の大きさなどを替えられる（検証計画 M5）"""
    import lightgbm as lgb
    idx, g = _sorted(X)
    Y = X.loc[idx]; w = pd.Series(Y['勝'].values).groupby(g).transform('sum').values; n = pd.Series(g).groupby(g).transform('size').values
    keep = (w > 0) & (n >= 2)
    Y = Y[keep]; g = g[keep]; y = Y['勝'].values / w[keep]
    rwv = None if rw is None else pd.Series(np.asarray(rw, dtype=float), index=X.index).loc[Y.index].values      # rw：X の行の順の重み（同じレースは同じ値）
    od = pd.DataFrame({'g': g, 'f': pd.to_numeric(Y['着'], errors='coerce').fillna(99).values, 'b': pd.to_numeric(Y['馬番'], errors='coerce').values})
    order = (od.sort_values(['g', 'f', 'b']).groupby('g').cumcount() + 1).reindex(od.index).values      # 着の順（同着は馬番の順）
    races = np.unique(g); models = []
    for sd in seeds:
        va = np.isin(g, races[np.random.default_rng(sd).random(len(races)) < 0.1])

        def ds(m):
            d = lgb.Dataset(Y.loc[m, FE], label=y[m], categorical_feature=[c for c in cat if c in FE], free_raw_data=False)
            d.gs = groups(g[m]); d.order = order[m]
            if rwv is not None: d.rw = rwv[m]
            return d
        b = lgb.train(dict(P, **(params or {}), objective=make_obj(tuple(wt)), seed=sd, num_threads=os.cpu_count() or 4), ds(~va), num_boost_round=3000, valid_sets=[ds(va)],
                      feval=_feval, callbacks=[lgb.early_stopping(30, verbose=False)])
        models.append(b)
        if log: log('モデル 1〜3着の順（レースの中で比べる）', '乱数', sd, '学習', int((~va).sum()), '回数', b.best_iteration)
    return models


def predict(models, X, FE):
    """1着の見込み（レースの中で足して1、3つの平均）と、そこからの3着内の見込み（ハービル）。X の行の順で返す"""
    idx, g = _sorted(X); st, sz = groups(g); Z = X.loc[idx, FE]
    p = np.mean([softmax_masked(b.predict(Z, num_iteration=b.best_iteration, raw_score=True), np.ones(len(Z)), st, sz)[0] for b in models], axis=0)
    p = p / np.repeat(np.add.reduceat(p, st), sz)
    p3 = harville3(p, st, sz)
    return pd.Series(p, index=idx).reindex(X.index).values, pd.Series(p3, index=idx).reindex(X.index).values
