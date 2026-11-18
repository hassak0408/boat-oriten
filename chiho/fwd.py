"""これからのレースで数える記録（前向きの確かめ）をまとめて作る。STORE/data/fwd/matome.txt（読む用）に置く。買い方の決まりではない。外れも全部数える。
数えるもの（検証計画の名前）：
  1) 一覧の当たり方：AIの1番手の1着・3着内、1番人気、上位3頭の3着内、ワイドの上位1組（地方 2026-11-17〜＝N6＋NQ1、中央 2026-11-21〜＝M8＋Q1）
  2) WD5：1番人気を軸に、7番人気以下の馬へのワイド。相手がAIの5位以内（A）と6位以下（B）
  3) Z1の印：中央の「市場より来やすい型／来にくい型」の1着の数と、市場の見込み（確定オッズ）の和（2026-11-14〜）
  4) R1中央c：中央の連対の見込み（直す前の値に、先に決めた直しをかけたもの）の帯ごとの合い方（2026-11-14〜）
  ※ 3) と 6) には、窓口で見える表示で選んだ形（AC3b・AC3）も並べる（確定は窓口では見えないため）
  9) JN4：地方の乗り替わりの区分ごとの単勝（一覧に区分が出た日から。2026-11-20〜の予定）
  7) WD9：地方のワイドを、AI・ワイドのオッズ・3連複のオッズを合わせた見込みの値打ち別（2026-11-18〜）
  8) E1：地方の当日の馬体重の増減の帯ごとの単勝（1〜6番人気。2026-11-18〜）
  6) ZN1・ZN2：地方の市場のずれの印（型ごとの頭数・1着・単勝の回収）と、来やすい型（かなり含む）で4〜6番人気（確定）の単勝（2026-11-18〜）
  5) WD8：地方の締切前（発走の1分以上前でいちばんあとの回）のワイドのオッズと、AIの見込みを合わせた見込みの値打ち別（2026-11-12〜。重みは 11/11 までの167レースで決めて固定）
使い方：python chiho/fwd.py STORE [nosave]"""
import os, sys, glob, json, subprocess, datetime as dt, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, f'{HERE}/jra')
import jk_wide
store = sys.argv[1]; NOSAVE = 'nosave' in sys.argv[2:]
GIT_ID = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com']
START = {'地方': '20261117', '中央': '20261121'}; ZN_FROM = '20261118'; Z1_FROM = '20261114'; R1C_FROM = '20261114'; WD8_FROM = '20261112'
WD8 = dict(c=0.3397, a=0.5826, b=0.5940)                   # 合わせた見込み＝1/(1+exp(−(c＋a×L(AI)＋b×L(0.75÷オッズ))))
R1C = dict(alpha=0.1429, beta=1.1026)
num = lambda v: pd.to_numeric(v, errors='coerce'); L = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
WCAL = {'地方': json.load(open(f'{HERE}/an/wide_calib.json', encoding='utf-8')), '中央': json.load(open(f'{HERE}/jra/jra_wide_calib.json', encoding='utf-8'))}
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)


def nar_results():
    """{(日, 場, R): dict(fin={馬番: 着}, pop={馬番: 人気}, W={組: 払戻})}"""
    out = {}
    for d in sorted(glob.glob(f'{store}/data/daily/2*')):
        hp, pp = f'{d}/race_horselist.csv.gz', f'{d}/race_payback.csv.gz'
        if not (os.path.exists(hp) and os.path.exists(pp)): continue
        H, P = rd(hp), rd(pp)
        for k, g in H.groupby(['競走年月日', '競馬場', 'レース番号']):
            out[(k[0], k[1], int(k[2]))] = dict(fin=dict(zip(num(g['馬番']), num(g['着順']))), pop=dict(zip(num(g['馬番']), num(g['人気']))), odds={}, W={}, tan={})
        for _, r in P.iterrows():
            k = (r['競走年月日'], r['競馬場'], int(r['レース番号']))
            if k not in out: continue
            a, y = num(r.get('単勝組番', '')), num(str(r.get('単勝払戻金（円）', '')).replace(',', ''))
            if a == a and y == y: out[k]['tan'][int(a)] = y
            for i in (1, 2, 3):
                a, b, y = num(r.get(f'ワイド組番{i}馬番1', '')), num(r.get(f'ワイド組番{i}馬番2', '')), num(str(r.get(f'ワイド払戻金{i}（円）', '')).replace(',', ''))
                if a == a and b == b and y == y: out[k]['W'][frozenset((int(a), int(b)))] = y
    return out


