"""当日の前残り（検証計画「D：当日の前残り」）
当日の前残り率：同じ日・同じ場の、それより前のレース（3レース以上）の1・2着の馬のうち、最初のコーナーを2番手以内で回った馬の割合。
線：2016〜2020年のレースで上位3分の1になる値。D1 前の2頭の馬複、D2 先頭の見込みが一番の馬の単勝（率が線以上のレースだけ）。"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl')[KEY + ['馬番', '着', '初角', '年', '日']].copy()
H['R'] = pd.to_numeric(H['レース番号'], errors='coerce')
top2 = H[H['着'].isin([1, 2]) & H['初角'].notna()].copy()
top2['前'] = (top2['初角'] <= 2).astype(int)
g = top2.groupby(KEY).agg(前=('前', 'sum'), 数=('前', 'size'), R=('R', 'first'), 年=('年', 'first'), 日=('日', 'first')).reset_index()
g = g.sort_values(['競馬場', '競走年月日', 'R'])
d = g.groupby(['競馬場', '競走年月日'])
g['前の数'] = d['前'].transform(lambda s: s.shift(1).cumsum())
g['全の数'] = d['数'].transform(lambda s: s.shift(1).cumsum())
g['前のレース'] = d.cumcount()
g['率'] = np.where(g['前のレース'] >= 3, g['前の数'] / g['全の数'], np.nan)
g['今の前残り'] = g['前'] / g['数']          # そのレースで、1・2着のうち2番手以内で回った馬の割合（結果）
base = g[(g['年'] <= 2020) & g['率'].notna()]
cut_hi = base['率'].quantile(2 / 3); cut_lo = base['率'].quantile(1 / 3)
print(f'線（2016〜2020年の上位3分の1）：{cut_hi:.3f}　下3分の1：{cut_lo:.3f}　（{len(base)}レース）')
g['帯'] = np.select([g['率'] >= cut_hi, g['率'] < cut_lo], ['高', '低'], '中'); g.loc[g['率'].isna(), '帯'] = '（3レース未満）'

print('\n■ 前提：傾向は1日の中で続くか（そのレースの1・2着のうち、最初のコーナーを2番手以内で回った馬の割合）')
for lab, X in (('2016〜2020年', g[g['年'] <= 2020]), ('2021〜2025年', g[(g['年'] >= 2021) & (g['年'] <= 2025)]), ('2026年', g[g['年'] == 2026])):
    t = X.groupby('帯')['今の前残り'].agg(['size', 'mean']); print(' ', lab, '　'.join(f"{k} {v['mean']*100:.1f}%（{int(v['size'])}）" for k, v in t.iterrows()))

R = pd.read_pickle('/tmp/chiho_front2.pkl')
R = R.merge(g[KEY + ['率', '帯']], on=KEY, how='left')
T = pd.read_pickle('/tmp/chiho_style.pkl')
lead = T.sort_values(['p先頭'], ascending=False).drop_duplicates(KEY)[KEY + ['単払', '人気']].rename(columns={'単払': 'D2', '人気': '逃げ予想の人気'})
R = R.merge(lead, on=KEY, how='left')


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


rows = []
for bet, col in (('D1 前の2頭の馬複', 'K1'), ('D2 逃げ予想の単勝', 'D2')):
    for band in ('高', '中', '低', '（3レース未満）'):
        X = R[(R['帯'] == band) & R[col].notna()]; A = X[(X['年'] >= 2021) & (X['年'] <= 2025)]; Z = X[X['年'] == 2026]
        if len(A) < 30: continue
        by = A.groupby('年')[col].mean() * 100; lo, hi = boot(A[col].values, A['日'].values); top3 = A[col].nlargest(3)
        rows.append(dict(券=bet, 当日の前残り=band, 点_年=round(len(A) / 5), 的中=f"{(A[col] > 0).mean()*100:.1f}", 回収5年=f"{A[col].mean()*100:.1f}",
                         幅=f'{lo:.0f}〜{hi:.0f}', 年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)), 百以上=f'{(by >= 100).sum()}/5',
                         上位3本抜き=f"{(A[col].sum() - top3.sum()) / len(A) * 100:.1f}", 最長の外れ=streak(A.sort_values('日')[col].values),
                         y2026=f"{Z[col].mean()*100:.1f}（{len(Z)}点）"))
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print('\n■ 買い方（決めたのは「高」だけ。中・低・3レース未満はくらべるため）'); print(pd.DataFrame(rows).to_string(index=False))
A = R[(R['年'] >= 2021) & (R['年'] <= 2025) & (R['帯'] == '高')]
print('\n「高」のレースの場ごと（D1）'); print(A.groupby('競馬場').agg(レース=('K1', 'size'), 回収=('K1', lambda s: round(s.mean() * 100, 1))).to_string())
R.to_pickle('/tmp/chiho_front_day.pkl')
