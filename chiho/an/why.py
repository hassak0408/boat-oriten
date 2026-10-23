"""選んだ馬の複勝の払戻は、1番人気が3着内に来たときと来なかったときでどれだけ違うか（人気馬と組むと下がる理由）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl'); P = pd.read_pickle('/tmp/chiho_pred.pkl'); P = P[P['券'] == '複']
fav = H[H['人気'] == 1][KEY + ['3着内']].rename(columns={'3着内': '人1_3着内'})
A = H[H['複払'].notna() & H['人気'].notna() & (H['人気'] >= 2) & (H['年'] >= 2021) & (H['年'] <= 2025)].merge(fav, on=KEY, how='left')
for q in (1, 5):
    S = P[(P[f'比{q}'] >= 1) & (P['Y'] <= 2025) & (P['人気'] >= 2)].merge(fav, on=KEY, how='left')
    print(f'■ 上位{q}%（1番人気の馬は除く）', len(S), '頭')
    for lab, D in (('選んだ馬', S), ('同じ人気の全部', A[A['人気'].isin(S['人気'].unique())])):
        if lab == '同じ人気の全部':  # 人気の混ざり方をそろえる
            w = S['人気'].value_counts(normalize=True)
            g = D.groupby(['人気', '人1_3着内']).agg(n=('複払', 'size'), p3=('3着内', 'mean'), ret=('複払', 'mean'))
            tot = {}
            for f in (0, 1):
                share = sum(w.get(k, 0) * (D[(D['人気'] == k) & (D['人1_3着内'] == f)].shape[0] / max(1, D[D['人気'] == k].shape[0])) for k in w.index)
                p3 = sum(w.get(k, 0) * g.loc[(k, f), 'p3'] * (g.loc[(k, f), 'n'] / g.loc[k, 'n'].sum()) for k in w.index if (k, f) in g.index) / share
                ret = sum(w.get(k, 0) * g.loc[(k, f), 'ret'] * (g.loc[(k, f), 'n'] / g.loc[k, 'n'].sum()) for k in w.index if (k, f) in g.index) / share
                tot[f] = (share, p3, ret)
            for f, (sh, p3, ret) in tot.items():
                print(f'  {lab}：1番人気が3着内{"に来た" if f else "に来なかった"}  割合{sh*100:.0f}%  3着内{p3*100:.1f}%  複勝回収{ret*100:.1f}%')
        else:
            for f in (0, 1):
                d = D[D['人1_3着内'] == f]
                print(f'  {lab}：1番人気が3着内{"に来た" if f else "に来なかった"}  割合{len(d)/len(D)*100:.0f}%  3着内{d["3着内"].mean()*100:.1f}%  複勝回収{d["ret"].mean()*100:.1f}%  当たりの平均{d.loc[d["ret"]>0,"ret"].mean()*100:.0f}円')