def jra_results():
    out = {}; y = dt.date.today().year
    hs = [rd(f) for yy in (y - 1, y) for f in glob.glob(f'{store}/jra/data/{yy}/*_horses.csv.gz')]; rs = [rd(f) for yy in (y - 1, y) for f in glob.glob(f'{store}/jra/data/{yy}/*_races.csv.gz')]
    if not hs: return out
    H = pd.concat(hs, ignore_index=True); H = H[H['年月日'] >= '20261101']; R = pd.concat(rs, ignore_index=True); R = R[R['年月日'] >= '20261101']
    for k, g in H.groupby(['年月日', '場', 'R']):
        out[(k[0], k[1], int(k[2]))] = dict(fin=dict(zip(num(g['馬番']), num(g['着順']))), pop=dict(zip(num(g['馬番']), num(g['人気']))), odds=dict(zip(num(g['馬番']), num(g['単勝オッズ']))), W={})
    for _, r in R.iterrows():
        k = (r['年月日'], r['場'], int(r['R'])); p = json.loads(r['払戻']) if r.get('払戻') else {}; w = p.get('ワイド')
        if k not in out or not w or len(w) != 3: continue
        fin = out[k]['fin']; t = sorted((v, n) for n, v in fin.items() if v == v and v <= 3)
        if [v for v, _ in t] != [1, 2, 3]: continue
        a, b, c = (int(n) for _, n in t); out[k]['W'] = {frozenset((a, b)): w[0], frozenset((a, c)): w[1], frozenset((b, c)): w[2]}
    return out


def picks(kind):
    out = {}
    for f in sorted(glob.glob(f'{store}/data/picks/2*_jra.json' if kind == '中央' else f'{store}/data/picks/2???????.json')):
        day = os.path.basename(f)[:8]
        try: J = json.load(open(f, encoding='utf-8'))
        except Exception: continue
        for r in J.get('レース', []): out[(day, r['場'], int(r['R']))] = r
    return out


lines = [f'これからのレースで数える記録（{dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")} に作った）。買い方の決まりではない。回収は確定の払戻、1点100円。', '']
RES = {'地方': nar_results(), '中央': jra_results()}; PK = {'地方': picks('地方'), '中央': picks('中央')}
pct = lambda a, b: f'{a / b * 100:.1f}%' if b else '—'
SNC = {}
def snap_last(kind, day):
    """{(場, R): {馬番: (表示のオッズ, 表示の人気)}}：1分以上前のいちばんあとの回の単勝（検証計画 AC3・AC3b）"""
    if (kind, day) in SNC: return SNC[(kind, day)]
    p = f'{store}/data/daily/{day}/odds_snap.csv.gz' if kind == '地方' else f'{store}/jra/odds/{day}.csv.gz'; out = {}
    if os.path.exists(p):
        O = rd(p); pl, rc = ('競馬場', 'レース番号') if kind == '地方' else ('場', 'R'); O = O[O['賭式'] == '単勝'].copy()
        for c in ('発走まで分', '番号1', 'オッズ'): O[c] = num(O[c])
        O = O[(O['発走まで分'] >= 1) & (O['オッズ'] > 0)]
        if len(O):
            O = O[O['発走まで分'] == O.groupby([pl, rc])['発走まで分'].transform('min')]
            for (a_, b_), g in O.groupby([pl, rc]):
                g = g.drop_duplicates('番号1'); rk = g['オッズ'].rank(method='min')
                out[(a_, int(b_))] = {int(n): (float(o), int(r)) for n, o, r in zip(g['番号1'], g['オッズ'], rk)}
    SNC[(kind, day)] = out; return out
