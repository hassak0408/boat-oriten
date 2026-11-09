"""地方：N4（検証計画「地方：精度を上げる」N4。展開の材料）。N3（nk_m4b.py）の材料に、脚質の予想に使っている展開の材料（SF）を足したものだけを作る。
元の説明：地方：N1・N2。今の一覧の材料（pipe.py の材料づくりの部分をそのまま動かす）で、
年ごとに学んで2021〜2026年の見込みを出す。今（HGB 乱数0）、HGB（乱数0・1・2の平均）、1〜3着の順を学ぶモデル（jsoft.py、中央の M4b・M5b と同じ作り方）、
それぞれ騎手の格の差の材料あり（_j）。出力：STORE/data/exp/nk_m4c_pred（年）.csv.gz（h_3_s・pl_1_s・pl_3_s）。手元でくらべる（nk_m4cmp.py）。
使い方：python chiho/an/nk_m4c.py STORE 日付YYYYMMDD（出馬表のある日。材料づくりに使うだけで、その日の行は使わない）"""
import os, sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jsoft
store, day = sys.argv[1], sys.argv[2]
YEARS = [int(v) for v in sys.argv[3:]] or list(range(2021, 2027))
ARGV = list(sys.argv)
src = open(f'{HERE}/pipe.py', encoding='utf-8').read()
head = src[:src.index("Y = int(today[:4])")]      # pipe.py の材料づくりの部分（モデルを作る前まで）
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}
sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H, FEATS, NEW, EXTRA3, USE3, BW, KEY, log = (g[k] for k in ('H', 'FEATS', 'NEW', 'EXTRA3', 'USE3', 'BW', 'KEY', 'log'))
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW]
# 騎手の格の差（N2）：今の騎手の勝率・3着内率 − 前走の騎手の勝率・3着内率（どちらもその日より前の成績）
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True); gg = H.groupby('馬', sort=False)
H['騎勝率差'] = H['騎勝率'] - gg['騎勝率'].shift(1); H['騎3率差'] = H['騎3率'] - gg['騎3率'].shift(1)
JF = ['騎勝率差', '騎3率差']


def roll(H, ent, cols, days):
    """ent ごとに、前の日までの days 日の合計（同じ日は入れない。feat.roll365 と同じ作り方）"""
    D = H.groupby([ent, '日'])[cols].sum().reset_index().sort_values([ent, '日'])
    out = []
    for e, g in D.groupby(ent, sort=False):
        d = g['日'].values.astype('datetime64[D]').astype(np.int64)
        c = np.vstack([np.zeros(len(cols))] + [g[cols].values]).cumsum(axis=0)
        lo = np.searchsorted(d, d - days, side='left'); hi = np.arange(len(d))
        out.append(pd.DataFrame(c[hi] - c[lo], columns=cols).assign(**{ent: e, '日': g['日'].values}))
    return pd.concat(out, ignore_index=True)


# 騎手の性能（N3）：近ごろの調子（60日）、その競馬場での成績（365日）、厩舎との組み合わせ（365日）
H['騎場'] = H['騎'] + '#' + H['競馬場'].astype(str); H['騎調'] = H['騎'] + '#' + H['調']
KF = []
for ent, days, pre in (('騎', 60, '騎近'), ('騎場', 365, '騎場'), ('騎調', 365, '騎調')):
    if all(pre + k in H for k in ('数', '勝率', '3率')):      # 今の pipe.py（N3）の材料づくりで、もう入っている
        KF += [pre + '数', pre + '勝率', pre + '3率']; continue
    S = roll(H, ent, ['乗', '勝', '3着内'], days)
    S[pre + '数'] = S['乗']; S[pre + '勝率'] = S['勝'] / S['乗'].where(S['乗'] > 0); S[pre + '3率'] = S['3着内'] / S['乗'].where(S['乗'] > 0)
    H = H.merge(S[[ent, '日', pre + '数', pre + '勝率', pre + '3率']], on=[ent, '日'], how='left'); KF += [pre + '数', pre + '勝率', pre + '3率']
log('騎手の性能の材料', KF, '入った行', round(float(H['騎近数'].notna().mean()), 3))
CAT = ['場c', '馬場c', '天候c', '性c']
W3 = {'num_leaves': 127, 'min_data_in_leaf': 400, 'feature_fraction': 0.7, 'lambda_l2': 10.0}
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
H = H[~H['予測'] & (H['年'] >= 2017)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']      # jsoft.py の名前に合わせる
H['着'] = pd.to_numeric(H['着'], errors='coerce')
log('材料', len(H), '材料の数', len(FE3), '騎手の格の差が入った行', round(float(H['騎勝率差'].notna().mean()), 3))
out = []
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', '五場走数']].copy()
    for vn, FE in (('_s', FE3 + JF + KF + [c for c in g['SF'] if c in H]),):      # 展開の材料（pipe.py の SF）
        F = [c for c in FE if tr[c].nunique(dropna=True) >= 2]; cat = [F.index(c) for c in CAT if c in F]
        ps = []
        for sd in (0, 1, 2):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
            m.fit(tr[F], tr['3着内']); p = m.predict_proba(te[F])[:, 1]; ps.append(p)
        o['h_3' + vn] = np.mean(ps, axis=0)
        o['pl_1' + vn], o['pl_3' + vn] = jsoft.predict(jsoft.fit(tr, F, CAT, wt=(1.0, 0.5, 0.25), params=W3), te, F)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(F), '順を学ぶモデルの1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['pl_1' + vn].values[w], 1e-9, 1)).mean()), 4))
    out.append(o)
os.makedirs(f'{store}/data/exp', exist_ok=True)
suffix = ('_' + '_'.join(map(str, YEARS))) if len(ARGV) > 3 else ''
pd.concat(out, ignore_index=True).to_csv(f'{store}/data/exp/nk_m4c_pred{suffix}.csv.gz', index=False)
log('できた')
