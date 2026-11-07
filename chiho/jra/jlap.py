"""中央競馬：ラップタイム（検証計画「中央：ラップタイム」L1・L2）。
成績表の先頭の200mごとのラップ（races の「ラップ」）から、レースごとに 前後半の差・中盤のゆるみ・最後の失速 を作り、
芝ダ・距離ごとの2016〜2018年の平均を引く（100レース未満の距離は芝ダ・距離の帯）。分け目（上下4分の1）も同じ分け方で2016〜2018年で決める。
使い方：python jlap.py 材料.pkl STORE/jra/data [純粋な評価の見込み.pkl]（L1・L2を数える）。lap_table(root) はほかのスクリプトから使う。"""
import os, sys, glob, json, numpy as np, pandas as pd

KEY = ['年月日', '場', 'R']
LAPC = ['前後半差', '中盤ゆるみ', '失速']


def one(laps, d):
    """1レースのラップから（前半3F、後半3F、前後半差、中盤ゆるみ、失速）。数が距離と合わなければ空"""
    if not laps or not d or len(laps) != -(-d // 200) or len(laps) < 4: return None
    rem = d % 200; L0 = rem if rem else 200      # 最初のラップの長さ（1150mは150m、100m余る距離は100m）
    f3 = sum(laps[:3]) + (200 - L0) / 200 * laps[3]      # 最初の600m
    l3 = sum(laps[-3:]); tot = sum(laps)
    mid = (tot - f3 - l3) / ((d - 1200) / 200) - tot / (d / 200) if d > 1200 else np.nan
    return f3, l3, f3 - l3, mid, laps[-1] - laps[-2]


def lap_table(root):
    rows = []
    for f in sorted(glob.glob(f'{root}/*/*_races.csv.gz')):
        r = pd.read_csv(f, dtype=str, keep_default_na=False)
        if 'ラップ' not in r: continue
        for a, b, c, sd, dist, lp in r[KEY + ['芝ダ', '距離', 'ラップ']].itertuples(index=False, name=None):
            if sd not in ('芝', 'ダート') or not lp: continue
            try: laps = json.loads(lp); d = int(dist)
            except ValueError: continue
            v = one(laps, d)
            if v: rows.append((a, b, c, sd, d) + v)
    T = pd.DataFrame(rows, columns=KEY + ['芝ダ', '距離', '前半3F', '後半3F'] + LAPC)
    T['年'] = T['年月日'].str[:4].astype(int)
    T['距帯3'] = pd.cut(T['距離'], [0, 1400, 1800, 9999], labels=['〜1400', '1401〜1800', '1801〜']).astype(str)
    base = T[T['年'] <= 2018]
    nd = base.groupby(['芝ダ', '距離']).size()
    T['群'] = [f'{a}{d}' if nd.get((a, d), 0) >= 100 else f'{a}{b}' for a, d, b in zip(T['芝ダ'], T['距離'], T['距帯3'])]
    base = T[T['年'] <= 2018]
    for c in LAPC:
        mu = base.groupby('群')[c].mean(); T[c] = T[c] - T['群'].map(mu)
    B = T[T['年'] <= 2018]
    for c in LAPC:
        q = B.groupby('群')[c].quantile([0.25, 0.75]).unstack()
        T[c + '下'] = (T[c] <= T['群'].map(q[0.25])).astype(float).where(T[c].notna() & T['群'].isin(q.index))
        T[c + '上'] = (T[c] >= T['群'].map(q[0.75])).astype(float).where(T[c].notna() & T['群'].isin(q.index))
    T['R'] = T['R'].astype(str)
    return T


def boot(v, day, B=2000, ratio=None):
    x = pd.DataFrame({'d': day, 's': v} | ({'q': ratio} if ratio is not None else {})).groupby('d').sum()
    rng = np.random.default_rng(0); k = rng.integers(0, len(x), (B, len(x)))
    if ratio is not None: s = x['s'].values[k].sum(1) / x['q'].values[k].sum(1)
    else:
        n = pd.DataFrame({'d': day}).groupby('d').size().reindex(x.index).values
        s = x['s'].values[k].sum(1) / n[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


if __name__ == '__main__':
    T = lap_table(sys.argv[2])
    print('ラップのあるレース', len(T), '年ごと', T.groupby('年').size().to_dict(), flush=True)
    H = pd.read_pickle(sys.argv[1]); H = H[~H['予測']].copy(); H['R'] = H['R'].astype(str)
    H['Ri'] = pd.to_numeric(H['R'], errors='coerce')
    H['zq'] = H.groupby(KEY)['単勝オッズ'].transform(lambda s: (1 / s).sum())
    H = H.merge(T[KEY + LAPC + [c + s for c in LAPC for s in ('下', '上')]], on=KEY, how='left')
    H = H.sort_values(['馬', '日', 'Ri']).reset_index(drop=True); g = H.groupby('馬', sort=False)
    for c in ['初角'] + [c + s for c in LAPC for s in ('下', '上')]: H['前の' + c] = g[c].shift(1)
    H = H[(H['合わない'] == 0) & (H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
    H = H[H['着x1'].notna() & (H['前不利あり'] == 0)].copy()
    H['q'] = 1 / H['単勝オッズ'] / H['zq']; H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)
    x6, x4 = H['着x1'] >= 6, H['着x1'] >= 4
    seg = {
        'L1a 前に厳しい流れで先行して負けた': (H['前の前後半差下'] == 1) & (H['前の初角'] <= 3) & x6,
        'L1b 後ろに厳しい流れで後ろから届かず': (H['前の前後半差上'] == 1) & (H['初角率1'] > 0.6) & x4,
        'L2a 消耗戦で先行して負けた': (H['前の失速上'] == 1) & (H['前の初角'] <= 3) & x6,
        'L2b 瞬発戦で後ろから届かず': (H['前の失速下'] == 1) & (H['初角率1'] > 0.6) & x4,
        '（くらべる）前走6着以下の全部': x6,
        '（くらべる）前走4着以下の全部': x4,
    }
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
    if len(sys.argv) > 3:
        P = pd.read_pickle(sys.argv[3]); P = P.loc[:, ~P.columns.duplicated()]; P['R'] = P['R'].astype(str)
        P = P[(P['n'] >= 5) & P.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
        P['p1'] = P['p1'] / P.groupby(KEY)['p1'].transform('sum')
        print('\n■ 一覧の評価（3つの平均、2021〜2026年）でも低く見ているか：実際÷評価（実際÷市場）')
        for name in seg:
            X = H[seg[name].fillna(False).astype(bool)].merge(P[KEY + ['馬番', 'p1']], on=KEY + ['馬番'], how='inner')
            if len(X) >= 50: print(f" {name}：{len(X)}頭 実際÷評価 {X['勝'].sum()/X['p1'].sum():.3f}（実際÷市場 {X['勝'].sum()/X['q'].sum():.3f}）")
