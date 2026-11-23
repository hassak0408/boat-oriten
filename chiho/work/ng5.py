# NG5：逃げ馬は3着内に残りやすいか・ワイドの軸に向くか（検証計画 NG5）
import glob, json, numpy as np, pandas as pd
rng = np.random.default_rng(71)
ST = '/home/claude/chiho-keiba'
def s(v): return pd.to_numeric(v, errors='coerce').astype('Int64').astype(str)
def jra():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/hdump_*.csv.gz'))])
    for c in ('R', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '人気', 'n', '着', '3着内'): H[c] = pd.to_numeric(H[c], errors='coerce')
    Z = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/z2_pred_*.csv.gz'))])
    for c in ('R', '馬番'): Z[c] = s(Z[c])
    Z['f'] = pd.to_numeric(Z['f_z2'], errors='coerce')
    H = H.merge(Z[['年月日', '場', 'R', '馬番', 'f']].drop_duplicates(['年月日', '場', 'R', '馬番']), on=['年月日', '場', 'R', '馬番'], how='left')
    # 払戻（着順の順）：複勝 [1着,2着,3着]、ワイド [1-2, 1-3, 2-3]
    PAY = {}
    for f in sorted(glob.glob(f'{ST}/jra/data/202[1-6]/*_races.csv.gz')):
        R = pd.read_csv(f, dtype=str, usecols=['年月日', '場', 'R', '払戻'])
        for d, p, r, x in zip(R['年月日'], R['場'], R['R'], R['払戻']):
            try: PAY[(d, p, str(int(float(r))))] = json.loads(x)
            except Exception: pass
    H['日'] = H['年月日']; H['_k'] = list(zip(H['年月日'], H['場'], H['R']))
    fuku, wide = {}, {}
    for k, X in H[H['着'].isin([1, 2, 3])].groupby('_k'):
        pay = PAY.get(k)
        if not pay: continue
        T = X.sort_values('着')
        if len(T) != 3 or T['着'].tolist() != [1, 2, 3] or len(pay.get('複勝', [])) != 3 or len(pay.get('ワイド', [])) != 3: continue
        u = [int(v) for v in T['馬番']]
        for uu, v in zip(u, pay['複勝']): fuku[(k, uu)] = v
        for (a, b), v in zip(((u[0], u[1]), (u[0], u[2]), (u[1], u[2])), pay['ワイド']): wide[(k, frozenset((a, b)))] = v
    ok = {k for (k, _) in fuku}
    H = H[H['_k'].isin(ok)].copy()
    H['複'] = [fuku.get((k, int(u)), 0) for k, u in zip(H['_k'], H['馬番'])]
    return H, wide, 0.165, -0.2528
def nar():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_hdump_*.csv.gz'))])
    for c in ('レース番号', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '人気', 'n', '着', '3着内'): H[c] = pd.to_numeric(H[c], errors='coerce')
    Z = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_z2_pred_*.csv.gz'))])
    for c in ('レース番号', '馬番'): Z[c] = s(Z[c])
    Z['f'] = pd.to_numeric(Z['f'], errors='coerce')
    K = ['競馬場', '競走年月日', 'レース番号', '馬番']
    H = H.merge(Z[K + ['f']].drop_duplicates(K), on=K, how='left')
    P = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/race/202[1-6]*/01_*payback*.csv.gz'))])
    P['レース番号'] = s(P['レース番号'])
    fuku, wide = {}, {}
    for _, r in P.iterrows():
        k = (r['競走年月日'], r['競馬場'], r['レース番号'])
        for i in (1, 2, 3):
            try: fuku[(k, int(float(r[f'複勝組番{i}'])))] = float(r[f'複勝払戻金{i}（円）'])
            except Exception: pass
            try: wide[(k, frozenset((int(float(r[f'ワイド組番{i}馬番1'])), int(float(r[f'ワイド組番{i}馬番2'])))))] = float(r[f'ワイド払戻金{i}（円）'])
            except Exception: pass
    H['日'] = H['競走年月日']; H['_k'] = list(zip(H['競走年月日'], H['競馬場'], H['レース番号']))
    ok = {k for (k, _) in fuku}
    H = H[H['_k'].isin(ok)].copy()
    H['複'] = [fuku.get((k, int(u)), 0) for k, u in zip(H['_k'], H['馬番'])]
    return H, wide, 0.2964, -0.8271
