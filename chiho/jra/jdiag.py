"""中央競馬：モデルの使いどころを探す（検証計画「中央：モデルの使いどころを探す」①〜③）。
使い方：python jdiag.py 材料.pkl 見込み.pkl（jeval.py の出力）"""
import sys, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
F = pd.read_pickle(sys.argv[1])[KEY + ['馬番', '走数', '新馬', 'クラス', '合わない']]
D = pd.read_pickle(sys.argv[2]); D = D.loc[:, ~D.columns.duplicated()]
D = D.drop(columns=[c for c in ('走数', '新馬', 'クラス') if c in D]).merge(F, on=KEY + ['馬番'], how='left')
ok = D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())
D = D[ok & (D['n'] >= 5) & (D['合わない'] == 0)].copy()
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
D['m順'] = D.groupby(KEY)['p3'].rank(ascending=False, method='first')
D['m1順'] = D.groupby(KEY)['p1'].rank(ascending=False, method='first')
D['q順'] = D.groupby(KEY)['人気'].rank(method='first')
pd.set_option('display.width', 250)


def capture(X):
    """上位3頭に1着が入る率（モデル・人気）と、勝ち馬の −log 見込み（モデル・市場）"""
    g = X.groupby(KEY)
    m = g.apply(lambda x: bool(((x['m順'] <= 3) & (x['勝'] == 1)).any()), include_groups=False).mean()
    q = g.apply(lambda x: bool(((x['q順'] <= 3) & (x['勝'] == 1)).any()), include_groups=False).mean()
    w = X[X['勝'] == 1]
    return len(w), m, q, float(-np.log(w['p1'].clip(1e-6)).mean()), float(-np.log(w['q'].clip(1e-6)).mean())


# ① どこで負けているか（2021〜2023年）
A = D[D['年'] <= 2023].copy()
first = A.groupby(KEY)['走数'].transform(lambda s: (s == 0).mean())      # レースの中で初めて走る馬の割合
A['区分'] = np.select([A['新馬'] == 1, first >= 0.5, A['クラス'] >= 5, A['クラス'] >= 3], ['新馬', '未勝利（初出走が半分以上）', 'オープン・重賞', '2勝・3勝'], '未勝利・1勝')
rows = []
for (seg, sd), X in A.groupby(['区分', '芝ダ']):
    n, m, q, lm, lq = capture(X)
    rows.append({'区分': seg, '芝ダ': sd, 'レース': n, '上位3頭に1着（モデル）': f'{m*100:.1f}%', '（人気）': f'{q*100:.1f}%', '差': round((q - m) * 100, 1),
                 '損失（モデル）': round(lm, 3), '（市場）': round(lq, 3)})
print('■ ① どこで市場に負けているか（2021〜2023年）'); print(pd.DataFrame(rows).sort_values('差', ascending=False).to_string(index=False))

# ② モデルと人気が同じとき・違うとき
print('\n■ ② 1番手がモデルと人気で同じか（1着の率）')
for lab, X in (('2021〜2023年', D[D['年'] <= 2023]), ('2024〜2026年', D[D['年'] >= 2024])):
    t = X[X['m1順'] == 1][KEY + ['馬番', '勝', '人気', '単勝オッズ']].rename(columns={'馬番': 'm', '勝': 'm勝', '人気': 'm人気', '単勝オッズ': 'mオッズ'})
    f = X[X['q順'] == 1][KEY + ['馬番', '勝']].rename(columns={'馬番': 'f', '勝': 'f勝'})
    T = t.merge(f, on=KEY)
    same = T['m'] == T['f']
    print(f"{lab}：同じ {same.mean()*100:.0f}% のレース → その馬の1着 {T.loc[same, 'm勝'].mean()*100:.1f}%／"
          f"違う {(~same).mean()*100:.0f}% → モデルの1番手 {T.loc[~same, 'm勝'].mean()*100:.1f}%（平均{T.loc[~same, 'm人気'].mean():.1f}番人気）、1番人気 {T.loc[~same, 'f勝'].mean()*100:.1f}%")
print('\n■ ② 上位3頭（モデル）と人気の1〜3番人気の重なりの数ごと：重なった馬のどれかが1着の率・6頭（合わせた頭数）のどれかが1着の率')
for lab, X in (('2021〜2023年', D[D['年'] <= 2023]), ('2024〜2026年', D[D['年'] >= 2024])):
    X = X.assign(両方=(X['m順'] <= 3) & (X['q順'] <= 3), どちらか=(X['m順'] <= 3) | (X['q順'] <= 3))
    g = X.groupby(KEY).agg(重なり=('両方', 'sum'), 両方で1着=('勝', lambda s: 0), 合わせた頭数=('どちらか', 'sum'))
    g['両方で1着'] = X[X['両方']].groupby(KEY)['勝'].max().reindex(g.index).fillna(0)
    g['どちらかで1着'] = X[X['どちらか']].groupby(KEY)['勝'].max().reindex(g.index).fillna(0)
    t = g.groupby('重なり').agg(レース=('合わせた頭数', 'size'), 割合=('合わせた頭数', lambda s: len(s)), 重なった馬で1着=('両方で1着', 'mean'),
                              合わせた頭数=('合わせた頭数', 'mean'), 合わせた馬で1着=('どちらかで1着', 'mean'))
    t['割合'] = (t['割合'] / t['割合'].sum() * 100).round(1); t['重なった馬で1着'] = (t['重なった馬で1着'] * 100).round(1)
    t['合わせた馬で1着'] = (t['合わせた馬で1着'] * 100).round(1); t['合わせた頭数'] = t['合わせた頭数'].round(1)
    print(lab); print(t.to_string())

# ③ 勝ちきり度は、オッズで分かることの上に見分けるか（3着内に来た馬のうち1着の割合）
print('\n■ ③ 3着内に来た馬のうち1着の割合：単勝オッズの帯 × 勝ちきり度（帯の中で上半分・下半分）')
D['勝ちきり度'] = D['p1'] / D['p3']
T3 = D[D['着'] <= 3].copy()
T3['帯'] = pd.cut(T3['単勝オッズ'], [0, 2, 3.5, 6, 10, 20, 50, 9999], labels=['〜2.0', '2.1〜3.5', '3.6〜6', '6.1〜10', '10.1〜20', '20.1〜50', '50.1〜'])
for lab, X in (('2021〜2023年', T3[T3['年'] <= 2023]), ('2024〜2026年', T3[T3['年'] >= 2024])):
    X = X.copy()
    X['上下'] = X.groupby('帯', observed=True)['勝ちきり度'].transform(lambda s: np.where(s >= s.median(), '上', '下'))
    t = X.pivot_table(index='帯', columns='上下', values='勝', aggfunc=['mean', 'size'], observed=True)
    out = pd.DataFrame({'頭（上）': t[('size', '上')], '1着の割合（上）': (t[('mean', '上')] * 100).round(1),
                        '頭（下）': t[('size', '下')], '1着の割合（下）': (t[('mean', '下')] * 100).round(1)})
    out['差'] = (out['1着の割合（上）'] - out['1着の割合（下）']).round(1)
    print(lab); print(out.to_string())
