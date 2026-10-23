"""D の場の分け（検証計画「D の場の分け」）：岩手（盛岡・水沢）と笠松の D1 を、まだ見ていない期間（2018〜2020年・2026年の場ごと）で確かめる。
D1＝前の2頭（3番手以内の見込みの上位2頭）の馬複を、当日の前残り率0.5以上のレースだけ。"""
import numpy as np, pandas as pd
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']


def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan


T = pd.read_pickle('/tmp/chiho_style_all.pkl')[KEY + ['馬番', '年', '日', 'p先行', 'p先頭']].copy()
T['馬番'] = T['馬番'].astype(int)
T = T.sort_values(KEY + ['p先行', 'p先頭'], ascending=[True, True, True, False, False])
T['順'] = T.groupby(KEY).cumcount(); T['頭'] = T.groupby(KEY)['馬番'].transform('size')
top = T[(T['順'] <= 1) & (T['頭'] >= 4)]
pair = top.groupby(KEY).agg(a=('馬番', 'min'), b=('馬番', 'max'), 年=('年', 'first'), 日=('日', 'first')).reset_index()

PB = _read('race', 'payback')
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy()
x['a'] = pd.to_numeric(x['馬複組番1'], errors='coerce'); x['b'] = pd.to_numeric(x['馬複組番2'], errors='coerce'); x['払'] = x['馬複払戻金（円）'].map(num)
x = x.dropna(subset=['a', 'b', '払']); x['lo'] = x[['a', 'b']].min(axis=1).astype(int); x['hi'] = x[['a', 'b']].max(axis=1).astype(int)
sold = x[KEY].drop_duplicates()
hit = x.drop_duplicates(KEY + ['lo', 'hi'])[KEY + ['lo', 'hi', '払']]
pair = pair.merge(sold, on=KEY, how='inner').merge(hit, left_on=KEY + ['a', 'b'], right_on=KEY + ['lo', 'hi'], how='left')
pair['y'] = pair['払'].fillna(0) / 100

H = pd.read_pickle('/tmp/chiho_feat.pkl')[KEY + ['着', '初角']].copy()
H['R'] = pd.to_numeric(H['レース番号'], errors='coerce')
t2 = H[H['着'].isin([1, 2]) & H['初角'].notna()].copy(); t2['前'] = (t2['初角'] <= 2).astype(int)
g = t2.groupby(KEY).agg(前=('前', 'sum'), 数=('前', 'size'), R=('R', 'first')).reset_index().sort_values(['競馬場', '競走年月日', 'R'])
d = g.groupby(['競馬場', '競走年月日'])
g['前の数'] = d['前'].transform(lambda s: s.shift(1).cumsum()); g['全の数'] = d['数'].transform(lambda s: s.shift(1).cumsum())
g['当日率'] = np.where(d.cumcount() >= 3, g['前の数'] / g['全の数'], np.nan)
pair = pair.merge(g[KEY + ['当日率']], on=KEY, how='left')
pair['群'] = pair['競馬場'].map({'盛岡': '岩手・笠松', '水沢': '岩手・笠松', '笠松': '岩手・笠松', '園田': '園田・姫路', '姫路': '園田・姫路'})
D1 = pair[pair['当日率'] >= 0.5]


def boot(s, d, B=3000):
    x = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(x), len(x)); o.append(x['sum'].values[k].sum() / x['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])


pd.set_option('display.width', 250)
rows = []
for lab, m in (('2018〜2020年', (D1['年'] >= 2018) & (D1['年'] <= 2020)), ('2026年1〜9月', D1['年'] == 2026), ('（見た期間）2021〜2025年', (D1['年'] >= 2021) & (D1['年'] <= 2025))):
    for grp in ('岩手・笠松', '園田・姫路'):
        S = D1[m & (D1['群'] == grp)]
        if len(S) < 30: continue
        lo, hi = boot(S['y'].values, S['日'].values); by = S.groupby('年')['y'].mean() * 100
        rows.append(dict(期間=lab, 場=grp, 点=len(S), 的中=f"{(S['y'] > 0).mean()*100:.1f}", 回収=f"{S['y'].mean()*100:.1f}", 幅=f'{lo:.0f}〜{hi:.0f}',
                         年ごと='・'.join(f'{v:.0f}' for v in by.values), 上位3本抜き=f"{(S['y'].sum() - S['y'].nlargest(3).sum()) / len(S) * 100:.1f}"))
print(pd.DataFrame(rows).to_string(index=False))
print('\n場ごと（2018〜2020年・2026年）')
for lab, m in (('2018〜2020年', (D1['年'] >= 2018) & (D1['年'] <= 2020)), ('2026年', D1['年'] == 2026)):
    print(' ', lab, '　'.join(f"{k} {v['mean']*100:.0f}%（{int(v['size'])}）" for k, v in D1[m].groupby('競馬場')['y'].agg(['size', 'mean']).iterrows()))
pair.to_pickle('/tmp/chiho_pair_all.pkl')
