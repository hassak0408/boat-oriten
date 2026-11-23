# TB1：当日の傾向（前が残る日か）（検証計画 TB1）
import glob, json, numpy as np, pandas as pd
rng = np.random.default_rng(73)
ST = '/home/claude/chiho-keiba'
def s(v): return pd.to_numeric(v, errors='coerce').astype('Int64').astype(str)
def jra():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/hdump_*.csv.gz'))])
    for c in ('R', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '先行率5', '人気', 'n', '着', '3着内', '初角率', '単勝オッズ', '勝'): H[c] = pd.to_numeric(H[c], errors='coerce')
    PAY = {}
    for f in sorted(glob.glob(f'{ST}/jra/data/202[1-6]/*_races.csv.gz')):
        R = pd.read_csv(f, dtype=str, usecols=['年月日', '場', 'R', '払戻'])
        for d, p, r, x in zip(R['年月日'], R['場'], R['R'], R['払戻']):
            try: PAY[(d, p, str(int(float(r))))] = json.loads(x).get('複勝', [])
            except Exception: pass
    H['日'] = H['年月日']; H['会'] = H['年月日'] + H['場'] + H['芝ダ'].astype(str); H['区分'] = '中央' + H['芝ダ'].astype(str)
    H['Rn'] = pd.to_numeric(H['R'], errors='coerce')
    fk = {}
    for (d, p, r), X in H[H['着'].isin([1, 2, 3])].groupby(['年月日', '場', 'R']):
        T = X.sort_values('着'); f = PAY.get((d, p, r), [])
        if len(T) == 3 and T['着'].tolist() == [1, 2, 3] and len(f) == 3:
            for u, v in zip(T['馬番'], f): fk[(d, p, r, u)] = v
    H['複'] = [fk.get((d, p, r, u), 0 if c == c and c <= 3 else 0) for d, p, r, u, c in zip(H['年月日'], H['場'], H['R'], H['馬番'], H['着'])]
    H['複ok'] = H.groupby(['年月日', '場', 'R'])['複'].transform(lambda x: (x > 0).sum() >= 3)
    H['単払'] = np.where(H['勝'] == 1, H['単勝オッズ'] * 100, 0.0)
    return H
def nar():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_hdump_*.csv.gz'))])
    for c in ('レース番号', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '先行率5', '人気', 'n', '着', '3着内', '初角率'): H[c] = pd.to_numeric(H[c], errors='coerce')
    Z = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_z2_pred_*.csv.gz'))])
    for c in ('レース番号', '馬番'): Z[c] = s(Z[c])
    for c in ('単', '勝'): Z[c] = pd.to_numeric(Z[c], errors='coerce')
    K = ['競馬場', '競走年月日', 'レース番号', '馬番']
    H = H.drop(columns=[c for c in ('勝',) if c in H]).merge(Z[K + ['単', '勝']].drop_duplicates(K), on=K, how='left')
    P = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/race/202[1-6]*/01_*payback*.csv.gz'))]); P['レース番号'] = s(P['レース番号'])
    fk = {}
    for _, r in P.iterrows():
        for i in (1, 2, 3):
            try: fk[(r['競走年月日'], r['競馬場'], r['レース番号'], str(int(float(r[f'複勝組番{i}']))))] = float(r[f'複勝払戻金{i}（円）'])
            except Exception: pass
    H['複'] = [fk.get((d, p, r, u), 0) for d, p, r, u in zip(H['競走年月日'], H['競馬場'], H['レース番号'], H['馬番'])]
    H['複ok'] = H.groupby(['競走年月日', '競馬場', 'レース番号'])['複'].transform(lambda x: (x > 0).sum() >= 2)
    H['日'] = H['競走年月日']; H['会'] = H['競走年月日'] + H['競馬場']; H['区分'] = '地方'; H['Rn'] = pd.to_numeric(H['レース番号'], errors='coerce')
    H['単払'] = np.where(H['勝'] == 1, H['単'].fillna(0), 0.0)
    return H
