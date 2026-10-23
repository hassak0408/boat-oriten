"""手順4：前の2頭の馬複の戻りモデル（検証計画「手順4：前の2頭の馬複の戻りモデル」）
1レース1行。組は前の2頭（3番手以内の見込みの上位2頭）。答えはその馬複の100円あたりの払戻（外れは0）。
Y年のモデルは2018年〜Y−2年で作り、線はY−1年の見込みの上位10%・20%（主）・33%。オッズと今のレースの人気は使わない。"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']


def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan


T = pd.read_pickle('/tmp/chiho_style_all.pkl')
T['馬番'] = T['馬番'].astype(int)

# 馬複の払戻
PB = _read('race', 'payback')
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy()
x['a'] = pd.to_numeric(x['馬複組番1'], errors='coerce'); x['b'] = pd.to_numeric(x['馬複組番2'], errors='coerce'); x['払'] = x['馬複払戻金（円）'].map(num)
x = x.dropna(subset=['a', 'b', '払'])
UREN = {}
for r in x.itertuples(index=False):
    UREN.setdefault((r[0], r[1], r[2]), {})[tuple(sorted((int(r.a), int(r.b))))] = r.払 / 100

# 当日の前残り率（front_day.py と同じ）
H = pd.read_pickle('/tmp/chiho_feat.pkl')[KEY + ['着', '初角']].copy()
H['R'] = pd.to_numeric(H['レース番号'], errors='coerce')
t2 = H[H['着'].isin([1, 2]) & H['初角'].notna()].copy(); t2['前'] = (t2['初角'] <= 2).astype(int)
g = t2.groupby(KEY).agg(前=('前', 'sum'), 数=('前', 'size'), R=('R', 'first')).reset_index().sort_values(['競馬場', '競走年月日', 'R'])
d = g.groupby(['競馬場', '競走年月日'])
g['前の数'] = d['前'].transform(lambda s: s.shift(1).cumsum()); g['全の数'] = d['数'].transform(lambda s: s.shift(1).cumsum())
g['前のレース'] = d.cumcount()
g['当日率'] = np.where(g['前のレース'] >= 3, g['前の数'] / g['全の数'], np.nan)
DAY = {tuple(k): (r, n) for k, r, n in zip(g[KEY].values.tolist(), g['当日率'], g['前のレース'])}
del H

RACE = ['場c', '月', '時', '距離', '馬場c', '天候c', 'n', '賞金']
EACH = ['p先頭', 'p先行', '枠番', '馬番率', '負担重量', '減量', '齢', '着率1', '過去3差', '過去3着率', '最高T順率', '全3率',
        '騎勝率', '騎3率', '間隔', '距離差', '賞金比', '前人気率']
rows = []
for k, gg in T.groupby(KEY, sort=False):
    if len(gg) < 4 or k not in UREN: continue
    gg = gg.sort_values(['p先行', 'p先頭'], ascending=False)
    a, b = gg.iloc[0], gg.iloc[1]
    s, t = (a, b) if a['p先頭'] >= b['p先頭'] else (b, a)
    rec = dict(zip(KEY, k)); rec.update(年=int(a['年']), 日=a['日'])
    for c in RACE: rec[c] = a[c]
    for lab, h in (('先_', s), ('次_', t)):
        for c in EACH: rec[lab + c] = h[c]
    rest = gg.iloc[2:]
    rec['3番目_p先行'] = rest['p先行'].iloc[0]; rec['4番目_p先行'] = rest['p先行'].iloc[1] if len(rest) > 1 else np.nan
    rec['他_p先頭計'] = rest['p先頭'].sum()
    dr = DAY.get(tuple(k), (np.nan, np.nan)); rec['当日率'], rec['前のレース'] = dr
    rec['y'] = UREN[k].get(tuple(sorted((int(a['馬番']), int(b['馬番'])))), 0.0)
    rows.append(rec)
D = pd.DataFrame(rows)
FE = RACE + [p + c for p in ('先_', '次_') for c in EACH] + ['3番目_p先行', '4番目_p先行', '他_p先頭計', '当日率', '前のレース']
cat = [FE.index(c) for c in ['場c', '馬場c', '天候c']]
print('行', len(D), D.groupby('年').size().to_dict(), flush=True)

out = []
for Y in range(2021, 2027):
    tr = D[(D['年'] >= 2018) & (D['年'] <= Y - 2)]; pv = D[D['年'] == Y - 1].copy(); te = D[D['年'] == Y].copy()
    pv['見込み'] = 0.0; te['見込み'] = 0.0
    for seed in (0, 1, 2):
        m = HistGradientBoostingRegressor(loss='poisson', max_leaf_nodes=15, min_samples_leaf=500, learning_rate=0.05, max_iter=500,
                                          early_stopping=True, validation_fraction=0.1, random_state=seed, categorical_features=cat)
        m.fit(tr[FE], tr['y']); pv['見込み'] += m.predict(pv[FE]) / 3; te['見込み'] += m.predict(te[FE]) / 3
    for q in (10, 20, 33):
        te[f'比{q}'] = te['見込み'] / pv['見込み'].quantile(1 - q / 100)
    out.append(te); print(Y, '学習', len(tr), 'レース', flush=True)
P = pd.concat(out, ignore_index=True)
P.to_pickle('/tmp/chiho_pair_model.pkl')


def boot(s, d, B=3000):
    x = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(x), len(x)); o.append(x['sum'].values[k].sum() / x['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])


def streak(v):
    m = c = 0
    for x in v:
        c = c + 1 if x == 0 else 0; m = max(m, c)
    return m


pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
A5 = P[(P['年'] >= 2021) & (P['年'] <= 2025)]
days = A5['日'].nunique()
rows = []
for q in (10, 20, 33):
    S = P[P[f'比{q}'] >= 1]; A = S[(S['年'] >= 2021) & (S['年'] <= 2025)]; Z = S[S['年'] == 2026]
    by = A.groupby('年')['y'].mean() * 100; lo, hi = boot(A['y'].values, A['日'].values); top3 = A['y'].nlargest(3)
    rows.append(dict(線=f'上位{q}%' + ('（主）' if q == 20 else ''), 一日=round(len(A) / days, 1), 的中=f"{(A['y'] > 0).mean()*100:.1f}",
                     当たりの平均=f"{A.loc[A['y'] > 0, 'y'].mean()*100:,.0f}円", 回収5年=f"{A['y'].mean()*100:.1f}", 幅=f'{lo:.0f}〜{hi:.0f}',
                     年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)), 百以上=f'{(by >= 100).sum()}/5',
                     上位3本抜き=f"{(A['y'].sum() - top3.sum()) / len(A) * 100:.1f}", 最長の外れ=streak(A.sort_values(['日'] + KEY)['y'].values),
                     y2026=f"{Z['y'].mean()*100:.1f}（{len(Z)}点）"))
print('\n■ 前の2頭の馬複・戻りモデルで選んだレース'); print(pd.DataFrame(rows).to_string(index=False))
print(f"  くらべる：全部のレース（同じ組） {A5['y'].mean()*100:.1f}%  2026年 {P[P['年']==2026]['y'].mean()*100:.1f}%")

# 厳しい数え方：線を前の年までの成績で選び直す（2021年は主の20%）
tot = []
for Y in range(2021, 2027):
    if Y == 2021: q = 20
    else:
        prev = P[(P['年'] >= 2021) & (P['年'] < Y)]
        q = max((10, 20, 33), key=lambda qq: prev.loc[prev[f'比{qq}'] >= 1, 'y'].mean())
    S = P[(P['年'] == Y) & (P[f'比{q}'] >= 1)]; tot.append(S.assign(選んだ線=q)); print(f'  {Y}年：線 上位{q}%  {len(S)}点  回収 {S["y"].mean()*100:.1f}%')
S = pd.concat(tot); S2 = S[S['年'] <= 2025]
print(f"  厳しい数え方 2021〜2025年 {len(S2)}点 {S2['y'].mean()*100:.1f}%／2026年 {S[S['年']==2026]['y'].mean()*100:.1f}%")

# 見込みの当たり方（2021〜2025年、見込みの10分位）
A5 = A5.copy(); A5['帯'] = pd.qcut(A5['見込み'], 10, labels=False, duplicates='drop')
print('\n■ 見込みと実際（2021〜2025年、見込みで10に分けて）')
print(A5.groupby('帯').agg(レース=('y', 'size'), 見込み=('見込み', lambda s: round(s.mean() * 100, 1)), 実際=('y', lambda s: round(s.mean() * 100, 1)),
                          的中=('y', lambda s: round((s > 0).mean() * 100, 1))).to_string())
