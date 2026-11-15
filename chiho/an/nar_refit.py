"""地方 N6（E＋V を採用）のときの値の決め直し（もとは N5 のときの nar_refit.py）。使い方：python nar_refit.py STORE m5|m6b（HGBの3着内と着差のモデルの出どころ） 出力.csv.gz
決める値（a b e ／ c f）を2021〜2026年の全部で決め、枠の付け直し・連対の直し・馬連の直しを作り直して、
nar_fix.json・rentai_calib.json・pair_calib.json に書く。作り方は、前の w1_fit.py・nk_r1cal.py・nar_pair_calib.py と同じ。"""
import os, sys, glob, json, numpy as np, pandas as pd
from itertools import combinations
from scipy.optimize import minimize
from sklearn.isotonic import IsotonicRegression
ST, HS, OUTP = sys.argv[1], sys.argv[2], sys.argv[3]; AN = os.path.dirname(os.path.abspath(__file__))
KEY = ['競馬場', '競走年月日', 'レース番号']
rd = lambda pat: pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(pat))], ignore_index=True)
if HS == 'm6b': D = rd(f'{ST}/data/exp/nk_m6b_pred_*.csv.gz').rename(columns={'h_EV': 'h', 'mg_EV': 'mg'})      # 順を学ぶモデルも HGB・着差も N6b の回のもの
else: D = rd(f'{ST}/data/exp/nk_m6_pred_*.csv.gz').merge(rd(f'{ST}/data/exp/nk_m5_pred_*.csv.gz')[KEY + ['馬番', 'h', 'mg']], on=KEY + ['馬番'], how='inner')
D = D[(D['n'] >= 5) & (D.groupby(KEY)['勝'].transform('sum') >= 1) & (D.groupby(KEY)['馬番'].transform('size') == D['n'])]
R = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['馬番', '着順', '枠番']) for f in glob.glob(f'{ST}/data/race/*/*horselist*.csv.gz')], ignore_index=True).drop_duplicates(KEY + ['馬番'], keep='last')
for c in ('馬番', '着順', '枠番'): R[c] = pd.to_numeric(R[c], errors='coerce')
D['馬番'] = pd.to_numeric(D['馬番'], errors='coerce'); D = D.merge(R.rename(columns={'着順': '着'}), on=KEY + ['馬番'], how='left')
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True); D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
gs = lambda v: pd.Series(v).groupby(G).transform('sum').values
n3 = lambda v: np.clip(v * np.minimum(3, D['n'].values) / gs(v), 1e-4, 0.97)
hh = n3(D['h'].values); lh = np.log(hh); m = (D['mg'] - D.groupby('g')['mg'].transform('mean')).values
l1b = np.log(np.clip(D['pl_1_EV'].values / gs(D['pl_1_EV'].values), 1e-6, 1))
m3 = n3(np.where((D['五場走数'] == 0).values, hh, n3(D['pl_3_EV'].values)))
win = D['勝'].values == 1; y3 = D['3着内'].values


def p1of(w):
    s = w[0] * l1b + w[1] * lh - w[2] * m; s = s - pd.Series(s).groupby(G).transform('max').values
    x = np.exp(s); return x / gs(x)


def p3of(c): return n3(m3 ** c[0] * np.exp(-c[1] * m))
NM = dict(method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7, 'maxiter': 2000})
r1 = minimize(lambda w: float(-np.log(np.clip(p1of(w)[win], 1e-6, 1)).mean()), [1.0, 0.2, 0.05], **NM)
r3 = minimize(lambda c: float(-(y3 * np.log(p3of(c)) + (1 - y3) * np.log(1 - p3of(c))).mean()), [0.75, 0.25], **NM)
a, b, e = (round(float(x), 3) for x in r1.x); c, f = (round(float(x), 3) for x in r3.x)
print('決めた値（2021〜2026年の全部）a b e', a, b, e, '／c f', c, f, 'レース', D['g'].nunique())
D['p1'] = p1of([a, b, e]); D['p3'] = p3of([c, f])
# 枠の付け直し（1着）
D['枠群'] = pd.cut(D['枠番'], [0, 2, 6, 8], labels=['内（1〜2枠）', '中（3〜6枠）', '外（7〜8枠）']).astype(str); D['区分'] = D['競馬場'] + '・' + D['枠群']
ok = D['枠番'].notna()
W = ((D[ok].groupby('区分')['勝'].sum() + 50) / (D[ok].groupby('区分')['p1'].sum() + 50)).round(4).to_dict()
print('枠の掛ける値', W)
v = D['p1'].values * D['区分'].map(W).fillna(1.0).where(ok, 1.0).values; D['p1'] = v / gs(v)
# 連対の直し（ハービル→単調な直し、2021〜2023年で作って2024〜2026年で確かめる）
r = D['p1'] / (1 - D['p1']).clip(lower=1e-9); p2 = (D['p1'] + D['p1'] * (r.groupby(G).transform('sum') - r)).clip(0, 1).values
y2 = (D['着'] <= 2).astype(float).values; okk = D['着'].notna().values | True
A_, B_ = (D['年'] <= 2023).values, (D['年'] >= 2024).values
ir = IsotonicRegression(out_of_bounds='clip', y_min=0.001, y_max=0.999).fit(p2[A_], y2[A_])
grid = np.round(np.arange(0, 1.0001, 0.01), 2); mapped = ir.predict(grid); q = np.interp(p2, grid, mapped)
ll = lambda v_, mk: float(-(y2[mk] * np.log(np.clip(v_[mk], 1e-4, 1 - 1e-4)) + (1 - y2[mk]) * np.log(np.clip(1 - v_[mk], 1e-4, 1))).mean())
print(f'連対の当て分け 2024〜2026年：直す前 {ll(p2, B_):.5f} → 直した後 {ll(q, B_):.5f}')
json.dump({'見込み': grid.tolist(), '直した見込み': np.round(mapped, 4).tolist(),
           '作り方': '検証計画 R1・N6。1着の見込み（N6、枠の付け直しのあと）からハービルで出した連対（2着内）の見込みに、2021〜2023年で単調な直しを作った（nar_refit.py）'},
          open(f'{AN}/rentai_calib.json', 'w', encoding='utf-8'), ensure_ascii=False)
