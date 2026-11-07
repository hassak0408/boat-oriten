"""中央競馬：K8 モデルを3つ作って平均する（検証計画 K8）。
random_state だけを変えた純粋な評価の見込み（jk.py TROUBLE=1 SEED=0・1・2 の出力）を平均し、1つのモデル（SEED=0）とくらべる。
使い方：python jk8.py 見込み0.pkl 見込み1.pkl 見込み2.pkl [平均の出力.pkl]"""
import sys, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']
COLS = ['馬番', '年', 'n', '着', '勝', '3着内', '人気', '単勝オッズ', '新馬', '走数']
Ps = [pd.read_pickle(f) for f in sys.argv[1:4]]
Ps = [P.loc[:, ~P.columns.duplicated()] for P in Ps]
D = Ps[0][KEY + COLS].copy()
for i, P in enumerate(Ps):
    D = D.merge(P[KEY + ['馬番', 'p1', 'p3']].rename(columns={'p1': f'p1_{i}', 'p3': f'p3_{i}'}), on=KEY + ['馬番'], how='inner')
print('行', len(D), '／モデルどうしの1着の見込みの相関', round(float(np.corrcoef(D['p1_0'], D['p1_1'])[0, 1]), 4), flush=True)
D['p1_a'] = D[['p1_0', 'p1_1', 'p1_2']].mean(axis=1); D['p3_a'] = D[['p3_0', 'p3_1', 'p3_2']].mean(axis=1)
if len(sys.argv) > 4:      # F1・馬連の見込みの直しを作り直すための、平均の見込み（jk.py の出力と同じ形）
    D[KEY + COLS].assign(p1=D['p1_a'], p3=D['p3_a']).to_pickle(sys.argv[4])
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
for s in ('0', '1', '2', 'a'):
    D[f'p1_{s}'] = D[f'p1_{s}'] / D.groupby(KEY)[f'p1_{s}'].transform('sum')
    D[f'p3_{s}'] = (D[f'p3_{s}'] * np.minimum(3, D['n']) / D.groupby(KEY)[f'p3_{s}'].transform('sum')).clip(1e-4, 0.97)


def ev(X, s):
    w = X[X['勝'] == 1]; l1 = float(-np.log(w[f'p1_{s}'].clip(1e-6)).mean())
    p = X[f'p3_{s}']; y = X['3着内']; l3 = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    rk = X.groupby(KEY)[f'p3_{s}'].rank(ascending=False, method='first')
    return l1, l3, X.loc[rk <= 3, '3着内'].mean() * 100, X.loc[rk == 1, '勝'].mean() * 100


rows = []
for per, a, b in (('2021〜2023', 2021, 2023), ('2024〜2026', 2024, 2026)):
    X = D[D['年'].between(a, b)]
    for s, nm in (('0', '1つ（乱数0、今の一覧）'), ('1', '1つ（乱数1）'), ('2', '1つ（乱数2）'), ('a', '3つの平均')):
        l1, l3, t3, t1 = ev(X, s)
        rows.append({'期間': per, 'モデル': nm, 'レース': X.groupby(KEY).ngroups, '1着の当て分け': f'{l1:.4f}', '3着内の当て分け': f'{l3:.4f}',
                     '上位3頭の3着内の率': f'{t3:.2f}%', '1番手の1着率': f'{t1:.2f}%'})
pd.set_option('display.width', 220)
print(pd.DataFrame(rows).to_string(index=False))
