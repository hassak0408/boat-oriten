"""中央競馬の来そうな馬（開催日の朝の一覧。検証計画「中央競馬」）。
STORE/jra/data（成績表を読んだ表）と STORE/jra/card/日付.csv.gz（今日の出馬表）から、今日の馬ごとに3着内・1着の見込みと脚質の予想を出し、
STORE/data/picks/日付_jra.json と 日付_jra.txt に置く。
- モデルは毎回作る（Y年はY−1年まで、2017年から）。3着内と1着は乱数0・1・2の3つを作って平均する（検証計画 K8）。脚質は乱数0の1つ。材料はレース前に分かるものだけ。人気・オッズは、そのレースの分も前のレースの分も使わない
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

H = jfeat.build(f'{store}/jra/data', card=C, verbose=False); log('材料')
FE = [c for c in FEATS + EXTRA + PACE + TROUBLE + LAPF + UPF if c not in MKT and c in H]       # EXTRA・PACE は2021〜2023年で選んだ（検証計画「中央：直してみること」その1・その2）。市場の材料は外す（K3）。ラップ（L3）と1頭ごとの推定上り（U1）を足す
FES = [c for c in ['場c', '芝ダc', '距離', 'n', '馬番', '馬番率', '枠', '齢', '斤量', '走数', '間隔', '距離差', '芝ダ変更', '先頭率5', '先行率5', '終角率1',
                   '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '過去3角', '騎勝率', 'クラス'] if c in H]
NEED = set(FE + FES + KEY + ['年', '予測', '合わない', '3着内', '勝', '先頭', '先行', '初角', 'n', '馬番', '馬名', '走数', '新馬', '前不利発走', '前不利疾病'])
H = H[[c for c in H.columns if c in NEED]]; gc.collect()      # 使わない列を落としてメモリを空ける
Y = int(today[:4])
TRN = H[(H['年'] >= 2017) & (H['年'] <= Y - 1) & ~H['予測'] & (H['合わない'] == 0)]
TE = H[H['予測']].copy()
if not len(TE):
    log('今日の馬の行が作れなかった'); sys.exit(1)
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
SMALL = dict(max_leaf_nodes=15, min_samples_leaf=1500, learning_rate=0.05, max_iter=500)
for tgt, col, F, P, rows in (('3着内', 'p3', FE, BIG, TRN), ('勝', 'p1', FE, BIG, TRN),
                             ('先頭', 'p先頭', FES, SMALL, TRN[TRN['初角'].notna()]), ('先行', 'p先行', FES, SMALL, TRN[TRN['初角'].notna()])):
    F = [c for c in F if rows[c].notna().any()]      # 全部空の列は使わない（試しのときだけ起きる）
    cat = [F.index(c) for c in CATF if c in F]
    P = dict(P, min_samples_leaf=min(P['min_samples_leaf'], max(20, len(rows) // 50)))      # 学習の行が少ないとき（試しのとき）だけ小さくする
    ps = []
    for sd in ((0, 1, 2) if tgt in ('3着内', '勝') else (0,)):      # 3つの平均で、作り直すたびの揺れを減らす（K8）
        m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=sd, categorical_features=cat, **P)
        m.fit(rows[F], rows[tgt]); ps.append(m.predict_proba(TE[F])[:, 1]); log('モデル', tgt, '乱数', sd, '学習', len(rows), '回数', m.n_iter_)
    TE[col] = np.mean(ps, axis=0)

TE['p3'] = (TE['p3'] * np.minimum(3, TE['n']) / TE.groupby(KEY)['p3'].transform('sum')).clip(1e-4, 0.97)
TE['p1'] = TE['p1'] / TE.groupby(KEY)['p1'].transform('sum')
fx = f'{HERE}/jra_fix.json'
FIX = json.load(open(fx, encoding='utf-8')) if os.path.exists(fx) else {}
grp = [TE[k] for k in KEY]
if '1着の付け直し' in FIX:      # 1着 ∝ exp(a×log 1着 + b×log 3着内)（検証計画 M2a。3着内の見込みにも1着の手がかりがある）
    a, b = FIX['1着の付け直し']['a'], FIX['1着の付け直し']['b']
    sc = a * np.log(TE['p1'].clip(1e-6)) + b * np.log(TE['p3'].clip(1e-6)); sc = sc - sc.groupby(grp).transform('max')
    TE['p1'] = np.exp(sc)
if '中央で初めて走る馬（新馬以外）の1着の見込みに掛ける値' in FIX:      # F1（M2aで要らなくなった。値があるときだけ）
    TE.loc[(TE['走数'] == 0) & (TE['新馬'] == 0), 'p1'] *= FIX['中央で初めて走る馬（新馬以外）の1着の見込みに掛ける値']
TE['p1'] = TE['p1'] / TE.groupby(KEY)['p1'].transform('sum')
if '3着内の付け直し' in FIX:      # 3着内 ∝ 3着内^c（足して3、M2a）
    e = TE['p3'] ** FIX['3着内の付け直し']['c']
    TE['p3'] = (e * np.minimum(3, TE['n']) / e.groupby(grp).transform('sum')).clip(1e-4, 0.97)
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


def top_pairs(g, m=3):
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum()
    if len(nums) < 3: return []
    P = {(i, j): p1[i] * p3[j] / (1 - p3[i]) + p1[j] * p3[i] / (1 - p3[j]) for i, j in combinations(range(len(nums)), 2)}
    z = sum(P.values())
    f = (lambda v: float(np.interp(v, CAL['見込み'], CAL['直した見込み']))) if CAL else (lambda v: v)
    return [('-'.join(str(v) for v in sorted((nums[i], nums[j]))), f(P[(i, j)] / z)) for i, j in sorted(P, key=P.get, reverse=True)[:m]]


RC = C.drop_duplicates(['場', 'R']).set_index(['場', 'R'])
wd = '月火水木金土日'[dt.datetime.strptime(today, '%Y%m%d').weekday()]
out = {'日付': today, '作った時刻': dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M'), '評価': '純粋な評価（人気・オッズ・騎手と厩舎の単勝の回収を使わない。前走の不利の印を使う。3つのモデルの平均）', 'レース': []}
lines = [f'中央競馬 来そうな馬（{int(today[4:6])}月{int(today[6:])}日・{wd}）',
         '数字は3着内に来る見込み（かっこは1着の見込み）。馬の走りと成績だけの評価で、人気・オッズは前走の分も見ていない。朝の出馬表で計算（馬体重・当日の馬場は入れていない）。',
         '見方：来る馬・勝つ馬は人気（オッズ）のほうがよく当たる。1番手が1番人気と同じなら信頼できる。違うときは1番人気を重く。',
         '頭向き＝3着内に来れば半分以上は1着の見込み、ヒモ向き＝来ても2・3着が多い見込み（同じオッズの馬どうしでも少し見分けられる）。逃げ・先行＝前に行く見込み。',
         '「前走で出遅れなど」「前走で疾病」＝前走で発走の不利や競走中の疾病があった馬。これまで市場もこの評価も低く見がちだった（実際の1着は市場の見込みの1.3〜1.5倍）。'
         '人気薄でも気にかける目印（買えば勝てるという決まりではない）。上位5頭の外でも「ほか」に出す。',
         '馬連＝1・2着に来る見込みの高い組。' + ('（見込みは2021〜2023年で合わせ、2024〜2026年で確かめた）' if CAL else '（見込みの直しはまだ。目安）'),
         '新馬は血統の情報が無く、モデルが弱い（人気を重く）。「初出走」「中央で初」は中央の前の成績が無い馬。', '']
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
    hs = [dict(順位=int(r['順位']), 馬番=int(r['馬番']), 馬名=r['馬名'], 三着内=round(float(r['p3']) * 100), 一着=round(float(r['p1']) * 100), 脚質=r['脚質'], 印=r['印'],
               不利明け=r['不利明け'], 向き=r['向き']) for _, r in g.iterrows()]
    tp = top_pairs(g)
    out['レース'].append(dict(場=place, R=int(rno), 発走=post, レース名=nm, 格=grade, 芝ダ=info.get('芝ダ', ''), 距離=info.get('距離', ''), 頭数=len(g), 馬=hs,
                            馬連=[dict(組=a, 見込み=round(b * 100)) for a, b in tp]))
    lines.append(head)
    for h in hs[:5]:
        tail = ' '.join(x for x in (h['向き'], h['脚質'], h['印'], h['不利明け']) if x)
        lines.append(f" {h['馬番']:>2}番 {h['馬名']} {h['三着内']}%（{h['一着']}%）{tail}".rstrip())
    for h in hs[5:]:
        if h['不利明け']: lines.append(f" ほか {h['馬番']}番 {h['馬名']} {h['三着内']}%（{h['一着']}%）{h['不利明け']}（評価{h['順位']}番目）")
    if tp:
        any3 = sum(b for _, b in tp)
        if CAL and '3組の和' in CAL: any3 = float(np.interp(any3, CAL['3組の和'], CAL['3組の和の直した見込み']))     # 和は高い所で言いすぎるので直す
        lines.append(' 馬連 ' + '・'.join(f'{a} {round(b * 100)}%' for a, b in tp) + f'（3組のどれか {round(any3 * 100)}%）')
    lines.append('')
os.makedirs(f'{store}/data/picks', exist_ok=True)
json.dump(out, open(f'{store}/data/picks/{today}_jra.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(f'{store}/data/picks/{today}_jra.txt', 'w', encoding='utf-8').write('\n'.join(lines).rstrip() + '\n')
log('できた', len(out['レース']), 'レース')