# 1) 一覧の当たり方 ／ 2) WD5
for kind in ('地方', '中央'):
    n = w1 = t1 = fw = ft = t3 = n3 = wn = wh = 0; wq = 0.0; A = [0, 0, 0.0]; B = [0, 0, 0.0]; days = set()
    for k, r in PK[kind].items():
        if k[0] < START[kind] or k not in RES[kind]: continue
        res = RES[kind][k]; hs = [h for h in r['馬'] if res['fin'].get(h['馬番']) == res['fin'].get(h['馬番'])]      # 着順のある馬（取消・中止は外す）
        fin = res['fin']; pop = res['pop']
        if len(hs) < 5 or not any(fin.get(h['馬番']) == 1 for h in hs): continue
        n += 1; days.add(k[0]); a = hs[0]['馬番']; w1 += fin[a] == 1; t1 += fin[a] <= 3
        fav = [x for x, p in pop.items() if p == 1]
        if len(fav) == 1: fw += fin.get(fav[0]) == 1; ft += (fin.get(fav[0]) or 99) <= 3
        for h in hs[:3]: n3 += 1; t3 += fin[h['馬番']] <= 3
        if r.get('ワイド') and res['W']:
            x, y = (int(v) for v in r['ワイド'][0]['組'].split('-')); wn += 1; wh += frozenset((x, y)) in res['W']; wq += r['ワイド'][0]['見込み'] / 100
        if len(fav) == 1 and res['W']:
            for rk, h in enumerate(hs, 1):
                if (pop.get(h['馬番']) or 0) >= 7:
                    acc = A if rk <= 5 else B; acc[0] += 1; pay = res['W'].get(frozenset((int(fav[0]), int(h['馬番']))), 0); acc[1] += pay > 0; acc[2] += pay
    lines += [f'【{kind}】一覧の当たり方（{START[kind][4:6]}/{START[kind][6:]}〜、{len(days)}日・{n}レース）',
              f'  AIの1番手：1着 {w1}（{pct(w1, n)}）・3着内 {t1}（{pct(t1, n)}）／1番人気：1着 {fw}（{pct(fw, n)}）・3着内 {ft}（{pct(ft, n)}）',
              f'  上位3頭の3着内 {t3}/{n3}（{pct(t3, n3)}）／ワイドの上位1組 的中 {wh}/{wn}（{pct(wh, wn)}。見込みの平均 {pct(wq, wn)}）',
              f'  WD5（1番人気×7番人気以下のワイド）：相手がAIの5位以内 {A[0]}点・的中 {pct(A[1], A[0])}・回収 {pct(A[2] / 100, A[0])}／6位以下 {B[0]}点・的中 {pct(B[1], B[0])}・回収 {pct(B[2] / 100, B[0])}', '']
# 3) Z1の印 ／ 4) R1中央c
Z = {'市場よりかなり来やすい型': [0, 0, 0.0], '市場より来やすい型': [0, 0, 0.0], '市場より来にくい型': [0, 0, 0.0]}; ZB = [0, 0, 0.0]; ZBw = [0, 0, 0.0]; bands = {}; zr = set()      # ZB：来やすい型（かなり含む）で単勝3〜6倍（確定オッズ）
for k, r in PK['中央'].items():
    if k not in RES['中央']: continue
    res = RES['中央'][k]; od = res['odds']; fin = res['fin']; hs = r['馬']
    if any(od.get(h['馬番']) != od.get(h['馬番']) or not od.get(h['馬番']) for h in hs if fin.get(h['馬番']) == fin.get(h['馬番'])): continue
    run = [h for h in hs if fin.get(h['馬番']) == fin.get(h['馬番'])]
    if len(run) < 5: continue
    inv = sum(1 / od[h['馬番']] for h in run)
    for h in run:
        if k[0] >= Z1_FROM and h.get('型') in Z: zr.add(k); Z[h['型']][0] += 1; Z[h['型']][1] += fin[h['馬番']] == 1; Z[h['型']][2] += (1 / od[h['馬番']]) / inv
        if k[0] >= '20261121' and h.get('型') in ('市場よりかなり来やすい型', '市場より来やすい型') and 3 <= od[h['馬番']] < 6: ZB[0] += 1; ZB[1] += fin[h['馬番']] == 1; ZB[2] += od[h['馬番']] * 100 * (fin[h['馬番']] == 1)
        sw = snap_last('中央', k[0]).get((k[1], k[2]), {}) if k[0] >= '20261121' else {}
        if h.get('型') in ('市場よりかなり来やすい型', '市場より来やすい型') and h['馬番'] in sw and 3 <= sw[h['馬番']][0] < 6: ZBw[0] += 1; ZBw[1] += fin[h['馬番']] == 1; ZBw[2] += od[h['馬番']] * 100 * (fin[h['馬番']] == 1)
        if k[0] >= R1C_FROM and h.get('連対の素') is not None:
            p = h['連対の素'] / 100; q = 1 / (1 + np.exp(-(R1C['alpha'] + R1C['beta'] * L(p)))); b = min(int(q * 10), 9); x = bands.setdefault(b, [0, 0.0, 0, 0.0]); x[0] += 1; x[1] += q; x[2] += fin[h['馬番']] <= 2; x[3] += p
