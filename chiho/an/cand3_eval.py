"""来そうな馬の候補の当たり方（検証計画「来そうな馬の候補」）。モデルの見込みの順と、人気の順（確定）をくらべる。
- 上位K頭に1着がいる率、上位K頭に入った3着内の頭数の平均、上位3頭に1・2着がそろう率（馬連BOX3頭）、
  上位4頭・5頭に3着内の3頭がそろう率（3連複BOX）、見込みと実際の3着内率。"""
import sys, numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
kind = sys.argv[1] if len(sys.argv) > 1 else '朝'
H = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '着', '勝', '3着内', '人気', 'n', '年']]
D = H[H['年'] >= 2021].merge(pd.read_pickle(f'/tmp/chiho_cand3_{kind}.pkl'), on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]   # 人気がそろうレース
D = D[(D.groupby(KEY)['3着内'].transform('sum') >= 3) & (D['n'] >= 5)]
D['p3n'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
D['モ順'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first')
D['人順'] = D.groupby(KEY)['人気'].rank(method='first')


def stats(X, rk):
    g = X.groupby(KEY)
    r = {}
    for k in (2, 3, 4, 5):
        top = X[X[rk] <= k]; gt = top.groupby(KEY)
        r[f'上位{k}頭に1着'] = gt['勝'].max().mean()
        r[f'上位{k}頭の3着内の頭数'] = gt['3着内'].sum().mean()
    t3 = X[X[rk] <= 3].groupby(KEY)
    r['馬連BOX3頭（1・2着がそろう）'] = (X[(X[rk] <= 3) & (X['着'] <= 2)].groupby(KEY).size().reindex(g.size().index, fill_value=0) >= 2).mean()
    for k in (4, 5):
        r[f'3連複BOX{k}頭（3頭そろう）'] = (X[(X[rk] <= k) & (X['3着内'] == 1)].groupby(KEY).size().reindex(g.size().index, fill_value=0) >= 3).mean()
    return r


rows = []
for lab, X in (('2021〜2025年', D[D['年'] <= 2025]), ('2026年1〜9月', D[D['年'] == 2026])):
    a = stats(X, 'モ順'); b = stats(X, '人順')
    for k in a:
        rows.append(dict(期間=lab, 物差し=k, モデル=a[k], 人気=b[k]))
R = pd.DataFrame(rows)
fmt = lambda v, k: f'{v:.2f}頭' if '頭数' in k else f'{v*100:.1f}%'
R['モデル'] = [fmt(v, k) for v, k in zip(R['モデル'], R['物差し'])]; R['人気'] = [fmt(v, k) for v, k in zip(R['人気'], R['物差し'])]
pd.set_option('display.width', 250)
print(kind, 'レース数', D[KEY].drop_duplicates().shape[0])
print(R.to_string(index=False))
A = D[D['年'] <= 2025]
print('\n見込み（足して3にそろえた後）と実際の3着内率（2021〜2025年）')
print(A.groupby(pd.cut(A['p3n'], [0, .1, .2, .3, .4, .5, .6, .7, .8, 1]), observed=True).agg(
    頭=('3着内', 'size'), 見込み=('p3n', lambda s: round(s.mean() * 100, 1)), 実際=('3着内', lambda s: round(s.mean() * 100, 1))).to_string())
# モデルと人気が食い違う馬：モデルの上位3頭に入るのに人気が6番以下
X = A[(A['モ順'] <= 3) & (A['人気'] >= 6)]
print(f"\nモデルの上位3頭で6番人気以下の馬：{len(X)}頭（1レースあたり{len(X)/A[KEY].drop_duplicates().shape[0]:.2f}頭）、3着内 {X['3着内'].mean()*100:.1f}%"
      f"（同じ人気の全部の馬 {A[A['人気'].isin(X['人気'].unique())].groupby('人気')['3着内'].mean().reindex(X['人気']).mean()*100:.1f}%）")
