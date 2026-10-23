"""X：券の間の値段のずれ（単勝と馬連）。確定オッズ（2026年3〜9月）での仮説づくり（検証計画「X」）。
r＝ハービル式の確率（単勝のオッズから）×馬連のオッズ。rの帯ごとに実際の回収（確定の払戻）を見る。ハービル式の確率が2%以上の組だけ。"""
import numpy as np, pandas as pd
from load import _read, odds as load_odds
KEY = ['競馬場', '競走年月日', 'レース番号']


def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan


O = load_odds()
for c in ('番号1', '番号2'): O[c] = pd.to_numeric(O[c], errors='coerce')
W = O[(O['賭式'] == '単勝') & (O['オッズ'] > 0)].dropna(subset=['番号1'])
U = O[(O['賭式'] == '馬複') & (O['オッズ'] > 0)].dropna(subset=['番号1', '番号2']).copy()
U['lo'] = U[['番号1', '番号2']].min(axis=1).astype(int); U['hi'] = U[['番号1', '番号2']].max(axis=1).astype(int)

PB = _read('race', 'payback')
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy()
x['a'] = pd.to_numeric(x['馬複組番1'], errors='coerce'); x['b'] = pd.to_numeric(x['馬複組番2'], errors='coerce'); x['払'] = x['馬複払戻金（円）'].map(num)
x = x.dropna(subset=['a', 'b', '払'])
PAY = {}
for r in x.itertuples(index=False):
    PAY.setdefault((r[0], r[1], r[2]), {})[tuple(sorted((int(r.a), int(r.b))))] = r.払 / 100

rows = []
for k, g in W.groupby(KEY):
    if k not in PAY: continue
    inv = 1 / g['オッズ'].values; q = dict(zip(g['番号1'].astype(int), inv / inv.sum()))
    rows.append((k, q))
Ug = {k: g for k, g in U.groupby(KEY)}
out = []
for k, q in rows:
    if k not in Ug: continue
    g = Ug[k]; n = len(q)
    for lo, hi, od, pop in zip(g['lo'], g['hi'], g['オッズ'], g['人気']):
        qi, qj = q.get(lo, 0), q.get(hi, 0)
        if qi <= 0 or qj <= 0 or qi >= 1 or qj >= 1: continue
        h = qi * qj / (1 - qi) + qj * qi / (1 - qj)
        out.append((k[0], k[1], k[2], lo, hi, h, od, pop, n, PAY[k].get((lo, hi), 0.0)))
X = pd.DataFrame(out, columns=KEY + ['lo', 'hi', 'ハービル', '馬連オッズ', '馬連人気', '頭', '払'])
X['r'] = X['ハービル'] * X['馬連オッズ']
X['月'] = X['競走年月日'].str[4:6]
S = X[X['ハービル'] >= 0.02].copy()
S['帯'] = pd.cut(S['r'], [0, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.7, 99])


def boot(s, d, B=2000):
    x = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(x), len(x)); o.append(x['sum'].values[k].sum() / x['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])


pd.set_option('display.width', 250)
print('レース', X[KEY].drop_duplicates().shape[0], '組', len(X), '（ハービル2%以上', len(S), '）')
t = S.groupby('帯', observed=True).agg(組=('払', 'size'), ハービル=('ハービル', 'mean'), 実際の的中=('払', lambda s: (s > 0).mean()), オッズ平均=('馬連オッズ', 'mean'), 回収=('払', 'mean'))
t['幅'] = [('{:.0f}〜{:.0f}'.format(*boot(S.loc[S['帯'] == b, '払'].values, S.loc[S['帯'] == b, '競走年月日'].values)) if n >= 50 else '') for b, n in zip(t.index, t['組'])]
for c in ('ハービル', '実際の的中'): t[c] = (t[c] * 100).round(1)
t['回収'] = (t['回収'] * 100).round(1); t['オッズ平均'] = t['オッズ平均'].round(1)
print(t.to_string())
print('\n月ごと（r 1.2以上）'); print(S[S['r'] >= 1.2].groupby('月').agg(組=('払', 'size'), 回収=('払', lambda s: round(s.mean() * 100, 1))).to_string())
print('\n場ごと（r 1.2以上）'); print(S[S['r'] >= 1.2].groupby('競馬場').agg(組=('払', 'size'), 回収=('払', lambda s: round(s.mean() * 100, 1))).to_string())
X.to_pickle('/tmp/chiho_xpool.pkl')
