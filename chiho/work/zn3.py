# ZN3：地方の市場のずれの印（ZN1 の f）の複勝（検証計画 ZN3）
import glob, numpy as np, pandas as pd
rng = np.random.default_rng(86)
ST = '/home/claude/chiho-keiba'; K = ['競馬場', '競走年月日', 'レース番号']
Z = pd.concat([pd.read_csv(f, dtype={k: str for k in K}) for f in sorted(glob.glob(f'{ST}/data/exp/nk_z2_pred_*.csv.gz'))], ignore_index=True)
Z['馬番'] = pd.to_numeric(Z['馬番'], errors='coerce').astype('Int64'); Z['人気'] = pd.to_numeric(Z['人気'], errors='coerce')
Z = Z[Z['f'].notna() & Z['人気'].notna()]
q90, q95 = Z['f'].quantile(0.9), Z['f'].quantile(0.95)
pay = {}
for f in sorted(glob.glob(f'{ST}/data/race/202[1-6]*/*payback*.csv.gz')):
    P = pd.read_csv(f, dtype=str, keep_default_na=False)
    for _, r in P.iterrows():
        k = (r['競馬場'], r['競走年月日'], r['レース番号'])
        for i in (1, 2, 3):
            b = pd.to_numeric(r.get(f'複勝組番{i}', ''), errors='coerce'); y = pd.to_numeric(str(r.get(f'複勝払戻金{i}（円）', '')).replace(',', ''), errors='coerce')
            if b == b and y == y: pay[k + (int(b),)] = float(y)
key = list(zip(Z['競馬場'], Z['競走年月日'], Z['レース番号'], Z['馬番'].astype(int)))
Z['複払'] = [pay.get(k, 0.0) for k in key]
has = set(k[:3] for k in pay); Z = Z[[k[:3] in has for k in key]].copy()      # 払戻の表があるレースだけ
Z['期'] = np.where(Z['競走年月日'] <= '20231231', '2021〜23', '2024〜26')
Z['人気帯'] = pd.cut(Z['人気'], [0, 1, 3, 6, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下']).astype(str)
print('頭', len(Z), 'レース', Z.groupby(K).ngroups, '／しきい 上位10%', round(float(q90), 3), '上位5%', round(float(q95), 3), '／複勝の払戻がある馬の割合', round(float((Z['複払'] > 0).mean()), 3))
def boot_ci(S):
    d = S['競走年月日'].values; ds = np.sort(np.unique(d)); ix = np.searchsorted(ds, d); W = rng.poisson(1.0, (1000, len(ds)))
    r = (W @ np.bincount(ix, S['複払'].values, len(ds))) / (W @ np.bincount(ix, None, len(ds))); return np.percentile(r, [2.5, 97.5])
rows = []; win = []
for band in ('1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下'):
    base = Z[Z['人気帯'] == band]
    for nm, thr in (('上位10%', q90), ('上位5%', q95)):
        S = base[base['f'] >= thr]; out = [band, nm]
        for per in ('2021〜23', '2024〜26'):
            s = S[S['期'] == per]; b = base[base['期'] == per]
            out += [len(s), s['複払'].mean(), b['複払'].mean(), (s['複払'] > 0).mean() * 100, (b['複払'] > 0).mean() * 100]
        ci = boot_ci(S); out += list(ci); rows.append(out)
        if out[3] >= 100 and out[8] >= 100 and ci[0] > 100: win.append(f'{band}×{nm}')
T = pd.DataFrame(rows, columns=['人気', 'f', '頭1', '回収1', '全部1', '複勝率1', '全部率1', '頭2', '回収2', '全部2', '複勝率2', '全部率2', '幅下', '幅上'])
print(T.round(1).to_string(index=False))
print('勝負になる帯：', win or 'なし')
