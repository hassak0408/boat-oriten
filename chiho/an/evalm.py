"""手順3の答え合わせ：見込みが線以上の馬を100円ずつ買ったときの回収（毎年作り直し）"""
import sys, numpy as np, pandas as pd
P = pd.read_pickle(sys.argv[1] if len(sys.argv) > 1 else '/tmp/chiho_pred.pkl')
P = P.sort_values(['日', '競馬場', 'レース番号', '馬番'])
def boot(d, B=3000):
    g = d.groupby('日')['ret'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    s, n = g['sum'].values, g['size'].values; out = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); out.append(s[k].sum() / n[k].sum() * 100)
    return np.percentile(out, [2.5, 97.5])
def streak(r):
    m = c = 0
    for x in r:
        c = c + 1 if x == 0 else 0; m = max(m, c)
    return m
rows = []; per = {}
days = P.groupby('Y')['日'].nunique()
for b in ('単', '複'):
    for q in (1, 2, 5):
        S = P[(P['券'] == b) & (P[f'比{q}'] >= 1)]
        if S.empty: continue
        by = S.groupby('Y').agg(点=('ret', 'size'), 回収=('ret', lambda x: round(x.mean() * 100, 1)))
        per[(b, q)] = S.groupby('Y')['ret'].agg(['sum', 'size'])
        T5 = S[(S['Y'] >= 2021) & (S['Y'] <= 2025)]
        lo, hi = boot(T5)
        S26 = S[S['Y'] == 2026]
        rows.append(dict(券='単勝' if b == '単' else '複勝', 線=f'上位{q}%', 点_年=int(T5.groupby('Y').size().mean()),
                         一日=round(len(T5) / days.loc[2021:2025].sum(), 1), 的中=round((T5['ret'] > 0).mean() * 100, 1),
                         当たり平均=round(T5.loc[T5['ret'] > 0, 'ret'].mean() * 100), 回収5年=round(T5['ret'].mean() * 100, 1),
                         幅=f'{lo:.1f}〜{hi:.1f}', 年ごと='・'.join(str(by.loc[y, '回収']) for y in range(2021, 2026) if y in by.index),
                         百以上=f"{(by.loc[2021:2025, '回収'] >= 100).sum()}/5", 外れ続き=streak(T5['ret'].values),
                         y2026=f"{round(S26['ret'].mean() * 100, 1)}（{len(S26)}点）", 人気平均=round(T5['人気'].mean(), 1)))
pd.set_option('display.width', 260)
print(pd.DataFrame(rows).to_string(index=False))
# 厳しい数え方：前の年までの通算で一番よかった形を、次の年で買う
print('\n■ 厳しい数え方（前の年までで形を選び直す）')
tot_s = tot_n = 0
for Y in range(2022, 2027):
    best = max(per, key=lambda k: per[k].loc[2021:Y - 1, 'sum'].sum() / max(1, per[k].loc[2021:Y - 1, 'size'].sum()))
    s, n = (per[best].loc[Y, 'sum'], per[best].loc[Y, 'size']) if Y in per[best].index else (0, 0)
    tot_s += s; tot_n += n
    print(Y, '選んだ形', best, '点', int(n), '回収', round(s / max(n, 1) * 100, 1))
print('通算', int(tot_n), '点', round(tot_s / max(tot_n, 1) * 100, 1))
