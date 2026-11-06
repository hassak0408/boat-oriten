"""中央競馬：K9 その日の馬場の偏りに逆らって負けた馬は舐められているか（検証計画 K9）。
その日の偏り＝同じ日・同じ場・同じ芝ダのほかのレース（そのレースは入れない）の3着内の馬の、最初の角の順位÷頭数の平均（前残り度）と馬番÷頭数の平均（内外）。
使い方：python jtrack.py 材料.pkl [純粋な評価の見込み.pkl]"""
import sys, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']; DAY = ['年月日', '場', '芝ダ']
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy()
H['Ri'] = pd.to_numeric(H['R'], errors='coerce')
H['zq'] = H.groupby(KEY)['単勝オッズ'].transform(lambda s: (1 / s).sum())      # 市場の見込みはレースの全部の馬で割る
H['番率'] = H['馬番'].astype(float) / H['n']
T = H[(H['着'] <= 3) & H['初角率'].notna()]
RS = H.drop_duplicates(KEY)[KEY + ['芝ダ', '年']].merge(
    T.groupby(KEY).agg(s前=('初角率', 'sum'), s内=('番率', 'sum'), c=('初角率', 'size')).reset_index(), on=KEY, how='left').fillna({'s前': 0, 's内': 0, 'c': 0})
RS['有'] = (RS['c'] > 0).astype(int)
D = RS.groupby(DAY).agg(S前=('s前', 'sum'), S内=('s内', 'sum'), C=('c', 'sum'), NR=('有', 'sum')).reset_index()
RS = RS.merge(D, on=DAY)
ok = (RS['NR'] - RS['有']) >= 3
RS['日前残り'] = ((RS['S前'] - RS['s前']) / (RS['C'] - RS['c'])).where(ok)
RS['日内外'] = ((RS['S内'] - RS['s内']) / (RS['C'] - RS['c'])).where(ok)
Q = RS[RS['年'] <= 2018].groupby('芝ダ')[['日前残り', '日内外']].quantile([0.25, 0.75])
print('分け目（芝ダごと、2016〜2018年）\n', Q.round(3).to_string(), flush=True)
for c, lo, hi in (('日前残り', '前残り日', '差し日'), ('日内外', '内日', '外日')):
    q25 = RS['芝ダ'].map(Q[c].xs(0.25, level=1)); q75 = RS['芝ダ'].map(Q[c].xs(0.75, level=1))
    RS[lo] = (RS[c] <= q25).astype(float).where(RS[c].notna()); RS[hi] = (RS[c] >= q75).astype(float).where(RS[c].notna())
H = H.merge(RS[KEY + ['前残り日', '差し日', '内日', '外日']], on=KEY, how='left')
H = H.sort_values(['馬', '日', 'Ri']).reset_index(drop=True); g = H.groupby('馬', sort=False)
for c in ('前残り日', '差し日', '内日', '外日', '初角', '番率'): H['前の' + c] = g[c].shift(1)

H = H[(H['合わない'] == 0) & (H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = H[H['着x1'].notna() & (H['前不利あり'] == 0)].copy()
H['q'] = 1 / H['単勝オッズ'] / H['zq']; H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)
x6 = H['着x1'] >= 6
seg = {
    'K9a 前が残る日に後ろから': (H['前の前残り日'] == 1) & (H['初角率1'] > 0.5) & (H['着x1'] >= 4),
    'K9b 後ろが来る日に前から': (H['前の差し日'] == 1) & (H['前の初角'] <= 3) & x6,
    'K9c 内が来る日に外の枠': (H['前の内日'] == 1) & (H['前の番率'] > 0.6) & x6,
    'K9d 外が来る日に内の枠': (H['前の外日'] == 1) & (H['前の番率'] <= 0.4) & x6,
    '（くらべる）前走6着以下の全部': x6,
}


def boot(v, day, B=2000, ratio=None):
    x = pd.DataFrame({'d': day, 's': v} | ({'q': ratio} if ratio is not None else {})).groupby('d').sum()
    rng = np.random.default_rng(0); k = rng.integers(0, len(x), (B, len(x)))
    if ratio is not None: s = x['s'].values[k].sum(1) / x['q'].values[k].sum(1)
    else:
        n = pd.DataFrame({'d': day}).groupby('d').size().reindex(x.index).values
        s = x['s'].values[k].sum(1) / n[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


rows, keep = [], {}
for name, m in seg.items():
    res = {}
    for lab, pm in (('2016〜2021', H['年'] <= 2021), ('2022〜2026', H['年'] >= 2022)):
        X = H[m.fillna(False).astype(bool) & pm]
        if len(X) < 50: continue
        lo_, hi_ = boot(X['払'].values, X['年月日'].values); rl, rh = boot(X['勝'].values, X['年月日'].values, ratio=X['q'].values)
        r = X['勝'].sum() / X['q'].sum(); res[lab] = (r, rl, rh, X['払'].mean() * 100, lo_)
        by = X.groupby('年')['払'].mean() * 100
        rows.append({'印': name, '期間': lab, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '人気の平均': round(X['人気'].mean(), 1),
                     '実際÷市場': f'{r:.3f}（{rl:.3f}〜{rh:.3f}）', '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo_:.0f}〜{hi_:.0f}）",
                     '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
    if len(res) == 2:
        a, b = res['2016〜2021'], res['2022〜2026']
        keep[name] = ('傾向として残す' if min(a[0], b[0]) >= 1.05 and a[1] > 1 and b[1] > 1 else '残さない',
                      '買い方の候補' if a[3] >= 100 and b[3] >= 100 and b[4] >= 100 else '候補でない')
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(pd.DataFrame(rows).to_string(index=False))
print('\n■ 決めごとに照らすと')
for k, v in keep.items(): print(f' {k}：{v[0]}・{v[1]}')
if len(sys.argv) > 2:
    P = pd.read_pickle(sys.argv[2]); P = P.loc[:, ~P.columns.duplicated()]
    P = P[(P['n'] >= 5) & P.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    P['p1'] = P['p1'] / P.groupby(KEY)['p1'].transform('sum')
    print('\n■ 一覧の評価（純粋な評価、2021〜2026年）でも低く見ているか：実際÷評価（実際÷市場）')
    for name in seg:
        X = H[seg[name].fillna(False).astype(bool)].merge(P[KEY + ['馬番', 'p1']], on=KEY + ['馬番'], how='inner')
        if len(X) >= 50: print(f" {name}：{len(X)}頭 実際÷評価 {X['勝'].sum()/X['p1'].sum():.3f}（実際÷市場 {X['勝'].sum()/X['q'].sum():.3f}）")
