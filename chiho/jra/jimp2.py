"""中央競馬：評価のかたよりを直す（検証計画の同じ名前の節）。F2：前のレースの市場の評価（PASTM）を足すか、F1：中央で初めて走る馬（新馬以外）の直し。
各年はその前の年まで（2017年から）。2021〜2023年で選び、2024〜2026年で確かめる。
使い方：python jimp2.py 材料.pkl 出力.pkl"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, PASTM

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
out = {}
for lab, FE in (('今の材料', FEATS + EXTRA + PACE), ('PASTMを足す', FEATS + EXTRA + PACE + PASTM)):
    FE = [c for c in FE if c in H and H[c].notna().any()]; cat = [FE.index(c) for c in CATF if c in FE]
    P = []
    for y in range(2021, 2027):
        tr = H[(H['年'] >= 2017) & (H['年'] < y)]; te = H[H['年'] == y].copy()
        for tgt, col in (('3着内', 'p3'), ('勝', 'p1')):
            m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG)
            m.fit(tr[FE], tr[tgt]); te[col] = m.predict_proba(te[FE])[:, 1]
        P.append(te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', '単勝オッズ', '新馬', '走数', 'p1', 'p3']])
        print(lab, y, round(time.time() - t0), '秒', flush=True)
    out[lab] = pd.concat(P, ignore_index=True)
pd.to_pickle(out, sys.argv[2])


def prep(D):
    D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
    D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
    D['r3'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first')
    return D


def loss(X):
    w = X[X['勝'] == 1]; return float(-np.log(w['p1'].clip(1e-6)).mean())


rows = []
for lab, D in out.items():
    D = prep(D)
    for per, pm in (('2021〜2023', D['年'] <= 2023), ('2024〜2026', D['年'] >= 2024)):
        X = D[pm]; N = X[X['新馬'] == 1]
        pop = pd.cut(X['人気'], [0, 1, 3, 6, 9, 99], labels=['1', '2〜3', '4〜6', '7〜9', '10〜'])
        ratio = X.groupby(pop, observed=True).apply(lambda z: z['勝'].sum() / z['p1'].sum(), include_groups=False)
        rows.append({'材料': lab, '期間': per, '1着の当て分け': round(loss(X), 4), '上位3頭に1着': f"{X[X['r3'] <= 3].groupby(KEY)['勝'].max().mean()*100:.1f}%",
                     '新馬の上位3頭に1着': f"{N[N['r3'] <= 3].groupby(KEY)['勝'].max().mean()*100:.1f}%",
                     '人気ごとの実際÷見込み（1・2〜3・4〜6・7〜9・10〜）': '・'.join(f'{v:.2f}' for v in ratio.values)})
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(pd.DataFrame(rows).to_string(index=False))

# F1：中央で初めて走る馬（新馬以外）の直し（今の材料の見込みで）
D = prep(out['今の材料'])
f = (D['走数'] == 0) & (D['新馬'] == 0)
A = D[f & (D['年'] <= 2023)]
k1 = A['勝'].sum() / A['p1'].sum(); k3 = A['3着内'].sum() / A['p3'].sum()
print(f'\n■ F1 中央で初めて走る馬（新馬以外）：2021〜2023年で決めた掛ける値 1着 {k1:.3f}、3着内 {k3:.3f}（{len(A)}頭）')
E = D.copy(); E.loc[f, 'p1'] *= k1; E.loc[f, 'p3'] *= k3
E['p1'] = E['p1'] / E.groupby(KEY)['p1'].transform('sum')
E['p3'] = (E['p3'] * np.minimum(3, E['n']) / E.groupby(KEY)['p3'].transform('sum'))
for per, pm in (('2024〜2026', E['年'] >= 2024),):
    B = E[f & pm]; B0 = D[f & pm]
    print(f"  {per}：実際÷見込み 1着 {B0['勝'].sum()/B0['p1'].sum():.3f}→{B['勝'].sum()/B['p1'].sum():.3f}、3着内 {B0['3着内'].sum()/B0['p3'].sum():.3f}→{B['3着内'].sum()/B['p3'].sum():.3f}（{len(B)}頭）"
          f"／1着の当て分け（全部） {loss(D[pm]):.4f}→{loss(E[pm]):.4f}")
print(round(time.time() - t0), '秒')
