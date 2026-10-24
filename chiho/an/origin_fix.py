"""前の所属による見込みの直し（検証計画「前の所属による見込みの直し」）。3着内の見込み（cand3.py 朝3）に、来かた×5場で何戦目の「実際÷見込み」を掛ける。
掛ける値は2021〜2025年で決め、2026年1〜9月で確かめる。"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '馬', '日', '着', '勝', '3着内', '人気', 'n', '年', '芝走', '全走', '初データ']]
F2 = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '走数']].rename(columns={'走数': '五場走数'})
H['馬番'] = H['馬番'].astype(float); F2['馬番'] = F2['馬番'].astype(float); H = H.merge(F2, on=KEY + ['馬番'], how='left')
H = H.sort_values(['馬', '日', 'レース番号'])
first = np.select([(H['五場走数'] == 0) & (H['全走'] == 0), (H['五場走数'] == 0) & (H['初データ'] == 1) & (H['芝走'] > 0),
                   (H['五場走数'] == 0) & (H['初データ'] == 1), (H['五場走数'] == 0) & (H['初データ'] == 0)], ['デビュー', '中央', '外（芝なし）', 'ほかの地方'], '')
H['来かた'] = pd.Series(first, index=H.index).replace('', np.nan); H['来かた'] = H.groupby('馬')['来かた'].transform(lambda s: s.ffill())
H['戦目'] = H['五場走数'] + 1
H['組'] = np.where(H['来かた'].notna() & (H['戦目'] <= 3), H['来かた'].astype(str) + H['戦目'].astype(int).astype(str), '')
C = pd.read_pickle('/tmp/chiho_cand3_朝3.pkl'); C['馬番'] = C['馬番'].astype(float)
D = H[H['年'] >= 2021].merge(C, on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D = D[(D.groupby(KEY)['3着内'].transform('sum') >= 3) & (D['n'] >= 5)].copy()
D['p3n'] = (D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
A = D[D['年'] <= 2025]
f = A[A['組'] != ''].groupby('組').apply(lambda g: g['3着内'].sum() / g['p3n'].sum())
print('掛ける値（2021〜2025年）'); print(f.round(3).to_string())
D['f'] = D['組'].map(f).fillna(1.0)
D['p3f'] = D['p3n'] * D['f']; D['p3f'] = (D['p3f'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3f'].transform('sum')).clip(upper=0.97)


def stats(X, col):
    X = X.copy(); X['順'] = X.groupby(KEY)[col].rank(ascending=False, method='first'); t = X[X['順'] <= 3]; g = t.groupby(KEY)
    r = {'上位3頭に1着': g['勝'].max().mean(), '上位3頭の3着内の頭数': g['3着内'].sum().mean(),
         '馬連BOX3頭': (t[t['着'] <= 2].groupby(KEY).size().reindex(X.groupby(KEY).size().index, fill_value=0) >= 2).mean()}
    t5 = X[X['順'] <= 5]; r['3連複BOX5頭'] = (t5[t5['3着内'] == 1].groupby(KEY).size().reindex(X.groupby(KEY).size().index, fill_value=0) >= 3).mean()
    return r


for lab, X in (('2021〜2025年（値を決めた期間）', A.assign(p3f=D.loc[A.index, 'p3f'])), ('2026年1〜9月（確かめ）', D[D['年'] == 2026])):
    a, b = stats(X, 'p3n'), stats(X, 'p3f')
    print(f'\n{lab}'); [print(f"  {k}：直す前 {a[k]*100 if '頭数' not in k else a[k]:.4f}  直した後 {b[k]*100 if '頭数' not in k else b[k]:.4f}") for k in a]
Z = D[(D['年'] == 2026) & (D['組'] != '')]
print('\n2026年、来かたのある馬（1〜3戦目）の実際÷見込み：直す前', round(Z['3着内'].sum() / Z['p3n'].sum(), 3), '直した後', round(Z['3着内'].sum() / Z['p3f'].sum(), 3), f'（{len(Z)}頭）')
print(Z.groupby('組').apply(lambda g: pd.Series({'頭': len(g), '直す前': g['3着内'].sum() / g['p3n'].sum(), '直した後': g['3着内'].sum() / g['p3f'].sum()})).round(2).to_string())
f.rename('掛ける値').to_frame().to_json('/tmp/chiho_origin_fix.json', force_ascii=False)