lines += [f'【中央】市場のずれの印（11/14〜16 は Z1、11/21〜 は Z2。{len(zr)}レース。1,000レースで判断）', f'  ZS2：来やすい型（かなりも含む）で単勝3〜6倍（11/21〜）：{ZB[0]}頭・1着 {ZB[1]}・回収 {pct(ZB[2] / 100, ZB[0])}', f'  AC3b：同じ形を、窓口で見える締切前のオッズ（1分以上前のいちばんあとの回）で3〜6倍に選んだ時：{ZBw[0]}頭・1着 {ZBw[1]}・回収 {pct(ZBw[2] / 100, ZBw[0])}'] + [f'  {nm}：{v[0]}頭・1着 {v[1]}・市場の見込みの和 {v[2]:.1f}（実際÷市場 {v[1] / v[2]:.2f}）' if v[2] else f'  {nm}：まだ無い' for nm, v in Z.items()] + ['']
lines += ['【中央】連対の見込み（R1中央c。11/14〜。40〜70%の帯が500頭ずつたまったら判断）'] + [f'  {b * 10}〜{b * 10 + 10}%：{v[0]}頭・直した見込み {v[1] / v[0] * 100:.1f}%・実際 {v[2] / v[0] * 100:.1f}%（直す前の見込み {v[3] / v[0] * 100:.1f}%）' for b, v in sorted(bands.items())] + ['']
# 6) ZN1・ZN2
ZN = {'市場よりかなり来やすい型': [0, 0, 0.0], '市場より来やすい型': [0, 0, 0.0], '市場より来にくい型': [0, 0, 0.0], '印なし': [0, 0, 0.0]}; ZN2 = [0, 0, 0.0]; ZN2w = [0, 0, 0.0]; znr = set()
for k, r in PK['地方'].items():
    if k[0] < ZN_FROM or k not in RES['地方']: continue
    res = RES['地方'][k]; fin = res['fin']; pop = res['pop']
    if not res['tan'] or not any(h.get('型') for h in r['馬']): continue
    znr.add(k)
    for h in r['馬']:
        b = h['馬番']
        if fin.get(b) != fin.get(b): continue
        t = h.get('型') or '印なし'; pay = res['tan'].get(b, 0) if fin.get(b) == 1 else 0
        ZN[t][0] += 1; ZN[t][1] += fin[b] == 1; ZN[t][2] += pay
        if '来やすい' in t and 4 <= (pop.get(b) or 0) <= 6: ZN2[0] += 1; ZN2[1] += fin[b] == 1; ZN2[2] += pay
        sw = snap_last('地方', k[0]).get((k[1], k[2]), {})
        if '来やすい' in t and b in sw and 4 <= sw[b][1] <= 6: ZN2w[0] += 1; ZN2w[1] += fin[b] == 1; ZN2w[2] += pay
lines += [f'【地方】市場のずれの印（ZN1。11/18〜、{len(znr)}レース。1,000頭で判断）'] + [f'  {nm}：{v[0]}頭・1着 {v[1]}（{pct(v[1], v[0])}）・単勝の回収 {pct(v[2] / 100, v[0])}' for nm, v in ZN.items()] + \
         [f'  ZN2：来やすい型（かなり含む）で4〜6番人気：{ZN2[0]}頭・1着 {ZN2[1]}・回収 {pct(ZN2[2] / 100, ZN2[0])}', f'  AC3：同じ形を、窓口で見える人気（1分以上前のいちばんあとの表示）で4〜6番人気に選んだ時：{ZN2w[0]}頭・1着 {ZN2w[1]}・回収 {pct(ZN2w[2] / 100, ZN2w[0])}', '']
