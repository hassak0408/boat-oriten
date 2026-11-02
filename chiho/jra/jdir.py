"""中央競馬：J6 頭とヒモの向き（馬単）（検証計画の同じ名前の節）。1番人気の勝ちきり度（モデルの1着の見込み÷3着内の見込み）で、馬単の表と裏を選ぶ。
使い方：python jdir.py 見込み.pkl（jeval.py の出力） STORE/jra/data"""
import sys, glob, json, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1]); D = D.loc[:, ~D.columns.duplicated()]
D = D[(D['n'] >= 5)].copy()
D = D[D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())]
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
D['勝ちきり度'] = D['p1'] / D['p3']
D = D.sort_values(KEY + ['単勝オッズ', '馬番']); D['人気順'] = D.groupby(KEY).cumcount() + 1
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        if isinstance(d.get('馬単'), list) and len(d['馬単']) == 1: pays[(a, b, int(c))] = d['馬単'][0] / 100
rows = []
for k, g in D.groupby(KEY, sort=False):
    pk = (k[0], k[1], int(k[2]))
    if pk not in pays: continue
    f = g[g['人気順'] == 1].iloc[0]
    w1 = g.loc[g['着'] == 1, '人気順'].tolist(); w2 = g.loc[g['着'] == 2, '人気順'].tolist()
    if len(w1) != 1 or len(w2) != 1: continue
    a, b = w1[0], w2[0]; pay = pays[pk]
    rows.append(dict(年=int(k[0][:4]), 日=k[0], 帯=('2.0以下' if f['単勝オッズ'] <= 2.0 else '2.1〜3.5' if f['単勝オッズ'] <= 3.5 else '3.6以上'), 勝ちきり度=f['勝ちきり度'],
                     表=pay if (a == 1 and b in (2, 3, 4)) else 0.0, 裏=pay if (b == 1 and a in (2, 3, 4)) else 0.0))
R = pd.DataFrame(rows)
sel = R['年'] <= 2023
lo = R[sel].groupby('帯')['勝ちきり度'].quantile(1 / 3); hi = R[sel].groupby('帯')['勝ちきり度'].quantile(2 / 3)
R['向き'] = np.where(R['勝ちきり度'] >= R['帯'].map(hi), '頭向き', np.where(R['勝ちきり度'] <= R['帯'].map(lo), 'ヒモ向き', '中'))


def boot(v, day, B=2000):
    x = pd.DataFrame({'d': day, 's': v}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


out = []
for lab, pm in (('2021〜2023', sel), ('2024〜2026', ~sel)):
    for muki in ('頭向き', '中', 'ヒモ向き', '全部'):
        X = R[pm] if muki == '全部' else R[pm & (R['向き'] == muki)]
        for col, name in (('表', '1番人気→2〜4番人気（3点）'), ('裏', '2〜4番人気→1番人気（3点）')):
            v = X[col].values / 3
            a, b = boot(v, X['日'].values)
            out.append({'期間': lab, '1番人気': muki, '券': name, 'レース': len(X), '的中': f"{(X[col] > 0).mean()*100:.1f}%", '回収': f'{v.mean()*100:.1f}%（{a:.0f}〜{b:.0f}）'})
pd.set_option('display.width', 200)
print(pd.DataFrame(out).to_string(index=False))
