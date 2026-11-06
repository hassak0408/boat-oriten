"""中央競馬：K6 注記に書かれない不利（見えない不利）は舐められているか（検証計画 K6）。
前走の着差・通過順・ペース・馬場・枠から不利を推し、その馬の実際の1着÷市場の見込みと単勝の回収を、選ぶ期間2016〜2021年・確かめる期間2022〜2026年で見る。
どれも前走の注記に不利が無い馬（前不利あり＝0）だけ。
使い方：python jhidden.py 材料.pkl [純粋な評価の見込み.pkl（jk.py TROUBLE=1 の出力）]"""
import sys, json, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy()
H['Ri'] = pd.to_numeric(H['R'], errors='coerce')
H['zq'] = H.groupby(KEY)['単勝オッズ'].transform(lambda s: (1 / s).sum())      # 市場の見込みはレースの全部の馬で割る

# 角ごとの位置（レースの通過順から）。角から次の角までに一番大きく下げた頭数
U = H.drop_duplicates(KEY); cl = {}
for k, js in zip(map(tuple, U[KEY].values), U['角']):
    try: d = json.loads(js) if isinstance(js, str) and js else {}
    except ValueError: d = {}
    cl[k] = [d[c] for c in sorted(d, key=int)]
drop = []
for k, b in zip(map(tuple, H[KEY].values), H['馬番']):
    ps = [lst.index(b) + 1 for lst in cl.get(k, []) if b in lst]
    drop.append(max(q - p for p, q in zip(ps, ps[1:])) if len(ps) >= 2 else np.nan)
H['最大下げ'] = drop

# ペース比の分け目（芝ダ・距離の帯ごと、2016〜2018年のレース）
H['距帯'] = pd.cut(H['距離'], [0, 1400, 1800, 9999], labels=['〜1400', '1401〜1800', '1801〜'])
R0 = H[H['年'] <= 2018].drop_duplicates(KEY)
qs = R0.groupby(['芝ダ', '距帯'], observed=True)['ペース比'].quantile([0.25, 0.75]).unstack()
lo = [qs.loc[(a, b), 0.25] if (a, b) in qs.index else np.nan for a, b in zip(H['芝ダ'], H['距帯'])]
hi = [qs.loc[(a, b), 0.75] if (a, b) in qs.index else np.nan for a, b in zip(H['芝ダ'], H['距帯'])]
H['速い'] = (H['ペース比'] <= np.array(lo, dtype=float)).astype(float).where(H['ペース比'].notna())
H['ゆっくり'] = (H['ペース比'] >= np.array(hi, dtype=float)).astype(float).where(H['ペース比'].notna())
print('ペース比の分け目', qs.round(3).to_dict('index'), flush=True)

# 前走の値（その馬の1つ前のレース）
H = H.sort_values(['馬', '日', 'Ri']).reset_index(drop=True)
g = H.groupby('馬', sort=False)
for c in ('差', '着x', 'n', '終角率', '上げ', '初角', '初角率', '速い', 'ゆっくり', '芝ダ', '馬場', '馬番', '最大下げ'):
    H['前の' + c] = g[c].shift(1)
chk = H[['前の差', '差1']].dropna(); print('前走の差が材料の差1と同じ割合', round(float((chk['前の差'] - chk['差1']).abs().lt(1e-9).mean()), 4), flush=True)

H = H[(H['合わない'] == 0) & (H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = H[H['前の着x'].notna() & (H['前不利あり'] == 0)].copy()
H['q'] = 1 / H['単勝オッズ'] / H['zq']
H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)
x6 = H['前の着x'] >= 6
seg = {
    'K6a 着順ほど負けていない（6着以下・0.5秒以内）': x6 & (H['前の差'] <= 0.5),
    'K6b 追い込んで届かず': (H['前の終角率'] > 0.5) & (H['前の上げ'] >= 5) & (H['前の着x'] >= 4),
    'K6c 前が速くて止まった': (H['前の初角'] <= 3) & (H['前の速い'] == 1) & x6,
    'K6d ゆっくりで届かず': (H['前の初角率'] > 0.6) & (H['前のゆっくり'] == 1) & (H['前の着x'] >= 4),
    'K6e 途中で位置を下げた': (H['前の最大下げ'] >= 4) & (H['前の上げ'] >= 2),
    'K6f 重い馬場で負けた': H['前の馬場'].isin(['重', '不良']) & x6,
    'K6g 大外で負けた': (H['前の芝ダ'] == '芝') & (H['前のn'] >= 14) & (H['前の馬番'] >= H['前のn'] - 1) & x6,
    '（くらべる）前走6着以下の全部': x6,
    '（くらべる）前走4着以下の全部': H['前の着x'] >= 4,
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
                     '実際÷市場': f'{r:.3f}（{rl:.2f}〜{rh:.2f}）', '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo_:.0f}〜{hi_:.0f}）",
                     '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
    if len(res) == 2:
        a, b = res['2016〜2021'], res['2022〜2026']
        keep[name] = ('傾向として残す' if min(a[0], b[0]) >= 1.05 and a[1] > 1 and b[1] > 1 else '残さない',
                      '買い方の候補' if a[3] >= 100 and b[3] >= 100 and b[4] >= 100 else '候補でない')
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(pd.DataFrame(rows).to_string(index=False))
print('\n■ 決めごとに照らすと')
for k, v in keep.items(): print(f' {k}：{v[0]}・{v[1]}')

if len(sys.argv) > 2:      # 一覧の評価（純粋な評価）も低く見ているか
    P = pd.read_pickle(sys.argv[2]); P = P.loc[:, ~P.columns.duplicated()]
    P = P[(P['n'] >= 5) & P.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    P['p1'] = P['p1'] / P.groupby(KEY)['p1'].transform('sum')
    print('\n■ 一覧の評価（純粋な評価、2021〜2026年）でも低く見ているか：実際÷評価（実際÷市場）')
    for name in seg:
        mk = seg[name].fillna(False).astype(bool)
        X = H[mk].merge(P[KEY + ['馬番', 'p1']], on=KEY + ['馬番'], how='inner')
        if len(X) < 50: continue
        print(f" {name}：{len(X)}頭 実際÷評価 {X['勝'].sum()/X['p1'].sum():.3f}（実際÷市場 {X['勝'].sum()/X['q'].sum():.3f}）")
