"""地方競馬の来そうな馬（毎朝の一覧。検証計画「来そうな馬の候補」）。
STORE（非公開のリポジトリ）の data/race（月ごと）と data/daily/日付（毎日の記録）から、今日の出馬表の馬ごとに
3着内・1着の見込みと脚質の予想を出し、STORE/data/picks/日付.json と 日付.txt に置く。
- モデルは毎回作る（Y年はY−1年まで、2017年から）。材料はレース前に分かるものだけで、人気・オッズは使わない。
- 1着と3着内は、レースの中で1〜3着の順を学ぶやり方（jsoft.py、中央と同じ作り方）とHGBの3着内（乱数0・1・2の平均）を合わせる（検証計画「地方：精度を上げる」。値は nar_fix.json）。
  LightGBM が無いときは前のやり方（HGB 乱数0の1着・3着内）に戻す。脚質（先頭・先行）は前のまま。
- 1着の見込みは、場×枠の群ごとの値を掛けて直す（検証計画 W1。値は nar_fix.json の「枠の付け直し」）。
- 朝の出馬表には馬体重が無いレースがあるので、馬体重は使わない。材料は cand3.py の「朝3」と同じ（B2＋全部の場の前の成績＝B3）。
- 全部の場の前の成績は STORE/data_all（環境変数 CHIHO_ALL）から作る。
- 月ごとのデータより後の日は、毎日の記録の最後の分（結果入り）で埋める。
使い方：python chiho/an/pipe.py STORE [日付YYYYMMDD]   （環境変数 CHIHO_DATA が無ければ STORE/data を読む）"""
import os, sys, glob, json, time, datetime as dt, numpy as np, pandas as pd
from itertools import combinations
store = sys.argv[1]
os.environ.setdefault('CHIHO_DATA', f'{store}/data')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feat, feat2, feat3, hist_all
from feat import FEATS, KEY, add_cats, corner_pos
from feat2cols import NEW
from feat3 import EXTRA3
from load import _read
from sklearn.ensemble import HistGradientBoostingClassifier

JST = dt.timezone(dt.timedelta(hours=9))
today = sys.argv[2] if len(sys.argv) > 2 else dt.datetime.now(JST).strftime('%Y%m%d')
DATA = os.environ['CHIHO_DATA']
ALL = os.environ.get('CHIHO_ALL', f'{store}/data_all')
BW = ('馬体重', '馬体重増減', '馬体重差')
t0 = time.time()


def log(*a):
    print(f'[{time.time() - t0:5.0f}秒]', *a, flush=True)


def rd(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False) if os.path.exists(path) else None


# 今日の出馬表（朝の分。無ければ最新の分）
dd = f'{DATA}/daily/{today}'
TR = rd(f'{dd}/race_racelist_am.csv.gz'); TH = rd(f'{dd}/race_horselist_am.csv.gz')
if TR is None or TH is None:
    TR = rd(f'{dd}/race_racelist.csv.gz'); TH = rd(f'{dd}/race_horselist.csv.gz')
if TR is None or TH is None or len(TH) == 0:
    log('今日の出馬表が無い', today); sys.exit(0)
TR = TR[TR['競走年月日'] == today].copy(); TH = TH[TH['競走年月日'] == today]
# 朝は馬場・天候がまだ空のことがある：同じ場の今日の分で入っている値、無ければ「良」「晴」で埋める
for c, dflt in (('馬場', '良'), ('天候', '晴')):
    known = TR[TR[c] != ''].groupby('競馬場')[c].agg(lambda s: s.iloc[0])
    TR[c] = [v if v != '' else known.get(p, dflt) for v, p in zip(TR[c], TR['競馬場'])]
if len(TH) == 0:
    log('今日の5場の出馬表が無い', today); sys.exit(0)
