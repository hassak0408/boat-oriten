"""前に行くきっかけがあるのに、過去の位置だけでは前に行かなそうに見える馬（H1・H2）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
T = pd.read_pickle('/tmp/chiho_style.pkl')
T['順頭'] = T.groupby(KEY)['p先頭'].rank(ascending=False, method='first')
T['順行'] = T.groupby(KEY)['p先行'].rank(ascending=False, method='first')
T['H1'] = (T['順頭'] == 1) & (T['過去3角順'] >= 3)
T['H2'] = (T['順行'] <= 2) & (T['過去3角順'] >= 4)
base = T[T['人気'].notna()].groupby(['年', '人気'])[['単払', '複払']].mean()
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
rows = []
for h in ('H1', 'H2'):
    for bet, col in (('単勝', '単払'), ('複勝', '複払')):
        S = T[T[h] & T[col].notna() & T['人気'].notna()]; T5 = S[(S['年'] >= 2021) & (S['年'] <= 2025)]; S26 = S[S['年'] == 2026]
        b = base.reindex(list(zip(T5['年'], T5['人気'])))[col]
        by = T5.groupby('年')[col].mean() * 100; lo, hi = boot(T5[col].values, T5['日'].values)
        rows.append(dict(形=h, 券=bet, 点_年=round(len(T5) / 5), 人気平均=round(T5['人気'].mean(), 1), 実際に先頭=round(T5['先頭'].mean() * 100, 1),
                         実際に3番手以内=round(T5['先行'].mean() * 100, 1), 回収5年=round(T5[col].mean() * 100, 1), 同じ人気=round(b.mean() * 100, 1),
                         幅=f'{lo:.0f}〜{hi:.0f}', 年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)),
                         y2026=f"{S26[col].mean()*100:.1f}（{len(S26)}点）"))
pd.set_option('display.width', 250); print(pd.DataFrame(rows).to_string(index=False))
