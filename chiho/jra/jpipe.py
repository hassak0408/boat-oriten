"""中央競馬の来そうな馬（開催日の朝の一覧。検証計画「中央競馬」）。
STORE/jra/data（成績表を読んだ表）と STORE/jra/card/日付.csv.gz（今日の出馬表）から、今日の馬ごとに3着内・1着の見込みと脚質の予想を出し、
STORE/data/picks/日付_jra.json と 日付_jra.txt に置く。
- モデルは毎回作る（Y年はY−1年まで、2017年から）。3着内と1着は乱数0・1・2の3つを作って平均する（検証計画 K8）。脚質は乱数0の1つ。材料はレース前に分かるものだけ。人気・オッズは、そのレースの分も前のレースの分も使わない
- 1着と3着内は、レースの中で1〜3着の順を学ぶやり方（プラケット・ルース、重み1・0.5・0.25、葉127・葉の最小400・材料7割・L2 10、LightGBM。検証計画 M4b・M5・M5b。jsoft.py）。
  1着はそれにHGBの3着内を少し混ぜる。
  3着内は、中央で初めて走る馬（新馬以外）だけ HGB の3着内を使う（M4c）。
  LightGBM が無いときは前のやり方（HGBの1着と3着内、M2a）に戻す。
  材料に血統（父・母父・母の産駒の成績、P1）を足し、順を学ぶモデルにはレースの中での差の材料（M6・M7）も足す。3着内には着差を学ぶモデルの見込みを掛ける（mg3）。どれも jra_fix.json の印で入り切り。
  1着と3着内は、芝ダ×枠の群（芝は開催1〜2日目か・外回り・直線も）ごとの値を掛けて直す（検証計画 W1。値は jra_fix.json の「枠の付け直し」）。
  （騎手・厩舎の単勝の回収も使わない＝馬の走りと成績だけの「純粋な評価」。前走の不利（注記の出遅れ・疾病など）は使う。検証計画「一覧の評価を『正しい評価』に替える」）。馬体重も使わない。
  前走までのラップ（L3）と1頭ごとの推定上り（U1。STORE/jra/ses、ped.py が毎朝足す）も使う。
- 障害のレースは出さない。朝は馬場・天候が分からないので「良」「晴」とする。
使い方：python chiho/jra/jpipe.py STORE [日付YYYYMMDD]"""
import os, sys, gc, json, time, datetime as dt, numpy as np, pandas as pd
from itertools import combinations
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat
from jfeat import FEATS, CATF, KEY, EXTRA, PACE, MKT, TROUBLE, LAPF, UPF
from sklearn.ensemble import HistGradientBoostingClassifier

JST = dt.timezone(dt.timedelta(hours=9))
store = sys.argv[1]
today = sys.argv[2] if len(sys.argv) > 2 else dt.datetime.now(JST).strftime('%Y%m%d')
HERE = os.path.dirname(os.path.abspath(__file__))
t0 = time.time()


def log(*a):
    print(f'[{time.time() - t0:5.0f}秒]', *a, flush=True)


cf = f'{store}/jra/card/{today}.csv.gz'
if not os.path.exists(cf):
    log('今日の出馬表が無い', today); sys.exit(0)
C = pd.read_csv(cf, dtype=str, keep_default_na=False)
C = C[C['芝ダ'].isin(['芝', 'ダート']) & (C['状態'] == '')].copy()
if not len(C):
    log('今日の平地のレースが無い', today); sys.exit(0)
C['馬場'] = C.get('馬場', '').replace('', '良') if '馬場' in C else '良'
C['天候'] = C.get('天候', '').replace('', '晴') if '天候' in C else '晴'
for c in ('着順', 'タイム', '単勝オッズ', '人気', '馬体重', '増減', 'ブリンカー', '角', '上り3F', '払戻'):
    if c not in C: C[c] = ''
log('今日', today, 'レース', C.groupby(['場', 'R']).ngroups, '頭', len(C))

