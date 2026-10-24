"""来そうな馬の一覧と人気の重ね方（2021〜2025年）：モデルの上位3頭と人気の上位3頭が、どれだけ重なるかで分けた当たり方と、両方を合わせた馬の当たり方。"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '着', '勝', '3着内', '人気', 'n', '年']]
D = H[(H['年'] >= 2021) & (H['年'] <= 2025)].merge(pd.read_pickle('/tmp/chiho_cand3_朝.pkl'), on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D = D[(D.groupby(KEY)['3着内'].transform('sum') >= 3) & (D['n'] >= 5)]
D['モ順'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first'); D['人順'] = D.groupby(KEY)['人気'].rank(method='first')
rows = []
for k, g in D.groupby(KEY, sort=False):
    m = set(g.loc[g['モ順'] <= 3, '馬番']); p = set(g.loc[g['人順'] <= 3, '馬番']); u = m | p
    top3 = set(g.loc[g['3着内'] == 1, '馬番']); top2 = set(g.loc[g['着'] <= 2, '馬番']); win = set(g.loc[g['着'] == 1, '馬番'])
    rows.append(dict(重なり=len(m & p), 合わせた頭数=len(u), 合わせてに1着=bool(win & u), 合わせて3着内の頭数=len(top3 & u),
                     合わせて3頭そろう=top3 <= u, モデル上位3に1着=bool(win & m), 人気上位3に1着=bool(win & p),
                     モデルだけの馬が3着内=len(top3 & (m - p)), モデルだけの馬の数=len(m - p)))
R = pd.DataFrame(rows)
pd.set_option('display.width', 250)
print('レース', len(R))
t = R.groupby('重なり').agg(レース=('合わせた頭数', 'size'), 合わせた頭数=('合わせた頭数', 'mean'), 人気上位3に1着=('人気上位3に1着', 'mean'), モデル上位3に1着=('モデル上位3に1着', 'mean'),
                         合わせてに1着=('合わせてに1着', 'mean'), 合わせて3頭そろう=('合わせて3頭そろう', 'mean'))
t['割合'] = t['レース'] / t['レース'].sum()
print((t * [1, 1, 100, 100, 100, 100, 100]).round(1).to_string())
print('\n全部：合わせた頭数の平均', round(R['合わせた頭数'].mean(), 2), '／合わせてに1着', f"{R['合わせてに1着'].mean()*100:.1f}%", '／合わせて3着内の3頭がそろう', f"{R['合わせて3頭そろう'].mean()*100:.1f}%")
x = R[R['モデルだけの馬の数'] > 0]
print('モデルだけが上位3頭に入れた馬（人気は4番以下）：', int(x['モデルだけの馬の数'].sum()), '頭、3着内', f"{x['モデルだけの馬が3着内'].sum()/x['モデルだけの馬の数'].sum()*100:.1f}%")
