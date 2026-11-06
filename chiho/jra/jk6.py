"""中央競馬：K6c' 「前が速くて止まった」をモデルの材料にする（検証計画 K6c'）。
今の一覧のモデル（純粋な評価・不利の印あり。jk.py TROUBLE=1 の見込み）と、材料（前速い・前ゆっくり・前初角・前先行崩れ）を足したモデルの1着の見込みをくらべる。
使い方：python jk6.py 材料.pkl 今の見込み.pkl 出力.pkl"""
import os, sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy()
H['Ri'] = pd.to_numeric(H['R'], errors='coerce')
# ペース比の分け目（K6と同じ：芝ダと距離の帯ごと、2016〜2018年のレース）
H['距帯3'] = pd.cut(H['距離'], [0, 1400, 1800, 9999], labels=['〜1400', '1401〜1800', '1801〜'])
qs = H[H['年'] <= 2018].drop_duplicates(KEY).groupby(['芝ダ', '距帯3'], observed=True)['ペース比'].quantile([0.25, 0.75]).unstack()
lo = np.array([qs.loc[(a, b), 0.25] if (a, b) in qs.index else np.nan for a, b in zip(H['芝ダ'], H['距帯3'])], dtype=float)
hi = np.array([qs.loc[(a, b), 0.75] if (a, b) in qs.index else np.nan for a, b in zip(H['芝ダ'], H['距帯3'])], dtype=float)
H['速い'] = (H['ペース比'] <= lo).astype(float).where(H['ペース比'].notna())
H['ゆっくり'] = (H['ペース比'] >= hi).astype(float).where(H['ペース比'].notna())
H = H.sort_values(['馬', '日', 'Ri']).reset_index(drop=True); g = H.groupby('馬', sort=False)
H['前速い'] = g['速い'].shift(1); H['前ゆっくり'] = g['ゆっくり'].shift(1); H['前初角'] = g['初角'].shift(1)
H['前先行崩れ'] = ((H['前初角'] <= 3) & (H['前速い'] == 1) & (H['着x1'] >= 6)).astype(float).where(H['前初角'].notna() & H['前速い'].notna())
NEW = ['前速い', '前ゆっくり', '前初角', '前先行崩れ']
H = H[H['合わない'] == 0].copy()
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE if c not in MKT and c in H and H[c].notna().any()] + ([] if os.environ.get('NONEW') == '1' else NEW)      # NONEW=1：足さない（同じ行の順で今のモデルを作り直す確かめ）
cat = [FE.index(c) for c in CATF if c in FE]
print('材料', len(FE), '足した', NEW, round(time.time() - t0), '秒', flush=True)
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
P = []
for y in range(2021, 2027):
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
    m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG)
    m.fit(tr[FE], tr['勝']); te['p1新'] = m.predict_proba(te[FE])[:, 1]
    P.append(te[KEY + ['馬番', '年', 'n', '勝', '単勝オッズ', '前先行崩れ', '前不利あり', 'p1新']])
    print('足したモデル', y, '回数', m.n_iter_, round(time.time() - t0), '秒', flush=True)
D = pd.concat(P, ignore_index=True); D.to_pickle(sys.argv[3])
B = pd.read_pickle(sys.argv[2]); B = B.loc[:, ~B.columns.duplicated()][KEY + ['馬番', 'p1']]
D = D.merge(B, on=KEY + ['馬番'], how='inner')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
for c in ('p1', 'p1新'): D[c] = D[c] / D.groupby(KEY)[c].transform('sum')
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')


def loss(X, c):
    w = X[X['勝'] == 1]; return float(-np.log(w[c].clip(1e-6)).mean())


k6c = (D['前先行崩れ'] == 1) & (D['前不利あり'] == 0)
for per, a, b in (('2021〜2023', 2021, 2023), ('2024〜2026', 2024, 2026)):
    X = D[D['年'].between(a, b)]; K = X[k6c.loc[X.index]]
    print(f"{per}：1着の当て分け 今 {loss(X, 'p1'):.4f} → 足した {loss(X, 'p1新'):.4f}／K6cの馬 {len(K)}頭 実際÷評価 今 {K['勝'].sum()/K['p1'].sum():.3f} → 足した {K['勝'].sum()/K['p1新'].sum():.3f}"
          f"（実際÷市場 {K['勝'].sum()/K['q'].sum():.3f}）")
print(round(time.time() - t0), '秒')
