"""中央競馬：U1 1頭ごとの上り3F（推定上り）をモデルに足す（検証計画 U1）。
jk_lap.py と同じモデル（純粋な評価・不利の印・ラップ、3つの平均）に、jra/ses/ の推定上りから作った材料を足してくらべる。
使い方：python jk_up.py 材料.pkl STORE jk_lap の出力.pkl 出力.pkl"""
import sys, glob, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE
import jlap

t0 = time.time()
store = sys.argv[2]


def up_table(store):
    """jra/ses から1頭ごとの推定上り。レースの中の順位÷頭数（上り順率）と、一番速い上りとの差（上り差）"""
    rs = []
    for f in glob.glob(f'{store}/jra/ses/*/*.csv.gz'):
        r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '馬番', '推定上り'])
        rs.append(r)
    U = pd.concat(rs, ignore_index=True)
    U['上り'] = pd.to_numeric(U['推定上り'], errors='coerce'); U['馬番'] = pd.to_numeric(U['馬番'], errors='coerce')
    U = U[U['上り'].notna() & U['馬番'].notna()].drop_duplicates(KEY + ['馬番'])
    g = U.groupby(KEY)['上り']
    U['推上順率'] = g.rank(method='min') / g.transform('size'); U['推上差'] = U['上り'] - g.transform('min')      # 名前は成績表の「上り差」（レースの上り3Fから）と分ける
    U['推上1位'] = (g.rank(method='min') == 1).astype(float)
    return U[KEY + ['馬番', '推上順率', '推上差', '推上1位']]


T = jlap.lap_table(f'{store}/jra/data'); U = up_table(store)
print('ラップ', len(T), '推定上り', len(U), round(time.time() - t0), '秒', flush=True)
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy(); H['R'] = H['R'].astype(str)
lt = T.set_index(KEY)[jlap.LAPC]; idx = pd.MultiIndex.from_frame(H[KEY])
for c in jlap.LAPC: H[c] = lt[c].reindex(idx).values
ut = U.set_index(KEY + ['馬番'])[['推上順率', '推上差', '推上1位']]
idx2 = pd.MultiIndex.from_arrays([H[k] for k in KEY] + [pd.to_numeric(H['馬番'], errors='coerce')])
for c in ('推上順率', '推上差', '推上1位'): H[c] = ut[c].reindex(idx2).values
print('推定上りが入った行', round(float(H['推上順率'].notna().mean()), 3), flush=True)
S = H[['馬', '日', 'R'] + jlap.LAPC + ['推上順率', '推上差', '推上1位']].copy(); S['Ri'] = pd.to_numeric(S['R'], errors='coerce')
S = S.sort_values(['馬', '日', 'Ri']); g = S.groupby('馬', sort=False)
LAPN, UPN = [], []
for c, nm in (('前後半差', '前後半差'), ('中盤ゆるみ', '中盤'), ('失速', '失速')):
    S['前' + nm] = g[c].shift(1); S['過去3' + nm] = g[c].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()); LAPN += ['前' + nm, '過去3' + nm]
for c in ('推上順率', '推上差'):
    S['前' + c] = g[c].shift(1); S['過去3' + c] = g[c].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()); UPN += ['前' + c, '過去3' + c]
S['過去5推上1位'] = g['推上1位'].transform(lambda s: s.shift(1).rolling(5, min_periods=1).sum()); UPN.append('過去5推上1位')
for c in LAPN + UPN: H[c] = S[c].reindex(H.index)
del S; H = H[H['合わない'] == 0].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE if c not in MKT and c in H and H[c].notna().any()] + LAPN + UPN
cat = [FE.index(c) for c in CATF if c in FE]
print('材料', len(FE), '足した', UPN, round(time.time() - t0), '秒', flush=True)
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
P = []
for y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
    for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
        ps = []
        for sd in (0, 1, 2):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **BIG)
            m.fit(tr[FE], tr[tgt]); ps.append(m.predict_proba(te[FE])[:, 1])
        te[col] = np.mean(ps, axis=0)
    P.append(te[KEY + ['馬番', '年', 'n', '着', '勝', '3着内', '人気', '単勝オッズ', '新馬', '走数', 'p1', 'p3']])
    print('上りを足したモデル', y, round(time.time() - t0), '秒', flush=True)
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


for per, a, b in (('2021〜2023', 2021, 2023), ('2024〜2026', 2024, 2026)):
    X = M[M['年'].between(a, b)]
    for nm, c1, c3 in (('今（3つの平均＋ラップ）', 'p1b', 'p3b'), ('上りを足した', 'p1', 'p3')):
        l1, l3, t3, t1 = ev(X, c1, c3)
        print(f'{per} {nm}：1着の当て分け {l1:.4f}・3着内の当て分け {l3:.4f}・上位3頭の3着内 {t3:.2f}%・1番手の1着 {t1:.2f}%（{X.groupby(KEY).ngroups}レース）')
print(round(time.time() - t0), '秒')
