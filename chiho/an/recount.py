"""手順1・2の数え直し（競走中止・失格を負けとして入れ、同着の払戻を全部見る）"""
import numpy as np, pandas as pd
H = pd.read_pickle('/tmp/chiho_feat.pkl')
KEY = ['競馬場', '競走年月日', 'レース番号']
H['年s'] = H['年'].astype(str)
print('頭数', len(H), 'レース', H[KEY].drop_duplicates().shape[0], '中止・失格', int(H['中止'].sum()))
F = H[H['複払'].notna()]
print('全部の馬：単勝 %.1f%%  複勝 %.1f%%' % (H['単払'].mean() * 100, F['複払'].mean() * 100))
H['人気帯'] = H['人気'].clip(upper=8)
t = H.groupby('人気帯').agg(頭=('単払', 'size'), 勝率=('勝', 'mean'), 単勝=('単払', 'mean'), 複勝=('複払', 'mean'))
t['勝率'] = (t['勝率'] * 100).round(1); t['単勝'] = (t['単勝'] * 100).round(1); t['複勝'] = (t['複勝'] * 100).round(1)
print(t.to_string())
# 候補
H['C1'] = (H['過去3差順率'] * H['n'] <= 2) & H['過去3差'].notna() & (H['人気'] >= 4)
H['C2'] = (H['着x1'] >= 6) & H['最良着2_5'].le(3)
ak = H.groupby(KEY)['過去3角'].rank(method='first')
H['C4'] = (ak == 1) & H['過去3角'].notna()
H['C5'] = (H['走数'] == 0) & (H['全走'] >= 3) & (H['齢'] >= 3) & (H['年'] >= 2017)
jy = H.groupby(['競馬場', '年', '騎']).agg(n=('勝', 'size'), w=('勝', 'sum')).reset_index()
jy = jy[jy['n'] >= 100]; jy['率'] = jy['w'] / jy['n']
jy['順'] = jy.groupby(['競馬場', '年'])['率'].rank(ascending=False, method='first')
top = jy[jy['順'] <= 3][['競馬場', '年', '騎']].copy(); top['年'] += 1; top['C3'] = True
H = H.merge(top, on=['競馬場', '年', '騎'], how='left'); H['C3'] = H['C3'].fillna(False).astype(bool)
rows = []
for c in ['C1', 'C2', 'C3', 'C4', 'C5']:
    for bet, col in (('単勝', '単払'), ('複勝', '複払')):
        D = H[(H['年'] >= 2016) & (H['年'] <= 2025) & H[col].notna() & H['人気帯'].notna()].copy()
        D['基準'] = D.groupby(['年', '人気帯'])[col].transform('mean')
        S = D[D[c]]; d = S[col] - S['基準']
        by = S.groupby('年').apply(lambda x: (x[col] - x['基準']).mean() * 100)
        dd = S.assign(diff=d).groupby('競走年月日')['diff'].agg(['sum', 'size'])
        rng = np.random.default_rng(0); bs = []
        for _ in range(2000):
            k = rng.integers(0, len(dd), len(dd)); bs.append(dd['sum'].values[k].sum() / dd['size'].values[k].sum() * 100)
        lo, hi = np.percentile(bs, [2.5, 97.5])
        allm = D[col].mean() * 100; cand = S[col].mean() * 100
        sa = S.groupby('年')[col].mean(); up_all = (sa > D.groupby('年')[col].mean().reindex(sa.index)).sum()
        rows.append(dict(候補=c, 券=bet, 頭=len(S), 回収=round(cand, 1), 全部=round(allm, 1), 全部より上の年=f'{up_all}/{S["年"].nunique()}',
                         同じ人気との差=round(d.mean() * 100, 1), 幅=f'{lo:+.1f}〜{hi:+.1f}', 差がプラスの年=f'{(by > 0).sum()}/{len(by)}'))
pd.set_option('display.width', 250)
print(pd.DataFrame(rows).to_string(index=False))
