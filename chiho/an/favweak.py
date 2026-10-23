"""1番人気が材料の本命でないレースに絞った、選んだ馬の複勝（検証計画「続けて試すこと」）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
H = pd.read_pickle('/tmp/chiho_feat.pkl'); P = pd.read_pickle('/tmp/chiho_pred.pkl'); P = P[P['券'] == '複'].copy()
W = pd.read_pickle('/tmp/chiho_win.pkl')
top = W.sort_values('p勝', ascending=False).drop_duplicates(KEY)[KEY + ['馬番']].rename(columns={'馬番': '材本命'})
fav = H[H['人気'] == 1][KEY + ['馬番', '3着内', '複払']].rename(columns={'馬番': '人1', '3着内': '人1_3', '複払': '人1複'})
R = fav.merge(top, on=KEY, how='inner'); R['食い違い'] = R['人1'] != R['材本命']
R['年'] = R['競走年月日'].str[:4].astype(int)
print('■ 1番人気の複勝（全部のレース、2021〜2025年）')
T = R[(R['年'] <= 2025) & R['人1複'].notna()]
print(T.groupby('食い違い').agg(レース=('人1', 'size'), 三着内=('人1_3', 'mean'), 複勝回収=('人1複', 'mean')).assign(
    三着内=lambda d: (d['三着内'] * 100).round(1), 複勝回収=lambda d: (d['複勝回収'] * 100).round(1)).to_string())
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
P = P.merge(R[KEY + ['食い違い', '人1_3']], on=KEY, how='left')
rows = []
for q in (1, 2, 5):
    for lab, m in (('食い違う', P['食い違い'] == True), ('食い違わない', P['食い違い'] == False)):
        S = P[(P[f'比{q}'] >= 1) & m]
        T5 = S[(S['Y'] >= 2021) & (S['Y'] <= 2025)]; S26 = S[S['Y'] == 2026]
        by = T5.groupby('Y')['ret'].mean() * 100; lo, hi = boot(T5['ret'].values, T5['日'].values)
        rows.append(dict(線=f'上位{q}%', レース=lab, 点_年=int(len(T5) / 5), 的中=round((T5['ret'] > 0).mean() * 100, 1),
                         一番人気が3着外=round((1 - T5['人1_3'].mean()) * 100, 1), 回収5年=round(T5['ret'].mean() * 100, 1), 幅=f'{lo:.0f}〜{hi:.0f}',
                         年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)), 百以上=f'{(by >= 100).sum()}/5',
                         y2026=f"{S26['ret'].mean()*100:.1f}（{len(S26)}点）"))
pd.set_option('display.width', 250)
print('\n■ 選んだ馬の複勝'); print(pd.DataFrame(rows).to_string(index=False))