def run(H):
    H = H[H['人気'].notna() & H['3着内'].notna() & (H['日'] >= '20210101')].copy()
    H['期'] = np.where(H['日'] <= '20231231', 1, 2)
    # レースごとの「1〜3着の最初の角の位置の平均」→ その日のそれより前のレースの平均（3レース以上）
    T = H[H['着'].isin([1, 2, 3]) & H['初角率'].notna()].groupby(['会', 'Rn'])['初角率'].mean().rename('r3').reset_index().sort_values(['会', 'Rn'])
    T['前の和'] = T.groupby('会')['r3'].transform(lambda x: x.shift(1).expanding().sum()); T['前の数'] = T.groupby('会').cumcount()
    T['前残り度'] = np.where(T['前の数'] >= 3, T['前の和'] / T['前の数'], np.nan)
    H = H.merge(T[['会', 'Rn', '前残り度']], on=['会', 'Rn'], how='left')
    H['前行き'] = (H['先頭率5'] >= 0.4) | (H['先行率5'] >= 0.6); H['後ろ'] = (H['先頭率5'] == 0) & (H['先行率5'] == 0)
    H['頭帯'] = pd.cut(H['n'], [0, 8, 12, 99], labels=['a', 'b', 'c']).astype(str); H['人'] = H['人気'].clip(upper=18).astype(int)
    H['見込'] = H.groupby(['期', '人', '頭帯'])['3着内'].transform('mean')
    for kb, X in H.groupby('区分'):
        if kb not in ('中央芝', '中央ダート', '地方'): continue
        X = X[X['前残り度'].notna()].copy()
        q1, q2 = X.loc[X['期'] == 1, '前残り度'].drop_duplicates().quantile([1 / 3, 2 / 3])
        X['帯'] = np.where(X['前残り度'] <= q1, '前が残る日', np.where(X['前残り度'] >= q2, '後ろが来る日', 'ふつう'))
        ds = np.sort(X['日'].unique()); Wt = rng.poisson(1.0, (1000, len(ds)))
        def bs(S, col): dix = np.searchsorted(ds, S['日'].values); return Wt @ np.bincount(dix, S[col].values.astype(float), len(ds))
        def rat(S):
            r = [S.loc[S['期'] == p, '3着内'].sum() / S.loc[S['期'] == p, '見込'].sum() for p in (1, 2)]; return r, bs(S, '3着内') / bs(S, '見込')
        def ret(S, col):
            if len(S) < 50: return ''
            S = S if col == '単払' else S[S['複ok']]
            r = [S.loc[S['期'] == p, col].mean() for p in (1, 2)]; b = bs(S, col) / bs(S.assign(_o=1), '_o')
            ok = len(S) >= 300 and min(r) >= 100 and np.percentile(b, 2.5) >= 90
            return f"{'単勝' if col == '単払' else '複勝'} {r[0]:.0f}／{r[1]:.0f}%（{np.percentile(b, 2.5):.0f}〜{np.percentile(b, 97.5):.0f}）" + (' ★' if ok else '')
        print(f'\n===== {kb}：しきい 前残り度 {q1:.3f}・{q2:.3f}（2021〜23 の3等分）')
        for who, m in (('前に行きやすい馬', X['前行き']), ('後ろの馬', X['後ろ'])):
            for b in ('前が残る日', 'ふつう', '後ろが来る日'):
                S = X[m & (X['帯'] == b)]; r, bb = rat(S)
                print(f'  {who}・{b}：{len(S)}頭 3着内 {S["3着内"].mean() * 100:.0f}% 実際÷見込み {r[0]:.3f}／{r[1]:.3f}（{np.percentile(bb, 2.5):.3f}〜{np.percentile(bb, 97.5):.3f}） {ret(S, "単払")} {ret(S, "複")}')
        A = X[X['前行き'] & (X['帯'] == '前が残る日')]; B = X[X['前行き'] & (X['帯'] == 'ふつう')]
        ra, ba = rat(A); rb, bb = rat(B); d = ba - bb
        print(f'  H1：前に行きやすい馬（前が残る日−ふつう）{ra[0] - rb[0]:+.3f}／{ra[1] - rb[1]:+.3f}（合わせて {d.mean():+.3f}、95%幅 {np.percentile(d, 2.5):+.3f}〜{np.percentile(d, 97.5):+.3f}）')
        for a_, b_ in ((1, 1), (2, 3), (4, 6), (7, 18)):
            S = A[A['人'].between(a_, b_)]
            if len(S) >= 50: r, _ = rat(S); print(f'   数字だけ：前が残る日の前に行きやすい馬 {a_}〜{b_}番人気：{len(S)}頭 実際÷見込み {r[0]:.3f}／{r[1]:.3f} {ret(S, "単払")} {ret(S, "複")}')
for f in (jra, nar): run(f())
