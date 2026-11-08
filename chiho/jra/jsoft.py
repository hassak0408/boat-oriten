"""中央競馬：レースの中で比べる学び方（1着をレースごとのソフトマックスで学ぶ。検証計画 M3。jpipe.py が使う）。
LightGBM に自分で書いた目的関数（レースごとのソフトマックスの当て分け）を渡す。作り方は jk_m3.py と同じ
（葉63・葉の最小200・学びの速さ0.05・L2 1.0、学ぶレースの1割で早く止める。乱数0・1・2の3つの平均）。"""
import os, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']
P = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=200, lambda_l2=1.0, max_bin=255, verbose=-1, metric='None', feature_pre_filter=False)


def groups(gid):
    st = np.r_[0, np.flatnonzero(np.diff(gid)) + 1]
    return st, np.diff(np.r_[st, len(gid)])


def softmax(s, st, sz):
    m = np.maximum.reduceat(s, st); e = np.exp(s - np.repeat(m, sz))
    return e / np.repeat(np.add.reduceat(e, st), sz)


def _obj(preds, data):
    st, sz = data.gs; p = softmax(preds, st, sz)
    return p - data.get_label(), np.maximum(p * (1 - p), 1e-6)


def _feval(preds, data):
    st, sz = data.gs; y = data.get_label()
    m = np.maximum.reduceat(preds, st); s = preds - np.repeat(m, sz)
    ll = np.log(np.add.reduceat(np.exp(s), st)) - np.add.reduceat(y * s, st)
    return 'race_ll', float(ll.mean()), False


def _sorted(X):
    """レースごとにまとまるように並べる（元の行の番号は index に残る）"""
    o = pd.DataFrame({'d': X['年月日'].astype(str).values, 'p': X['場'].astype(str).values, 'r': pd.to_numeric(X['R'], errors='coerce').values,
                      'b': pd.to_numeric(X['馬番'], errors='coerce').values}, index=X.index).sort_values(['d', 'p', 'r', 'b'])
    g = o.groupby(['d', 'p', 'r'], sort=False).ngroup().values
    return o.index, g


def fit(X, FE, cat, seeds=(0, 1, 2), log=None):
    """X：学ぶ行（勝・年月日・場・R・馬番と材料）。勝ち馬のいないレースと1頭のレースは除く。同着はレースの中で分ける"""
    import lightgbm as lgb
    idx, g = _sorted(X)
    Y = X.loc[idx]; w = pd.Series(Y['勝'].values).groupby(g).transform('sum').values; n = pd.Series(g).groupby(g).transform('size').values
    keep = (w > 0) & (n >= 2)
    Y = Y[keep]; g = g[keep]; y = Y['勝'].values / w[keep]
    races = np.unique(g); models = []
    for sd in seeds:
        va = np.isin(g, races[np.random.default_rng(sd).random(len(races)) < 0.1])

        def ds(m):
            d = lgb.Dataset(Y.loc[m, FE], label=y[m], categorical_feature=[c for c in cat if c in FE], free_raw_data=False)
            d.gs = groups(g[m]); return d
        b = lgb.train(dict(P, objective=_obj, seed=sd, num_threads=os.cpu_count() or 4), ds(~va), num_boost_round=3000, valid_sets=[ds(va)], feval=_feval,
                      callbacks=[lgb.early_stopping(30, verbose=False)])
        models.append(b)
        if log: log('モデル 1着（レースの中で比べる）', '乱数', sd, '学習', int((~va).sum()), '回数', b.best_iteration)
    return models


def predict(models, X, FE):
    """1着の見込み（レースの中で足して1、3つの平均）。X の行の順で返す"""
    idx, g = _sorted(X); st, sz = groups(g); Z = X.loc[idx, FE]
    p = np.mean([softmax(b.predict(Z, num_iteration=b.best_iteration, raw_score=True), st, sz) for b in models], axis=0)
    return pd.Series(p, index=idx).reindex(X.index).values
