"""中央競馬：連対の見込みを、なめらかな直し（α・β の2つ）で確かめる（検証計画「R1中央b」）。
連対の見込みは R1a（馬連の組の見込み（B式、直す前）を、その馬が入る組について足す）。直し：log(p'/(1−p')) = α + β×log(p/(1−p))。
① 2021〜2023年で決めて2024〜2026年に当てる、と逆向き（jra_m7_final.pkl）。
② まだ見ていない2019年・2020年（STORE/jra/exp/m7_pred_2019・2020、今の jra_fix.json の値を当てる）に、2021〜2026年の全部で決めた α・β を当てる。
どちらも、500頭以上ある帯（10%ごと）がどれもずれ3ポイント以内、かつ連対の当て分けが直す前より下がれば満たす。両方満たせば jra_rentai_calib.json を書く。
使い方：python jk_r1b.py jra_m7_final.pkl STORE"""
import os, sys, glob, json, numpy as np, pandas as pd
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = ['年月日', '場', 'R']
num = lambda s: pd.to_numeric(s, errors='coerce')
lg = lambda p: np.log(p / (1 - p))


def r1a(D):
    """R1a の連対の見込み（足して2）。D は KEY・n・p1・p3・着 を持つ（1つのレースが続けて並んでいなくてよい）"""
    gk = [D[k] for k in KEY]; gs = lambda v: pd.Series(v, index=D.index).groupby(gk).transform('sum').values
    p1 = D['p1'].values / gs(D['p1'].values)
    q = np.clip(D['p3'].values * np.minimum(3, D['n'].values) / gs(D['p3'].values), None, 0.97); q = q / gs(q)
    t = p1 / (1 - q); u = p1 + q * (gs(t) - t)
    return np.clip(2 * u / gs(u), 1e-4, 0.999)


def prep(D):
    D = D[D['n'] >= 5].copy(); D['連対'] = (D['着'] <= 2).astype(int)
    D = D[D.groupby(KEY)['連対'].transform('sum') >= 2].reset_index(drop=True)
    D['R1a'] = r1a(D); return D


def ll(y, p): return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
def cal(p, ab): return np.clip(1 / (1 + np.exp(-(ab[0] + ab[1] * lg(p)))), 1e-4, 0.999)


def fit(X):
    y = X['連対'].values; p = X['R1a'].values
    r = minimize(lambda ab: ll(y, cal(p, ab)), [0.0, 1.0], method='Nelder-Mead', options={'xatol': 1e-6, 'fatol': 1e-9, 'maxiter': 4000})
    return r.x


def check(X, ab, lab):
    y = X['連対'].values; p0 = X['R1a'].values; p = cal(p0, ab)
    l0, l1 = ll(y, p0), ll(y, p)
    b = np.minimum((p * 10).astype(int), 9)
    T = pd.DataFrame({'帯': b, '見込み': p, '実際': y}).groupby('帯').agg(頭数=('実際', 'size'), 見込み=('見込み', 'mean'), 実際=('実際', 'mean'))
    T['ずれ'] = (T['実際'] - T['見込み']) * 100
    bad = T[(T['頭数'] >= 500) & (T['ずれ'].abs() > 3)]
    good = len(bad) == 0 and l1 < l0
    print(f'\n{lab}（α={ab[0]:.4f}・β={ab[1]:.4f}）：連対の当て分け {l0:.5f} → {l1:.5f}、レース {X.groupby(KEY).ngroups}・頭数 {len(X)}')
    print('| 帯 | 頭数 | 見込み | 実際 | ずれ |'); print('|---|---|---|---|---|')
    for k, x in T.iterrows():
        print(f"| {k * 10}〜{k * 10 + 10}% | {int(x['頭数'])} | {x['見込み'] * 100:.1f}% | {x['実際'] * 100:.1f}% | {x['ずれ']:+.1f}{'' if x['頭数'] >= 500 else '（500頭未満）'} |")
    print('→', '満たす' if good else '届かない' + ('（' + '、'.join(f'{k * 10}〜{k * 10 + 10}% {v:+.1f}' for k, v in bad['ずれ'].items()) + '）' if len(bad) else '（当て分けが下がらない）'))
    return good


D = prep(pd.read_pickle(sys.argv[1]))
A, B = D[D['年'] <= 2023], D[D['年'] >= 2024]
print('① 両方の向き')
ok1 = all([check(B, fit(A), '2021〜23で決めて2024〜26に当てる'), check(A, fit(B), '2024〜26で決めて2021〜23に当てる')])
ABALL = fit(D); print('\n2021〜2026年の全部で決めた α・β', np.round(ABALL, 4))

