# NG3：当日の馬場と逃げ馬（検証計画 NG3）。逃げ馬（先頭率5≥0.4）の単勝の回収を、良／稍重／重・不良で分ける
import glob, numpy as np, pandas as pd
rng = np.random.default_rng(67)
ST = '/home/claude/chiho-keiba'
def s(v): return pd.to_numeric(v, errors='coerce').astype('Int64').astype(str)
def baba(x):
    x = str(x)
    if x.startswith('良'): return '良'
    if x.startswith('稍'): return '稍重'
    if x.startswith('重') or x.startswith('不'): return '重・不良'
    return ''
def jra():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/hdump_*.csv.gz'))])
    for c in ('R', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '単勝オッズ', '勝', '人気', '距離'): H[c] = pd.to_numeric(H[c], errors='coerce')
    Z = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/jra/exp/z2_pred_*.csv.gz'))])
    for c in ('R', '馬番'): Z[c] = s(Z[c])
    Z['f'] = pd.to_numeric(Z['f_z2'], errors='coerce')
    H = H.merge(Z[['年月日', '場', 'R', '馬番', 'f']].drop_duplicates(['年月日', '場', 'R', '馬番']), on=['年月日', '場', 'R', '馬番'], how='left')
    H['pay'] = np.where(H['勝'] == 1, H['単勝オッズ'] * 100, 0.0); H['日'] = H['年月日']; H['区分'] = '中央' + H['芝ダ'].astype(str)
    return H, 0.165, -0.2528
def nar():
    H = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_hdump_*.csv.gz'))])
    for c in ('レース番号', '馬番'): H[c] = s(H[c])
    for c in ('先頭率5', '人気', '距離'): H[c] = pd.to_numeric(H[c], errors='coerce')
    Z = pd.concat([pd.read_csv(f, dtype=str) for f in sorted(glob.glob(f'{ST}/data/exp/nk_z2_pred_*.csv.gz'))])
    for c in ('レース番号', '馬番'): Z[c] = s(Z[c])
    for c in ('f', '単', '勝'): Z[c] = pd.to_numeric(Z[c], errors='coerce')
    K = ['競馬場', '競走年月日', 'レース番号', '馬番']
    H = H.drop(columns=[c for c in ('勝',) if c in H]).merge(Z[K + ['f', '単', '勝']].drop_duplicates(K), on=K)
    H['pay'] = np.where(H['勝'] == 1, H['単'].fillna(0), 0.0); H['日'] = H['競走年月日']; H['区分'] = '地方'; H['場'] = H['競馬場']
    return H, 0.2964, -0.8271
def boot(S, ds, Wt):
    dix = np.searchsorted(ds, S['日'].values); return (Wt @ np.bincount(dix, S['pay'].values, len(ds))) / (Wt @ np.bincount(dix, None, len(ds)))
def line(S, ds, Wt, star=False):
    if len(S) < 50: return f'{len(S)}頭'
    bs = boot(S, ds, Wt); lo, hi = np.percentile(bs, [2.5, 97.5]); r1, r2 = (S.loc[S['期'] == p, 'pay'].mean() for p in (1, 2))
    ok = star and len(S) >= 300 and r1 >= 100 and r2 >= 100 and lo >= 90
    return f"{len(S)}（{int((S['期'] == 1).sum())}／{int((S['期'] == 2).sum())}） 1着 {S['勝'].mean() * 100:.1f}% 回収 {r1:.0f}／{r2:.0f}%（{S['pay'].mean():.0f}%・{lo:.0f}〜{hi:.0f}）" + (' ★' if ok else '')
for H, HI, LO in (jra(), nar()):
    H = H[H['先頭率5'].notna() & H['pay'].notna() & (H['日'] >= '20210101')].copy()
    H['期'] = np.where(H['日'] <= '20231231', 1, 2); H['馬場3'] = H['馬場'].map(baba); H['逃げ'] = H['先頭率5'] >= 0.4
    H['型'] = np.where(H['f'] >= HI, '来やすい', np.where(H['f'] <= LO, '来にくい', 'ふつう'))
    print('馬場の書き方', H['馬場'].value_counts().head(8).to_dict())
    for kb, X in H.groupby('区分'):
        if kb not in ('中央芝', '中央ダ', '中央ダート', '地方'): continue
        ds = np.sort(X['日'].unique()); Wt = rng.poisson(1.0, (1000, len(ds)))
        E = X[X['逃げ']]
        print(f'\n===== {kb}：全部 {len(X)}頭・逃げ馬 {len(E)}頭')
        for b in ('良', '稍重', '重・不良'):
            print(f'  {b}：逃げ馬 ' + line(E[E['馬場3'] == b], ds, Wt, star=(b == '重・不良')) + ' ｜ 全部の馬 ' + line(X[X['馬場3'] == b], ds, Wt))
        A = E[E['馬場3'] == '重・不良']; B = E[E['馬場3'] == '良']
        d = [A.loc[A['期'] == p, 'pay'].mean() - B.loc[B['期'] == p, 'pay'].mean() for p in (1, 2)]; bd = boot(A, ds, Wt) - boot(B, ds, Wt)
        print(f'  H1：重・不良−良（逃げ馬の単勝の回収）{d[0]:+.1f}／{d[1]:+.1f} ポイント（合わせて {bd.mean():+.1f}、95%幅 {np.percentile(bd, 2.5):+.1f}〜{np.percentile(bd, 97.5):+.1f}）')
        print('  数字だけ：')
        for b in ('良', '重・不良'):
            for t in ('来やすい', 'ふつう', '来にくい'): print(f'    {b}・{t}の逃げ馬：' + line(E[(E['馬場3'] == b) & (E['型'] == t)], ds, Wt))
            for nm, m in (('1400m以下', E['距離'] <= 1400), ('1401m以上', E['距離'] > 1400)): print(f'    {b}・{nm}の逃げ馬：' + line(E[(E['馬場3'] == b) & m], ds, Wt))
        if kb == '地方':
            for v, Y in E.groupby('場'):
                print(f'    場 {v}：良 ' + line(Y[Y['馬場3'] == '良'], ds, Wt) + ' ｜ 重・不良 ' + line(Y[Y['馬場3'] == '重・不良'], ds, Wt))