# 月ごとのデータより後で、今日より前の日（毎日の記録の最後の分）
RM = _read('race', 'racelist')
PM = _read('race', 'payback')
last_month_day = PM.loc[PM['単勝組番'] != '', '競走年月日'].max()     # 結果（払戻）が入っている最後の日（月ごとのファイルには先の日の出馬表も入っている）
ER, EP, EH = [], [], []
for d in sorted(glob.glob(f'{DATA}/daily/2*')):
    day = os.path.basename(d)
    if not (last_month_day < day < today): continue
    r, p, h = rd(f'{d}/race_racelist.csv.gz'), rd(f'{d}/race_payback.csv.gz'), rd(f'{d}/race_horselist.csv.gz')
    if r is not None: ER.append(r[r['競走年月日'] == day])
    if p is not None: EP.append(p[p['競走年月日'] == day])
    if h is not None: EH.append(h[h['競走年月日'] == day])
cat_or_none = lambda xs: pd.concat(xs, ignore_index=True) if xs else None
extra = {'R': pd.concat(ER + [TR], ignore_index=True), 'P': cat_or_none(EP), 'H': cat_or_none(EH), 'T': TH}
log('今日', today, 'レース', len(TR), '頭', len(TH), '／月ごとのデータの最後', last_month_day, '／足した日', len(EH))

H = add_cats(feat.build(verbose=False, extra=extra)); log('材料1')
H = feat2.add2(H, pd.concat([RM, extra['R']], ignore_index=True)); log('材料2')
USE3 = False
H['五場走数'] = H['走数']          # 5場だけで数えた前の走数（前の所属の直しに使う）
try:
    if not glob.glob(f'{ALL}/race/2*'): raise FileNotFoundError(ALL)
    H = feat3.apply3(H, hist_all.build_hist(ALL, extra, verbose=False)); USE3 = True; log('材料3（全部の場の前の成績）')
except Exception as e:      # 全部の場のデータが使えないときは、B2の材料のまま作る
    log('全部の場の前の成績は使わない：', type(e).__name__, str(e)[:200])

# 脚質の材料（style.py と同じ）
R = pd.concat([RM, extra['R']], ignore_index=True).drop_duplicates(KEY, keep='last')
cc = [f'コーナー通過順{i}' for i in range(1, 9)]
last = R[cc].replace('', np.nan).ffill(axis=1).iloc[:, -1]
lastpos = dict(zip(map(tuple, R[KEY].values), last.map(lambda s: corner_pos(s) if isinstance(s, str) else {})))
H['終角'] = [lastpos.get(tuple(k), {}).get(int(b)) for k, b in zip(H[KEY].values, H['馬番'])]
H['終角'] = pd.to_numeric(H['終角'], errors='coerce'); H['終角率'] = H['終角'] / H['n']
H['先頭'] = (H['初角'] == 1).astype(float).where(H['初角'].notna())
H['先行'] = (H['初角'] <= 3).astype(float).where(H['初角'].notna())
H['上げ'] = H['終角'] - H['着x']
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
g = H.groupby('馬', sort=False)
for c in ['先頭', '先行']:
    H[c + '率5'] = g[c].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
H['終角率1'] = g['終角率'].shift(1); H['上げ1'] = g['上げ'].shift(1)
H['上げ3'] = g['上げ'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
H['終角率3'] = g['終角率'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())      # 一覧の脚質（差し・追込）の表示だけに使う（モデルの材料ではない）
H['逃げ型'] = (H['先頭率5'] >= 0.4).astype(int)
H['他の逃げ型'] = H.groupby(KEY)['逃げ型'].transform('sum') - H['逃げ型']
H['先頭率5順'] = H.groupby(KEY)['先頭率5'].rank(ascending=False, method='min')
H['過去3角順'] = H.groupby(KEY)['過去3角'].rank(method='min')
mx = H.groupby(KEY)['先頭率5'].transform(lambda s: s.nlargest(2).iloc[-1] if s.notna().sum() >= 2 else np.nan)
top = H.groupby(KEY)['先頭率5'].transform('max')
H['他の最大先頭率'] = np.where(H['先頭率5'] >= top, mx, top)
SF = ['先頭率5', '先行率5', '終角率1', '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '他の最大先頭率']
log('材料4（脚質）')

NFIX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nar_fix.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nar_fix.json')) else {}
SOFT = 'a' in NFIX
if SOFT:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'jra'))
        import lightgbm, jsoft      # noqa: F401（LightGBM が入っているかをここで確かめる）
    except ImportError as e:
        log('LightGBM が無いので、前のやり方（HGB 乱数0）', e); SOFT = False
