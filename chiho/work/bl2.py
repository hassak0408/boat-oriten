# BL2：地方で、AIは窓口のオッズに足せる情報を持っているか（検証計画 BL2）
import glob, json, os, numpy as np, pandas as pd
from scipy.optimize import minimize
rng = np.random.default_rng(84)
ST = '/home/claude/chiho-keiba'
import sys
USE_P1 = len(sys.argv) > 1 and sys.argv[1] == 'p1'   # 主は一覧の「一着」（%）。p1 は 11/17〜の数字だけ
rows = []
for f in sorted(glob.glob(f'{ST}/data/picks/2026????.json')):
    day = os.path.basename(f)[:8]; snap = f'{ST}/data/daily/{day}/odds_snap.csv.gz'; hl = f'{ST}/data/daily/{day}/race_horselist.csv.gz'
    if not (os.path.exists(snap) and os.path.exists(hl)): continue
    P = json.load(open(f, encoding='utf-8'))
    if USE_P1 and 'p1' not in P['レース'][0]['馬'][0]: continue
    S = pd.read_csv(snap, dtype=str); S = S[S['賭式'] == '単勝'].copy(); S['分'] = pd.to_numeric(S['発走まで分'], errors='coerce'); S['o'] = pd.to_numeric(S['オッズ'], errors='coerce')
    S = S[S['分'] >= 1]
    H = pd.read_csv(hl, dtype=str); H['着'] = pd.to_numeric(H['着順'], errors='coerce')
    for r in P['レース']:
        pl, rn = r['場'], int(r['R'])
        s = S[(S['競馬場'] == pl) & (pd.to_numeric(S['レース番号'], errors='coerce') == rn)]
        if s.empty: continue
        last = s[s['取得'] == s['取得'].max()]; od = dict(zip(pd.to_numeric(last['番号1'], errors='coerce').astype(int), last['o']))
        h = H[(H['競馬場'] == pl) & (pd.to_numeric(H['レース番号'], errors='coerce') == rn)]; win = dict(zip(pd.to_numeric(h['馬番'], errors='coerce'), h['着'] == 1))
        for x in r['馬']:
            o = od.get(int(x['馬番']));
            if o is None or not (o > 0): continue
            rows.append((day, pl, rn, int(x['馬番']), (float(x['p1']) if USE_P1 else max(float(x.get('一着', 0) or 0), 0.5) / 100), 1.0 / o, bool(win.get(int(x['馬番']), False)), float(last['分'].iloc[0])))
D = pd.DataFrame(rows, columns=['日', '場', 'R', '馬番', 'ai', 'mk', '勝', '分'])
K = ['日', '場', 'R']
D = D[D.groupby(K)['勝'].transform('sum') == 1].copy()
for c in ('ai', 'mk'): D[c] = D[c].clip(lower=1e-6); D[c] = D[c] / D.groupby(K)[c].transform('sum')
D = D.sort_values(K + ['馬番']).reset_index(drop=True); D['_r'] = D.groupby(K).ngroup()
days = sorted(D['日'].unique()); grp = {d: i % 2 for i, d in enumerate(days)}; D['組'] = D['日'].map(grp)
print('日', len(days), f'（{days[0]}〜{days[-1]}）', 'レース', D['_r'].nunique(), '頭', len(D), '／場', D.drop_duplicates(K)['場'].value_counts().to_dict(), '／オッズを取った時刻（発走まで分）の中ほど', round(float(D.drop_duplicates(K)['分'].median()), 1))
def prep(S):
    idx = np.flatnonzero(np.r_[True, S['_r'].values[1:] != S['_r'].values[:-1]]); return np.c_[np.log(S['ai'].values), np.log(S['mk'].values)], idx, S['勝'].values
def lq(th, X, idx):
    u = X @ th; rep = np.diff(np.append(idx, len(u))); mm = np.maximum.reduceat(u, idx); s_ = np.add.reduceat(np.exp(u - np.repeat(mm, rep)), idx); return u - np.repeat(mm + np.log(s_), rep)
def nll(th, X, idx, y): return -lq(th, X, idx)[y].sum() / len(idx)
def fit(S): X, idx, y = prep(S); return minimize(nll, np.array([0.5, 0.5]), args=(X, idx, y), method='L-BFGS-B').x
ok = []
for a, b in ((0, 1), (1, 0)):
    th = fit(D[D['組'] == a]); T = D[D['組'] == b]; X, idx, y = prep(T); dd = T['日'].values[idx]
    lb = -lq(th, X, idx)[y]; lm = -lq(np.array([0.0, 1.0]), X, idx)[y]; la = -lq(np.array([1.0, 0.0]), X, idx)[y]
    ds = np.sort(np.unique(dd)); ix = np.searchsorted(ds, dd); W = rng.poisson(1.0, (1000, len(ds)))
    diff = (W @ np.bincount(ix, lb - lm, len(ds))) / (W @ np.bincount(ix, None, len(ds))); ci = np.percentile(diff, [2.5, 97.5])
    print(f'組{a}で決めて組{b}に当てる（{len(ds)}日・{len(idx)}レース）：α {th[0]:.3f}・β {th[1]:.3f}／AIだけ {la.mean():.4f}・人気だけ {lm.mean():.4f}・合わせて {lb.mean():.4f}（人気だけとの差 {lb.mean() - lm.mean():+.4f}、95%幅 {ci[0]:+.4f}〜{ci[1]:+.4f}）')
    ok.append(lb.mean() < lm.mean() and ci[1] < 0)
print('判断：', '地方では AI は窓口のオッズに足せる' if all(ok) else 'この日数では言えない')
th = fit(D); print('全部の日で決めた α・β', np.round(th, 3))
