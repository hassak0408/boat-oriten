"""脚質と複勝の見込みを重ねる（検証計画「脚質と複勝の見込みを重ねる」）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
P = pd.read_pickle('/tmp/chiho_pred.pkl'); P = P[P['券'] == '複'][KEY + ['馬番', '比1', '比2', '比5']]
T = pd.read_pickle('/tmp/chiho_style.pkl')
T['順行'] = T.groupby(KEY)['p先行'].rank(ascending=False, method='first')
D = T.merge(P, on=KEY + ['馬番'], how='inner')
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
rows = []
for q in (1, 2, 5):
    for lab, m in (('前に行ける（2位以内）', D['順行'] <= 2), ('前に行けない', D['順行'] > 2)):
        S = D[(D[f'比{q}'] >= 1) & m]
        for bet, col in (('複勝', '複払'), ('単勝', '単払')):
            X = S[S[col].notna()]; T5 = X[(X['年'] >= 2021) & (X['年'] <= 2025)]; X26 = X[X['年'] == 2026]
            if len(T5) < 30: continue
            by = T5.groupby('年')[col].mean() * 100; lo, hi = boot(T5[col].values, T5['日'].values)
            rows.append(dict(線=f'上位{q}%', 脚質=lab, 券=bet, 点_年=round(len(T5) / 5), 人気平均=round(T5['人気'].mean(), 1),
                             実際に3番手以内=round(T5['先行'].mean() * 100, 1), 的中=round((T5[col] > 0).mean() * 100, 1),
                             回収5年=round(T5[col].mean() * 100, 1), 幅=f'{lo:.0f}〜{hi:.0f}',
                             年ごと='・'.join(f'{by.get(y, np.nan):.0f}' for y in range(2021, 2026)), 百以上=f'{(by >= 100).sum()}/5',
                             y2026=f"{X26[col].mean()*100:.1f}（{len(X26)}点）"))
pd.set_option('display.width', 250); print(pd.DataFrame(rows).to_string(index=False))