# 騎手の格の差（今の騎手の勝率・3着内率 − 前走の騎手の勝率・3着内率。N2）
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True); _g = H.groupby('馬', sort=False)
H['騎勝率差'] = H['騎勝率'] - _g['騎勝率'].shift(1); H['騎3率差'] = H['騎3率'] - _g['騎3率'].shift(1)
JF = ['騎勝率差', '騎3率差'] if (SOFT and NFIX.get('騎手の格の差')) else []
if SOFT and NFIX.get('騎手の性能'):      # 騎手の性能（N3）：近ごろの調子（60日）、その競馬場での成績（365日）、厩舎との組み合わせ（365日）
    def _roll(H, ent, cols, days):
        D = H.groupby([ent, '日'])[cols].sum().reset_index().sort_values([ent, '日'])
        out = []
        for e, g in D.groupby(ent, sort=False):
            d = g['日'].values.astype('datetime64[D]').astype(np.int64)
            c = np.vstack([np.zeros(len(cols))] + [g[cols].values]).cumsum(axis=0)
            lo = np.searchsorted(d, d - days, side='left'); hi = np.arange(len(d))
            out.append(pd.DataFrame(c[hi] - c[lo], columns=cols).assign(**{ent: e, '日': g['日'].values}))
        return pd.concat(out, ignore_index=True)
    H['騎場'] = H['騎'] + '#' + H['競馬場'].astype(str); H['騎調'] = H['騎'] + '#' + H['調']
    for ent, days, pre in (('騎', 60, '騎近'), ('騎場', 365, '騎場'), ('騎調', 365, '騎調')):
        _S = _roll(H, ent, ['乗', '勝', '3着内'], days)
        _S[pre + '数'] = _S['乗']; _S[pre + '勝率'] = _S['勝'] / _S['乗'].where(_S['乗'] > 0); _S[pre + '3率'] = _S['3着内'] / _S['乗'].where(_S['乗'] > 0)
        H = H.merge(_S[[ent, '日', pre + '数', pre + '勝率', pre + '3率']], on=[ent, '日'], how='left'); JF += [pre + '数', pre + '勝率', pre + '3率']
    log('騎手の性能の材料', len(JF))

Y = int(today[:4])
TRN = H[(H['年'] >= 2017) & (H['年'] <= Y - 1) & ~H['予測']]
TE = H[H['予測']].copy()
FE3 = [c for c in FEATS + NEW + (EXTRA3 if USE3 else []) if c not in BW] + JF
if SOFT and NFIX.get('展開の材料'):      # 展開の材料（脚質の予想の材料 SF）を3着内・1着のモデルにも入れる（N4）
    FE3 += [c for c in SF if c not in FE3]
FES = [c for c in FEATS + SF if c not in BW]
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
SMALL = dict(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500)
for tgt, col, FE, P, rows, seeds in ((('3着内', 'p3', FE3, BIG, TRN, (0, 1, 2) if SOFT else (0,)),) + ((('勝', 'p1', FE3, BIG, TRN, (0,)),) if not SOFT else ()) +
                                     (('先頭', 'p先頭', FES, SMALL, TRN[TRN['初角'].notna()], (0,)), ('先行', 'p先行', FES, SMALL, TRN[TRN['初角'].notna()], (0,)))):
    FE = [c for c in FE if rows[c].nunique(dropna=True) >= 2]
    cat = [FE.index(c) for c in ['場c', '馬場c', '天候c', '性c'] if c in FE]
    ps = []
    for sd in seeds:
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **P)
        m.fit(rows[FE], rows[tgt]); ps.append(m.predict_proba(TE[FE])[:, 1]); log('モデル', tgt, '乱数', sd, '回数', m.n_iter_)
    TE[col] = np.mean(ps, axis=0)
