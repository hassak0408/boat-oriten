"""候補の回収を、同じ年・同じ人気（1〜7、8以上）の全部の馬の回収とくらべる（人気の混ざり方の違いを除く）"""
import numpy as np, pandas as pd
H = pd.read_pickle('/tmp/chiho_H.pkl')
H['人気帯'] = H['人気'].clip(upper=8)
rows = []
for c in ['C1', 'C2', 'C3', 'C4', 'C5']:
    for bet, col in (('単勝', '単払'), ('複勝', '複払')):
        D = H[(H['年'] >= '2016') & (H['年'] <= '2025') & H[col].notna() & H['人気帯'].notna()].copy()
        D['基準'] = D.groupby(['年', '人気帯'])[col].transform('mean')
        S = D[D[c]]
        by = S.groupby('年').apply(lambda d: pd.Series({'実': d[col].mean(), '基': d['基準'].mean()}))
        d = (S[col] - S['基準'])
        # 日を単位に引き直した95%幅
        dd = S.assign(diff=d).groupby('競走年月日')['diff'].agg(['sum', 'size'])
        rng = np.random.default_rng(0); idx = np.arange(len(dd)); bs = []
        for _ in range(2000):
            k = rng.choice(idx, len(idx)); bs.append(dd['sum'].values[k].sum() / dd['size'].values[k].sum())
        lo, hi = np.percentile(bs, [2.5, 97.5])
        D26 = H[(H['年'] == '2026') & H[col].notna() & H['人気帯'].notna()].copy(); D26['基準'] = D26.groupby('人気帯')[col].transform('mean'); S26 = D26[D26[c]]
        rows.append(dict(候補=c, 券=bet, 頭=len(S), 実際=round(S[col].mean(), 1), 同じ人気の全部=round(S['基準'].mean(), 1),
                         差=round(d.mean(), 1), 幅=f'{lo:+.1f}〜{hi:+.1f}', 上回った年=f"{(by['実'] > by['基']).sum()}/{len(by)}",
                         年ごとの差='・'.join(f"{v:+.0f}" for v in by['実'] - by['基']),
                         差2026=round((S26[col] - S26['基準']).mean(), 1)))
pd.set_option('display.width', 250)
print(pd.DataFrame(rows).to_string(index=False))
print(); print('人気の平均：全部', round(H['人気'].mean(), 2), {c: round(H.loc[H[c], '人気'].mean(), 2) for c in ['C1','C2','C3','C4','C5']})
