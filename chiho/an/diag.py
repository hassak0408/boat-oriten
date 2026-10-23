"""市場より劣っている所の洗い出し：馬の種類ごとに、材料だけの1着の見込み（model_win.py）と市場（確定の人気）の当て方をくらべる。
- 当て方：その種類の馬の中での1着の当て分け（AUC）。市場は人気の順、モデルは見込みの順。
- 見込みのずれ：実際の1着の数 ÷ モデルの見込みの合計（1より大きい＝その種類を低く見すぎ）。
- 市場の見込み：人気の順と頭数ごとの1着率（2016〜2020年）を当てはめたもの。"""
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl')
W = pd.read_pickle('/tmp/chiho_win.pkl')
# 前のレース（このデータの中）とのあいだに、ほかで走ったか（全成績の走数の増え方）
H = H.sort_values(['馬', '日', 'レース番号'])
H['前の全走'] = H.groupby('馬')['全走'].shift(1)
H['外を挟む'] = np.where(H['前の全走'].isna(), np.nan, (H['全走'] - H['前の全走'] - 1 > 0).astype(float))
base = H[(H['年'] <= 2020) & H['人気'].notna()]
qtab = base.groupby(['n', '人気'])['勝'].mean()
D = H[(H['年'] >= 2021) & H['人気'].notna()].merge(W, on=KEY + ['馬番'], how='inner')
D['p'] = D['p勝'] / D.groupby(KEY)['p勝'].transform('sum')
D['q'] = [qtab.get((n, r), np.nan) for n, r in zip(D['n'], D['人気'])]
D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
D['外の走数'] = D['全走'] - D['走数']


A = D[D['年'] <= 2025]
segs = {
    'このデータでの過去の走数': pd.cut(D['走数'], [-1, 0, 1, 4, 9, 999], labels=['0（初めて）', '1', '2〜4', '5〜9', '10以上']),
    '5場の外での走数（全成績−このデータ）': pd.cut(D['外の走数'], [-1, 0, 5, 20, 999], labels=['0', '1〜5', '6〜20', '21以上']),
    '前走（このデータ）とのあいだに外で走った': D['外を挟む'].map({0.0: 'いいえ', 1.0: 'はい'}).fillna('（このデータで初めて）'),
    '間隔（日）': pd.cut(D['間隔'], [0, 10, 20, 35, 60, 120, 9999], labels=['〜10', '11〜20', '21〜35', '36〜60', '61〜120', '121〜']).cat.add_categories('（初めて）').fillna('（初めて）'),
    '距離の変化': pd.cut(D['距離差'], [-9999, -200, -1, 0, 199, 9999], labels=['200m以上短縮', '短縮', '同じ', '延長', '200m以上延長']),
    'クラスの変化（1着賞金の比）': pd.cut(D['賞金比'], [0, 0.8, 1.25, 999], labels=['下がる', '同じくらい', '上がる']),
    '乗り替わり': D['乗替'].map({0: 'なし', 1: 'あり'}),
    '齢': pd.cut(D['齢'], [0, 2, 3, 5, 7, 99], labels=['2歳', '3歳', '4〜5歳', '6〜7歳', '8歳以上']),
    '馬体重の増減': pd.cut(D['馬体重増減'], [-99, -10, -4, 3, 9, 99], labels=['−10以下', '−9〜−4', '−3〜+3', '+4〜+9', '+10以上']),
    '減量騎手': D['減量'].map({0: 'いいえ', 1: 'はい'}),
    '場': D['競馬場'],
    '頭数': pd.cut(D['n'], [0, 8, 10, 99], labels=['8頭以下', '9〜10頭', '11頭以上']),
    '馬場': D['馬場'],
    '人気': pd.cut(D['人気'], [0, 1, 3, 6, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下']),
}
rows = []
for name, s in segs.items():
    X = D[D['年'] <= 2025].copy(); X['_s'] = s[X.index]
    tmp = []
    for k, Y in X.groupby('_s', observed=True):
        if len(Y) < 300 or Y['勝'].nunique() < 2: continue
        am = roc_auc_score(Y['勝'], Y['p']); aq = roc_auc_score(Y['勝'], -Y['人気'])
        tmp.append(dict(種類=name, 値=str(k), 頭=len(Y), 一着率=round(Y['勝'].mean() * 100, 1),
                        モデル見込み=round(Y['p'].mean() * 100, 1), 市場見込み=round(Y['q'].mean() * 100, 1),
                        実際_モデル=round(Y['勝'].sum() / Y['p'].sum(), 2), 実際_市場=round(Y['勝'].sum() / Y['q'].sum(), 2),
                        当て分けモデル=round(am, 3), 当て分け市場=round(aq, 3), 差=round(aq - am, 3)))
    rows += tmp
R = pd.DataFrame(rows)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
print('全体（2021〜2025年）：当て分け モデル', round(roc_auc_score(A['勝'], A['p']), 3), '市場', round(roc_auc_score(A['勝'], -A['人気']), 3))
print(R.to_string(index=False))
R.to_csv('/tmp/chiho_diag.csv', index=False)

# レースの本命どうし：モデルの本命と1番人気が違うレースで、どちらが勝ったか（1番人気の種類ごと）
A = A.copy(); A['モ順'] = A.groupby(KEY)['p'].rank(ascending=False, method='first')
fav = A[A['人気'] == 1].set_index(KEY); mtop = A[A['モ順'] == 1].set_index(KEY)
J = fav[['馬番', '勝', '走数', '外の走数', '外を挟む', '間隔']].join(mtop[['馬番', '勝']], rsuffix='_モ', how='inner')
J = J[J['馬番'] != J['馬番_モ']]
print('\n■ モデルの本命と1番人気が違うレース', len(J), '：1番人気の勝ち', f"{J['勝'].mean()*100:.1f}%", '／モデルの本命の勝ち', f"{J['勝_モ'].mean()*100:.1f}%")
J['1番人気の種類'] = np.select([J['走数'] == 0, J['外を挟む'] == 1, J['間隔'] > 60], ['このデータで初めて', '前走とのあいだに外で走った', '61日以上の休み明け'], 'そのほか')
print(J.groupby('1番人気の種類').agg(レース=('勝', 'size'), 一番人気の勝ち=('勝', lambda s: round(s.mean() * 100, 1)), モデル本命の勝ち=('勝_モ', lambda s: round(s.mean() * 100, 1))).to_string())
