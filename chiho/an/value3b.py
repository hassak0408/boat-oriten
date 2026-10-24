"""前の所属（中央・ほかの地方）ごとの、市場の値付けとモデルの見込みの合い方（検証計画「オッズや過去の戦績に惑わされずに…」の書き足し）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '馬', '日', '勝', '3着内', '単払', '人気', 'n', '年', '芝走', '全走', '初データ', '走数']]
F2 = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '走数']].rename(columns={'走数': '五場走数'})
H['馬番'] = H['馬番'].astype(float); F2['馬番'] = F2['馬番'].astype(float)
H = H.merge(F2, on=KEY + ['馬番'], how='left')
W = pd.read_pickle('/tmp/chiho_win_B3.pkl'); W['馬番'] = W['馬番'].astype(float)
qtab = H[(H['年'] <= 2020) & H['人気'].notna()].groupby(['n', '人気'])['勝'].mean()
# 5場に来た初戦の種類を、その馬の5場での2戦目・3戦目にも付ける
H = H.sort_values(['馬', '日', 'レース番号'])
first = np.select([(H['五場走数'] == 0) & (H['全走'] == 0), (H['五場走数'] == 0) & (H['初データ'] == 1) & (H['芝走'] > 0),
                   (H['五場走数'] == 0) & (H['初データ'] == 1), (H['五場走数'] == 0) & (H['初データ'] == 0)],
                  ['デビュー', '中央から来た', '中央か地方の外から来た（芝なし）', 'ほかの地方の場から来た'], '')
H['来かた'] = pd.Series(first, index=H.index).replace('', np.nan)
H['来かた'] = H.groupby('馬')['来かた'].transform(lambda s: s.ffill())
H['5場で何戦目'] = H['五場走数'] + 1
D = H[(H['年'] >= 2021) & (H['年'] <= 2025) & H['人気'].notna()].merge(W, on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D['p'] = D['p'] / D.groupby(KEY)['p'].transform('sum')
D['q'] = [qtab.get((n, r), np.nan) for n, r in zip(D['n'], D['人気'])]; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
X = D[D['来かた'].notna() & (D['5場で何戦目'] <= 3)]
t = X.groupby(['来かた', '5場で何戦目']).agg(頭=('勝', 'size'), 人気の平均=('人気', 'mean'), 一着率=('勝', 'mean'), モデル見込み=('p', 'mean'), 人気の順の見込み=('q', 'mean'),
                                          単勝の回収=('単払', 'mean'), 三着内率=('3着内', 'mean'))
t['モデル_実際割る見込み'] = (t['一着率'] / t['モデル見込み']).round(2); t['人気の順_実際割る見込み'] = (t['一着率'] / t['人気の順の見込み']).round(2)
for c in ('一着率', 'モデル見込み', '人気の順の見込み', '単勝の回収', '三着内率'): t[c] = (t[c] * 100).round(1)
t['人気の平均'] = t['人気の平均'].round(1)
pd.set_option('display.width', 250); print('■ 5場に来た初戦の種類と、5場での1〜3戦目（2021〜2025年）'); print(t.to_string())
print('全部の馬：単勝の回収', round(D['単払'].mean() * 100, 1))
