"""中央 M8（E＋V）を採用するときの値を作り直す（もとは M7 のときの jra_refit.py）：a・b、中央で初めて走る馬（新馬以外）に掛ける値、c・f（着差のモデル）、枠の付け直し（1着・3着内）を2021〜2026年の全部で決めて jra_fix.json に書き、
馬連の直し（jpair.py）用の見込みを pkl に置く。使い方：python jra_refit.py STORE 出力.pkl"""
import sys, glob, json, numpy as np, pandas as pd
from scipy.optimize import minimize
import os
VAR = 'EV'; ST = sys.argv[1]; OUTP = sys.argv[2]; JR = os.path.dirname(os.path.abspath(__file__))
KEY = ['年月日', '場', 'R']; num = lambda s: pd.to_numeric(s, errors='coerce')
rd = lambda pat: pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(pat))], ignore_index=True)
D = rd(f'{ST}/jra/exp/m8_pred_*.csv.gz').merge(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz')[KEY + ['馬番', 'h', 'mg']], on=KEY + ['馬番'], how='inner')      # HGBの3着内・着差のモデルは M7 のもの
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['馬番', '枠', '着順', '人気']) for f in glob.glob(f'{ST}/jra/data/202[123456]/*_horses.csv.gz')], ignore_index=True).drop_duplicates(KEY + ['馬番'])
RC = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['芝ダ', 'コース', '日目']) for f in glob.glob(f'{ST}/jra/data/202[123456]/*_races.csv.gz')], ignore_index=True).drop_duplicates(KEY)
for X in (D, H, RC): X['R'] = num(X['R']).astype('Int64').astype(str)
H['馬番'] = num(H['馬番']); D['馬番'] = num(D['馬番'])
D = D.merge(H, on=KEY + ['馬番'], how='left').merge(RC, on=KEY, how='left')
D['着'] = num(D['着順']); D['人気'] = num(D['人気']); D['枠'] = num(D['枠'])
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True); D['g'] = D.groupby(KEY, sort=False).ngroup(); G = D['g'].values
gs = lambda v: pd.Series(v).groupby(G).transform('sum').values
n3 = lambda v: np.clip(v * np.minimum(3, D['n'].values) / gs(v), 1e-4, 0.97)
hh = n3(D['h'].values); lh = np.log(hh); m = (D['mg'] - D.groupby('g')['mg'].transform('mean')).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
pl = D[f'p1_{VAR}'].values; l1v = np.log(np.clip(pl / gs(pl), 1e-6, 1)); m3 = n3(np.where(first, hh, n3(D[f'p3_{VAR}'].values)))
win = D['勝'].values == 1; y3 = D['3着内'].values


def p1of(w, F1=1.0):
    s = w[0] * l1v + w[1] * lh; s = s - pd.Series(s).groupby(G).transform('max').values
    x = np.exp(s) * np.where(first, F1, 1.0); return x / gs(x)


def p3of(c): return n3(m3 ** c[0] * np.exp(-c[1] * m))
ll1 = lambda p: float(-np.log(np.clip(p[win], 1e-6, 1)).mean()); ll3 = lambda p: float(-(y3 * np.log(p) + (1 - y3) * np.log(1 - p)).mean())
NM = dict(method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-7, 'maxiter': 2000})
r1 = minimize(lambda w: ll1(p1of(w)), [0.9, 0.25], **NM); a, b = (round(float(x), 3) for x in r1.x)
rF = minimize(lambda w: ll1(p1of([a, b], w[0])), [1.0], **NM); F1 = round(float(rF.x[0]), 3)
r3 = minimize(lambda c: ll3(p3of(c)), [0.75, 0.45], **NM); c, f = (round(float(x), 3) for x in r3.x)
print('レース', D['g'].nunique(), 'a b', a, b, 'F1', F1, 'c f', c, f, '／1着の当て分け', round(ll1(p1of([a, b], F1)), 5), '3着内', round(ll3(p3of([c, f])), 5))
D['p1'] = p1of([a, b], F1); D['p3'] = p3of([c, f])
# 枠の付け直し（w12.py と同じ区分）
wg = pd.cut(D['枠'], [0, 2, 6, 8], labels=['内（1〜2枠）', '中（3〜6枠）', '外（7〜8枠）']).astype(str)
kai = np.where(D['コース'].str.contains('外'), '外回り', np.where(D['コース'].str.contains('直線'), '直線', '内回り・ふつう'))
D['区分'] = np.where(D['芝ダ'] == 'ダート', 'ダ・' + wg, '芝・' + np.where(num(D['日目']) <= 2, '1〜2日目', '3日目以降') + '・' + kai + '・' + wg)
ok = D['枠'].notna() & D['芝ダ'].isin(['芝', 'ダート'])
mult = lambda p, y: ((D[ok].groupby('区分')[y].sum() + 50) / (D[ok].groupby('区分')[p].sum() + 50)).round(4).to_dict()
W1, W3 = mult('p1', '勝'), mult('p3', '3着内')
v = D['p1'].values * D['区分'].map(W1).fillna(1.0).where(ok, 1.0).values; D['p1'] = v / gs(v)
v = D['p3'].values * D['区分'].map(W3).fillna(1.0).where(ok, 1.0).values; D['p3'] = n3(v)
print('枠を掛けたあと 1着の当て分け', round(ll1(D['p1'].values), 5), '3着内', round(ll3(D['p3'].values), 5))
print('枠の値（1着）', {k: W1[k] for k in list(W1)[:6]}, '…')
D[KEY + ['馬番', '年', 'n', '着', '人気', '勝', '3着内', '単勝オッズ', 'p1', 'p3']].to_pickle(OUTP)
J = json.load(open(f'{JR}/jra_fix.json', encoding='utf-8'))
J['1着の付け直し'].update({'a': a, 'b': b, '中央で初めて走る馬（新馬以外）に掛ける値': F1})
J['3着内の付け直し'].update({'c': c})
J['血統'] = True; J['レースの中での差'] = True
J['相手の材料'] = {'E': True, 'V': True, '作り方': '検証計画 M8。強さの点数（E）と前走の相手のその後（V）を、順を学ぶモデルの材料に足す（jk_elo.py）。HGBの3着内と着差のモデルには足さない（M8b で変わらなかった）'}
J['着差のモデル'] = {'f': f, '作り方': '検証計画 mg3。HGB（3つの平均）で勝ち馬との着差（秒、1000mあたり、0〜5で切る）を学び、見込みの着差−レースの平均を m として、3着内に exp(−f×m) を掛ける（1着には使わない）'}
J['枠の付け直し']['1着'] = W1; J['枠の付け直し']['3着内'] = W3
J['枠の付け直し']['作り方'] = '検証計画 W1。M8（血統・レースの中での差・着差のモデル・相手の材料）の見込みに、芝ダ×枠の群ごとの値を掛けて直す（芝は開催1〜2日目か・外回り・直線を分ける）。値＝（実際＋50）÷（見込みの和＋50）、2021〜2026年の全部で決めた（jra_refit.py）。'
J['作り方の覚え'] = 'M8（2026-11-16）：a・b・c・f・初めて走る馬に掛ける値・枠は、jk_m8.py の見込み（EV）と jk_m7.py の HGB・着差で2021〜2026年の全部から決めた（jra_refit.py）'
json.dump(J, open(f'{JR}/jra_fix.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('書いた')
