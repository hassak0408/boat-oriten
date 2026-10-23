"""材料だけのランキングの上位3頭：1着・馬連BOXなど（検証計画「馬の評価のランキングと上位3頭」）"""
import numpy as np, pandas as pd
from itertools import combinations
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl'); W = pd.read_pickle('/tmp/chiho_win.pkl')
D = H.merge(W, on=KEY + ['馬番'], how='inner')
D['p'] = D['p勝'] / D.groupby(KEY)['p勝'].transform('sum')
D['材順'] = D.groupby(KEY)['p'].rank(ascending=False, method='first')
D['人順'] = D.groupby(KEY)['人気'].rank(method='first')
def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan
PB = _read('race', 'payback')
pays = {}
def add(t, cols, pc):
    x = PB[KEY + cols + [pc]].copy()
    for c in cols: x[c] = pd.to_numeric(x[c], errors='coerce')
    x[pc] = x[pc].map(num); x = x.dropna()
    for r in x.itertuples(index=False):
        k = tuple(r[:3]); combo = tuple(sorted(int(v) for v in r[3:3 + len(cols)]))
        pays.setdefault(t, {}).setdefault(k, {})[combo] = r[-1] / 100
add('馬連', ['馬複組番1', '馬複組番2'], '馬複払戻金（円）')
for i in (1, 2, 3): add('ワイド', [f'ワイド組番{i}馬番1', f'ワイド組番{i}馬番2'], f'ワイド払戻金{i}（円）')
add('3連複', ['３連複組番馬番1', '３連複組番馬番2', '３連複組番馬番3'], '３連複払戻金（円）')
rows = []
for k, g in D.groupby(KEY, sort=False):
    g = g.sort_values('材順'); m3 = [int(x) for x in g['馬番'].iloc[:3]]
    gm = g.sort_values('人順'); p3 = [int(x) for x in gm['馬番'].iloc[:3]] if g['人気'].notna().sum() >= 3 else None
    win = g.loc[g['着'] == 1, '馬番'].astype(int).tolist(); sec = g.loc[g['着'] == 2, '馬番'].astype(int).tolist()
    rec = dict(zip(KEY, k)); rec.update(Y=int(k[1][:4]), 日=k[1], n=len(g), 合計p3=g['p'].iloc[:3].sum(), 本命p=g['p'].iloc[0])
    for lab, top in (('材', m3), ('人', p3)):
        if top is None or len(top) < 3: continue
        rec[lab + '_1着'] = bool(win) and win[0] == top[0]
        rec[lab + '_3頭に1着'] = any(w in top for w in win)
        rec[lab + '_1・2着そろう'] = bool(win) and bool(sec) and all(w in top for w in win + sec)
        rec[lab + '_単勝'] = g.loc[g['馬番'] == top[0], '単払'].sum()
        for t in ('馬連', 'ワイド'):
            if k in pays.get(t, {}):
                rec[f'{lab}_{t}BOX'] = sum(pays[t][k].get(tuple(sorted(c)), 0) for c in combinations(top, 2)) / 3
        if k in pays.get('3連複', {}):
            rec[f'{lab}_3連複'] = pays['3連複'][k].get(tuple(sorted(top)), 0)
    rows.append(rec)
R = pd.DataFrame(rows)
R.to_pickle('/tmp/chiho_rank3.pkl')
T5 = R[(R['Y'] >= 2021) & (R['Y'] <= 2025)]; T26 = R[R['Y'] == 2026]
print('レース数 2021〜25年', len(T5), '／2026年', len(T26))
print('\n■ 当たり方（2021〜25年 → 2026年）')
for c in ('1着', '3頭に1着', '1・2着そろう'):
    print(f"  {c}：材料のランキング {T5['材_'+c].mean()*100:.1f}%  市場（1〜3番人気） {T5['人_'+c].mean()*100:.1f}%   2026年 {T26['材_'+c].mean()*100:.1f}% / {T26['人_'+c].mean()*100:.1f}%")
# 見込みと実際
D5 = D[(D['年'] >= 2021) & (D['年'] <= 2025)]
D5['帯'] = pd.cut(D5['p'], [0, .05, .1, .2, .3, .4, .5, 1])
print('\n■ 1着の見込みと実際（2021〜25年）'); print(D5.groupby('帯', observed=True).agg(頭=('勝', 'size'), 見込み=('p', 'mean'), 実際=('勝', 'mean')).assign(
    見込み=lambda d: (d['見込み'] * 100).round(1), 実際=lambda d: (d['実際'] * 100).round(1)).to_string())
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
print('\n■ 買ったら（100円あたりの回収、BOXは3点を1つとして）')
out = []
for bet in ('馬連BOX', 'ワイドBOX', '3連複', '単勝'):
    for lab, nm in (('材', '材料の上位3頭'), ('人', '1〜3番人気')):
        c = f'{lab}_{bet}'
        S = T5.dropna(subset=[c]); by = S.groupby('Y')[c].mean() * 100; lo, hi = boot(S[c].values, S['日'].values)
        out.append(dict(券=bet, 選び方=nm, レース=len(S), 回収5年=round(S[c].mean() * 100, 1), 幅=f'{lo:.0f}〜{hi:.0f}',
                        年ごと='・'.join(f'{by.get(y):.0f}' for y in range(2021, 2026)), y2026=round(T26[c].mean() * 100, 1)))
pd.set_option('display.width', 250); print(pd.DataFrame(out).to_string(index=False))
# 自信の強さ（上位3頭の見込みの合計）で分ける：線は同じ年の見込みの分布だけから（結果は使わない）
print('\n■ 上位3頭の見込みの合計で5つに分けた馬連BOX（2021〜25年）')
T5 = T5.copy(); T5['帯'] = T5.groupby('Y')['合計p3'].transform(lambda s: pd.qcut(s, 5, labels=['1弱', '2', '3', '4', '5強']))
print(T5.groupby('帯', observed=True).agg(レース=('Y', 'size'), そろう=('材_1・2着そろう', 'mean'), 回収=('材_馬連BOX', 'mean'), 人気そろう=('人_1・2着そろう', 'mean'), 人気回収=('人_馬連BOX', 'mean')).assign(
    そろう=lambda d: (d['そろう'] * 100).round(1), 回収=lambda d: (d['回収'] * 100).round(1), 人気そろう=lambda d: (d['人気そろう'] * 100).round(1), 人気回収=lambda d: (d['人気回収'] * 100).round(1)).to_string())
