# EX1：キャリアが浅い馬で、AIと人気のどちらが当たるか（検証計画 EX1）
import glob, json, numpy as np, pandas as pd
rng = np.random.default_rng(82)
ST = '/home/claude/chiho-keiba'; K = ['年月日', '場', 'R']
FX = json.load(open('/home/claude/boat-oriten/chiho/jra/jra_fix.json', encoding='utf-8'))
A_, B_ = FX['1着の付け直し']['a'], FX['1着の付け直し']['b']; F1 = FX['1着の付け直し'].get('中央で初めて走る馬（新馬以外）に掛ける値', 1.0)
C_ = FX['3着内の付け直し']['c']; FM = FX['着差のモデル']['f']
def rd(pat, **kw): return pd.concat([pd.read_csv(f, **kw) for f in sorted(glob.glob(pat))], ignore_index=True)
def fixk(X):
    X['R'] = pd.to_numeric(X['R'], errors='coerce').astype('Int64').astype(str); X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['年月日'] = X['年月日'].astype(str); return X
D = fixk(rd(f'{ST}/jra/exp/m8_pred_*.csv.gz', dtype={k: str for k in K}))
M7 = fixk(rd(f'{ST}/jra/exp/m7_pred_202[1-6].csv.gz', dtype={k: str for k in K})[K + ['馬番', 'h', 'mg']])
D = D.merge(M7, on=K + ['馬番'], how='inner')
D = D[D['p1_EV'].notna() & D['p3_EV'].notna() & D['h'].notna() & (D['単勝オッズ'] > 0)]
D = D[D.groupby(K)['勝'].transform('sum') == 1].sort_values(K + ['馬番']).reset_index(drop=True)
D['nn'] = D.groupby(K)['馬番'].transform('count'); G = [D[k] for k in K]
def n3(v): v = pd.Series(v, index=D.index); return np.clip(v * np.minimum(3, D['nn']) / v.groupby(G).transform('sum'), 1e-4, 0.97).values
first = ((D['走数'] == 0) & (D['新馬'] == 0)).values
hh = n3(D['h'].values); m = (D['mg'] - D.groupby(K)['mg'].transform('mean')).values
s1 = A_ * np.log(np.clip(D['p1_EV'] / D.groupby(K)['p1_EV'].transform('sum'), 1e-6, 1)).values + B_ * np.log(hh)
s1 = s1 - pd.Series(s1, index=D.index).groupby(G).transform('max').values
x1 = np.exp(s1) * np.where(first, F1, 1.0); D['p1'] = x1 / pd.Series(x1, index=D.index).groupby(G).transform('sum').values
m3 = n3(np.where(first, hh, n3(D['p3_EV'].values))); D['p3'] = n3(m3 ** C_ * np.exp(-FM * m))
D['pm'] = 1 / D['単勝オッズ']; D['pm'] = D['pm'] / D.groupby(K)['pm'].transform('sum')
Hd = fixk(rd(f'{ST}/jra/exp/hdump_20*.csv.gz', dtype={k: str for k in K}, usecols=K + ['馬番', '前走数']))
Ag = fixk(rd(f'{ST}/jra/data/202[1-6]/*_horses.csv.gz', dtype=str, usecols=K + ['馬番', '齢']))
D = D.merge(Hd.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left').merge(Ag.drop_duplicates(K + ['馬番']), on=K + ['馬番'], how='left')
D['齢'] = pd.to_numeric(D['齢'], errors='coerce'); D['二歳戦'] = D.groupby(K)['齢'].transform('max') == 2
D['経'] = np.where(D['前走数'] <= 1, '浅い', np.where(D['前走数'] == 2, '2走', '3走以上')); D.loc[D['前走数'].isna(), '経'] = None
D['r'] = D['p1'] / D['pm']; D['帯'] = np.where(D['r'] >= 1.5, 'AIが高い', np.where(D['r'] <= 1 / 1.5, 'AIが低い', '近い'))
D['期'] = np.where(D['年月日'] <= '20231231', '2021〜23', '2024〜26')
print('馬', len(D), 'レース', D.groupby(K).ngroups, '／走った数が分からない', int(D['経'].isna().sum()))
def boot(T, a, b, num, den):
    days = T['年月日'].values; ds = np.sort(np.unique(days)); ix = np.searchsorted(ds, days); W = rng.poisson(1.0, (1000, len(ds)))
    s = lambda mk, c: W @ np.bincount(ix[mk], T[c].values[mk], len(ds))
    return np.percentile((s(a, num) / s(a, den)) / (s(b, num) / s(b, den)), [2.5, 97.5])
ok = []
for per in ('2021〜23', '2024〜26'):
    P = D[D['期'] == per]
    print(f'\n{per}：')
    t = P.groupby(['帯', '経']).agg(頭=('勝', 'size'), 勝=('勝', 'sum'), AI=('p1', 'sum'), 人気=('pm', 'sum'), 三着内=('3着内', 'sum'), AI3=('p3', 'sum'))
    t['実際÷AI'] = t['勝'] / t['AI']; t['実際÷人気'] = t['勝'] / t['人気']; t['3着内÷AI'] = t['三着内'] / t['AI3']
    print(t[['頭', '勝', '実際÷AI', '実際÷人気', '3着内÷AI']].round(3).to_string())
    for band in ('AIが高い', 'AIが低い'):
        T = P[(P['帯'] == band) & P['経'].isin(['浅い', '3走以上'])]; a = (T['経'] == '浅い').values
        q = (T.loc[a, '勝'].sum() / T.loc[a, 'p1'].sum()) / (T.loc[~a, '勝'].sum() / T.loc[~a, 'p1'].sum()); ci = boot(T, a, ~a, '勝', 'p1')
        print(f'  {"★" if band == "AIが高い" else "数字だけ："}{band}：Q（浅い÷3走以上、実際÷AI）{q:.3f}（95%幅 {ci[0]:.3f}〜{ci[1]:.3f}）')
        if band == 'AIが高い': ok.append(q < 1 and ci[1] < 1)
    Z = P[P['二歳戦'] & (P['帯'] == 'AIが高い')]
    print(f'  数字だけ：2歳戦で AIが高い 馬 {len(Z)}頭：実際÷AI {Z["勝"].sum() / Z["p1"].sum():.3f}・実際÷人気 {Z["勝"].sum() / Z["pm"].sum():.3f}')
print('\n判断：', '浅い馬でAIが人気より高く見る時は、AIを割り引く' if all(ok) else '割り引くとは言えない')