_fx0 = f'{HERE}/jra_fix.json'; _FX0 = json.load(open(_fx0, encoding='utf-8')) if os.path.exists(_fx0) else {}
PED, REL, MG = bool(_FX0.get('血統')), bool(_FX0.get('レースの中での差')), (_FX0.get('着差のモデル') or {})      # 検証計画 P1・M6・mg3（2026-11-13）
H = jfeat.build(f'{store}/jra/data', card=C, verbose=False, ped=PED); log('材料', '血統のある行' if PED else '', round(float(H['父数'].notna().mean()), 3) if PED and '父数' in H else '')
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF + (jfeat.PEDF if PED else []) if c not in MKT and c in H]       # EXTRA・PACE は2021〜2023年で選んだ（検証計画「中央：直してみること」その1・その2）。市場の材料は外す（K3）。ラップ（L3）と1頭ごとの推定上り（U1）を足す
FES = [c for c in ['場c', '芝ダc', '距離', 'n', '馬番', '馬番率', '枠', '齢', '斤量', '走数', '間隔', '距離差', '芝ダ変更', '先頭率5', '先行率5', '終角率1',
                   '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '過去3角', '騎勝率', 'クラス'] if c in H]
RELF = []
if REL:      # レースの中での差の材料（順を学ぶモデルだけが使う）
    import jk_rel
    H, RELF = jk_rel.add_rel(H, KEY)
ZF = _FX0.get('市場のずれ') or (_FX0.get('市場のずれ（試し）') if os.environ.get('PICKS_DIR') else None) or {}      # 検証計画「Z1の印」：しきいがあるときだけ型を出す（「試し」の値は jk_pipetest.py のときだけ）
NEED = set(FE + FES + RELF + KEY + ['年', '予測', '合わない', '3着内', '勝', '着', '先頭', '先行', '初角', 'n', '馬番', '馬名', '走数', '新馬', '前不利発走', '前不利疾病', '差', '距離']
           + (['単勝オッズ'] if ZF else []))
H = H[[c for c in H.columns if c in NEED]]; gc.collect()      # 使わない列を落としてメモリを空ける
Y = int(today[:4])
TRN = H[(H['年'] >= 2017) & (H['年'] <= Y - 1) & ~H['予測'] & (H['合わない'] == 0)]
TE = H[H['予測']].copy()
if not len(TE):
    log('今日の馬の行が作れなかった'); sys.exit(1)
fx = f'{HERE}/jra_fix.json'
FIX = json.load(open(fx, encoding='utf-8')) if os.path.exists(fx) else {}
FIX1 = FIX.get('1着の付け直し', {}); FIX3 = FIX.get('3着内の付け直し', {})
SOFT = '重み' in FIX1      # 1〜3着の順を学ぶやり方（M4b）
if SOFT:
    try:
        import lightgbm, jsoft      # noqa: F401（LightGBM が入っているかをここで確かめる）
    except ImportError as e:      # LightGBM が入っていないとき：前のやり方（HGBの1着と3着内＋M2a の値）に戻す
        log('LightGBM が無いので、前のやり方（HGB）', e); SOFT = False
        FIX1 = FIX.get('1着の付け直し（HGBのとき）', {}); FIX3 = FIX.get('3着内の付け直し（HGBのとき）', FIX3)
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
SMALL = dict(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500)
for tgt, col, F, P, rows in (('3着内', 'p3', FE, BIG, TRN),) + ((('勝', 'p1', FE, BIG, TRN),) if not SOFT else ()) + (
                             ('先頭', 'p先頭', FES, SMALL, TRN[TRN['初角'].notna()]), ('先行', 'p先行', FES, SMALL, TRN[TRN['初角'].notna()])):
    F = [c for c in F if rows[c].notna().any()]      # 全部空の列は使わない（試しのときだけ起きる）
    cat = [F.index(c) for c in CATF if c in F]
    P = dict(P, min_samples_leaf=min(P['min_samples_leaf'], max(20, len(rows) // 50)))      # 学習の行が少ないとき（試しのとき）だけ小さくする
    ps = []
    for sd in ((0, 1, 2) if tgt in ('3着内', '勝') else (0,)):      # 3つの平均で、作り直すたびの揺れを減らす（K8）
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **P)
        m.fit(rows[F], rows[tgt]); ps.append(m.predict_proba(TE[F])[:, 1]); log('モデル', tgt, '乱数', sd, '学習', len(rows), '回数', m.n_iter_)
    TE[col] = np.mean(ps, axis=0)
if SOFT:      # 1着と3着内：レースの中で1〜3着の順を学ぶ（M4b）
    F = [c for c in FE if TRN[c].notna().any()]; F2 = F + [c for c in RELF if TRN[c].notna().any()]
    TE['p1'], TE['p3順'] = jsoft.predict(jsoft.fit(TRN, F2, CATF, wt=FIX1['重み'], params=FIX1.get('木'), log=log), TE, F2)      # 木の大きさ（M5）
    if MG:      # 着差を学ぶモデル（mg3）：勝ち馬との着差（秒、1000mあたり）の見込み。3着内だけに使う
        import jk_rel
        TE['mg'] = jk_rel.margin_fit_predict(TRN, TE, F, [F.index(c) for c in CATF if c in F], BIG); log('モデル 着差', '見込みの着差の平均', round(float(TE['mg'].mean()), 3))

TE['p3'] = (TE['p3'] * np.minimum(3, TE['n']) / TE.groupby(KEY)['p3'].transform('sum')).clip(1e-4, 0.97)
TE['p1'] = TE['p1'] / TE.groupby(KEY)['p1'].transform('sum')
grp = [TE[k] for k in KEY]
if FIX1:      # 1着 ∝ exp(a×log 1着 + b×log HGBの3着内)（検証計画 M2a・M3・M4。3着内の見込みにも1着の手がかりがある）
    a, b = FIX1['a'], FIX1['b']
    sc = a * np.log(TE['p1'].clip(1e-6)) + b * np.log(TE['p3'].clip(1e-6)); sc = sc - sc.groupby(grp).transform('max')
    TE['p1'] = np.exp(sc)
if '中央で初めて走る馬（新馬以外）に掛ける値' in FIX1:      # F1（そのやり方で作った値があるときだけ。M5 v2 で作り直して入れた）
    TE.loc[(TE['走数'] == 0) & (TE['新馬'] == 0), 'p1'] *= FIX1['中央で初めて走る馬（新馬以外）に掛ける値']
TE['p1'] = TE['p1'] / TE.groupby(KEY)['p1'].transform('sum')
if FIX3:      # 3着内 ∝ 3着内^c（足して3。M4c なら順を学んだモデルの3着内（中央で初めて走る馬（新馬以外）だけ HGB）、前のやり方なら HGB の3着内）
    base = TE['p3']
    if SOFT and FIX3.get('3着内の見込み') == 'M4c':
        q = (TE['p3順'] * np.minimum(3, TE['n']) / TE['p3順'].groupby(grp).transform('sum')).clip(1e-4, 0.97)
        base = pd.Series(np.where((TE['走数'] == 0) & (TE['新馬'] == 0), TE['p3'], q), index=TE.index)
        base = (base * np.minimum(3, TE['n']) / base.groupby(grp).transform('sum')).clip(1e-4, 0.97)
    e = base ** FIX3['c']
    if SOFT and MG and 'mg' in TE: e = e * np.exp(-MG.get('f', 0.0) * (TE['mg'] - TE['mg'].groupby(grp).transform('mean')))
    TE['p3'] = (e * np.minimum(3, TE['n']) / e.groupby(grp).transform('sum')).clip(1e-4, 0.97)
WFIX = FIX.get('枠の付け直し', {}) if SOFT else {}
if WFIX:      # 枠の付け直し（検証計画 W1）：芝ダ×枠の群（芝は開催1〜2日目か・外回り・直線も）ごとの値を1着と3着内の見込みに掛けて直す
    _c = C.drop_duplicates(['場', 'R'])[['場', 'R', '芝ダ', 'コース', '日目']].copy(); _c['_R'] = pd.to_numeric(_c['R'], errors='coerce')
    _t = pd.DataFrame({'場': TE['場'].astype(str).values, '_R': pd.to_numeric(TE['R'], errors='coerce').values}).merge(_c.drop(columns=['R']), on=['場', '_R'], how='left')
    _wk = pd.to_numeric(TE['枠'], errors='coerce').values
    _wg = np.where(_wk <= 2, '内（1〜2枠）', np.where(_wk <= 6, '中（3〜6枠）', '外（7〜8枠）'))
    _cs = _t['コース'].fillna('').astype(str)
    _kai = np.where(_cs.str.contains('外').values, '外回り', np.where(_cs.str.contains('直線').values, '直線', '内回り・ふつう'))
    _day = np.where(pd.to_numeric(_t['日目'], errors='coerce').values <= 2, '1〜2日目', '3日目以降')
    _cell = pd.Series(np.where(_t['芝ダ'].values == 'ダート', 'ダ・' + _wg, '芝・' + _day + '・' + _kai + '・' + _wg), index=TE.index)
    for _k, _col in (('1着', 'p1'), ('3着内', 'p3')):
        if _k not in WFIX: continue
        _m = _cell.map(WFIX[_k]).fillna(1.0); _m[np.isnan(_wk)] = 1.0
        _v = TE[_col] * _m
        TE[_col] = _v / _v.groupby(grp).transform('sum') if _k == '1着' else (_v * np.minimum(3, TE['n']) / _v.groupby(grp).transform('sum')).clip(1e-4, 0.97)
        log('枠の付け直し（' + _k + '）', '値を掛けた馬', int((_m != 1.0).sum()), '／', len(TE))
TE['型'] = ''
if SOFT and ZF:      # Z1の印：f（市場の見込みに掛ける exp(f) の f）を、Z1 と同じ材料・同じ木で、全部の馬に単勝オッズがある5頭以上のレースで学ぶ。評価（1着・3着内）は変えない
    import jz1
    _o = pd.to_numeric(TRN['単勝オッズ'], errors='coerce')
    ZT = TRN[_o.groupby([TRN[k] for k in KEY]).transform(lambda s: s.notna().all()) & (TRN['n'] >= 5)].copy()
    _q = 1 / pd.to_numeric(ZT['単勝オッズ'], errors='coerce'); ZT['pm'] = _q / _q.groupby([ZT[k] for k in KEY]).transform('sum')
    FZ = [c for c in FE if c not in set(jfeat.PEDF) and ZT[c].notna().any()]
    _nz = ZT.groupby(KEY).ngroups
    TE['f'] = jz1.predict(jz1.fit_resid(ZT, FZ, CATF, log=log), TE, FZ); del ZT; gc.collect()
    TE['型'] = np.where(TE['f'] >= ZF['上のしきい'], '市場より来やすい型', np.where(TE['f'] <= ZF['下のしきい'], '市場より来にくい型', ''))
    log('市場のずれ', '学んだレース', _nz, 'f の標準偏差', round(float(TE['f'].std()), 4),
        '来やすい型', round(float((TE['型'] == '市場より来やすい型').mean()) * 100, 1), '%・来にくい型', round(float((TE['型'] == '市場より来にくい型').mean()) * 100, 1), '%')
TE['逃げ順'] = TE.groupby(KEY)['p先頭'].rank(ascending=False, method='first')
TE['脚質'] = np.where((TE['逃げ順'] == 1) & (TE['p先頭'] >= 0.3), '逃げ', np.where(TE['p先行'] >= 0.5, '先行', ''))
TE['順位'] = TE.groupby(KEY)['p3'].rank(ascending=False, method='first').astype(int)
TE['勝ちきり度'] = TE['p1'] / TE['p3']
TE['向き'] = np.where(TE['勝ちきり度'] >= 0.5, '頭向き', np.where(TE['勝ちきり度'] <= 0.2, 'ヒモ向き', ''))
TE['印'] = np.where(TE['走数'] == 0, np.where(TE['新馬'] == 1, '初出走', '中央で初'), '')
# 不利明け（検証計画 K2：前走で発走の不利・疾病のあった馬は、市場にも評価にも低く見られがち）。目印で、買い方の決まりではない
TE['不利明け'] = ['・'.join(x for x in (('前走で出遅れなど' if a == 1 else ''), ('前走で疾病' if b == 1 else '')) if x)
                for a, b in zip(TE['前不利発走'].fillna(0), TE['前不利疾病'].fillna(0))]
cp = f'{HERE}/jra_pair_calib.json'
CAL = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else None
# 連対（2着内）の見込み（検証計画 R1中央・R1中央b）：馬連の組の見込み（B式、直す前）を、その馬の入る組について足し（足すと2）、
# jra_rentai_calib.json（なめらかな直し）で直す。表が無いときは出さない（ページは「—」）
rp = f'{HERE}/jra_rentai_calib.json'
RCAL = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else None
if RCAL:
    _gs = lambda v: v.groupby(grp).transform('sum')
    _p1 = TE['p1'] / _gs(TE['p1']); _q = (TE['p3'] * np.minimum(3, TE['n']) / _gs(TE['p3'])).clip(upper=0.97); _q = _q / _gs(_q)      # jk_r1b.py の r1a と同じ
    _t = _p1 / (1 - _q); _u = _p1 + _q * (_gs(_t) - _t)
    TE['p2'] = np.interp((2 * _u / _gs(_u)).clip(1e-4, 0.999), RCAL['見込み'], RCAL['直した見込み'])
    log('連対の見込み', '1レースの和の平均', round(float(TE['p2'].groupby(grp).sum().mean()), 3))


def top_pairs(g, m=3):
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum()
    if len(nums) < 3: return []
    P = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(P.values())
    f = (lambda v: float(np.interp(v, CAL['見込み'], CAL['直した見込み']))) if CAL else (lambda v: v)
    return [('-'.join(str(v) for v in sorted((nums[i], nums[j]))), f(P[(i, j)] / z)) for i, j in sorted(P, key=P.get, reverse=True)[:m]]


RC = C.drop_duplicates(['場', 'R']).set_index(['場', 'R'])
wd = '月火水木金土日'[dt.datetime.strptime(today, '%Y%m%d').weekday()]
out = {'日付': today, '作った時刻': dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M'),
       '評価': '純粋な評価（人気・オッズ・騎手と厩舎の単勝の回収を使わない。前走の不利の印・ラップ・推定上りを使う。3つのモデルの平均。' + ('レースの中で1〜3着の順を学ぶやり方' if SOFT else 'HGB') + '）', 'レース': []}
lines = [f'中央競馬 来そうな馬（{int(today[4:6])}月{int(today[6:])}日・{wd}）',
         '数字は3着内に来る見込み（かっこは' + ('2着内＝連対と1着' if RCAL else '1着') + 'の見込み）。馬の走りと成績だけの評価で、人気・オッズは前走の分も見ていない。朝の出馬表で計算（馬体重・当日の馬場は入れていない）。',
         '見方：来る馬・勝つ馬は人気（オッズ）のほうがよく当たる。1番手が1番人気と同じなら信頼できる。違うときは1番人気を重く。',
         '頭向き＝3着内に来れば半分以上は1着の見込み、ヒモ向き＝来ても2・3着が多い見込み（同じオッズの馬どうしでも少し見分けられる）。逃げ・先行＝前に行く見込み。',
         '「前走で出遅れなど」「前走で疾病」＝前走で発走の不利や競走中の疾病があった馬。これまで市場もこの評価も低く見がちだった（実際の1着は市場の見込みの1.3〜1.5倍）。'
         '人気薄でも気にかける目印（買えば勝てるという決まりではない）。上位5頭の外でも「ほか」に出す。',
         '馬連＝1・2着に来る見込みの高い組。' + ('（見込みは2021〜2023年で合わせ、2024〜2026年で確かめた）' if CAL else '（見込みの直しはまだ。目安）'),
         '新馬は血統の情報が無く、モデルが弱い（人気を重く）。「初出走」「中央で初」は中央の前の成績が無い馬。「中央で初」（新馬戦以外）の3着内の％は高めに出やすい（これまで実際は見込みの7〜8割）。']
if ZF: lines.append('市場より来やすい型・来にくい型＝朝の材料だけで見た「市場（オッズ）とのずれ」の型（上位1割・下位1割）。これまで来やすい型は市場の見込みの1.1倍ほど1着に来て、'
                    '来にくい型は0.8倍ほどだった。単勝の回収は9割前後・4割前後で、買えば得という印ではない（来にくい型を買う前にもう一度考える目印）。')
lines.append('')
order = {p: i for i, p in enumerate(['札幌', '函館', '福島', '新潟', '東京', '中山', '中京', '京都', '阪神', '小倉'])}
TE['Ri'] = TE['R'].astype(int)
for (place, rno), g in sorted(TE.groupby(['場', 'Ri']), key=lambda kv: (order.get(kv[0][0], 9), kv[0][1])):
    info = RC.loc[(place, str(rno))] if (place, str(rno)) in RC.index else {}
    hhmm = str(info.get('発走', '')).zfill(4) if len(info) else ''
    post = f'{hhmm[:2]}:{hhmm[2:]}' if hhmm.strip('0') else ''
    nm = str(info.get('レース名', '')) if len(info) else ''
    grade = str(info.get('格', '')) if len(info) else ''
    head = f"{place}{rno}R {post} {nm}{('（' + grade + '）') if grade else ''} {info.get('芝ダ', '')}{info.get('距離', '')}m {len(g)}頭"
    if len(info) and info.get('条件', '') == '新馬': head += '［新馬：人気を重く］'
    g = g.sort_values('順位')
    # 指数＝AIの評価を1つの数に：50＝このレースの平均の馬（1着の見込みが1÷頭数）、10上がるごとに1着の見込みが2倍
    _ix = lambda p: int(round(min(100.0, max(0.0, 50 + 10 / np.log(2) * np.log(max(float(p), 1e-4) * len(g))))))
    # タイムの指数（過去3走の平均と最高。その場・距離・馬場の勝ち馬の基準より1000mあたり何秒速いか）。ページで見やすい数に直す
    _tv = lambda r, c: None if c not in r or pd.isna(r[c]) else round(float(r[c]), 2)
    hs = [dict(順位=int(r['順位']), 馬番=int(r['馬番']), 馬名=r['馬名'], 指数=_ix(r['p1']), タイム平均=_tv(r, '指数平均3'), タイム最高=_tv(r, '指数最高3'), 三着内=round(float(r['p3']) * 100), 一着=round(float(r['p1']) * 100), 脚質=r['脚質'], 印=r['印'],
               不利明け=r['不利明け'], 向き=r['向き'], 型=r['型'], **({'連対': round(float(r['p2']) * 100)} if RCAL else {})) for _, r in g.iterrows()]
    _pc = lambda h: f"（連対{h['連対']}%・1着{h['一着']}%）" if '連対' in h else f"（{h['一着']}%）"
    tp = top_pairs(g)
    out['レース'].append(dict(場=place, R=int(rno), 発走=post, レース名=nm, 格=grade, 芝ダ=info.get('芝ダ', ''), 距離=info.get('距離', ''), 頭数=len(g), 馬=hs,
                            馬連=[dict(組=a, 見込み=round(b * 100)) for a, b in tp]))
    lines.append(head)
    for h in hs[:5]:
        tail = ' '.join(x for x in (h['向き'], h['脚質'], h['印'], h['不利明け'], h['型']) if x)
        lines.append(f" {h['馬番']:>2}番 {h['馬名']} {h['三着内']}%{_pc(h)}{tail}".rstrip())
    for h in hs[5:]:
        if h['不利明け']: lines.append(f" ほか {h['馬番']}番 {h['馬名']} {h['三着内']}%{_pc(h)}{h['不利明け']}（評価{h['順位']}番目）")
    if tp:
        any3 = sum(b for _, b in tp)
        if CAL and '3組の和' in CAL: any3 = float(np.interp(any3, CAL['3組の和'], CAL['3組の和の直した見込み']))     # 和は高い所で言いすぎるので直す
        lines.append(' 馬連 ' + '・'.join(f'{a} {round(b * 100)}%' for a, b in tp) + f'（3組のどれか {round(any3 * 100)}%）')
    lines.append('')
pdir = f"{store}/{os.environ.get('PICKS_DIR', 'data/picks')}"      # 試しのときだけ置き場を替える（jk_pipetest.py）
os.makedirs(pdir, exist_ok=True)
json.dump(out, open(f'{pdir}/{today}_jra.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(f'{pdir}/{today}_jra.txt', 'w', encoding='utf-8').write('\n'.join(lines).rstrip() + '\n')
log('できた', len(out['レース']), 'レース')
