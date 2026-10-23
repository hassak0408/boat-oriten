"""B：各レースで複勝の見込みの上位2頭が、どちらも線以上なら、その2頭のワイド（と馬複）を1点ずつ。"""
import sys, numpy as np, pandas as pd
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']
P = pd.read_pickle(sys.argv[1] if len(sys.argv) > 1 else '/tmp/chiho_pred.pkl')
P = P[P['券'] == '複'].copy()
PB = _read('race', 'payback')
def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan
parts = []
for i in (1, 2, 3):
    x = PB[KEY + [f'ワイド組番{i}馬番1', f'ワイド組番{i}馬番2', f'ワイド払戻金{i}（円）']].copy(); x.columns = KEY + ['a', 'b', '払']; x['券'] = 'ワ'; parts.append(x)
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy(); x.columns = KEY + ['a', 'b', '払']; x['券'] = '馬複'; parts.append(x)
W = pd.concat(parts)
W['a'] = pd.to_numeric(W['a'], errors='coerce'); W['b'] = pd.to_numeric(W['b'], errors='coerce'); W['払'] = W['払'].map(num)
W = W.dropna(subset=['a', 'b', '払'])
W['lo'] = W[['a', 'b']].min(axis=1); W['hi'] = W[['a', 'b']].max(axis=1)
W = W.drop_duplicates(KEY + ['券', 'lo', 'hi'])
pay = {(t, k): v for t, g in W.groupby('券') for k, v in zip(map(tuple, g[KEY + ['lo', 'hi']].values), g['払'] / 100)}
sold = {t: set(map(tuple, g[KEY].drop_duplicates().values)) for t, g in W.groupby('券')}
P['順'] = P.groupby(KEY)['見込み'].rank(ascending=False, method='first')
top = P[P['順'] <= 2].sort_values(KEY + ['順'])
rows = []
for k, g in top.groupby(KEY):
    if len(g) < 2: continue
    a, b = g.iloc[0], g.iloc[1]
    lo, hi = sorted([int(a['馬番']), int(b['馬番'])])
    rec = dict(zip(KEY, k)); rec.update(Y=a['Y'], 日=a['日'], 比5=min(a['比5'], b['比5']), 比2=min(a['比2'], b['比2']), 比1=min(a['比1'], b['比1']),
                                     人気a=a['人気'], 人気b=b['人気'])
    for t in ('ワ', '馬複'):
        rec[t] = pay.get((t, tuple(k) + (float(lo), float(hi))), 0.0) if tuple(k) in sold[t] else np.nan
    rows.append(rec)
R = pd.DataFrame(rows)
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
days = P.groupby('Y')['日'].nunique()
out = []
for line in ('比5', '比2', '比1'):
    for t in ('ワ', '馬複'):
        S = R[(R[line] >= 1) & R[t].notna()]
        T5 = S[(S['Y'] >= 2021) & (S['Y'] <= 2025)]
        by = S.groupby('Y')[t].mean() * 100
        lo, hi = boot(T5[t].values, T5['日'].values)
        S26 = S[S['Y'] == 2026]
        out.append(dict(券='ワイド' if t == 'ワ' else '馬複', 線={'比5': '2頭とも上位5%', '比2': '2頭とも上位2%', '比1': '2頭とも上位1%'}[line],
                        点_年=int(T5.groupby('Y').size().mean()), 一日=round(len(T5) / days.loc[2021:2025].sum(), 2),
                        的中=round((T5[t] > 0).mean() * 100, 1), 当たり平均=round(T5.loc[T5[t] > 0, t].mean() * 100),
                        回収5年=round(T5[t].mean() * 100, 1), 幅=f'{lo:.1f}〜{hi:.1f}',
                        年ごと='・'.join(f'{by.get(y, np.nan):.1f}' for y in range(2021, 2026)),
                        y2026=f"{S26[t].mean() * 100:.1f}（{len(S26)}点）"))
pd.set_option('display.width', 250)
print(pd.DataFrame(out).to_string(index=False))
R.to_pickle('/tmp/chiho_wide_rows.pkl')
