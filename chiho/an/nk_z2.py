"""地方：ZN1 市場のずれを学ぶ（検証計画 ZN1）。地方は馬ごとのオッズが無いので、市場の見込みを「人気の順×頭数ごとの、学ぶ年までの1着率」で代える。
その対数を出発点にして、今の一覧と同じ材料（N6＝強さの点数・前走の相手のその後つき。当日の人気・オッズは入れない）で、勝ち馬を当てる形で f を学ぶ。
Y年はY−1年まで（2017年から）。乱数0・1・2の平均。出力：STORE/data/exp/nk_z2_pred_年.csv.gz（f・pm・勝・人気・単勝の払戻）。
使い方：python chiho/an/nk_z2.py STORE 日付YYYYMMDD 年…"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jsoft, jk_elo, jz1
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
H, EF = jk_elo.add_elo_rel(H, KEY, ['E馬', 'E騎'])
VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
H = H[~H['予測'] & (H['年'] >= 2017)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']
H['着'] = pd.to_numeric(H['着'], errors='coerce'); H['人気'] = pd.to_numeric(H['人気'], errors='coerce')
gk = [H[k] for k in KEY]
H = H[(H['n'] >= 5) & H['人気'].groupby(gk).transform(lambda s: s.notna().all()) & (H.groupby(KEY)['勝'].transform('sum') >= 1)].copy()
H['人c'] = H['人気'].clip(upper=11).astype(int); H['頭c'] = pd.cut(H['n'], [0, 8, 10, 12, 99], labels=False)
log('人気のそろったレースの馬', len(H), '材料', len(FE3 + EF + VF))
for y in YEARS:
    tr = H[H['年'] < y].copy(); te = H[H['年'] == y].copy()
    if not len(te): continue
    T = tr.groupby(['頭c', '人c'])['勝'].agg(['sum', 'size']); T['r'] = (T['sum'] + 1) / (T['size'] + 20)      # 少し縮める
    for X in (tr, te):
        r = pd.Series(list(zip(X['頭c'], X['人c'])), index=X.index).map(T['r'].to_dict()).fillna(0.01)
        X['pm'] = r / r.groupby([X[k] for k in KEY]).transform('sum')
    F = [c for c in FE3 + EF + VF if tr[c].nunique(dropna=True) >= 2]
    ms = jz1.fit_resid(tr, F, CAT, log=log)
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', 'pm', '単', '五場走数']].copy()
    o['f'] = jz1.predict(ms, te, F)
    w = o['勝'] == 1; e = o['pm'] * np.exp(o['f']); pz = e / e.groupby([o[k] for k in KEY]).transform('sum')
    log(y, '年 f の標準偏差', round(float(o['f'].std()), 4), '1着の当て分け 人気の順だけ', round(float(-np.log(o.loc[w, 'pm']).mean()), 4), '→ f を掛けた', round(float(-np.log(pz[w]).mean()), 4))
    os.makedirs(f'{store}/data/exp', exist_ok=True)
    o.to_csv(f'{store}/data/exp/nk_z2_pred_{y}.csv.gz', index=False)
log('できた')
