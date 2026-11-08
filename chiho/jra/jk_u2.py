"""中央競馬：U2 前走の推定上りで、市場が見誤る馬はいるか（検証計画 U2）。
前走の推定上り（jra/ses、ped.py）で形を作り、その馬の実際の1着÷市場の見込みと単勝の回収を、選ぶ期間2016〜2021年・確かめる期間2022〜2026年で見る。
どれも前走の注記に不利が無い馬（前不利あり＝0）だけ。あわせて今の一覧の評価の実際÷評価。
使い方：python jk_u2.py 材料.pkl STORE 今の見込み.pkl"""
import sys, glob, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']
store = sys.argv[2]
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy(); H['R'] = H['R'].astype(str); H['Ri'] = pd.to_numeric(H['R'], errors='coerce')
rs = [pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '馬番', '推定上り']) for f in glob.glob(f'{store}/jra/ses/*/*.csv.gz')]
U = pd.concat(rs, ignore_index=True)
U['上り'] = pd.to_numeric(U['推定上り'], errors='coerce'); U['馬番'] = pd.to_numeric(U['馬番'], errors='coerce')
U = U[U['上り'].notna() & U['馬番'].notna()].drop_duplicates(KEY + ['馬番'])
g = U.groupby(KEY)['上り']; rk = g.rank(method='min')
U['推上順率'] = rk / g.transform('size'); U['推上1位'] = (rk == 1).astype(float)
ut = U.set_index(KEY + ['馬番'])[['推上順率', '推上1位']]
idx = pd.MultiIndex.from_arrays([H[k] for k in KEY] + [pd.to_numeric(H['馬番'], errors='coerce')])
for c in ('推上順率', '推上1位'): H[c] = ut[c].reindex(idx).values
H['zq'] = H.groupby(KEY)['単勝オッズ'].transform(lambda s: (1 / s).sum())      # 市場の見込みはレースの全部の馬で割る

H = H.sort_values(['馬', '日', 'Ri']).reset_index(drop=True)
g = H.groupby('馬', sort=False)
for c in ('着x', '初角', '推上順率', '推上1位'):
    H['前の' + c] = g[c].shift(1)
chk = H[['前の推上順率', '前の着x']].dropna(); print('前走の推定上りがある割合（前走のある行で）', round(len(chk) / H['前の着x'].notna().sum(), 4), flush=True)
H = H[(H['合わない'] == 0) & (H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = H[H['前の着x'].notna() & (H['前不利あり'] == 0)].copy()
H['q'] = 1 / H['単勝オッズ'] / H['zq']
H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)

P = pd.read_pickle(sys.argv[3]); P = P.loc[:, ~P.columns.duplicated()].copy(); P['R'] = P['R'].astype(str)
P['p1'] = P['p1'] / P.groupby(KEY)['p1'].transform('sum')
H = H.merge(P[KEY + ['馬番', 'p1']].rename(columns={'p1': '評価'}), on=KEY + ['馬番'], how='left')

seg = {
    'U2a 上り最速で負けた（4着以下）': (H['前の推上1位'] == 1) & (H['前の着x'] >= 4),
    'U2b 先行して止まった（上り下2割・6着以下）': (H['前の初角'] <= 3) & (H['前の推上順率'] > 0.8) & (H['前の着x'] >= 6),
    'U2c 上りがかかったのに粘った（上り下半分・3着内）': (H['前の推上順率'] > 0.5) & (H['前の着x'] <= 3),
    '（くらべる）前走4着以下の全部': H['前の着x'] >= 4,
    '（くらべる）前走3着内の全部': H['前の着x'] <= 3,
}


def boot(v, day, B=2000, ratio=None):
    x = pd.DataFrame({'d': day, 's': v} | ({'q': ratio} if ratio is not None else {})).groupby('d').sum()
    rng = np.random.default_rng(0); k = rng.integers(0, len(x), (B, len(x)))
    if ratio is not None: s = x['s'].values[k].sum(1) / x['q'].values[k].sum(1)
    else:
        n = pd.DataFrame({'d': day}).groupby('d').size().reindex(x.index).values
        s = x['s'].values[k].sum(1) / n[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


rows = []
for name, m in seg.items():
    for lab, pm in (('2016〜2021', H['年'] <= 2021), ('2022〜2026', H['年'] >= 2022)):
        X = H[m.fillna(False).astype(bool) & pm]
        if len(X) < 50: continue
        lo_, hi_ = boot(X['払'].values, X['年月日'].values); rl, rh = boot(X['勝'].values, X['年月日'].values, ratio=X['q'].values)
        r = X['勝'].sum() / X['q'].sum()
        by = X.groupby('年')['払'].mean() * 100
        rows.append({'形': name, '期間': lab, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '人気の平均': round(X['人気'].mean(), 1),
                     '実際÷市場': f'{r:.3f}（{rl:.2f}〜{rh:.2f}）', '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo_:.0f}〜{hi_:.0f}）",
                     '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(pd.DataFrame(rows).to_string(index=False))
print('\n■ 今の一覧の評価（U1＋付け直し）の実際÷評価')
for name, m in seg.items():
    out = []
    for lab, a, b in (('2021〜2023', 2021, 2023), ('2024〜2026', 2024, 2026)):
        X = H[m.fillna(False).astype(bool) & H['年'].between(a, b) & H['評価'].notna()]
        if len(X) >= 50: out.append(f"{lab} {X['勝'].sum() / X['評価'].sum():.3f}（{len(X)}頭）")
    print(name, '／'.join(out))