# 9) JN4：地方の乗り替わりの区分ごとの単勝（検証計画 JN4。一覧に区分が出た日から。確定の人気・確定の払戻）
def pband(p): return '1番人気' if p == 1 else '2〜3番人気' if p <= 3 else '4〜6番人気' if p <= 6 else '7番人気以下'
JB = {}; jr = set(); JD = []; JU = [0, 0, 0.0]
for k, r in PK['地方'].items():
    if k not in RES['地方'] or not any(h.get('乗替区分') for h in r['馬']): continue
    res = RES['地方'][k]; fin = res['fin']; pop = res['pop']
    if not res['tan']: continue
    jr.add(k)
    for h in r['馬']:
        b = h['馬番']; c = h.get('乗替区分') or '無'; p = pop.get(b)
        if fin.get(b) != fin.get(b) or p is None or p != p: continue
        pay = res['tan'].get(b, 0) if fin.get(b) == 1 else 0; x = JB.setdefault((c, pband(p)), [0, 0, 0.0]); x[0] += 1; x[1] += fin[b] == 1; x[2] += pay
        if c in ('大きく格上げ', '同じ騎手'): JD.append((k[0], pband(p), c, pay))
        if c == '大きく格上げ' and '来やすい' in (h.get('型') or ''): JU[0] += 1; JU[1] += fin[b] == 1; JU[2] += pay
lines.append(f'【地方】JN4：乗り替わりの区分ごとの単勝（{len(jr)}レース。大きく格上げが1,000頭たまったら判断）')
if JB:
    for c in ('大きく格上げ', '格上げ', '同じくらい', '格下げ', '大きく格下げ', '同じ騎手', '無'):
        n = sum(v[0] for (cc, _), v in JB.items() if cc == c); y = sum(v[2] for (cc, _), v in JB.items() if cc == c)
        if n: lines.append(f'  {c}：{n}頭・回収 {pct(y / 100, n)}（' + '・'.join(f"{b} {JB[(c, b)][0]}頭 {pct(JB[(c, b)][2] / 100, JB[(c, b)][0])}" for b in ('1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下') if (c, b) in JB) + '）')
    J4 = pd.DataFrame(JD, columns=['日', '帯', '区分', '払戻'])
    def diff(J):
        up = J[J['区分'] == '大きく格上げ']; sm = J[J['区分'] == '同じ騎手']
        if not len(up): return np.nan
        w = up['帯'].value_counts(normalize=True); ru = up.groupby('帯')['払戻'].mean(); rs = sm.groupby('帯')['払戻'].mean()
        return float(sum(w[b] * (ru[b] - rs.get(b, np.nan)) for b in w.index if b in rs.index))
    nu = int((J4['区分'] == '大きく格上げ').sum()); pt = diff(J4); ds = J4['日'].unique(); rng = np.random.default_rng(0); bs = []
    for _ in range(1000 if nu else 0):
        pick = rng.choice(ds, len(ds)); bs.append(diff(pd.concat([J4[J4['日'] == d] for d in pick])))
    ci = f'（95%幅 {np.nanpercentile(bs, 2.5):+.1f}〜{np.nanpercentile(bs, 97.5):+.1f}）' if len(bs) else ''
    lines.append(f'  大きく格上げ − 同じ人気の帯の同じ騎手（回収の差）：{pt:+.1f}ポイント{ci}・大きく格上げ {nu}頭' + ('' if nu >= 1000 else '（まだ判断しない）'))
    lines.append(f'  数字だけ：大きく格上げで来やすい型（かなり含む）：{JU[0]}頭・1着 {JU[1]}・回収 {pct(JU[2] / 100, JU[0])}')
else: lines.append('  まだ無い')
lines.append('')
# 5) WD8
T = []
for d in sorted(glob.glob(f'{store}/data/daily/2*')):
    day = os.path.basename(d); op = f'{d}/odds_snap.csv.gz'
    if day < WD8_FROM or not os.path.exists(op): continue
    O = rd(op); O = O[O['賭式'] == 'ワイド']
    for c in ('発走まで分', '番号1', '番号2', 'オッズ'): O[c] = num(O[c])
    O = O[O['発走まで分'] >= 1]
    if not len(O): continue
    O = O[O['発走まで分'] == O.groupby(['競馬場', 'レース番号'])['発走まで分'].transform('min')]
    for (pl, rno), g in O.groupby(['競馬場', 'レース番号']):
        k = (day, pl, int(rno)); r = PK['地方'].get(k); res = RES['地方'].get(k)
        if r is None or res is None or len(res['W']) != 3: continue
        hs = r['馬']; nums = [h['馬番'] for h in hs]; p1 = np.array([h.get('p1', max(h['一着'], 0.5) / 100) for h in hs], float); p1 = p1 / p1.sum()
        M = jk_wide.pairprob(p1, WCAL['地方']['λ2'], WCAL['地方']['λ3']); pos = {int(x): i for i, x in enumerate(nums)}
        for a, b, o in zip(g['番号1'], g['番号2'], g['オッズ']):
            if a != a or b != b or o != o or o <= 0 or int(a) not in pos or int(b) not in pos: continue
            q = float(np.interp(M[pos[int(a)], pos[int(b)]], WCAL['地方']['見込み'], WCAL['地方']['直した見込み']))
            bb = 1 / (1 + np.exp(-(WD8['c'] + WD8['a'] * L(q) + WD8['b'] * L(min(0.75 / o, 0.99))))); T.append((day, f'{pl}{rno}', bb, o, res['W'].get(frozenset((int(a), int(b))), 0)))