if SOFT:      # 1着と3着内：レースの中で1〜3着の順を学ぶ（jsoft.py）
    F = [c for c in FE3 if TRN[c].nunique(dropna=True) >= 2]
    A = TRN.assign(年月日=TRN['競走年月日'], 場=TRN['競馬場'], R=TRN['レース番号'], 着=pd.to_numeric(TRN['着'], errors='coerce'))
    B = TE.assign(年月日=TE['競走年月日'], 場=TE['競馬場'], R=TE['レース番号'])
    TE['p1'], TE['p3順'] = jsoft.predict(jsoft.fit(A, F, ['場c', '馬場c', '天候c', '性c'], wt=tuple(NFIX['重み']), params=NFIX['木'], log=log), B, F)
    del A, B

# レースの中で足し合わせをそろえる（3着内は合計3、1着は合計1）
TE['p3'] = (TE['p3'] * np.minimum(3, TE['n']) / TE.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
if SOFT:      # 1着 ∝ 順を学ぶモデルの1着^a × HGBの3着内^b、3着内 ∝ 順を学ぶモデルの3着内（5場で初めて走る馬だけHGB）^c
    _gk = [TE[k] for k in KEY]
    _s = NFIX['a'] * np.log(TE['p1'].clip(1e-6)) + NFIX['b'] * np.log(TE['p3'].clip(1e-6)); _s = _s - _s.groupby(_gk).transform('max')
    TE['p1'] = np.exp(_s); TE['p1'] = TE['p1'] / TE['p1'].groupby(_gk).transform('sum')
    _q = (TE['p3順'] * np.minimum(3, TE['n']) / TE['p3順'].groupby(_gk).transform('sum')).clip(1e-4, 0.97)
    _b = pd.Series(np.where(TE['五場走数'] == 0, TE['p3'], _q), index=TE.index); _b = (_b * np.minimum(3, TE['n']) / _b.groupby(_gk).transform('sum')).clip(1e-4, 0.97)
    _e = _b ** NFIX['c']; TE['p3'] = (_e * np.minimum(3, TE['n']) / _e.groupby(_gk).transform('sum')).clip(upper=0.97)
    # 枠の付け直し（検証計画 W1）：場×枠の群（内1〜2枠・中3〜6枠・外7〜8枠）ごとの値を1着の見込みに掛けて、足して1に直す。3着内は直さない。5場のほかの場は1のまま
    _wf = NFIX.get('枠の付け直し', {}).get('1着')
    if _wf:
        _wk = pd.to_numeric(TE['枠番'], errors='coerce')
        _wg = np.where(_wk <= 2, '内（1〜2枠）', np.where(_wk <= 6, '中（3〜6枠）', '外（7〜8枠）'))
        _m = pd.Series(TE['競馬場'].astype(str).values + '・' + _wg, index=TE.index).map(_wf).fillna(1.0)
        _m[_wk.isna()] = 1.0
        TE['p1'] = TE['p1'] * _m; TE['p1'] = TE['p1'] / TE['p1'].groupby(_gk).transform('sum')
        log('枠の付け直し（1着）', '値を掛けた馬', int((_m != 1.0).sum()), '／', len(TE))
# 前の所属による直し（origin_fix.py で2021〜2025年から決めた値。全部の場の前の成績があるときだけ）
H = H.sort_values(['馬', '日', 'レース番号'])
first = np.select([(H['五場走数'] == 0) & (H['全走'] == 0), (H['五場走数'] == 0) & (H['初データ'] == 1) & (H['芝走'] > 0),
                   (H['五場走数'] == 0) & (H['初データ'] == 1), (H['五場走数'] == 0) & (H['初データ'] == 0)], ['デビュー', '中央', '外（芝なし）', 'ほかの地方'], '')
H['来かた'] = pd.Series(first, index=H.index).replace('', np.nan); H['来かた'] = H.groupby('馬')['来かた'].transform(lambda s: s.ffill())
H['戦目'] = H['五場走数'] + 1
H['組'] = np.where(H['来かた'].notna() & (H['戦目'] <= 3), H['来かた'].astype(str) + H['戦目'].astype(int).astype(str), '')
TE = TE.drop(columns=[c for c in ('組', '来かた', '戦目') if c in TE]).merge(H.loc[H['予測'], KEY + ['馬番', '組', '来かた', '戦目']], on=KEY + ['馬番'], how='left')
if USE3:
    fix = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'origin_fix.json'), encoding='utf-8'))['掛ける値']
    TE['p3'] = TE['p3'] * TE['組'].map(fix).fillna(1.0)
    TE['p3'] = (TE['p3'] * np.minimum(3, TE['n']) / TE.groupby(KEY)['p3'].transform('sum')).clip(upper=0.97)
