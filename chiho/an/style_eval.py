"""脚質の買い方 F1・F2・F3 の答え合わせ（検証計画「脚質：前に行ける馬」）"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
T = pd.read_pickle('/tmp/chiho_style.pkl')
T['順頭'] = T.groupby(KEY)['p先頭'].rank(ascending=False, method='first')
T['順行'] = T.groupby(KEY)['p先行'].rank(ascending=False, method='first')
sec = T[T['順頭'] == 2][KEY + ['p先頭']].rename(columns={'p先頭': '2番目'})
T = T.merge(sec, on=KEY, how='left')
T['F1'] = T['順頭'] == 1
T['F2'] = T['F1'] & (T['p先頭'] >= 0.5) & (T['2番目'] < 0.2)
T['F3'] = (T['順行'] <= 2) & (T['人気'] >= 4)
T['人気帯'] = pd.cut(T['人気'], [0, 3, 6, 16], labels=['1〜3', '4〜6', '7〜'])
def boot(s, d, B=3000):
    g = pd.DataFrame({'d': d, 's': s}).dropna().groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0); o = []
    for _ in range(B):
        k = rng.integers(0, len(g), len(g)); o.append(g['sum'].values[k].sum() / g['size'].values[k].sum() * 100)
    return np.percentile(o, [2.5, 97.5])
rows = []
for f, nm in (('F1', '逃げ予想'), ('F2', '単騎の逃げ予想'), ('F3', '前に行く人気薄')):
    for band in [None, '1〜3', '4〜6', '7〜']:
        S = T[T[f] & ((T['人気帯'] == band) if band else True)]
        for bet, col in (('単勝', '単払'), ('複勝', '複払')):
            D = S[S[col].notna()]; T5 = D[(D['年'] >= 2021) & (D['年'] <= 2025)]; D26 = D[D['年'] == 2026]
            if len(T5) < 50: continue
            by = T5.groupby('年')[col].mean() * 100; lo, hi = boot(T5[col].values, T5['日'].values)
            rows.append(dict(形=nm, 人気=band or '全部', 券=bet, 点_年=int(len(T5) / 5), 実際に先頭=round(T5['先頭'].mean() * 100, 1),
                             的中=round((T5[col] > 0).mean() * 100, 1), 回収5年=round(T5[col].mean() * 100, 1), 幅=f'{lo:.0f}〜{hi:.0f}',
                             年ごと='・'.join(f'{by.get(y):.0f}' for y in range(2021, 2026)), 百以上=f'{(by >= 100).sum()}/5',
                             y2026=round(D26[col].mean() * 100, 1)))
pd.set_option('display.width', 250); print(pd.DataFrame(rows).to_string(index=False))
# 同じ人気の馬とくらべて、どれだけ上か（人気の混ざり方を除く）
print('\n■ 同じ年・同じ人気の馬との差（2021〜2025年）')
base = T[T['人気'].notna()].groupby(['年', '人気'])[['単払', '複払']].mean()
for f, nm in (('F1', '逃げ予想'), ('F2', '単騎の逃げ予想'), ('F3', '前に行く人気薄')):
    S = T[T[f] & T['人気'].notna() & (T['年'] <= 2025)]
    b = base.reindex(list(zip(S['年'], S['人気'])))
    print(f"  {nm}：単勝 {S['単払'].mean()*100:.1f}%（同じ人気 {b['単払'].mean()*100:.1f}%）  複勝 {S['複払'].mean()*100:.1f}%（同じ人気 {b['複払'].mean()*100:.1f}%）  人気の平均 {S['人気'].mean():.1f}")
