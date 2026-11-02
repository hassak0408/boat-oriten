"""中央競馬：正しい評価で舐められている馬を探す（検証計画 K3・K4）。
K3：市場から来る材料（前走の人気・騎手と厩舎の単勝の回収）を外したモデル（純粋な評価）。不利の印（K1）があれば足す（環境変数 TROUBLE=1）。
K4：照らし合わせ (a) 評価の上位3頭なのに6番人気以下 (b) 人気の帯ごとに評価÷市場の上位2割。
使い方：python jk.py 材料.pkl STORE/jra/data 出力.pkl [前に作った見込み.pkl]"""
import os, sys, glob, json, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
MKT = ['前人気', '前人気率', '前人気着差', '騎単回', '調単回']
TROUBLE = [c for c in H.columns if c.startswith('前不利') or c.startswith('過去3不利')] if os.environ.get('TROUBLE') == '1' else []
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE if c not in MKT and c in H and H[c].notna().any()]
print('材料', len(FE), '不利の印', TROUBLE, flush=True)
cat = [FE.index(c) for c in CATF if c in FE]
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
P = []
REUSE = os.environ.get('REUSE') == '1' and os.path.exists(sys.argv[3])      # 見込みを作り直さずに数えるだけ
for y in ([] if REUSE else range(2021, 2027)):
    tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
    for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG)
        m.fit(tr[FE], tr[tgt]); te[col] = m.predict_proba(te[FE])[:, 1]
    P.append(te[KEY + ['馬番', '年', 'n', '着', '勝', '3着内', '人気', '単勝オッズ', '新馬', '走数', 'p1', 'p3']])
    print('純粋な評価', y, round(time.time() - t0), '秒', flush=True)
if REUSE:
    D = pd.read_pickle(sys.argv[3]); D = D.loc[:, ~D.columns.duplicated()]
else:
    D = pd.concat(P, ignore_index=True); D.to_pickle(sys.argv[3])
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        if isinstance(d.get('馬連'), list) and len(d['馬連']) == 1: pays[(a, b, int(c))] = d['馬連'][0] / 100


def prep(D):
    D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
    D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
    D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
    D = D.sort_values(KEY + ['単勝オッズ', '馬番']); D['人気順'] = D.groupby(KEY).cumcount() + 1
    D['評価順'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first')
    D['r'] = D['p1'] / D['q']
    # その馬と1番人気の馬連（その馬が1番人気なら無し）
    fav = D[D['人気順'] == 1][KEY + ['馬番']].rename(columns={'馬番': '本命'})
    D = D.merge(fav, on=KEY, how='left')
    top2 = D[D['着'] <= 2].groupby(KEY)['馬番'].apply(lambda s: tuple(sorted(s.astype(int)))).rename('上2')
    D = D.merge(top2.reset_index(), on=KEY, how='left')
    pk = [(a, b, int(c)) for a, b, c in zip(D['年月日'], D['場'], D['R'])]
    D['馬連払'] = [pays.get(k, np.nan) for k in pk]
    D['本命と馬連'] = np.where(D['人気順'] == 1, np.nan,
                         [float(p) if isinstance(t, tuple) and t == tuple(sorted((int(a), int(b)))) else 0.0 for t, a, b, p in zip(D['上2'], D['馬番'], D['本命'], D['馬連払'].fillna(0))])
    D.loc[D['馬連払'].isna() & (D['人気順'] != 1), '本命と馬連'] = np.nan
    D['単払'] = np.where(D['勝'] == 1, D['単勝オッズ'], 0.0)
    return D


def boot(v, day, B=2000):
    x = pd.DataFrame({'d': day, 's': v}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


def loss(X):
    w = X[X['勝'] == 1]; return float(-np.log(w['p1'].clip(1e-6)).mean())


D = prep(D)
if len(sys.argv) > 4:
    B0 = pd.read_pickle(sys.argv[4]); B0 = B0['今の材料'] if isinstance(B0, dict) else B0
    B0 = B0[(B0['n'] >= 5) & B0.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    B0['p1'] = B0['p1'] / B0.groupby(KEY)['p1'].transform('sum')
    for per, lo_, hi_ in (('2021〜2023', 2021, 2023), ('2024〜2026', 2024, 2026)):
        print(f"K3 {per}：1着の当て分け 市場の材料あり {loss(B0[B0['年'].between(lo_, hi_)]):.4f} → 純粋な評価 {loss(D[D['年'].between(lo_, hi_)]):.4f}")
pop = pd.cut(D['人気順'], [0, 1, 3, 6, 9, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7〜9番人気', '10番人気以下'])
D['帯'] = pop
D['帯の中のr順'] = D.groupby(['年', '帯'], observed=True)['r'].rank(pct=True)
rows = []
for per, pm in (('2021〜2023', D['年'] <= 2023), ('2024〜2026', D['年'] >= 2024)):
    sets = {'(a) 評価の上位3頭なのに6番人気以下': (D['評価順'] <= 3) & (D['人気順'] >= 6)}
    for b in pop.cat.categories: sets[f'(b) {b}で評価÷市場の上位2割'] = (D['帯'] == b) & (D['帯の中のr順'] > 0.8)
    for name, mm in sets.items():
        X = D[pm & mm]
        if len(X) < 50: continue
        lo, hi = boot(X['単払'].values, X['年月日'].values)
        Y = X[X['本命と馬連'].notna()]
        rows.append({'期間': per, '形': name, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '実際÷市場': round(X['勝'].sum() / X['q'].sum(), 3),
                     '実際÷評価': round(X['勝'].sum() / X['p1'].sum(), 3), '単勝の回収': f"{X['単払'].mean()*100:.1f}%（{lo:.0f}〜{hi:.0f}）",
                     '本命との馬連の回収': f"{Y['本命と馬連'].mean()*100:.1f}%" if len(Y) else ''})
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 40)
print(pd.DataFrame(rows).to_string(index=False))
print(round(time.time() - t0), '秒')