TAG = {'中央': '中央から初戦', 'ほかの地方': 'ほかの地方から初戦', '外（芝なし）': '転入初戦', 'デビュー': '初出走'}
TE['印'] = [TAG.get(k, '') if (isinstance(k, str) and s == 1) else '' for k, s in zip(TE['来かた'], TE['戦目'])]
TE['p1'] = TE['p1'] / TE.groupby(KEY)['p1'].transform('sum')
TE['逃げ順'] = TE.groupby(KEY)['p先頭'].rank(ascending=False, method='first')
TE['脚質'] = np.where((TE['逃げ順'] == 1) & (TE['p先頭'] >= 0.3), '逃げ', np.where(TE['p先行'] >= 0.5, '先行',
              np.where((TE['p先行'] >= 0.25) | (TE['終角率3'] <= 0.6), '差し', np.where(TE['終角率3'].notna(), '追込', ''))))
# 差し＝前に行く見込みが2.5割以上か、前の3走の4角の位置（頭数で割る）が前から6割以内。追込＝それより後ろ。空欄＝前の走りの記録が無く、前に行く見込みも低い
TE['順位'] = TE.groupby(KEY)['p3'].rank(ascending=False, method='first').astype(int)
# 勝ちきり度＝1着の見込み÷3着内の見込み（3着内に来たとき1着になる割合の見込み。kachikiri.py で合い方を確かめた）
TE['勝ちきり度'] = TE['p1'] / TE['p3']
# 連対（2着内）の見込み：1着の見込みからハービル（その馬が1着、またはほかの馬が1着のあとで2着）、rentai_calib.json で直す（検証計画 R1）
_rc = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rentai_calib.json')
_r = TE['p1'] / (1 - TE['p1']).clip(lower=1e-9)
TE['p2'] = (TE['p1'] + TE['p1'] * (_r.groupby([TE[k] for k in KEY]).transform('sum') - _r)).clip(1e-4, 0.999)
if os.path.exists(_rc):
    _RC = json.load(open(_rc, encoding='utf-8')); TE['p2'] = np.interp(TE['p2'], _RC['見込み'], _RC['直した見込み'])
TE['向き'] = np.where(TE['勝ちきり度'] >= 0.5, '頭向き', np.where(TE['勝ちきり度'] <= 0.2, 'ヒモ向き', ''))
# 馬連の組の見込み（pair2.py の B：1着は1着の見込み、2着は3着内の見込みで割り振る。pair_calib.json で直す）
CAL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pair_calib.json'), encoding='utf-8'))
GX, GY = np.array(CAL['見込み']), np.array(CAL['直した見込み'])


def top_pairs(g, m=3):
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum()
    if len(nums) < 3: return []
    P = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(P.values())
    return [('-'.join(str(v) for v in sorted((nums[i], nums[j]))), float(np.interp(P[(i, j)] / z, GX, GY))) for i, j in sorted(P, key=P.get, reverse=True)[:m]]


