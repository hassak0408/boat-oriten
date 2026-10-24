"""オッズや過去の戦績に惑わされずに評価できているか、割安な馬が見えているか（検証計画の同じ名前の節）。B3の1着のモデル。"""
import numpy as np, pandas as pd
from load import odds as load_odds
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '勝', '3着内', '単払', '人気', 'n', '年', '日', '着x1', '着率1', '前人気', '前人気着差', '最良着2_5', '間隔']]
H['馬番'] = H['馬番'].astype(float)
W = pd.read_pickle('/tmp/chiho_win_B3.pkl'); W['馬番'] = W['馬番'].astype(float)
qtab = H[(H['年'] <= 2020) & H['人気'].notna()].groupby(['n', '人気'])['勝'].mean()
D = H[(H['年'] >= 2021) & H['人気'].notna()].merge(W, on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D['p'] = D['p'] / D.groupby(KEY)['p'].transform('sum')
D['q'] = [qtab.get((n, r), np.nan) for n, r in zip(D['n'], D['人気'])]; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
D['r'] = D['p'] / D['q']


def boot(s, d, B=2000):
    x = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(x), len(x)); o.append(x['sum'].values[k].sum() / x['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])


pd.set_option('display.width', 250)
A = D[D['年'] <= 2025]
# 1) 惑わされそうな馬の種類ごと
segs = {'前走1着': A['着x1'] == 1, '前走で人気よりずっと上の着（人気−着順≧5）': A['前人気着差'] >= 5,
        '前走1番人気で4着以下': (A['前人気'] == 1) & (A['着x1'] >= 4), '前走大敗でも2〜5走前に3着内': (A['着率1'] > 0.6) & (A['最良着2_5'] <= 3),
        '61日以上の休み明け': A['間隔'] > 60, '全部': pd.Series(True, index=A.index)}
rows = []
for s, m in segs.items():
    X = A[m]
    rows.append(dict(種類=s, 頭=len(X), 一着率=round(X['勝'].mean() * 100, 1), 人気の平均=round(X['人気'].mean(), 1),
                     モデル_実際割る見込み=round(X['勝'].sum() / X['p'].sum(), 2), 人気の順_実際割る見込み=round(X['勝'].sum() / X['q'].sum(), 2),
                     単勝の回収=round(X['単払'].mean() * 100, 1)))
print('■ 惑わされそうな馬の種類ごと（2021〜2025年）'); print(pd.DataFrame(rows).to_string(index=False))

# 2) モデルと市場（人気の順）の食い違い
bins = [0, 0.5, 0.8, 1.0, 1.25, 1.5, 2, 3, 99]
for lab, X in (('2021〜2025年', A), ('2026年1〜9月', D[D['年'] == 2026])):
    t = X.groupby(pd.cut(X['r'], bins), observed=True).agg(頭=('勝', 'size'), 人気の平均=('人気', 'mean'), モデル見込み=('p', 'mean'), 人気の見込み=('q', 'mean'),
                                                          一着率=('勝', 'mean'), 単勝の回収=('単払', 'mean'), 三着内率=('3着内', 'mean'))
    for c in ('モデル見込み', '人気の見込み', '一着率', '単勝の回収', '三着内率'): t[c] = (t[c] * 100).round(1)
    t['人気の平均'] = t['人気の平均'].round(1)
    print(f'\n■ r（モデル÷人気の順の見込み）の帯ごと（{lab}）'); print(t.to_string())

# 決めた形：rが2以上の4番人気以下の単勝
S = A[(A['r'] >= 2) & (A['人気'] >= 4)]
by = S.groupby('年')['単払'].mean() * 100; lo, hi = boot(S['単払'].values, S['日'].values)
Z = D[(D['年'] == 2026) & (D['r'] >= 2) & (D['人気'] >= 4)]
print(f"\n■ 決めた形（rが2以上・4番人気以下の単勝）：2021〜2025年 {len(S)}頭（1日{len(S)/A['日'].nunique():.1f}頭）、1着率 {S['勝'].mean()*100:.1f}%、"
      f"回収 {S['単払'].mean()*100:.1f}%（95%幅 {lo:.0f}〜{hi:.0f}）、年ごと {'・'.join(f'{v:.0f}' for v in by.values)}／2026年 {Z['単払'].mean()*100:.1f}%（{len(Z)}頭）")

# 3) 単勝のオッズの市場（2026年3〜9月）
O = load_odds(); WO = O[(O['賭式'] == '単勝') & (O['オッズ'] > 0)].copy(); WO['馬番'] = pd.to_numeric(WO['番号1'], errors='coerce')
Z = D[D['年'] == 2026].merge(WO[KEY + ['馬番', 'オッズ']], on=KEY + ['馬番'], how='inner')
Z = Z[Z.groupby(KEY)['馬番'].transform('size') == Z.groupby(KEY)['勝'].transform('size')].copy()
Z['qo'] = 1 / Z['オッズ']; Z['qo'] = Z['qo'] / Z.groupby(KEY)['qo'].transform('sum'); Z['ro'] = Z['p'] / Z['qo']
t = Z.groupby(pd.cut(Z['ro'], bins), observed=True).agg(頭=('勝', 'size'), 人気の平均=('人気', 'mean'), オッズの平均=('オッズ', 'median'), モデル見込み=('p', 'mean'),
                                                        オッズの見込み=('qo', 'mean'), 一着率=('勝', 'mean'), 単勝の回収=('単払', 'mean'))
for c in ('モデル見込み', 'オッズの見込み', '一着率', '単勝の回収'): t[c] = (t[c] * 100).round(1)
t['人気の平均'] = t['人気の平均'].round(1)
print('\n■ r（モデル÷単勝のオッズの見込み）の帯ごと（2026年3〜9月、確定オッズ）'); print(t.to_string())
S = Z[(Z['ro'] >= 2) & (Z['人気'] >= 4)]
print(f"  rが2以上・4番人気以下：{len(S)}頭、1着率 {S['勝'].mean()*100:.1f}%、単勝の回収 {S['単払'].mean()*100:.1f}%")
