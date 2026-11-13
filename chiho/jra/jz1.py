"""中央競馬：Z1（市場のずれ）の f を学ぶ・出す（検証計画「Z1」「Z1の印」）。jk_z1.py の学び方をそのまま、一覧の作り方（jpipe.py）から使えるように分けたもの。
1着 ∝ 市場の見込み × exp(f)。f は朝にわかる材料（オッズ・人気・血統・レースの中での差は入れない）の木のモデルで、市場の見込みの対数を出発点（init_score）にして、
勝ち馬を当てる形（レースの中のソフトマックス）で学ぶ。今日の馬にはオッズを使わない（f は材料だけから出る）。"""
import os, numpy as np, pandas as pd
import jsoft

PRM = dict(learning_rate=0.02, num_leaves=15, min_data_in_leaf=1000, lambda_l2=50.0, feature_fraction=0.7)


def fit_resid(X, FE, cat, seeds=(0, 1, 2), log=print):
    """jsoft.fit と同じ並べ方・分け方で、出発点を市場の見込みの対数にして1着だけを学ぶ（X には pm＝市場の見込み、勝・着・馬番が要る）"""
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
        models.append(b); log('  市場のずれ 乱数', sd, '回数', b.best_iteration, '確かめの当て分け', round(b.best_score['valid_0']['race_ll'], 5))
    return models


def predict(models, X, FE):
    return np.mean([b.predict(X[FE], num_iteration=b.best_iteration, raw_score=True) for b in models], axis=0)