RT = TR.drop_duplicates(KEY).set_index(KEY)
wd = '月火水木金土日'[dt.datetime.strptime(today, '%Y%m%d').weekday()]
out = {'日付': today, '作った時刻': dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M'), '材料': 'B3（全部の場の前の成績あり）' if USE3 else 'B2', 'レース': []}
lines = [f'地方競馬 来そうな馬（{int(today[4:6])}月{int(today[6:])}日・{wd}）',
         '数字は3着内に来る見込み（かっこは2着内＝連対と1着の見込み）。人気・オッズは見ていない。朝の出馬表で計算（馬体重は入れていない）。',
         '頭向き＝3着内に来れば半分以上は1着の見込み、ヒモ向き＝来ても2・3着が多い見込み。',
         '馬連＝1・2着に来る見込みの高い組（見込みは2021〜2023年で合わせ、2024〜2026年で合うことを確かめた）。',
         '馬連の相手を2位と3位で迷ったら、連対の数字が高い方（当たりが少し増える。回収率はほぼ同じで、買えば得という意味ではない。検証計画 B2）。',
         '「中央から初戦」などの印は、5場で初めて走る馬（前の成績が少なく、見込みがぶれやすい）。',
         '脚質＝逃げ（先頭に立つ見込みがレースで一番で3割以上）・先行（最初の角で3番手以内の見込みが5割以上）・差し（その見込みが2.5割以上か、前の3走の4角の位置が前から6割以内）・追込（それより後ろ）。', '']
order = {'盛岡': 0, '水沢': 1, '園田': 2, '姫路': 3, '笠松': 4}
for (place, ymd, rno), g in sorted(TE.groupby(KEY), key=lambda kv: (order.get(kv[0][0], 9), int(kv[0][2]))):
    info = RT.loc[(place, ymd, rno)] if (place, ymd, rno) in RT.index else {}
    hhmm = str(info.get('発走時刻', '')).zfill(4) if len(info) else ''
    post = f'{hhmm[:2]}:{hhmm[2:]}' if hhmm.strip('0') else ''
    head = f"{place} {int(rno)}R {post} {info.get('距離', '')}m {len(g)}頭"
    g = g.sort_values('順位')
    # 指数＝AIの評価を1つの数に：50＝このレースの平均の馬（1着の見込みが1÷頭数）、10上がるごとに1着の見込みが2倍
    _ix = lambda p: int(round(min(100.0, max(0.0, 50 + 10 / np.log(2) * np.log(max(float(p), 1e-4) * len(g))))))
    # タイムの指数（過去3走の平均と最高。その場・距離・馬場の勝ち馬の基準より1000mあたり何秒速いか）。ページで見やすい数に直す
    _tv = lambda r, c: None if c not in r or pd.isna(r[c]) else round(float(r[c]), 2)
    hs = [dict(馬番=int(r['馬番']), 馬名=r['馬名'], 指数=_ix(r['p1']), タイム平均=_tv(r, '指数平均3'), タイム最高=_tv(r, '指数最高3'), 三着内=round(float(r['p3']) * 100), 連対=round(float(r['p2']) * 100), 一着=round(float(r['p1']) * 100), 脚質=r['脚質'], 印=r['印'], 向き=r['向き'],
               逃げ見込み=round(float(r['p先頭']) * 100), 先行見込み=round(float(r['p先行']) * 100)) for _, r in g.iterrows()]
    tp = top_pairs(g)
    out['レース'].append(dict(場=place, R=int(rno), 発走=post, 距離=info.get('距離', ''), 頭数=len(g), 馬=hs,
                            馬連=[dict(組=a, 見込み=round(b * 100)) for a, b in tp]))
    lines.append(head)
    for h in hs[:5]:
        tail = ' '.join(x for x in (h['向き'], h['脚質'], h['印']) if x)
        lines.append(f" {h['馬番']:>2}番 {h['馬名']} {h['三着内']}%（連対{h['連対']}%・1着{h['一着']}%）{tail}".rstrip())
    if tp:
        any3 = sum(b for _, b in tp)
        if '3組の和' in CAL: any3 = float(np.interp(any3, CAL['3組の和'], CAL['3組の和の直した見込み']))     # 和は高い所で言いすぎるので直す
        lines.append(' 馬連 ' + '・'.join(f'{a} {round(b * 100)}%' for a, b in tp) + f'（3組のどれか {round(any3 * 100)}%）')
    lines.append('')
pdir = f"{store}/{os.environ.get('PICKS_DIR', 'data/picks')}"      # 試しのときだけ置き場を替える（nk_pipetest.py）
os.makedirs(pdir, exist_ok=True)
json.dump(out, open(f'{pdir}/{today}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(f'{pdir}/{today}.txt', 'w', encoding='utf-8').write('\n'.join(lines).rstrip() + '\n')
log('できた', len(out['レース']), 'レース')
