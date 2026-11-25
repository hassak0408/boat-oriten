"""地方：NP1（検証計画「地方の血統を足す（NP1）」）。nk_m6.py と同じ作り方で、順を学ぶモデルの材料を「今（EV）」と「今＋血統」の2つにする。
足す血統の材料（前の日まで・その馬自身の走りは除く・ならし k=20）：父・母父の産駒の 距離の帯ごと・このデータで初めて走る時・全体（自分を除く）の勝率と3着内率、母の産駒（兄弟）の勝率・3着内率。
出力：STORE/data/exp/nk_np1_pred_年.csv.gz（pl_1_・pl_3_ の base・ped）。使い方：python chiho/an/nk_np1.py STORE 日付YYYYMMDD 年…"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jsoft, jk_elo
store, day = sys.argv[1], sys.argv[2]
YEARS = [int(v) for v in sys.argv[3:]] or list(range(2021, 2027))
os.environ['CHIHO_EV'] = '1'
src = open(f'{HERE}/pipe.py', encoding='utf-8').read()
head = src[:src.index("Y = int(today[:4])")]
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}
sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H, KEY, log, NFIX, FEATS, NEW, EXTRA3, USE3, BW = (g[k] for k in ('H', 'KEY', 'log', 'NFIX', 'FEATS', 'NEW', 'EXTRA3', 'USE3', 'BW'))
if not g['SOFT']: raise SystemExit('LightGBM が無い')
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW] + list(g['JF']) + ([c for c in g['SF'] if c in H] if NFIX.get('展開の材料') else [])
FE3 = list(dict.fromkeys(c for c in FE3 if c in H))
CAT = ['場c', '馬場c', '天候c', '性c']
W3 = NFIX['木']
H, EF = jk_elo.add_elo_rel(H, KEY, ['E馬', 'E騎'])
VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
need = ['父馬名', '母馬名', '母父馬名', '馬', '日', '勝', '3着内', '走数', '距離', '予測']
miss = [c for c in need if c not in H.columns]
if miss: raise SystemExit(f'血統の材料に要る列が無い：{miss}')

# ---- 血統の材料 ----
X = H[need].copy().reset_index(drop=True); H = H.reset_index(drop=True)
for c in ('父馬名', '母馬名', '母父馬名'): X[c] = X[c].astype(str).str.strip().replace({'': np.nan, 'nan': np.nan})
X['距帯'] = pd.cut(pd.to_numeric(X['距離'], errors='coerce'), [0, 1000, 1300, 1600, 1900, 9999], labels=['a', 'b', 'c', 'd', 'e']).astype(str)
X['母'] = X['母馬名'] + '|' + X['母父馬名'].fillna('')
ok = ~X['予測'].astype(bool); first = X['走数'] == 0
k = 20; m1, m3 = X.loc[ok, '勝'].mean(), X.loc[ok, '3着内'].mean(); f1, f3 = X.loc[ok & first, '勝'].mean(), X.loc[ok & first, '3着内'].mean()
def cum(keys, contrib):
    """keys の値ごとに、contrib の行の（数・勝ち・3着内）を、その行の日より前の日まで足したもの"""
    kk = keys.fillna('__無__').astype(str)
    Z = pd.DataFrame({'k': kk[contrib], '日': X.loc[contrib, '日'], 'n': 1, 'w': X.loc[contrib, '勝'], 't': X.loc[contrib, '3着内']})
    dd = Z.groupby(['k', '日'])[['n', 'w', 't']].sum().reset_index().sort_values(['日'])
    dd[['cn', 'cw', 'ct']] = dd.groupby('k')[['n', 'w', 't']].cumsum().values
    Q = pd.DataFrame({'k': kk, '日': X['日']}).reset_index().sort_values('日')
    M = pd.merge_asof(Q, dd[['k', '日', 'cn', 'cw', 'ct']], on='日', by='k', allow_exact_matches=False).set_index('index').sort_index()
    out = M[['cn', 'cw', 'ct']].fillna(0).values
    out[keys.isna().values] = 0
    return out
PF = []
def rates(name, keys, contrib, b1, b3, own=True):
    c = cum(keys, contrib)
    if own: c = c - cum(X['馬'].astype(str) + '#' + keys.astype(str), contrib)
    n, w, t = c[:, 0], c[:, 1], c[:, 2]
    H[name + '数'] = n; H[name + '勝率'] = (w + k * b1) / (n + k); H[name + '3率'] = (t + k * b3) / (n + k)
    for s in ('数', '勝率', '3率'): H.loc[keys.isna().values, name + s] = np.nan
    PF.extend([name + '数', name + '勝率', name + '3率'])
for ent, pre in (('父馬名', 'p父'), ('母父馬名', 'p母父')):
    rates(pre + '全', X[ent], ok, m1, m3)
    rates(pre + '距', X[ent].where(X[ent].isna(), X[ent] + '|' + X['距帯']), ok, m1, m3)
    rates(pre + '初', X[ent], ok & first, f1, f3, own=False)
rates('p母', X['母'].where(X['母馬名'].notna()), ok, m1, m3)
log('血統の材料', len(PF), '父のある行', round(float(X['父馬名'].notna().mean()), 3), '母のある行', round(float(X['母馬名'].notna().mean()), 3),
    '兄弟の数が1以上', round(float((H['p母数'] > 0).mean()), 3))

if os.environ.get('NP1_DRY'):      # 手元での試し：材料だけ作って様子を出して終わる
    A = H[~H['予測'] & (H['年'] >= 2021)]; print(A[PF].describe().T[['count', 'mean', 'min', 'max']].round(3).to_string()); raise SystemExit(0)
H = H[~H['予測'] & (H['年'] >= 2017)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']
H['着'] = pd.to_numeric(H['着'], errors='coerce')
for y in YEARS:
    tr = H[H['年'] < y]; te = H[H['年'] == y]
    if not len(te): continue
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', '五場走数', '走数']].copy()
    F = [c for c in FE3 if tr[c].nunique(dropna=True) >= 2] + EF + VF
    P = [c for c in PF if tr[c].nunique(dropna=True) >= 2]
    for vn, FF in (('base', F), ('ped', F + P)):
        o['pl_1_' + vn], o['pl_3_' + vn] = jsoft.predict(jsoft.fit(tr, FF, CAT, wt=tuple(NFIX['重み']), params=W3), te, FF)
        w = te['勝'].values == 1
        log(y, '年', vn, '材料', len(FF), '1着の当て分け（そのまま）', round(float(-np.log(np.clip(o['pl_1_' + vn].values[w], 1e-9, 1)).mean()), 4))
    os.makedirs(f'{store}/data/exp', exist_ok=True)
    o.to_csv(f'{store}/data/exp/nk_np1_pred_{y}.csv.gz', index=False)
log('できた')