# 馬連の直し（B式、上位10組と上位3組の和）
cal, top3 = [], []
for k, g in D.groupby('g', sort=False):
    fin = g['着'].values
    if (fin <= 2).sum() < 2: continue
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum(); top2 = set(nums[fin <= 2])
    Pr = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(Pr.values()); order = sorted(Pr, key=Pr.get, reverse=True); yr = int(g['年'].iloc[0])
    for o in order[:10]: cal.append((yr, Pr[o] / z, {nums[o[0]], nums[o[1]]} == top2))
    top3.append((yr, [Pr[o] / z for o in order[:3]], any({nums[o[0]], nums[o[1]]} == top2 for o in order[:3])))
CA = pd.DataFrame(cal, columns=['年', '見込み', '的中'])
fit = CA[CA['年'] <= 2023]; irp = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(fit['見込み'], fit['的中'].astype(float))
gridp = np.round(np.arange(0, 0.801, 0.005), 3); mappedp = irp.predict(gridp)
T3 = pd.DataFrame([(y_, sum(np.interp(x, gridp, mappedp) for x in vs), h) for y_, vs, h in top3], columns=['年', '和', '的中'])
ir3 = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(T3.loc[T3['年'] <= 2023, '和'], T3.loc[T3['年'] <= 2023, '的中'].astype(float))
grid3 = np.round(np.arange(0, 1.501, 0.01), 2); mapped3 = ir3.predict(grid3)
json.dump({'見込み': gridp.tolist(), '直した見込み': np.round(mappedp, 4).tolist(), '3組の和': grid3.tolist(), '3組の和の直した見込み': np.round(mapped3, 4).tolist(),
           '作り方': f'2021〜2023年の各レースの上位10組と、上位3組の和（nar_refit.py。見込みは N6：a={a} b={b} e={e} c={c} f={f}、枠の付け直しのあと）'},
          open(f'{AN}/pair_calib.json', 'w', encoding='utf-8'), ensure_ascii=False)
CB = CA[CA['年'] >= 2024].copy(); CB['直した'] = np.interp(CB['見込み'], gridp, mappedp); CB['帯'] = pd.cut(CB['直した'], [0, .05, .1, .15, .2, .3, .4, 1])
print(CB.groupby('帯', observed=True).agg(組=('的中', 'size'), 直した後=('直した', lambda s: round(s.mean() * 100, 1)), 実際=('的中', lambda s: round(s.mean() * 100, 1))).to_string())
for lab, mk in (('2021〜2023年', lambda y_: y_ <= 2023), ('2024〜2026年', lambda y_: y_ >= 2024)):
    X = [t for t in top3 if mk(t[0])]; print(f'{lab}：上位3組のどれかの的中 {np.mean([t[2] for t in X]) * 100:.1f}%（{len(X)}レース）')
J = json.load(open(f'{AN}/nar_fix.json', encoding='utf-8'))
J.update({'a': a, 'b': b, 'c': c})
J['相手の材料'] = {'E': True, 'V': True, 'HGBにも': HS == 'm6b', '作り方': '検証計画 N6。強さの点数（E）と前走の相手のその後（V）を全部の場のレースで作り（hist_all.py・jra/jk_elo.py）、順を学ぶモデルの材料に足す'}
J['着差のモデル'] = {'e': e, 'f': f, '作り方': '検証計画 N5 の mg。HGB（3つの平均）で勝ち馬との着差（秒、1000mあたり、0〜5で切る）を学び、見込みの着差−レースの平均を m として、1着に exp(−e×m)、3着内に exp(−f×m) を掛ける。値は2021〜2026年の全部で決めた（nar_refit.py）'}
J['枠の付け直し']['1着'] = W
J['枠の付け直し']['作り方'] = '検証計画 W1。N6 の1着の見込みに、場×枠の群ごとの値を掛けて足して1に直す。値＝（実際の1着＋50）÷（見込みの和＋50）、2021〜2026年の全部で決めた（nar_refit.py）。3着内は直さない。5場のほかの場は1のまま。'
json.dump(J, open(f'{AN}/nar_fix.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
D[KEY + ['馬番', '年', 'n', '勝', '3着内', '着', '人気', 'p1', 'p3']].to_csv(OUTP, index=False)
print('書いた')
