# NG6：逃げ型の馬 × 先頭に行かせない騎手への乗り替わり（検証計画 NG6）
import glob, json, sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/boat-oriten/chiho/jra'); import jfeat
rng = np.random.default_rng(81)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
C_ = FX['3着内の付け直し']['c']; FM = FX['着差のモデル']['f']
def rd(pat, **kw): return pd.concat([pd.read_csv(f, **kw) for f in sorted(glob.glob(pat))], ignore_index=True)
def fixk(X):
    X['R'] = pd.to_numeric(X['R'], errors='coerce').astype('Int64').astype(str); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['年月日'] = X['年月日'].astype(str); return X

# 本番の形の見込み（JK2 の追記と同じ作り方）
D = fixk(rd(f'{ST}/jra/exp/m8_pred_*.csv.gz', dtype={k: str for k in K}))
M7 = fixk(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz', dtype={k: str for k in K})[K + ['馬番', 'h', 'mg']])
D = D.merge(M7, on=K + ['馬番'], how='inner')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['h'].notna()]
D = D[D.groupby(K)['勝'].transform('sum') == 1].sort_values(K + ['馬番']).reset_index(drop=True)
D['n'] = D.groupby(K)['馬番'].transform('count'); G = [D[k] for k in K]
def n3(v): v = pd.Series(v, index=D.index); return np.clip(v * np.minimum(3, D['n']) / v.groupby(G).transform('sum'), 1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
hh = n3(D['h'].values); m = (D['mg'] - D.groupby(K)['mg'].transform('mean')).values
m3 = n3(np.where(first, hh, n3(D['p3_EV'].values))); D['p3'] = n3(m3 ** C_ * np.exp(-FM * m))
D['pm'] = (1 / D['単勝オッズ']).where(D['単勝オッズ'] > 0); D['pm'] = D['pm'] / D.groupby(K)['pm'].transform('sum')
P = D[K + ['馬番', 'p3', 'pm', '勝', '3着内']]

# 先頭・逃げ型・騎手・乗り替わり（全部の中央のレースで、馬ごとに前のレースを見る）
Hd = fixk(rd(f'{ST}/jra/exp/hdump_20*.csv.gz', dtype={k: str for k in K}, usecols=K + ['馬番', '馬', '芝ダ', '先頭', '先頭率5', '前走数']))
J = fixk(rd(f'{ST}/jra/data/202[1-6]/*_horses.csv.gz', dtype=str, usecols=K + ['馬番', '騎手']))
J['騎手'] = J['騎手'].map(jfeat.clean_person)
Hd = Hd.merge(J.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left').sort_values(['馬', '年月日', '場', 'R'])
Hd['前騎手'] = Hd.groupby('馬')['騎手'].shift(1)
Hd['替'] = Hd['前騎手'].notna() & Hd['騎手'].notna() & (Hd['騎手'] != Hd['前騎手'])
Hd = Hd[Hd['芝ダ'].isin(['芝', 'ダート'])]   # 過去の表の書き方は「芝」「ダート」（最初は「ダ」と取り違えて芝だけになっていた）
E = Hd[(Hd['先頭率5'] >= 0.4) & Hd['騎手'].notna() & (Hd['騎手'] != '')].copy()
E['期'] = np.where(E['年月日'] <= '20231231', 1, 2)
E = E.merge(P, on=K + ['馬番'], how='inner')   # 平地で本番の形の見込みがあるレースだけ（癖を作る所も確かめる所も）
print('芝ダ', E['芝ダ'].value_counts().to_dict())
print('逃げ型の騎乗', len(E), '／最初のコーナーが分かる', int(E['先頭'].notna().sum()), '／AIの見込みあり', int(E['p3'].notna().sum()), '／乗り替わり', int(E['替'].sum()))

def tend(S):
    S = S[S['先頭'].notna()]; g = S.groupby('騎手'); A = g['先頭'].sum(); Ex = g['先頭率5'].sum(); rho = A.sum() / Ex.sum()
    t = (A + 10 * rho) / (Ex + 10); ok = Ex >= 10; tt = t[ok]
    lo, hi = tt.quantile(1 / 3), tt.quantile(2 / 3)
    cls = pd.Series(np.where(tt <= lo, 'L', np.where(tt >= hi, 'H', 'M')), index=tt.index)
    return cls, t, rho, lo, hi
def boot_ratio(T, a, b, num, den):
    days = T['年月日'].values; ds = np.sort(np.unique(days)); ix = np.searchsorted(ds, days); W = rng.poisson(1.0, (1000, len(ds)))
    def s(mask, col): return W @ np.bincount(ix[mask], T[col].values[mask], len(ds))
    q = (s(a, num) / s(a, den)) / (s(b, num) / s(b, den)); return np.percentile(q, [2.5, 97.5])
res = []
for fit, test in ((1, 2), (2, 1)):
    cls, t, rho, lo, hi = tend(E[E['期'] == fit])
    T = E[(E['期'] == test)].copy(); T['組'] = T['騎手'].map(cls)
    print(f'\n{fit}で分けて{test}で確かめる：分けた騎手 {len(cls)}人（行かせない {int((cls == "L").sum())}・ふつう {int((cls == "M").sum())}・行かせる {int((cls == "H").sum())}）、ρ {rho:.3f}、境目 {lo:.3f}・{hi:.3f}')
    for nm in ('C.デムーロ', '津村明秀', 'C.ルメール', '川田将雅', '武豊', '横山典弘'):
        if nm in t.index: print(f'   {nm}：行かせる度 {t[nm]:.3f}（{cls.get(nm, "分けない")}）')
    U = T[T['替'] & T['組'].notna() & T['p3'].notna()].copy(); U['y'] = U['3着内']; L_ = (U['組'] == 'L').values; O_ = ~L_
    RL = U.loc[L_, 'y'].sum() / U.loc[L_, 'p3'].sum(); RO = U.loc[O_, 'y'].sum() / U.loc[O_, 'p3'].sum(); ci = boot_ratio(U, L_, O_, 'y', 'p3')
    print(f'  ★乗り替わり：行かせない騎手 {L_.sum()}回（3着内 {int(U.loc[L_, "y"].sum())}・見込み {U.loc[L_, "p3"].sum():.1f}）実際÷AI {RL:.3f}／それ以外 {O_.sum()}回 {RO:.3f} → Q {RL / RO:.3f}（95%幅 {ci[0]:.3f}〜{ci[1]:.3f}）')
    res.append((RL / RO, ci))
    V = U[U['pm'].notna()]; Lv = (V['組'] == 'L').values
    w1 = (V.loc[Lv, '勝'].sum() / V.loc[Lv, 'pm'].sum()) / (V.loc[~Lv, '勝'].sum() / V.loc[~Lv, 'pm'].sum()); c1 = boot_ratio(V, Lv, ~Lv, '勝', 'pm')
    print(f'  数字だけ：1着の実際÷市場 の比 {w1:.3f}（{c1[0]:.3f}〜{c1[1]:.3f}）')
    Hh = (U['組'] == 'H').values; ch = boot_ratio(U, Hh, ~Hh, 'y', 'p3')
    print(f'  数字だけ：行かせる騎手 {Hh.sum()}回 の比 {(U.loc[Hh, "y"].sum() / U.loc[Hh, "p3"].sum()) / (U.loc[~Hh, "y"].sum() / U.loc[~Hh, "p3"].sum()):.3f}（{ch[0]:.3f}〜{ch[1]:.3f}）')
    N = T[~T['替'] & T['組'].notna() & T['p3'].notna()].copy(); N['y'] = N['3着内']; Ln = (N['組'] == 'L').values; cn = boot_ratio(N, Ln, ~Ln, 'y', 'p3')
    print(f'  数字だけ：乗り替わりでない {len(N)}回（行かせない騎手 {Ln.sum()}回）の比 {(N.loc[Ln, "y"].sum() / N.loc[Ln, "p3"].sum()) / (N.loc[~Ln, "y"].sum() / N.loc[~Ln, "p3"].sum()):.3f}（{cn[0]:.3f}〜{cn[1]:.3f}）')
    Z = U[U['先頭'].notna()]; Lz = (Z['組'] == 'L').values
    print(f'  数字だけ：確かめる期間で先頭に立った割合÷先頭率5：行かせない {Z.loc[Lz, "先頭"].sum() / Z.loc[Lz, "先頭率5"].sum():.3f}・それ以外 {Z.loc[~Lz, "先頭"].sum() / Z.loc[~Lz, "先頭率5"].sum():.3f}')
ok = all(q < 1 and ci[1] < 1 for q, ci in res)
print('\n判断：', '効く' if ok else '効かない')
