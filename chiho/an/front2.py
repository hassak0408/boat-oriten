"""行った行った：前に行く2頭の組（検証計画「K：行った行った」）
K1 前の2頭の馬複（主）／K2 前の2頭の馬単（先頭の見込みが高い方を1着）／K3 前の3頭の3連複
くらべる相手：1番人気と2番人気の馬複。分けて見る：前の2頭に1番人気がいるか。
仕組みの確かめ：2026年3〜9月の確定オッズで、ハービル式（連動なし）・馬複の値段・実際をくらべる。"""
import numpy as np, pandas as pd
from load import _read, odds as load_odds
KEY = ['競馬場', '競走年月日', 'レース番号']


def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan


T = pd.read_pickle('/tmp/chiho_style.pkl')
T = T[KEY + ['馬番', '着', '人気', '初角', 'p先行', 'p先頭', '年', '日']].copy()
T['馬番'] = T['馬番'].astype(int)

# 払戻（同着は行が増えるので、全部の行を足す。同じ組の重なりは1つにする）
PB = _read('race', 'payback')
def table(cols, pc, ordered=False):
    x = PB[KEY + cols + [pc]].copy()
    for c in cols: x[c] = pd.to_numeric(x[c], errors='coerce')
    x[pc] = x[pc].map(num); x = x.dropna()
    out, sold = {}, set()
    for r in x.itertuples(index=False):
        k = tuple(r[:3]); c = tuple(int(v) for v in r[3:3 + len(cols)])
        if not ordered: c = tuple(sorted(c))
        sold.add(k); out.setdefault(k, {})[c] = r[-1] / 100
    return out, sold
UREN, S_UREN = table(['馬複組番1', '馬複組番2'], '馬複払戻金（円）')
UTAN, S_UTAN = table(['馬単組番1', '馬単組番2'], '馬単払戻金（円）', ordered=True)
SANF, S_SANF = table(['３連複組番馬番1', '３連複組番馬番2', '３連複組番馬番3'], '３連複払戻金（円）')

rows = []
for k, g in T.groupby(KEY, sort=False):
    if len(g) < 4: continue
    g = g.sort_values(['p先行', 'p先頭'], ascending=False)
    a, b, c = (int(x) for x in g['馬番'].iloc[:3])
    pa, pb = g['p先頭'].iloc[0], g['p先頭'].iloc[1]
    first, second = (a, b) if pa >= pb else (b, a)
    rec = dict(zip(KEY, k)); rec.update(年=int(g['年'].iloc[0]), 日=g['日'].iloc[0], n=len(g))
    pop = g.dropna(subset=['人気']).sort_values('人気')
    fav = int(pop['馬番'].iloc[0]) if len(pop) else None
    rec['人気1を含む'] = fav in (a, b)
    rec['前2の人気'] = ' '.join(str(int(x)) if pd.notna(x) else '-' for x in sorted(g['人気'].iloc[:2]))
    if k in S_UREN:
        rec['K1'] = UREN[k].get(tuple(sorted((a, b))), 0.0)
        if len(pop) >= 2:
            rec['P12'] = UREN[k].get(tuple(sorted((int(pop['馬番'].iloc[0]), int(pop['馬番'].iloc[1])))), 0.0)
        # 結果から分かる数字（前提）：実際に最初のコーナーを1・2番手で回った2頭
        h = g.dropna(subset=['初角']).sort_values('初角')
        if len(h) >= 2:
            rec['実前2'] = UREN[k].get(tuple(sorted(int(x) for x in h['馬番'].iloc[:2])), 0.0)
    if k in S_UTAN: rec['K2'] = UTAN[k].get((first, second), 0.0)
    if k in S_SANF: rec['K3'] = SANF[k].get(tuple(sorted((a, b, c))), 0.0)
    rows.append(rec)
R = pd.DataFrame(rows).sort_values(['日'] + KEY).reset_index(drop=True)
R.to_pickle('/tmp/chiho_front2.pkl')


def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])


def streak(v):
    m = c = 0
    for x in v:
        c = c + 1 if x == 0 else 0; m = max(m, c)
    return m


def line(lab, X, col):
    X = X[X[col].notna()]; A = X[(X['年'] >= 2021) & (X['年'] <= 2025)]; Z = X[X['年'] == 2026]
    if len(A) < 30: return None
    by = A.groupby('年')[col].mean() * 100; lo, hi = boot(A[col].values, A['日'].values)
    top3 = A[col].nlargest(3)
    return dict(券=lab, 点_年=round(len(A) / 5), 的中=f"{(A[col] > 0).mean()*100:.1f}", 当たりの平均=f"{A.loc[A[col] > 0, col].mean()*100:,.0f}円",
                回収5年=f"{A[col].mean()*100:.1f}", 幅=f'{lo:.0f}〜{hi:.0f}', 年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)),
                百以上=f'{(by >= 100).sum()}/5', 上位3本抜き=f"{(A[col].sum() - top3.sum()) / len(A) * 100:.1f}",
                最長の外れ=streak(A[col].values), y2026=f"{Z[col].mean()*100:.1f}（{len(Z)}点）")


pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print('レース数', len(R), '（2021〜2025年', ((R['年'] >= 2021) & (R['年'] <= 2025)).sum(), '／2026年', (R['年'] == 2026).sum(), '）')
out = [line('K1 前の2頭の馬複', R, 'K1'), line('K2 前の2頭の馬単', R, 'K2'), line('K3 前の3頭の3連複', R, 'K3'),
       line('くらべる相手：1・2番人気の馬複', R, 'P12'),
       line('K1のうち 1番人気を含む', R[R['人気1を含む']], 'K1'), line('K1のうち 1番人気を含まない', R[~R['人気1を含む']], 'K1'),
       line('（結果から分かる数字）実際に1・2番手で回った2頭の馬複', R, '実前2')]
print(pd.DataFrame([o for o in out if o]).to_string(index=False))
A = R[(R['年'] >= 2021) & (R['年'] <= 2025)]
print('\n前の2頭が実際に1・2着に来た割合', f"{(A['K1'] > 0).mean()*100:.1f}%", '／1・2番人気が1・2着', f"{(A['P12'] > 0).mean()*100:.1f}%")
print('前の2頭の人気の組（多い順）'); print(A['前2の人気'].value_counts().head(8).to_string())
print('\n場ごと（K1、2021〜2025年）'); print(A.groupby('競馬場').agg(レース=('K1', 'size'), 的中=('K1', lambda s: round((s > 0).mean() * 100, 1)), 回収=('K1', lambda s: round(s.mean() * 100, 1))).to_string())

# 仕組みの確かめ：2026年3〜9月の確定オッズ
O = load_odds()
O['番号1'] = pd.to_numeric(O['番号1'], errors='coerce'); O['番号2'] = pd.to_numeric(O['番号2'], errors='coerce')
W = O[(O['賭式'] == '単勝') & (O['オッズ'] > 0)].dropna(subset=['番号1'])
U = O[(O['賭式'] == '馬複') & (O['オッズ'] > 0)].dropna(subset=['番号1', '番号2'])
q = {}
for k, g in W.groupby(KEY):
    inv = 1 / g['オッズ'].values; q[k] = dict(zip(g['番号1'].astype(int), inv / inv.sum()))
u = {}
for k, g in U.groupby(KEY):
    inv = 1 / g['オッズ'].values; lo = np.minimum(g['番号1'], g['番号2']).astype(int); hi = np.maximum(g['番号1'], g['番号2']).astype(int)
    u[k] = dict(zip(zip(lo, hi), inv / inv.sum()))
def harville(qq, i, j):
    qi, qj = qq.get(i, 0), qq.get(j, 0)
    return qi * qj / (1 - qi) + qj * qi / (1 - qj) if qi < 1 and qj < 1 else np.nan
m = []
for k, g in T[T['年'] == 2026].groupby(KEY, sort=False):
    if k not in q or k not in u or len(g) < 4: continue
    g = g.sort_values(['p先行', 'p先頭'], ascending=False); a, b = sorted(int(x) for x in g['馬番'].iloc[:2])
    pop = g.dropna(subset=['人気']).sort_values('人気')
    top2 = set(g.dropna(subset=['着']).sort_values('着')['馬番'].iloc[:2].astype(int)) if g['着'].notna().sum() >= 2 else None
    if top2 is None: continue
    rec = dict(zip(KEY, k))
    for lab, (i, j) in (('前の2頭', (a, b)), ('1・2番人気', tuple(sorted(int(x) for x in pop['馬番'].iloc[:2])))):
        m.append(dict(rec, 組=lab, ハービル=harville(q[k], i, j), 馬複の値段=u[k].get((i, j), np.nan), 実際=float({i, j} == top2),
                      払戻=UREN.get(k, {}).get((i, j), 0.0)))
M = pd.DataFrame(m).dropna()
print('\n■ 仕組みの確かめ（2026年3〜9月、確定オッズ）')
print(M.groupby('組').agg(レース=('実際', 'size'), ハービル=('ハービル', lambda s: round(s.mean() * 100, 1)), 馬複の値段=('馬複の値段', lambda s: round(s.mean() * 100, 1)),
                          実際=('実際', lambda s: round(s.mean() * 100, 1)), 回収=('払戻', lambda s: round(s.mean() * 100, 1))).to_string())
M2 = M[M['組'] == '前の2頭'].copy(); M2['帯'] = pd.qcut(M2['馬複の値段'], 4)
print('前の2頭を、馬複の値段の確率で4つに分けて'); print(M2.groupby('帯', observed=True).agg(レース=('実際', 'size'), ハービル=('ハービル', lambda s: round(s.mean() * 100, 1)),
      馬複の値段=('馬複の値段', lambda s: round(s.mean() * 100, 1)), 実際=('実際', lambda s: round(s.mean() * 100, 1)), 回収=('払戻', lambda s: round(s.mean() * 100, 1))).to_string())
