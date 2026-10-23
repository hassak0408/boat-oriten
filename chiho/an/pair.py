"""人気馬との馬連・ワイド（検証計画「人気馬との馬連・ワイド」）と、選んだ馬が3着内に来ているか。"""
import sys, os, numpy as np, pandas as pd
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl')
P = pd.read_pickle('/tmp/chiho_pred.pkl'); P = P[P['券'] == '複'].copy()
W = pd.read_pickle('/tmp/chiho_win.pkl') if os.path.exists('/tmp/chiho_win.pkl') else None
def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan
PB = _read('race', 'payback'); parts = []
for i in (1, 2, 3):
    x = PB[KEY + [f'ワイド組番{i}馬番1', f'ワイド組番{i}馬番2', f'ワイド払戻金{i}（円）']].copy(); x.columns = KEY + ['a', 'b', '払']; x['券'] = 'ワイド'; parts.append(x)
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy(); x.columns = KEY + ['a', 'b', '払']; x['券'] = '馬連'; parts.append(x)
X = pd.concat(parts); X['a'] = pd.to_numeric(X['a'], errors='coerce'); X['b'] = pd.to_numeric(X['b'], errors='coerce'); X['払'] = X['払'].map(num)
X = X.dropna(subset=['a', 'b', '払']); X['lo'] = X[['a', 'b']].min(axis=1).astype(int); X['hi'] = X[['a', 'b']].max(axis=1).astype(int)
X = X.drop_duplicates(KEY + ['券', 'lo', 'hi'])
PAY = {t: dict(zip(map(tuple, g[KEY + ['lo', 'hi']].values.tolist()), g['払'] / 100)) for t, g in X.groupby('券')}
SOLD = {t: set(map(tuple, g[KEY].drop_duplicates().values.tolist())) for t, g in X.groupby('券')}
def pay(t, race, a, b):
    if race not in SOLD[t]: return np.nan
    lo, hi = sorted((int(a), int(b))); return PAY[t].get(race + (lo, hi), 0.0)
# 人気の順の馬番（確定の人気）
pop = H[H['人気'].notna()].sort_values(KEY + ['人気']).groupby(KEY)['馬番'].apply(list)
popd = {tuple(k): v for k, v in pop.items()}
if W is not None:
    w = W.sort_values(KEY + ['p勝'], ascending=[True, True, True, False]).groupby(KEY)['馬番'].apply(list)
    wind = {tuple(k): v for k, v in w.items()}
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])

pd.set_option('display.width', 260)
# ■ 選んだ馬は3着内に来ているか
print('■ 選んだ馬の着（2021〜2025年）と、同じ年・同じ人気の馬との比べ')
base = H[H['複払'].notna() & H['人気'].notna()].groupby(['年', '人気'])[['勝', '3着内']].mean()
rows = []
for q in (1, 2, 5):
    S = P[(P[f'比{q}'] >= 1) & (P['Y'] <= 2025) & P['人気'].notna()].copy()
    b = base.reindex(list(zip(S['年'], S['人気'])))
    S['基勝'] = b['勝'].values; S['基3'] = b['3着内'].values
    S26 = P[(P[f'比{q}'] >= 1) & (P['Y'] == 2026) & P['人気'].notna()]
    b26 = base.reindex(list(zip(S26['年'], S26['人気'])))
    rows.append(dict(線=f'上位{q}%', 頭=len(S), 人気平均=round(S['人気'].mean(), 1), 一着=f"{S['勝'].mean()*100:.1f}%（同じ人気 {S['基勝'].mean()*100:.1f}%）",
                     三着内=f"{S['3着内'].mean()*100:.1f}%（同じ人気 {S['基3'].mean()*100:.1f}%）",
                     三着内2026=f"{S26['3着内'].mean()*100:.1f}%（{b26['3着内'].mean()*100:.1f}%）"))
print(pd.DataFrame(rows).to_string(index=False))
S = P[(P['比1'] >= 1) & (P['Y'] <= 2025) & P['人気'].notna()].copy()
b = base.reindex(list(zip(S['年'], S['人気']))); S['基3'] = b['3着内'].values
S['人気帯'] = pd.cut(S['人気'], [0, 3, 5, 7, 9, 16], labels=['1〜3', '4〜5', '6〜7', '8〜9', '10〜'])
print('\n上位1%の人気ごと'); print(S.groupby('人気帯', observed=True).agg(頭=('勝', 'size'), 三着内=('3着内', 'mean'), 同じ人気=('基3', 'mean'), 複勝回収=('ret', 'mean')).assign(
    三着内=lambda d: (d['三着内'] * 100).round(1), 同じ人気=lambda d: (d['同じ人気'] * 100).round(1), 複勝回収=lambda d: (d['複勝回収'] * 100).round(1)).to_string())

# ■ 人気馬との馬連・ワイド
print('\n■ 選んだ馬 × 相手 の馬連・ワイド（1点100円）')
def partners(race, s, kind):
    pl = popd.get(race, [])
    if kind == '1番人気':
        c = [h for h in pl[:2] if h != s]; return c[:1]
    if kind == '2番人気':
        c = [h for h in pl[:2] if h != s] if s in pl[:2] else pl[1:2]; return c[:1]
    if kind == '1・2番人気へ流し':
        c = [h for h in pl[:3] if h != s]; return c[:2]
    if kind == '材料の本命':
        c = [h for h in wind.get(race, [])[:2] if h != s]; return c[:1]
kinds = ['1番人気', '2番人気', '1・2番人気へ流し'] + (['材料の本命'] if W is not None else [])
out = []; days = P.groupby('Y')['日'].nunique()
for q in (1, 2, 5):
    S = P[P[f'比{q}'] >= 1]
    for kind in kinds:
        for t in ('ワイド', '馬連'):
            recs = []
            for r in S.itertuples(index=False):
                race = (r.競馬場, r.競走年月日, r.レース番号)
                ps = partners(race, int(r.馬番), kind)
                if not ps: continue
                for f in ps:
                    v = pay(t, race, r.馬番, f)
                    if not np.isnan(v): recs.append((r.Y, r.日, v))
            D = pd.DataFrame(recs, columns=['Y', '日', 'ret'])
            T5 = D[(D['Y'] >= 2021) & (D['Y'] <= 2025)]
            by = T5.groupby('Y')['ret'].mean() * 100
            lo, hi = boot(T5['ret'].values, T5['日'].values)
            x = np.sort(T5['ret'].values)[::-1]
            D26 = D[D['Y'] == 2026]
            out.append(dict(線=f'上位{q}%', 相手=kind, 券=t, 点_年=int(len(T5) / 5), 的中=round((T5['ret'] > 0).mean() * 100, 1),
                            当たり平均=round(T5.loc[T5['ret'] > 0, 'ret'].mean() * 100), 回収5年=round(T5['ret'].mean() * 100, 1), 幅=f'{lo:.0f}〜{hi:.0f}',
                            年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)), 上位3本抜き=round(x[3:].sum() / len(x) * 100, 1),
                            y2026=f"{D26['ret'].mean()*100:.1f}（{len(D26)}点）"))
print(pd.DataFrame(out).to_string(index=False))
