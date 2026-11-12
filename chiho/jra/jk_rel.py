"""N5・M6 で使う小さな部品（検証計画「今の評価を上回れるか」）：レースの中での差の材料と、着差を学ぶモデル。"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

REL = ['指数最高3', '指数平均3', '指数1', '過去3差', '全3率', '騎勝率', '調勝率', '過去3着率']
LOW = {'過去3差', '過去3着率'}      # 小さいほど良いもの（自分以外の一番良い馬＝一番小さい馬）


def add_rel(H, KEY):
    """REL のそれぞれに、レースの平均との差（_平均差）と、自分以外の一番良い馬との差（_他差）を足す。足した名前を返す"""
    new = {}; gk = [H[k] for k in KEY]
    for c in REL:
        if c not in H: continue
        v = pd.to_numeric(H[c], errors='coerce'); s = -v if c in LOW else v      # s は大きいほど良い
        new[c + '_平均差'] = v - v.groupby(gk).transform('mean')
        r = s.groupby(gk).rank(ascending=False, method='first')
        m1 = s.groupby(gk).transform('max')
        m2 = s.where(r >= 2).groupby(gk).transform('max')      # 2番目に良い値（1頭しか値が無ければ空）
        new[c + '_他差'] = s - np.where(r == 1, m2, m1)
    return pd.concat([H, pd.DataFrame(new, index=H.index)], axis=1), list(new)


def margin_fit_predict(tr, te, F, cat, params, seeds=(0, 1, 2)):
    """着差（秒、1000mあたり、0〜5で切る）を HGB で学んで、te の見込みの着差を返す（3つの平均）"""
    y = (pd.to_numeric(tr['差'], errors='coerce') / pd.to_numeric(tr['距離'], errors='coerce') * 1000).clip(0, 5)
    ok = y.notna().values
    ps = []
    for sd in seeds:
        m = HistGradientBoostingRegressor(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **params)
        m.fit(tr.loc[ok, F], y[ok]); ps.append(m.predict(te[F]))
    return np.mean(ps, axis=0)
