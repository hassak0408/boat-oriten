"""中央競馬：M1 今年のデータも学ばせる（検証計画 M1）。
2022〜2026年の各年の7〜12月を、(a) 去年までで学んだ見込み（jk_lap.py の出力）と、(b) その年の6月30日までで学んだ見込みでくらべる。
材料（純粋な評価・不利の印・ラップ）・行の順・乱数（0・1・2の平均）は jk_lap.py と同じ。
使い方：python jk_m1.py 材料.pkl STORE/jra/data jk_lap の出力.pkl 出力.pkl"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE
import jlap

t0 = time.time()
T = jlap.lap_table(sys.argv[2])
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy(); H['R'] = H['R'].astype(str)
lt = T.set_index(KEY)[jlap.LAPC]; idx = pd.MultiIndex.from_frame(H[KEY])
for c in jlap.LAPC: H[c] = lt[c].reindex(idx).values
S = H[['馬', '日', 'R'] + jlap.LAPC].copy(); S['Ri'] = pd.to_numeric(S['R'], errors='coerce')
S = S.sort_values(['馬', '日', 'Ri']); g = S.groupby('馬', sort=False)
NEW = []
for c, nm in (('前後半差', '前後半差'), ('中盤ゆるみ', '中盤'), ('失速', '失速')):
    S['前' + nm] = g[c].shift(1); S['過去3' + nm] = g[c].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()); NEW += ['前' + nm, '過去3' + nm]
for c in NEW: H[c] = S[c].reindex(H.index)
del S; H = H[H['合わない'] == 0].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE if c not in MKT and c in H and H[c].notna().any()] + NEW
cat = [FE.index(c) for c in CATF if c in FE]
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
print('材料', len(FE), round(time.time() - t0), '秒', flush=True)
P = []
for y in range(2022, 2027):
    tr = H[(H['年'] >= 2017) & (H['年月日'] <= f'{y}0630')]; te = H[(H['年'] == y) & (H['年月日'] >= f'{y}0701')].copy()
    if not len(te): continue
    for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
        ps = []
        for sd in (0, 1, 2):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
            m.fit(tr[FE], tr[tgt]); ps.append(m.predict_proba(te[FE])[:, 1])
        te[col] = np.mean(ps, axis=0)
    P.append(te[KEY + ['馬番', '年', 'n', '着', '勝', '3着内', '人気', '単勝オッズ', '新馬', '走数', 'p1', 'p3']])
    print(y, '年の7〜12月', len(te), '行', round(time.time() - t0), '秒', flush=True)
D = pd.concat(P, ignore_index=True); D.to_pickle(sys.argv[4])
B = pd.read_pickle(sys.argv[3]); B = B.loc[:, ~B.columns.duplicated()]; B['R'] = B['R'].astype(str)
M = D.merge(B[KEY + ['馬番', 'p1', 'p3']].rename(columns={'p1': 'p1b', 'p3': 'p3b'}), on=KEY + ['馬番'], how='inner')
M = M[(M['n'] >= 5) & M.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
for c in ('p1', 'p1b'): M[c] = M[c] / M.groupby(KEY)[c].transform('sum')
for c in ('p3', 'p3b'): M[c] = (M[c] * np.minimum(3, M['n']) / M.groupby(KEY)[c].transform('sum')).clip(1e-4, 0.97)


def ev(X, c1, c3):
    w = X[X['勝'] == 1]; l1 = float(-np.log(w[c1].clip(1e-6)).mean())
    p = X[c3]; y = X['3着内']; l3 = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    rk = X.groupby(KEY)[c3].rank(ascending=False, method='first')
    return l1, l3, X.loc[rk <= 3, '3着内'].mean() * 100, X.loc[rk == 1, '勝'].mean() * 100


for per, a, b in (('2022〜2023年の7〜12月', 2022, 2023), ('2024〜2026年の7〜12月', 2024, 2026)):
    X = M[M['年'].between(a, b)]
    for nm, c1, c3 in (('去年までで学ぶ（今）', 'p1b', 'p3b'), ('その年の6月まで学ぶ', 'p1', 'p3')):
        l1, l3, t3, t1 = ev(X, c1, c3)
        print(f'{per} {nm}：1着の当て分け {l1:.4f}・3着内の当て分け {l3:.4f}・上位3頭の3着内 {t3:.2f}%・1番手の1着 {t1:.2f}%（{X.groupby(KEY).ngroups}レース）')
print(round(time.time() - t0), '秒')