lines.append(f'【地方】WD8：AIとオッズを合わせた見込みの値打ち別のワイド（11/12〜。1,000レースで判断）')
if T:
    T = pd.DataFrame(T, columns=['日', 'レース', 'b', 'o', '払戻']); T['v'] = T['b'] * T['o']; T['帯'] = pd.cut(T['v'], [0, .7, .8, .9, 1.0, 99], labels=['0.7未満', '0.7〜0.8', '0.8〜0.9', '0.9〜1.0', '1.0以上'], right=False)
    lines.append(f"  {T['日'].nunique()}日・{T.groupby(['日', 'レース']).ngroups}レース・{len(T)}組")
    for b, g in T.groupby('帯', observed=True): lines.append(f"  値打ち {b}：{len(g)}点・合わせた見込み {g['b'].mean() * 100:.1f}%・的中 {(g['払戻'] > 0).mean() * 100:.1f}%・回収 {g['払戻'].mean():.1f}%")
else: lines.append('  まだ無い')
# 7) WD9：地方のワイドを、AI・ワイドのオッズ・3連複のオッズを合わせた見込みで見る（検証計画 E4。重みは 10/25〜11/11 の167レースで決めて固定。11/18〜）
WD9 = dict(c=0.4509, ai=0.4785, ww=0.1531, w3=0.5749); WD9_FROM = '20261118'; T9 = []
for d in sorted(glob.glob(f'{store}/data/daily/2*')):
    day = os.path.basename(d); op = f'{d}/odds_snap.csv.gz'
    if day < WD9_FROM or not os.path.exists(op): continue
    O = rd(op)
    for c in ('発走まで分', '番号1', '番号2', '番号3', 'オッズ'): O[c] = num(O[c])
    O = O[O['発走まで分'] >= 1]
    if not len(O): continue
    lastt = O.groupby(['競馬場', 'レース番号'])['発走まで分'].transform('min'); O = O[O['発走まで分'] == lastt]
    for (pl, rno), g in O.groupby(['競馬場', 'レース番号']):
        k = (day, pl, int(rno)); r = PK['地方'].get(k); res = RES['地方'].get(k)
        if r is None or res is None or len(res['W']) != 3: continue
        w = g[(g['賭式'] == 'ワイド') & (g['オッズ'] > 0)]; t3 = g[(g['賭式'] == '３連複') & (g['オッズ'] > 0)]
        if not len(w) or not len(t3): continue
        q3 = (1 / t3['オッズ']).values; q3 = q3 / q3.sum(); w3 = {}
        for (a1, a2, a3), v in zip(t3[['番号1', '番号2', '番号3']].astype(int).values, q3):
            for pr in ((a1, a2), (a1, a3), (a2, a3)): w3[frozenset(pr)] = w3.get(frozenset(pr), 0) + v
        iw = 1 / w['オッズ'].values; iw = 3 * iw / iw.sum()
        hs = r['馬']; nums = [h['馬番'] for h in hs]; p1 = np.array([h.get('p1', max(h['一着'], 0.5) / 100) for h in hs], float); p1 = p1 / p1.sum()
        M = jk_wide.pairprob(p1, WCAL['地方']['λ2'], WCAL['地方']['λ3']); pos = {int(x): i for i, x in enumerate(nums)}
        for (a1, a2), ww, o in zip(w[['番号1', '番号2']].astype(int).values, iw, w['オッズ'].values):
            pr = frozenset((a1, a2))
            if a1 not in pos or a2 not in pos or pr not in w3: continue
            ai = float(np.interp(M[pos[a1], pos[a2]], WCAL['地方']['見込み'], WCAL['地方']['直した見込み']))
            bb = 1 / (1 + np.exp(-(WD9['c'] + WD9['ai'] * L(ai) + WD9['ww'] * L(ww) + WD9['w3'] * L(w3[pr])))); T9.append((day, f'{pl}{rno}', bb, o, res['W'].get(pr, 0)))
