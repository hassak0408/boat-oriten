# ZN5：地方のかなり来やすい型（f 上位5%・4〜9番人気）を軸に、1番人気・2番人気と組むワイド（検証計画 ZN5）
import glob, numpy as np, pandas as pd
rng = np.random.default_rng(87)
ST = '/home/claude/chiho-keiba'; K = ['競馬場', '競走年月日', 'レース番号']
Z = pd.concat([pd.read_csv(f, dtype={k: str for k in K}) for f in sorted(glob.glob(f'{ST}/data/exp/nk_z2_pred_*.csv.gz'))], ignore_index=True)
Z['馬番'] = pd.to_numeric(Z['馬番'], errors='coerce'); Z['人気'] = pd.to_numeric(Z['人気'], errors='coerce')
q95 = Z['f'].quantile(0.95)
W = {}
for f in sorted(glob.glob(f'{ST}/data/race/202[1-6]*/*payback*.csv.gz')):
    P = pd.read_csv(f, dtype=str, keep_default_na=False)
    for _, r in P.iterrows():
        k = (r['競馬場'], r['競走年月日'], r['レース番号']); d = {}
        for i in (1, 2, 3):
            a, b = pd.to_numeric(r.get(f'ワイド組番{i}馬番1', ''), errors='coerce'), pd.to_numeric(r.get(f'ワイド組番{i}馬番2', ''), errors='coerce')
            y = pd.to_numeric(str(r.get(f'ワイド払戻金{i}（円）', '')).replace(',', ''), errors='coerce')
            if a == a and b == b and y == y: d[frozenset((int(a), int(b)))] = float(y)
        if d: W[k] = d
Z = Z[[ (a, b, c) in W for a, b, c in zip(Z['競馬場'], Z['競走年月日'], Z['レース番号'])]].copy()
print('ワイドの払戻があるレース', Z.groupby(K).ngroups, '／しきい 上位5%', round(float(q95), 3))
fav = Z[Z['人気'] == 1].set_index(K)['馬番'].to_dict(); sec = Z[Z['人気'] == 2].set_index(K)['馬番'].to_dict()
S = Z[(Z['f'] >= q95) & Z['人気'].between(4, 9)].copy()
rows = []
for _, h in S.iterrows():
    k = (h['競馬場'], h['競走年月日'], h['レース番号']); w = W[k]; b = int(h['馬番'])
    f1, f2 = fav.get(k), sec.get(k)
    if f1 != f1 or f2 != f2 or f1 is None or f2 is None: continue
    pa = w.get(frozenset((b, int(f1))), 0.0); pb = w.get(frozenset((b, int(f2))), 0.0)
    rows.append((h['競走年月日'], int(h['人気']), pa, pb))
R = pd.DataFrame(rows, columns=['日', '人気', 'a', 'b']); R['c'] = (R['a'] + R['b']) / 2      # (c) は2点の1点あたり
R['期'] = np.where(R['日'] <= '20231231', '2021〜23', '2024〜26')
print('選んだ馬', len(R), '（', R['期'].value_counts().to_dict(), '）')
def ci(x, d):
    ds = np.sort(np.unique(d)); ix = np.searchsorted(ds, d); Wt = rng.poisson(1.0, (1000, len(ds)))
    return np.percentile((Wt @ np.bincount(ix, x, len(ds))) / (Wt @ np.bincount(ix, None, len(ds))), [2.5, 97.5])
win = []
for col, nm in (('a', '(a) 1番人気と'), ('b', '(b) 2番人気と'), ('c', '(c) 1・2番人気と2点')):
    r1 = R.loc[R['期'] == '2021〜23', col].mean(); r2 = R.loc[R['期'] == '2024〜26', col].mean(); c = ci(R[col].values, R['日'].values)
    h1 = (R.loc[R['期'] == '2021〜23', col] > 0).mean() * 100; h2 = (R.loc[R['期'] == '2024〜26', col] > 0).mean() * 100
    print(f'{nm}：回収 {r1:.1f}%・{r2:.1f}%（合わせた95%幅 {c[0]:.1f}〜{c[1]:.1f}%）／当たった率 {h1:.1f}%・{h2:.1f}%')
    for lo, hi in ((4, 6), (7, 9)):
        g = R[R['人気'].between(lo, hi)]
        print(f'    数字だけ {lo}〜{hi}番人気：{len(g)}頭・回収 {g.loc[g["期"] == "2021〜23", col].mean():.1f}%・{g.loc[g["期"] == "2024〜26", col].mean():.1f}%')
    if r1 >= 100 and r2 >= 100 and c[0] > 100: win.append(nm)
print('勝負になる形：', win or 'なし')
