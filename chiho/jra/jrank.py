"""中央競馬：J3 人気の組み合わせごとの馬連・馬単（検証計画「中央：値段がずれる所を探す」）。
8頭以上のレースで、毎レース全部の升目（人気の組）を100円ずつ買ったとして、升目ごとの回収を出す。選ぶ期間 2016〜2021年、確かめる期間 2022〜2026年。
使い方：python jrank.py 材料.pkl STORE/jra/data"""
import sys, glob, json, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1])
H = H[~H['予測'] & (H['合わない'] == 0) & (H['n'] >= 8)].copy()
H = H[H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())]
H = H.sort_values(KEY + ['単勝オッズ', '馬番'])
H['人気順'] = H.groupby(KEY).cumcount() + 1
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        if isinstance(d.get('馬連'), list) and len(d['馬連']) == 1 and isinstance(d.get('馬単'), list) and len(d['馬単']) == 1:
            pays[(a, b, int(c))] = (d['馬連'][0] / 100, d['馬単'][0] / 100)
rows = []
for k, g in H.groupby(KEY, sort=False):
    pk = (k[0], k[1], int(k[2]))
    if pk not in pays: continue
    w1 = g.loc[g['着'] == 1, '人気順'].tolist(); w2 = g.loc[g['着'] == 2, '人気順'].tolist()
    if len(w1) != 1 or len(w2) != 1: continue
    rows.append(dict(年=int(k[0][:4]), 日=k[0], a=w1[0], b=w2[0], 馬連=pays[pk][0], 馬単=pays[pk][1]))
R = pd.DataFrame(rows)
print('レース', len(R), '（2016〜2021年', (R['年'] <= 2021).sum(), '・2022〜2026年', (R['年'] >= 2022).sum(), '）')


def boot(hit_pay, day, B=2000):
    x = pd.DataFrame({'d': day, 's': hit_pay}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


out = []
for kind, cells in (('馬連', [(i, j) for i in range(1, 9) for j in range(i + 1, 9)]), ('馬単', [(i, j) for i in range(1, 7) for j in range(1, 7) if i != j])):
    for i, j in cells:
        if kind == '馬連': hit = ((R['a'] == i) & (R['b'] == j)) | ((R['a'] == j) & (R['b'] == i))
        else: hit = (R['a'] == i) & (R['b'] == j)
        pay = np.where(hit, R[kind], 0.0)
        rec = {'券': kind, '組（人気）': f'{i}-{j}' if kind == '馬連' else f'{i}→{j}'}
        for lab, m in (('前', R['年'] <= 2021), ('後', R['年'] >= 2022)):
            rec[f'的中{lab}'] = round(hit[m].mean() * 100, 2); rec[f'回収{lab}'] = round(pay[m].mean() * 100, 1)
        if rec['回収前'] >= 100:
            lo, hi = boot(pay[R['年'] >= 2022], R.loc[R['年'] >= 2022, '日'].values); rec['後の95%幅'] = f'{lo:.0f}〜{hi:.0f}'
        out.append(rec)
O = pd.DataFrame(out)
pd.set_option('display.width', 200); pd.set_option('display.max_rows', 100)
for kind in ('馬連', '馬単'):
    X = O[O['券'] == kind].sort_values('回収前', ascending=False)
    print(f'\n■ {kind}（前＝2016〜2021年、後＝2022〜2026年。回収の高い順）'); print(X.drop(columns=['券']).to_string(index=False))
