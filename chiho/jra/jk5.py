"""中央競馬：K5 舐められている馬（前走で発走の不利・疾病）の馬連（検証計画の同じ名前の節）。
使い方：python jk5.py 材料.pkl STORE/jra/data 見込み.pkl（jk.py TROUBLE=1 の出力）"""
import sys, glob, json, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
H = H[(H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = H.sort_values(KEY + ['単勝オッズ', '馬番']); H['人気順'] = H.groupby(KEY).cumcount() + 1
P = pd.read_pickle(sys.argv[3]); P = P.loc[:, ~P.columns.duplicated()][KEY + ['馬番', 'p3']]
H = H.merge(P, on=KEY + ['馬番'], how='left')
H['評価順'] = H.groupby(KEY)['p3'].rank(ascending=False, method='first')
pays = {}
for f in glob.glob(f'{sys.argv[2]}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        if isinstance(d.get('馬連'), list) and len(d['馬連']) == 1: pays[(a, b, int(c))] = d['馬連'][0] / 100
H['不利明け'] = (H['前不利発走'] == 1) | (H['前不利疾病'] == 1)
rows = []
for k, g in H.groupby(KEY, sort=False):
    t = g[g['不利明け']]
    if not len(t): continue
    pk = (k[0], k[1], int(k[2]))
    if pk not in pays: continue
    top2 = tuple(sorted(g.loc[g['着'] <= 2, '馬番'].astype(int)))
    if len(top2) != 2: continue
    pop = dict(zip(g['人気順'], g['馬番'].astype(int)))
    for _, h in t.iterrows():
        me = int(h['馬番'])
        partner = pop[2] if h['人気順'] == 1 else pop[1]
        a_hit = tuple(sorted((me, partner))) == top2
        others = [pop[i] for i in (1, 2, 3) if i in pop and pop[i] != me]
        b_hit = sum(tuple(sorted((me, o))) == top2 for o in others)
        rows.append(dict(年=int(k[0][:4]), 日=k[0], 人気=int(h['人気順']), オッズ=h['単勝オッズ'], 評価順=h['評価順'],
                         単勝=h['単勝オッズ'] if h['着'] == 1 else 0.0, K5a=pays[pk] if a_hit else 0.0, K5a点=1,
                         K5b=pays[pk] * b_hit, K5b点=len(others)))
R = pd.DataFrame(rows)


def boot(v, n, day, B=2000):
    x = pd.DataFrame({'d': day, 's': v, 'n': n}).groupby('d')[['s', 'n']].sum(); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['s'].values[k].sum(1) / x['n'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


out = []
for lab, pm in (('2016〜2021', R['年'] <= 2021), ('2022〜2026', R['年'] >= 2022)):
    for name, col, ncol, mask in (('単勝（参考）', '単勝', None, None), ('K5a 1番人気との馬連1点', 'K5a', 'K5a点', None), ('K5b 1〜3番人気との馬連', 'K5b', 'K5b点', None),
                                  ('K5c 評価の上位5頭のときの単勝', '単勝', None, '評価'), ('K5c 評価の上位5頭のときのK5a', 'K5a', 'K5a点', '評価')):
        X = R[pm]
        if mask == '評価': X = X[(X['評価順'] <= 5) & (X['年'] >= 2021)]
        if not len(X): continue
        n = X[ncol].values if ncol else np.ones(len(X))
        lo, hi = boot(X[col].values, n, X['日'].values)
        by = X.groupby('年').apply(lambda z: z[col].sum() / (z[ncol].sum() if ncol else len(z)) * 100, include_groups=False)
        out.append({'期間': lab, '券': name, '頭': len(X), '点': int(n.sum()), '的中': f"{(X[col] > 0).mean()*100:.1f}%",
                    '回収': f'{X[col].sum()/n.sum()*100:.1f}%（{lo:.0f}〜{hi:.0f}）', '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
pd.set_option('display.width', 220)
print(pd.DataFrame(out).to_string(index=False))
print('\n■ 人気ごとの単勝（参考）')
R['帯'] = pd.cut(R['人気'], [0, 3, 6, 9, 99], labels=['1〜3番人気', '4〜6番人気', '7〜9番人気', '10番人気以下'])
print(R.groupby(['帯', R['年'] >= 2022], observed=True).agg(頭=('単勝', 'size'), 回収=('単勝', lambda s: round(s.mean() * 100, 1))).to_string())