def run(name, H, wide, HI, LO):
    H = H[H['先頭率5'].notna() & H['人気'].notna() & H['3着内'].notna() & (H['日'] >= '20210101')].copy()
    H['期'] = np.where(H['日'] <= '20231231', 1, 2); H['逃げ'] = H['先頭率5'] >= 0.4
    H['頭帯'] = pd.cut(H['n'], [0, 8, 12, 99], labels=['〜8頭', '9〜12頭', '13頭〜']).astype(str); H['人'] = H['人気'].clip(upper=18).astype(int)
    H['型'] = np.where(H['f'] >= HI, '来やすい', np.where(H['f'] <= LO, '来にくい', 'ふつう'))
    nige_n = H.groupby('_k')['逃げ'].transform('sum'); H['単騎'] = np.where(H['逃げ'] & (nige_n == 1), '単騎', np.where(H['逃げ'], '競り合い', ''))
    # 見込み：同じ期間・人気×頭数の帯の全部の馬の3着内の率
    H['見込'] = H.groupby(['期', '人', '頭帯'])['3着内'].transform('mean')
    ds = np.sort(H['日'].unique()); Wt = rng.poisson(1.0, (1000, len(ds)))
    def bsum(S, col): dix = np.searchsorted(ds, S['日'].values); return Wt @ np.bincount(dix, S[col].values.astype(float), len(ds))
    def ratio(S):
        r = [S.loc[S['期'] == p, '3着内'].sum() / S.loc[S['期'] == p, '見込'].sum() for p in (1, 2)]; b = bsum(S, '3着内') / bsum(S, '見込')
        return f"{len(S)}頭 3着内 {S['3着内'].mean() * 100:.0f}%（見込み {S['見込'].mean() * 100:.0f}%） 実際÷見込み {r[0]:.3f}／{r[1]:.3f}（{np.percentile(b, 2.5):.3f}〜{np.percentile(b, 97.5):.3f}）"
    print(f'\n===== {name}：{len(H)}頭・逃げ馬 {int(H["逃げ"].sum())}頭')
    E = H[H['逃げ']]
    print(' Q1 3着内（同じ人気×頭数の帯とくらべる）')
    print('  逃げ馬：' + ratio(E)); print('  逃げ馬でない：' + ratio(H[~H['逃げ']]))
    for t in ('単騎', '競り合い'): print(f'   {t}：' + ratio(E[E['単騎'] == t]))
    for t in ('来やすい', 'ふつう', '来にくい'): print(f'   {t}型：' + ratio(E[E['型'] == t]))
    for a, b in ((1, 1), (2, 3), (4, 6), (7, 18)): print(f'   {a}〜{b}番人気：' + ratio(E[E['人'].between(a, b)]))
    # Q2 複勝：同じ人気どうしの差（逃げ馬の頭数で重み）
    print(' Q2 複勝の回収')
    def wdiff(col, A, B, keys):
        out = []
        for per in (1, 2, None):
            X = A if per is None else A[A['期'] == per]; Y = B if per is None else B[B['期'] == per]
            if per is None:
                tot = 0; w = 0
                for kk, XA in X.groupby(keys):
                    YB = Y.set_index(keys).loc[[kk]] if False else Y[(Y[keys] == pd.Series(kk, index=keys)).all(axis=1)] if isinstance(kk, tuple) else Y[Y[keys[0]] == kk]
                    if len(YB) < 30 or len(XA) < 30: continue
                    tot = tot + len(XA) * (bsum(XA, col) / bsum(XA.assign(_o=1), '_o') - bsum(YB, col) / bsum(YB.assign(_o=1), '_o')); w += len(XA)
                v = tot / w; out.append((np.nanmean(v), np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5)))
            else:
                g1 = X.groupby(keys)[col].agg(['mean', 'size']); g0 = Y.groupby(keys)[col].mean()
                j = g1.join(g0.rename('m0'), how='inner'); out.append(float(((j['mean'] - j['m0']) * j['size']).sum() / j['size'].sum()))
        return out
    for lab, A in (('逃げ馬', E), ('単騎', E[E['単騎'] == '単騎']), ('来やすい型の逃げ馬', E[E['型'] == '来やすい'])):
        r1, r2 = (A.loc[A['期'] == p, '複'].mean() for p in (1, 2))
        print(f'  {lab}：{len(A)}頭 複勝の回収 {r1:.0f}／{r2:.0f}%')
    d1, d2, (dm, dlo, dhi) = wdiff('複', E, H[~H['逃げ']], ['人'])
    print(f'  逃げ馬−逃げ馬でない（同じ人気どうし）：{d1:+.1f}／{d2:+.1f} ポイント（合わせて {dm:+.1f}、95%幅 {dlo:+.1f}〜{dhi:+.1f}）')
    # Q3 ワイドの軸：1〜5番人気の軸から、人気の上位3頭（軸を除く）へ3点
    rows = []
    for k, X in H.groupby('_k'):
        X = X.sort_values('人気'); top = [int(u) for u in X['馬番']][:4]
        for _, r in X[X['人気'] <= 5].iterrows():
            a = int(r['馬番']); pa = [b for b in top if b != a][:3]
            pay = sum(wide.get((k, frozenset((a, b))), 0) for b in pa)
            rows.append(dict(日=r['日'], 期=r['期'], 人=int(r['人気']), 逃げ=bool(r['逃げ']), 単騎=r['単騎'], 型=r['型'], 払=pay / 3.0, 当=int(pay > 0)))
    W = pd.DataFrame(rows)
    print(' Q3 ワイドの軸（1〜5番人気の軸から、人気の上位3頭へ3点）')
    for lab, A in (('逃げ馬の軸', W[W['逃げ']]), ('逃げ馬でない軸', W[~W['逃げ']]), ('単騎の逃げ馬の軸', W[W['単騎'] == '単騎']), ('来やすい型の逃げ馬の軸', W[W['逃げ'] & (W['型'] == '来やすい')]), ('来にくい型の逃げ馬の軸', W[W['逃げ'] & (W['型'] == '来にくい')])):
        if len(A) < 50: print(f'  {lab}：{len(A)}'); continue
        r1, r2 = (A.loc[A['期'] == p, '払'].mean() for p in (1, 2)); h1, h2 = (A.loc[A['期'] == p, '当'].mean() * 100 for p in (1, 2))
        dix = np.searchsorted(ds, A['日'].values); b = (Wt @ np.bincount(dix, A['払'].values, len(ds))) / (Wt @ np.bincount(dix, None, len(ds)))
        print(f'  {lab}：{len(A)} 当たり {h1:.0f}／{h2:.0f}% 回収 {r1:.0f}／{r2:.0f}%（{A["払"].mean():.0f}%・{np.percentile(b, 2.5):.0f}〜{np.percentile(b, 97.5):.0f}）')
    for p in range(1, 6):
        A = W[(W['人'] == p) & W['逃げ']]; B = W[(W['人'] == p) & ~W['逃げ']]
        print(f'   {p}番人気の軸：逃げ馬 {len(A)} 当たり {A["当"].mean() * 100:.0f}% 回収 {A["払"].mean():.0f}% ｜ 逃げ馬でない {len(B)} 当たり {B["当"].mean() * 100:.0f}% 回収 {B["払"].mean():.0f}%')
    d1, d2, (dm, dlo, dhi) = wdiff('払', W[W['逃げ']], W[~W['逃げ']], ['人'])
    e1, e2, (em, elo, ehi) = wdiff('当', W[W['逃げ']], W[~W['逃げ']], ['人'])
    print(f'  回収の差（逃げ馬の軸−逃げ馬でない軸、同じ人気どうし）：{d1:+.1f}／{d2:+.1f} ポイント（合わせて {dm:+.1f}、95%幅 {dlo:+.1f}〜{dhi:+.1f}）')
    print(f'  当たりの差：{e1 * 100:+.1f}／{e2 * 100:+.1f} ポイント（合わせて {em * 100:+.1f}、95%幅 {elo * 100:+.1f}〜{ehi * 100:+.1f}）')
for nm, f in (('中央', jra), ('地方', nar)):
    H, wide, HI, LO = f(); run(nm, H, wide, HI, LO)
