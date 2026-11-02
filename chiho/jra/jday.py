"""中央競馬：J5 当日の傾向（検証計画の同じ名前の節）。モデルもオッズも使わずに前の馬を選び、当日の前残り率が高い日だけ買う。
使い方：python jday.py 材料.pkl STORE/jra/data"""
import sys, glob, json, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1])
H = H[~H['予測'] & (H['合わない'] == 0)].copy()
H['R'] = H['R'].astype(int)
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        if isinstance(d.get('馬連'), list) and len(d['馬連']) == 1: pays[(a, b, int(c))] = d['馬連'][0] / 100
# レースごとの前残り（1・2着のうち1角2番手以内の数と、1角の位置が分かる1・2着の数）
T = H[H['着'] <= 2]
rk = T.groupby(KEY + ['芝ダ']).agg(前=('初角', lambda s: (s <= 2).sum()), 数=('初角', lambda s: s.notna().sum())).reset_index()
rk = rk.sort_values(['年月日', '場', '芝ダ', 'R'])
g = rk.groupby(['年月日', '場', '芝ダ'], sort=False)
rk['前の前'] = g['前'].cumsum() - rk['前']; rk['前の数'] = g['数'].cumsum() - rk['数']
rk['前のレース'] = g.cumcount() - 0      # それより前の同じ芝ダのレースの数（1角の位置が無いレースも数える）
rk['当日の前残り率'] = np.where(rk['前のレース'] >= 3, rk['前の前'] / rk['前の数'].where(rk['前の数'] > 0), np.nan)
rk['年'] = rk['年月日'].str[:4].astype(int)
th = rk.loc[rk['年'] <= 2021, '当日の前残り率'].dropna().quantile(2 / 3)
rk['帯'] = pd.cut(rk['当日の前残り率'], [-0.01, rk.loc[rk['年'] <= 2021, '当日の前残り率'].dropna().quantile(1 / 3), th - 1e-9, 1.01], labels=['低', '中', '高'])
print(f'線（2016〜2021年の上位3分の1）：{th:.3f}')
# 前の馬：先頭率5 が高い順、同じなら過去3角が前の順（初めて走る馬は後ろ）
H = H.sort_values(KEY + ['先頭率5', '過去3角'], ascending=[True, True, True, False, True], na_position='last')
H['前順'] = H.groupby(KEY).cumcount() + 1
rows = []
for k, x in H.groupby(KEY, sort=False):
    top = x[x['前順'] <= 2]
    if len(top) < 2 or x['n'].iloc[0] < 5: continue
    f1 = top.iloc[0]; both = set(top['着'].fillna(99)) == {1, 2}
    rows.append({'年月日': k[0], '場': k[1], 'R': k[2], '前2の馬連': (pays.get((k[0], k[1], int(k[2])), 0.0) if both else 0.0) if (k[0], k[1], int(k[2])) in pays else np.nan,
                 '前1の単勝': f1['単勝オッズ'] if f1['着'] == 1 else 0.0, '前1の1角2番手以内': f1['初角'] <= 2 if pd.notna(f1['初角']) else np.nan,
                 '1・2着の前': ((x['着'] <= 2) & (x['初角'] <= 2)).sum(), '1・2着の数': ((x['着'] <= 2) & x['初角'].notna()).sum()})
B = pd.DataFrame(rows).merge(rk[KEY + ['当日の前残り率', '帯', '年']], on=KEY, how='inner')
B = B[B['帯'].notna()]


def boot(v, day, B_=2000):
    x = pd.DataFrame({'d': day, 's': v}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B_, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


pd.set_option('display.width', 220)
out = []
for lab, pm in (('2016〜2021', B['年'] <= 2021), ('2022〜2026', B['年'] >= 2022)):
    for band in ('高', '中', '低'):
        X = B[pm & (B['帯'] == band)]
        premise = X['1・2着の前'].sum() / X['1・2着の数'].sum()
        for col in ('前2の馬連', '前1の単勝'):
            Z = X[X[col].notna()]
            lo, hi = boot(Z[col].values, Z['年月日'].values)
            by = Z.groupby('年')[col].mean() * 100
            out.append({'期間': lab, '前残り': band, '券': col, 'レース': len(Z), '回収': f"{Z[col].mean()*100:.1f}%（{lo:.0f}〜{hi:.0f}）",
                        '年ごと': '・'.join(f'{v:.0f}' for v in by.values), '前提（1・2着のうち1角2番手以内）': f'{premise*100:.1f}%'})
print(pd.DataFrame(out).to_string(index=False))
for sd in ('芝', 'ダート'):
    pass