ok2 = None
if len(sys.argv) > 2:
    ST = sys.argv[2]; FX = json.load(open(f'{HERE}/jra_fix.json', encoding='utf-8'))
    a, b = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し']['中央で初めて走る馬（新馬以外）に掛ける値']
    c, f = FX['3着内の付け直し']['c'], FX['着差のモデル']['f']; W1, W3 = FX['枠の付け直し']['1着'], FX['枠の付け直し']['3着内']
    VAR = 'rel' if FX.get('レースの中での差') else 'base'
    fs = [f'{ST}/jra/exp/m7_pred_{y}.csv.gz' for y in (2019, 2020)]
    if all(os.path.exists(x) for x in fs):
        P = pd.concat([pd.read_csv(x, dtype={k: str for k in KEY}) for x in fs], ignore_index=True)
        P = P[(P['n'] >= 5) & P.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
        H = pd.concat([pd.read_csv(x, dtype=str, keep_default_na=False, usecols=KEY + ['馬番', '枠', '着順']) for y in ('2019', '2020') for x in glob.glob(f'{ST}/jra/data/{y}/*_horses.csv.gz')], ignore_index=True).drop_duplicates(KEY + ['馬番'])
        RC = pd.concat([pd.read_csv(x, dtype=str, keep_default_na=False, usecols=KEY + ['芝ダ', 'コース', '日目']) for y in ('2019', '2020') for x in glob.glob(f'{ST}/jra/data/{y}/*_races.csv.gz')], ignore_index=True).drop_duplicates(KEY)
        for X in (P, H, RC): X['R'] = num(X['R']).astype('Int64').astype(str)
        H['馬番'] = num(H['馬番']); P['馬番'] = num(P['馬番'])
        P = P.merge(H, on=KEY + ['馬番'], how='left').merge(RC, on=KEY, how='left')
        P['着'] = num(P['着順']); P['枠'] = num(P['枠'])
        P = P.sort_values(KEY + ['馬番']).reset_index(drop=True); G = P.groupby(KEY, sort=False).ngroup().values
        gs = lambda v: pd.Series(v).groupby(G).transform('sum').values
        n3 = lambda v: np.clip(v * np.minimum(3, P['n'].values) / gs(v), 1e-4, 0.97)
        hh = n3(P['h'].values); m = P['mg'].values - pd.Series(P['mg'].values).groupby(G).transform('mean').values
        first = ((P['走数'] == 0) & (P['新馬'] == 0)).values
        pl = P[f'p1_{VAR}'].values; s = a * np.log(np.clip(pl / gs(pl), 1e-6, 1)) + b * np.log(hh)
        x = np.exp(s - pd.Series(s).groupby(G).transform('max').values) * np.where(first, F1, 1.0); P['p1'] = x / gs(x)
        P['p3'] = n3(n3(np.where(first, hh, n3(P[f'p3_{VAR}'].values))) ** c * np.exp(-f * m))
        wg = pd.cut(P['枠'], [0, 2, 6, 8], labels=['内（1〜2枠）', '中（3〜6枠）', '外（7〜8枠）']).astype(str)
        kai = np.where(P['コース'].str.contains('外'), '外回り', np.where(P['コース'].str.contains('直線'), '直線', '内回り・ふつう'))
        P['区分'] = np.where(P['芝ダ'] == 'ダート', 'ダ・' + wg, '芝・' + np.where(num(P['日目']) <= 2, '1〜2日目', '3日目以降') + '・' + kai + '・' + wg)
        okw = P['枠'].notna() & P['芝ダ'].isin(['芝', 'ダート'])
        v = P['p1'].values * P['区分'].map(W1).fillna(1.0).where(okw, 1.0).values; P['p1'] = v / gs(v)
        v = P['p3'].values * P['区分'].map(W3).fillna(1.0).where(okw, 1.0).values; P['p3'] = n3(v)
        print('\n② まだ見ていない年（今の jra_fix.json の値を当てた見込み）')
        print('1着の当て分け', {y: round(float(-np.log(np.clip(P.loc[(P['年'] == y) & (P['勝'] == 1), 'p1'], 1e-6, 1)).mean()), 5) for y in (2019, 2020)},
              '・血統のある行', round(float(P['父数'].notna().mean()), 3) if '父数' in P else '（列なし）')
        Q = prep(P)
        ok2 = all([check(Q[Q['年'] == y], ABALL, f'{y}年（2021〜2026年で決めた α・β を当てる）') for y in (2019, 2020)])
    else:
        print('\n② の見込み（m7_pred_2019・2020）がまだ無い')
print('\n決めごと：①', '満たす' if ok1 else '届かない', '・②', {None: 'まだ', True: '満たす', False: '届かない'}[ok2])
if ok1 and ok2:
    grid = np.round(np.arange(0, 1.001, 0.01), 2)
    out = f'{HERE}/jra_rentai_calib.json'
    json.dump({'出し方': 'R1a', '見込み': grid.tolist(), '直した見込み': np.round(cal(np.clip(grid, 1e-4, 0.999), ABALL), 4).tolist(), 'α': round(float(ABALL[0]), 4), 'β': round(float(ABALL[1]), 4),
               '作り方': '検証計画 R1中央b。M7 の1着・3着内の見込みから、馬連の組の見込み（B式、直す前）をその馬の入る組について足して連対（2着内）の見込みにし、log(p/(1−p)) を α＋β×log(p/(1−p)) で直す（2021〜2026年の全部で決めた。jk_r1b.py）'},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('書いた', out)
