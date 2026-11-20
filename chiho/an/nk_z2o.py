"""地方：ほかの場の市場のずれ（検証計画 OV1）。nk_z2.py と同じ作り方（Y年はY−1年まで（2017年から）、乱数0・1・2の平均、材料も同じ）で、
5場の代わりに指定した場の f を学ぶ。データは data_all（全部の場）から、その場の分だけを一時の置き場に写して使う（2026年10月まで）。
「今日」は 2026年11月の、その場の最初の開催日（その日の行は学ぶのにも確かめにも使わない）。全部の場の前の成績（hist_all）の「5場」は、指定した場に置きかえる。
出力：STORE/data/exp/nk_z2o_タグ_年.csv.gz（f・pm・勝・人気・単勝の払戻・先頭率5・先行率5・他の逃げ型）。
使い方：python chiho/an/nk_z2o.py STORE まとまりの番号 年…（試しの仕組みの引数は数字だけなので、場は番号で選ぶ。タグは英字：保存の手順が日本語のファイル名を扱えないため）"""
import os, sys, glob, shutil, tempfile, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
GROUPS = {1: (['名古屋', '金沢'], 'tokai'), 2: (['佐賀', '高知'], 'kyushikoku'), 3: (['門別'], 'monbetsu'), 4: (['大井'], 'ooi'), 5: (['川崎', '船橋', '浦和'], 'nankan')}
store = sys.argv[1]; PL, TAG = GROUPS[int(sys.argv[2])]
YEARS = [int(v) for v in sys.argv[3:]] or list(range(2021, 2027))
tmp = tempfile.mkdtemp(); n_rows = 0
for d in sorted(glob.glob(f'{store}/data_all/race/2*')):
    b = os.path.basename(d)
    if b >= '202611': continue
    os.makedirs(f'{tmp}/race/{b}')
    for f in glob.glob(f'{d}/*.csv.gz'):
        X = pd.read_csv(f, dtype=str, keep_default_na=False)
        if '競馬場' in X.columns: X = X[X['競馬場'].isin(PL)]
        if 'horselist' in f: n_rows += len(X)
        X.to_csv(f'{tmp}/race/{b}/{os.path.basename(f)}', index=False, compression='gzip')
    if os.path.exists(f'{d}/done.json'): shutil.copy(f'{d}/done.json', f'{tmp}/race/{b}/done.json')
RL = pd.read_csv(glob.glob(f'{store}/data_all/race/202611/*racelist*')[0], dtype=str, keep_default_na=False); HL = pd.read_csv(glob.glob(f'{store}/data_all/race/202611/*horselist*')[0], dtype=str, keep_default_na=False)
RL = RL[RL['競馬場'].isin(PL)]; HL = HL[HL['競馬場'].isin(PL)]; day = sorted(set(HL['競走年月日']))[0]
os.makedirs(f'{tmp}/daily/{day}')
RL[RL['競走年月日'] == day].to_csv(f'{tmp}/daily/{day}/race_racelist.csv.gz', index=False, compression='gzip')
HL[HL['競走年月日'] == day].to_csv(f'{tmp}/daily/{day}/race_horselist.csv.gz', index=False, compression='gzip')
print('場', PL, 'タグ', TAG, '馬の行（2026年10月まで）', n_rows, '今日', day, flush=True)
os.environ['CHIHO_DATA'] = tmp; os.environ['CHIHO_EV'] = '1'
import hist_all; hist_all.FIVE = list(PL)
import jsoft, jk_elo, jz1
src = open(f'{HERE}/pipe.py', encoding='utf-8').read()
head = src[:src.index("Y = int(today[:4])")]
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}
sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H, KEY, log, NFIX, FEATS, NEW, EXTRA3, USE3, BW = (g[k] for k in ('H', 'KEY', 'log', 'NFIX', 'FEATS', 'NEW', 'EXTRA3', 'USE3', 'BW'))
if not g['SOFT']: raise SystemExit('LightGBM が無い')
if not USE3: raise SystemExit('全部の場の前の成績が作れなかった')
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW] + list(g['JF']) + ([c for c in g['SF'] if c in H] if NFIX.get('展開の材料') else [])
FE3 = list(dict.fromkeys(c for c in FE3 if c in H))
CAT = ['場c', '馬場c', '天候c', '性c']
H, EF = jk_elo.add_elo_rel(H, KEY, ['E馬', 'E騎'])
VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
H = H[~H['予測'] & (H['年'] >= 2017) & H['競馬場'].isin(PL)].copy()
H['年月日'] = H['競走年月日']; H['場'] = H['競馬場']; H['R'] = H['レース番号']
H['着'] = pd.to_numeric(H['着'], errors='coerce'); H['人気'] = pd.to_numeric(H['人気'], errors='coerce')
gk = [H[k] for k in KEY]
H = H[(H['n'] >= 5) & H['人気'].groupby(gk).transform(lambda s: s.notna().all()) & (H.groupby(KEY)['勝'].transform('sum') >= 1)].copy()
H['人c'] = H['人気'].clip(upper=11).astype(int); H['頭c'] = pd.cut(H['n'], [0, 8, 10, 12, 99], labels=False)
log('人気のそろったレースの馬', len(H), '材料', len(FE3 + EF + VF), '場ごと', H['競馬場'].value_counts().to_dict())
OUT = [c for c in ('先頭率5', '先行率5', '他の逃げ型') if c in H.columns]
for y in YEARS:
    tr = H[H['年'] < y].copy(); te = H[H['年'] == y].copy()
    if not len(te): continue
    T = tr.groupby(['頭c', '人c'])['勝'].agg(['sum', 'size']); T['r'] = (T['sum'] + 1) / (T['size'] + 20)
    for X in (tr, te):
        r = pd.Series(list(zip(X['頭c'], X['人c'])), index=X.index).map(T['r'].to_dict()).fillna(0.01)
        X['pm'] = r / r.groupby([X[k] for k in KEY]).transform('sum')
    F = [c for c in FE3 + EF + VF if tr[c].nunique(dropna=True) >= 2]
    ms = jz1.fit_resid(tr, F, CAT, log=log)
    o = te[KEY + ['馬番', '年', 'n', '勝', '3着内', '人気', 'pm', '単', '五場走数'] + OUT].copy()
    o['f'] = jz1.predict(ms, te, F)
    w = o['勝'] == 1; e = o['pm'] * np.exp(o['f']); pz = e / e.groupby([o[k] for k in KEY]).transform('sum')
    log(y, '年 f の標準偏差', round(float(o['f'].std()), 4), '1着の当て分け 人気の順だけ', round(float(-np.log(o.loc[w, 'pm']).mean()), 4), '→ f を掛けた', round(float(-np.log(pz[w]).mean()), 4))
    os.makedirs(f'{store}/data/exp', exist_ok=True)
    o.to_csv(f'{store}/data/exp/nk_z2o_{TAG}_{y}.csv.gz', index=False)
log('できた')
