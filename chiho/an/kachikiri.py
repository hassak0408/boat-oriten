"""割安かどうかと、勝ちきるかどうかは別（検証計画の同じ名前の節）。見方だけ。"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '着', '勝', '3着内', '単払', '人気', 'n', '年', '初角']]
H['馬番'] = H['馬番'].astype(float)
C = pd.read_pickle('/tmp/chiho_cand3_朝3.pkl'); C['馬番'] = C['馬番'].astype(float)
S = pd.read_pickle('/tmp/chiho_style.pkl')[KEY + ['馬番', 'p先頭', 'p先行']]; S['馬番'] = S['馬番'].astype(float)
D = H[(H['年'] >= 2021) & (H['年'] <= 2025)].merge(C, on=KEY + ['馬番']).merge(S, on=KEY + ['馬番'], how='left')
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D = D[(D.groupby(KEY)['3着内'].transform('sum') >= 3) & (D['n'] >= 5)].copy()
D['p1n'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3n'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
pd.set_option('display.width', 250)
# ① 勝ち馬の人気
w = D[D['勝'] == 1]
band = pd.cut(w['人気'], [0, 1, 3, 6, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下'])
print('■ 勝ち馬の人気（2021〜2025年、', w[KEY].drop_duplicates().shape[0], 'レース）'); print((band.value_counts(normalize=True).sort_index() * 100).round(1).to_string())
# ② 人気薄の中で、モデルが上に置いた馬ほど勝ちきるか
for lab, m in (('4〜6番人気', D['人気'].between(4, 6)), ('7番人気以下', D['人気'] >= 7)):
    X = D[m].copy(); X['帯'] = pd.qcut(X['p1n'].rank(method='first'), 5, labels=['モデルの見込み 下位2割', '2', '3', '4', '上位2割'])
    t = X.groupby('帯', observed=True).agg(頭=('勝', 'size'), モデルの1着の見込み=('p1n', 'mean'), 一着率=('勝', 'mean'), 三着内率=('3着内', 'mean'), 単勝の回収=('単払', 'mean'))
    for c in ('モデルの1着の見込み', '一着率', '三着内率', '単勝の回収'): t[c] = (t[c] * 100).round(1)
    print(f'\n■ {lab}の馬を、モデルの1着の見込みで5つに分けて'); print(t.to_string())
# ③ 3着内に来た馬のうち1着の割合を、勝ちきり度（1着の見込み÷3着内の見込み）で
T3 = D[D['3着内'] == 1].copy(); T3['勝ちきり度'] = T3['p1n'] / T3['p3n']
T3['帯'] = pd.qcut(T3['勝ちきり度'], 5, labels=['ヒモ寄り（下位2割）', '2', '3', '4', '頭寄り（上位2割）'])
t = T3.groupby('帯', observed=True).agg(頭=('勝', 'size'), 勝ちきり度=('勝ちきり度', 'mean'), 三着内のうち1着=('勝', 'mean'), 人気の平均=('人気', 'mean'))
t['勝ちきり度'] = (t['勝ちきり度'] * 100).round(1); t['三着内のうち1着'] = (t['三着内のうち1着'] * 100).round(1); t['人気の平均'] = t['人気の平均'].round(1)
print('\n■ 3着内に来た馬のうち1着だった割合（勝ちきり度＝1着の見込み÷3着内の見込みで5つに）'); print(t.to_string())
# 同じ人気どうしでも見分けられるか（人気でそろえる）
T3['人気帯'] = pd.cut(T3['人気'], [0, 1, 3, 6, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下'])
T3['頭寄り'] = T3.groupby('人気帯', observed=True)['勝ちきり度'].transform(lambda s: s >= s.median())
t = T3.groupby(['人気帯', '頭寄り'], observed=True)['勝'].agg(['size', 'mean']).unstack()
print('\n■ 同じ人気どうしで、勝ちきり度が真ん中より上・下（3着内に来た馬のうち1着の割合）')
print(pd.DataFrame({'下（ヒモ寄り）': (t['mean'][False] * 100).round(1), '上（頭寄り）': (t['mean'][True] * 100).round(1), '頭': t['size'].sum(axis=1)}).to_string())
# 脚質の予想で
T3['脚質'] = np.where(T3.groupby(KEY)['p先頭'].rank(ascending=False, method='first').eq(1) & (T3['p先頭'] >= 0.3), '逃げ予想', np.where(T3['p先行'] >= 0.5, '先行予想', 'それ以外'))
print('\n■ 3着内に来た馬のうち1着の割合（脚質の予想ごと、人気でそろえず）'); print(T3.groupby('脚質')['勝'].agg(['size', 'mean']).assign(mean=lambda d: (d['mean'] * 100).round(1)).to_string())