lines.append('【地方】WD9：AI・ワイドのオッズ・3連複のオッズを合わせた見込みの値打ち別のワイド（11/18〜。1,000レースで判断）')
if T9:
    T9 = pd.DataFrame(T9, columns=['日', 'レース', 'b', 'o', '払戻']); T9['v'] = T9['b'] * T9['o']; T9['帯'] = pd.cut(T9['v'], [0, .7, .8, .9, 1.0, 1.1, 99], labels=['0.7未満', '0.7〜0.8', '0.8〜0.9', '0.9〜1.0', '1.0〜1.1', '1.1以上'], right=False)
    lines.append(f"  {T9['日'].nunique()}日・{T9.groupby(['日', 'レース']).ngroups}レース・{len(T9)}組")
    for b, g in T9.groupby('帯', observed=True): lines.append(f"  値打ち {b}：{len(g)}点・合わせた見込み {g['b'].mean() * 100:.1f}%・的中 {(g['払戻'] > 0).mean() * 100:.1f}%・回収 {g['払戻'].mean():.1f}%")
else: lines.append('  まだ無い')
lines.append('')
# 8) E1：地方の当日の馬体重の増減と単勝の戻り（検証計画 E1。11/18〜）
WB = {}; E1_FROM = '20261118'
for d in sorted(glob.glob(f'{store}/data/daily/2*')):
    day = os.path.basename(d); hp, pp = f'{d}/race_horselist.csv.gz', f'{d}/race_payback.csv.gz'
    if day < E1_FROM or not (os.path.exists(hp) and os.path.exists(pp)): continue
    Hh = rd(hp); FIVE = {'盛岡', '水沢', '園田', '姫路', '笠松'}; Hh = Hh[Hh['競馬場'].isin(FIVE)]
    for _, h in Hh.iterrows():
        k = (day, h['競馬場'], int(h['レース番号'])); res = RES['地方'].get(k); fin = num(h['着順']); pop = num(h['人気']); w = num(h['馬体重増減'])
        if res is None or fin != fin or pop != pop or pop > 6: continue
        band = 'なし' if w != w else ('−10以下' if w <= -10 else '−9〜−4' if w <= -4 else '±3' if w <= 3 else '+4〜+9' if w <= 9 else '+10以上')
        x = WB.setdefault(('1〜3番人気' if pop <= 3 else '4〜6番人気', band), [0, 0, 0.0]); x[0] += 1; x[1] += fin == 1; x[2] += res['tan'].get(int(h['馬番']), 0) if fin == 1 else 0
lines.append('【地方】E1：当日の馬体重の増減と単勝（1〜6番人気。11/18〜。−9〜−4kg と +4〜+9kg がそれぞれ1,000頭たまったら判断）')
for pg in ('1〜3番人気', '4〜6番人気'):
    lines.append(f'  {pg}：' + '・'.join(f"{b} {WB[(pg, b)][0]}頭 回収{pct(WB[(pg, b)][2] / 100, WB[(pg, b)][0])}" for b in ('−10以下', '−9〜−4', '±3', '+4〜+9', '+10以上') if (pg, b) in WB) if any((pg, b) in WB for b in ('−10以下', '−9〜−4', '±3', '+4〜+9', '+10以上')) else f'  {pg}：まだ無い')
lines.append('')
txt = '\n'.join(lines) + '\n'; print(txt)
if not NOSAVE:
    os.makedirs(f'{store}/data/fwd', exist_ok=True); open(f'{store}/data/fwd/matome.txt', 'w', encoding='utf-8').write(txt)
    run = lambda *a: subprocess.run(['git', '-C', store] + GIT_ID + list(a), capture_output=True, text=True)
    run('add', 'data/fwd/matome.txt')
    if run('diff', '--cached', '--quiet').returncode != 0:
        run('commit', '-q', '-m', '前向きの記録のまとめ（fwd.py）')
        for i in range(5):
            if run('push', 'origin', 'HEAD:main').returncode == 0: break
            run('fetch', '-q', '--depth', '5', 'origin', 'main'); run('rebase', '-q', 'origin/main')
