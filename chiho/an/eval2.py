"""1着の見込みのモデルと市場のくらべ（検証計画「市場より劣る所の洗い出しと改善」）
当て分け（AUC）・本命の1着率・対数損失（レースの中で足して1にした見込みでの、勝ち馬の見込みの −log の平均。小さいほど良い）。
市場：人気（AUC・本命）、人気の順と頭数ごとの1着率（2016〜2020年）を当てはめた見込み、2026年3〜9月は単勝のオッズからの見込み。"""
import sys, numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from load import odds as load_odds
KEY = ['競馬場', '競走年月日', 'レース番号']
names = sys.argv[1:] or ['B0', 'B1', 'B2']
H = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '勝', '人気', 'n', '年', '走数', '外を挟む', '間隔', '齢', 'クラス差', '馬体重増減']]
try:
    H3 = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '初データ', '前走外']].rename(columns={'初データ': '全部で初めて'})
    H = H.merge(H3, on=KEY + ['馬番'], how='left')
except FileNotFoundError:
    H['全部で初めて'] = np.nan; H['前走外'] = np.nan
qtab = H[(H['年'] <= 2020) & H['人気'].notna()].groupby(['n', '人気'])['勝'].mean()
D = H[(H['年'] >= 2021) & H['人気'].notna()].copy()
D['市場'] = [qtab.get((n, r), np.nan) for n, r in zip(D['n'], D['人気'])]
old = pd.read_pickle('/tmp/chiho_win.pkl').rename(columns={'p勝': '前のモデル'})
D = D.merge(old, on=KEY + ['馬番'], how='left')
for nm in names:
    D = D.merge(pd.read_pickle(f'/tmp/chiho_win_{nm}.pkl').rename(columns={'p': nm}), on=KEY + ['馬番'], how='left')
O = load_odds(); W = O[(O['賭式'] == '単勝') & (O['オッズ'] > 0)].copy()
W['馬番'] = pd.to_numeric(W['番号1'], errors='coerce'); W['オッズ市場'] = 1 / W['オッズ']
D = D.merge(W[KEY + ['馬番', 'オッズ市場']], on=KEY + ['馬番'], how='left')
cols = ['市場', '前のモデル'] + names
for c in cols + ['オッズ市場']:
    D[c] = D[c] / D.groupby(KEY)[c].transform('sum')
one = D.groupby(KEY)['勝'].transform('sum') == 1
D = D[one & D[cols].notna().all(axis=1)]


def metrics(X, c, auc_col=None):
    a = roc_auc_score(X['勝'], X[auc_col] if auc_col is not None else X[c])
    top = X.loc[X.groupby(KEY)[c].idxmax()]['勝'].mean() if auc_col is None else X[X['人気'] == 1]['勝'].mean()
    ll = -np.log(X.loc[X['勝'] == 1, c].clip(1e-6)).mean()
    return a, top, ll


rows = []
for lab, X in (('2021〜2025年', D[D['年'] <= 2025]), ('2026年1〜9月', D[D['年'] == 2026])):
    X = X.assign(負人気=-X['人気'])
    a, t, l = metrics(X, '市場', auc_col='負人気'); rows.append(dict(期間=lab, 物=f'市場（人気）', 当て分け=a, 本命の1着率=t, 対数損失=l))
    for c in ['前のモデル'] + names:
        a, t, l = metrics(X, c); rows.append(dict(期間=lab, 物=c, 当て分け=a, 本命の1着率=t, 対数損失=l))
Z = D[(D['年'] == 2026) & D['オッズ市場'].notna()]
Z = Z[Z.groupby(KEY)['オッズ市場'].transform('size') == Z.groupby(KEY)['勝'].transform('size')]
for c in ['オッズ市場', '前のモデル'] + names:
    a, t, l = metrics(Z, c); rows.append(dict(期間='2026年3〜9月（オッズあり）', 物='市場（単勝のオッズ）' if c == 'オッズ市場' else c, 当て分け=a, 本命の1着率=t, 対数損失=l))
R = pd.DataFrame(rows)
R['当て分け'] = R['当て分け'].round(3); R['本命の1着率'] = (R['本命の1着率'] * 100).round(1); R['対数損失'] = R['対数損失'].round(3)
pd.set_option('display.width', 250)
print(R.to_string(index=False))

# 種類ごとの当て分け（2021〜2025年）
A = D[D['年'] <= 2025].copy()
segs = {'このデータで初めて': A['走数'] == 0, '　そのうち全部の場でも初めて': (A['走数'] == 0) & (A['全部で初めて'] == 1),
        '　そのうちほかの地方の場から来た': (A['走数'] == 0) & (A['全部で初めて'] == 0), '前走が5場の外': A['前走外'] == 1,
        '前走とのあいだに外で走った': A['外を挟む'] > 0, '61日以上の休み明け': A['間隔'] > 60,
        '2歳': A['齢'] == 2, '3歳': A['齢'] == 3, 'クラスが下がる': A['クラス差'] > 0.5, '馬体重±10以上': A['馬体重増減'].abs() >= 10, 'そのほか全部': None}
rows = []
for s, m in segs.items():
    X = A if m is None else A[m]
    r = dict(種類=s, 頭=len(X), 市場=round(roc_auc_score(X['勝'], -X['人気']), 3))
    for c in ['前のモデル'] + names: r[c] = round(roc_auc_score(X['勝'], X[c]), 3)
    rows.append(r)
print('\n■ 種類ごとの当て分け（2021〜2025年）'); print(pd.DataFrame(rows).to_string(index=False))
