"""中央競馬の成績表（JRA公式サイトのPDF、1日分）を読んで、レース・馬・払戻の表にする。
- 1ページに2レース（左と右）。馬の行は「枠番と馬番の数字」の位置で見つけ、その行から次の行までに入る文字を、横の位置で欄に分ける。
- 数字の多くは字の番号（cid 9872〜9881）で入っているので 0〜9 に直す。丸数字・記号は使わない（人気は単勝オッズの順で、払戻の組は着順から作る）。
使い方：python parse.py PDF ... （確かめ用に、読めた結果のあらましを出す）"""
import re, sys, unicodedata
from collections import defaultdict
import pdfplumber

SEX = {'牡': '牡', '牝': '牝', 'セ': 'セ'}
WEATHER = ('小雨', '小雪', '晴', '曇', '雨', '雪')
GOING = ('稍重', '不良', '良', '重')
STATUS = ('競走中止', '中止', '出走取消', '取消', '競走除外', '除外', '失格')
MARK = r'[▲△☆◇★]'      # 騎手の減量の印（名前の前にも後ろにも付く）
CLS = [('新馬', '新馬'), ('未出走', '新馬'), ('未勝利', '未勝利'), ('1勝クラス', '1勝'), ('500万円以下', '1勝'), ('2勝クラス', '2勝'), ('1000万円以下', '2勝'),
       ('3勝クラス', '3勝'), ('1600万円以下', '3勝'), ('オープン', 'オープン')]


def cond_of(h, grade):
    """見出しから、クラス・年齢・重量の種類・牝馬限定を読む"""
    t = h.replace('除未出走馬および未勝利馬', '★').replace('、', ',')
    t = t[t.find('第競走') + 3:] if '第競走' in t else t      # 見出しの「第○競走」から後ろ（ページの上の欄の名前「増減」などを除く）
    tc = re.sub(r'(\d),(\d{3})', r'\1\2', t)      # 「1,000万円以下」の3けたの区切りを取る
    cls = 'オープン' if grade else next((v for k, v in CLS if k in tc), 'オープン')      # クラスの書いていないレースはオープン
    am = re.search(r'(\d歳(?:以上)?)', t)
    wt = 'ハンデ' if 'ハンデ' in t else '別定' if ('別定' in t or '増' in t) else '馬齢' if '馬齢' in t else '定量' if '負担重量' in t else ''   # 賞金や勝ち数で重くなるのは別定
    fem = bool(re.search(r'(^|[;,)〓\d])牝[;,]', t)) or ('牝馬限定' in t)
    return cls, (am.group(1) if am else ''), wt, int(fem)
# 欄の境目（枠番の数字の左端からの距離）
COLS = [('枠', -6, 5), ('馬番', 5, 22), ('馬名', 22, 88), ('性', 88, 93), ('齢', 93, 100), ('毛色', 100, 110), ('斤量', 110, 125),
        ('騎手', 125, 171), ('馬主', 171, 213), ('調教師', 213, 241), ('産地', 241, 253), ('生産', 253, 282), ('馬装具', 282, 287),
        ('馬体重', 287, 298), ('増減', 298, 312), ('タイム', 312, 333), ('着差', 333, 362), ('単勝', 362, 378), ('人気', 378, 405)]


def ctext(t):
    m = re.fullmatch(r'\(cid:(\d+)\)', t)
    if m:
        v = int(m.group(1))
        return str(v - 9872) if 9872 <= v <= 9881 else '〓'      # 読めない字は〓
    return t


def z2h(s):
    return unicodedata.normalize('NFKC', s)


def lines_of(chars, tol=1.6):
    """文字を縦の位置でまとめて行にする（[(top, [chars...]), ...]）"""
    out = []
    for c in sorted(chars, key=lambda c: c['top']):
        if out and abs(c['top'] - out[-1][0]) <= tol: out[-1][1].append(c)
        else: out.append([c['top'], [c]])
    return [(t, sorted(cs, key=lambda c: c['x0'])) for t, cs in out]


def txt(cs):
    return ''.join(ctext(c['text']) for c in sorted(cs, key=lambda c: (round(c['top'] / 3), c['x0'])))


def parse_block(chars, meta=None):
    """1レース分（ページの半分）"""
    if not chars: return None
    L = lines_of(chars)
    full = '\n'.join(''.join(ctext(c['text']) for c in cs) for _, cs in L)
    flat = z2h(full.replace('\n', ' '))
    head = flat.replace(' ', '')
    m = re.search(r'(\d+)月(\d{1,2})日(小雨|小雪|晴|曇|雨|雪)?(?:芝|ダ)?(稍重|不良|良|重)?', head)
    if not m or not meta: return None
    mon, day, wx, gd = m.groups()
    year, kai, place, nichi = meta['年'], meta['回'], meta['場'], meta['日目']
    mon = mon[5:] if len(mon) >= 6 else mon[-2:] if len(mon) > 2 else mon     # 頭の5けたは通し番号（例 12061＋5月）
    if not 1 <= int(mon) <= 12: mon = mon[-1:]
    race = dict(年月日=f'{int(year):04d}{int(mon):02d}{int(day):02d}', 場=place, 回=int(kai), 日目=int(nichi), R=None, レース名='', 天候=wx or '', 馬場=gd or '')
    # レース番号：見出しの1つ上の行の先頭の数字（大きな字）
    hl = next((i for i, (t, cs) in enumerate(L) if re.search(r'月\d+日', z2h(''.join(ctext(c['text']) for c in cs)))), None)
    if hl is not None:
        for t, cs in L[max(0, hl - 3):hl][::-1]:
            s0 = z2h(''.join(ctext(c['text']) for c in cs))
            mm = re.match(r'^(\d{1,2})(?!\d)', s0)
            if mm: race['R'] = int(mm.group(1)); race['レース名'] = s0[mm.end():].replace('〓', '').replace(' ', ''); break
    sm = re.search(r'\((芝|ダート|障害)[^)]*\)', head); race['芝ダ'] = '障害' if '競走障害' in head else sm.group(1) if sm else ''
    race['コース'] = sm.group(0) if sm else ''
    gm = re.search(r'\((G[I]{1,3}|GⅠ|GⅡ|GⅢ|L|JpnI+|J・G[I]+)\)', head); race['格'] = gm.group(1) if gm else ''
    # 見出し（レース名から賞金の行まで）をそのまま残す（あとで条件を読み直せるように）
    k = head.find('本賞'); race['見出し'] = head[:k + 80] if k > 0 else head[:300]
    race['条件'], race['年齢'], race['重量'], race['牝限'] = cond_of(race['見出し'], race['格'])
    hd = head[m.end():m.end() + 120]
    ds = [int(x.replace(',', '')) for x in re.findall(r'(?<![\d(])(\d,\d{3}|\d{4})(?![年\d])', hd)]
    ds = [d for d in ds if 1000 <= d <= 4250 and d % 10 == 0]
    race['距離'] = ds[0] if ds else None
    dm = re.search(r'競走(.*?)([\d,]{3,6})(?:m|〓|メートル)?', head)
    tm = re.search(r'発走(\d+)時(\d+)分', head); race['発走'] = f'{int(tm.group(1)):02d}{int(tm.group(2)):02d}' if tm else ''
    nm = re.search(r'\((\d+)頭\)', head); race['頭数'] = int(nm.group(1)) if nm else None
    pm = re.search(r'本賞([\d,]+)円', head); race['賞金'] = int(pm.group(1).replace(',', '')) if pm else None
    # 馬の行：枠番の数字（左端の近く）で始まり、同じ行の右のほうにカタカナや漢字がある
    xs = [c['x0'] for c in chars]
    x0 = min(xs)
    cand = []
    for t, cs in L:
        d = [c for c in cs if ctext(c['text']).isdigit()]
        if not d: continue
        f = cs[0]
        if ctext(f['text']).isdigit() and f['x0'] - x0 < 18 and len(cs) >= 6:
            body = ''.join(ctext(c['text']) for c in cs)
            if re.search(r'[ァ-ヶ一-龥]', body) and not any(k in body for k in ('本賞', 'レコード', '発走', '頭)', '売得', '払戻', '票数', 'ハロン', '通過', '勝馬', 'デビュー', '負担重量', '万円', '賞品')) \
                    and not re.search(r'\d{4}[.．]\d+[.．]\d+生', body):
                cand.append((t, f['x0']))
    if not cand: return race | {'馬': [], '払戻': {}, '角': {}}
    xref = sorted(x for _, x in cand)[len(cand) // 2]
    tops = [t for t, x in cand if abs(x - xref) < 4]
    end_t = next((t for t, cs in L if '頭' in ''.join(ctext(c['text']) for c in cs) and '(' in z2h(''.join(ctext(c['text']) for c in cs)) and t > tops[-1]), tops[-1] + 12)
    horses = []
    for i, t in enumerate(tops):
        lo = t - 3.2; hi = (tops[i + 1] - 3.2) if i + 1 < len(tops) else end_t - 2
        band = [c for c in chars if lo <= c['top'] < hi]
        col = defaultdict(list)
        for c in band:
            dx = c['x0'] - xref
            for name, a, b in COLS:
                if a <= dx < b: col[name].append(c); break
        rec = {name: txt(col[name]).strip() for name, _, _ in COLS}
        rec = {k: z2h(v).replace(' ', '') for k, v in rec.items()}
        # 斤量は2段（基準と負担）のことがあるので、段ごとに数を読む
        wl = lines_of(col['斤量'], tol=1.2)
        rec['斤量s'] = [int(x) for _, cs in wl for x in re.findall(r'\d{2}', z2h(''.join(ctext(c['text']) for c in cs)))]
        if rec['性'][:1] == '〓' and re.match(r'\d', rec['齢'] or ''): rec['性'] = 'セ'      # セン馬の「セ」は読めない字で入っている
        alltxt = z2h(txt(band))
        rec['状態'] = next((s for s in STATUS if s in alltxt), '')
        horses.append(rec)
    horses = [h for h in horses if z2h(h['性'])[:1] in SEX]
    out = []
    for k, h in enumerate(horses, 1):
        try: wk = int(h['枠'][:1]); ub = int(re.sub(r'\D', '', h['馬番']) or h['枠'][1:])
        except ValueError: continue
        w = [x for x in h.get('斤量s', []) if 40 <= x <= 70]
        tm = re.search(r'(?:(\d):)?(\d{2})\.(\d)', h['タイム'])      # 1分を切るときは分が無い
        od = re.search(r'(\d+\.\d)', h['単勝'])
        bw = re.search(r'(\d{3})', h['馬体重']); dw = re.search(r'([+\-±−―]?)(\d+)', h['増減'])
        sign = -1 if dw and dw.group(1) in ('-', '−') else 1
        out.append(dict(行=k, 枠=wk, 馬番=ub, 馬名=re.sub(r'\(\d+頭\)', '', h['馬名'].replace('〓', '')), 性=h['性'][:1], 齢=int(h['齢']) if h['齢'].isdigit() else None,
                        毛色=h['毛色'], 斤量=min(w) if w else None, 騎手=re.sub(MARK, '', h['騎手']), 減量=''.join(re.findall(MARK, h['騎手']))[:1],
                        馬主=h['馬主'], 調教師=h['調教師'], 産地=h['産地'], 生産=h['生産'],
                        ブリンカー=int('B' in h['馬装具']), 馬体重=int(bw.group(1)) if bw else None,
                        増減=(sign * int(dw.group(2)) if dw and dw.group(1) != '―' else None),
                        タイム=(int(tm.group(1) or 0) * 60 + int(tm.group(2)) + int(tm.group(3)) / 10) if tm else None,
                        着差=h['着差'], 単勝オッズ=float(od.group(1)) if od else None, 状態=h['状態']))
    # タイムが「〃」の馬は、1つ上の馬と同じタイム
    for k, o in enumerate(out):
        if o['タイム'] is None and not o['状態'] and k > 0 and '〃' in horses[k]['タイム'] + horses[k]['着差']:
            o['タイム'] = out[k - 1]['タイム']
    # 着順：行の順（タイムがあり状態が空の馬）。同着は着差の「同着」で前と同じ着にする
    rank = 0; prev = None
    for o in out:
        if o['状態'] or o['タイム'] is None:
            o['着順'] = None; continue
        rank += 1
        o['着順'] = prev if ('同着' in o['着差'] and prev) else rank
        prev = o['着順']
    # 人気：単勝オッズの順
    ods = sorted([o['単勝オッズ'] for o in out if o['単勝オッズ']])
    for o in out:
        o['人気'] = (ods.index(o['単勝オッズ']) + 1) if o['単勝オッズ'] else None
    race['馬'] = out
    race['払戻'] = payouts(L)
    race['角'] = corners(L, xref)
    m3 = re.search(r'上り4F([\d.]+)―3F([\d.]+)', head)
    race['上り3F'] = float(m3.group(2)) if m3 else None
    return race


BETS = ['単勝', '複勝', '枠連', '馬連', '馬単', 'ワイド', '3連複', '3連単']


def payouts(L):
    texts = [(t, z2h(''.join(ctext(c['text']) for c in cs)).replace(' ', '')) for t, cs in L]
    cnt = {}
    for t, s in texts:
        m = re.search(r'(単勝|複勝|枠連|馬連|馬単|ワイド|3連複|3連単)票数', s)
        if m: cnt[m.group(1)] = len(re.findall(r'番人気', s))
    i0 = max((k for k, (t, s) in enumerate(texts) if '計:' in s), default=None)
    i1 = next((k for k, (t, s) in enumerate(texts) if '単勝票数' in s), None)
    i5 = next((k for k, (t, s) in enumerate(texts) if i0 is not None and k > i0 and ('対象競走' in s or '重勝' in s)), None)
    if i5 is not None and i1 is not None and i5 < i1: i1 = i5
    if i0 is None or i1 is None or i1 <= i0: return {}
    amts = []
    for t, s in texts[i0 + 1:i1]:
        if ':' in s: continue
        amts += [int(x.replace(',', '')) for x in re.findall(r'(\d[\d,]*)円', s)]
    need = [cnt.get(b, 0) for b in BETS]
    if sum(need) != len(amts) or not all(need[k] for k in (0, 1, 3)): return {'読めない': amts, '数': cnt}
    out, k = {}, 0
    for b, n in zip(BETS, need):
        out[b] = amts[k:k + n]; k += n
    return out


def corners(L, xref):
    out = {}
    start = next((k for k, (t, cs) in enumerate(L) if '通過順位' in z2h(''.join(ctext(c['text']) for c in cs)).replace(' ', '')), None)
    if start is None: return out
    for t, cs in L[start:start + 4]:
        s0 = z2h(''.join(ctext(c['text']) for c in cs)).replace(' ', '')
        if k_stop(s0): break
        cs = [c for c in cs if not re.match(r'[通過順位]', ctext(c['text']))]
        cols = [[c for c in cs if c['x0'] < xref + 205], [c for c in cs if c['x0'] >= xref + 205]]   # 左と右の欄（右の欄のコーナー番号は枠番の数字の約209右）
        for col in cols:
            s = z2h(''.join(ctext(c['text']) for c in col))
            m = re.match(r'^([1-4])(.*)$', s)
            if not m: continue
            nums = [int(x) for x in re.findall(r'\d+', m.group(2))]
            if nums: out[int(m.group(1))] = nums
    return out


def k_stop(s):
    return s.startswith('勝馬') or s.startswith('紹介') or s.startswith('〔')


PLACE = {'sapporo': '札幌', 'hakodate': '函館', 'fukushima': '福島', 'niigata': '新潟', 'tokyo': '東京', 'nakayama': '中山',
         'chukyo': '中京', 'kyoto': '京都', 'hanshin': '阪神', 'kokura': '小倉'}


def meta_of(path):
    m = re.search(r'(\d{4})-(\d+)([a-z]+)(\d+)\.pdf$', path)
    return dict(年=int(m.group(1)), 回=int(m.group(2)), 場=PLACE.get(m.group(3), m.group(3)), 日目=int(m.group(4))) if m else None


def parse_pdf(path):
    races = []; meta = meta_of(path)
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            W = p.width
            for a, b in ((0, W / 2), (W / 2, W)):
                r = parse_block([c for c in p.chars if a <= c['x0'] < b], meta)
                if r and r.get('馬'):
                    if r['R'] is None: r['R'] = (races[-1]['R'] + 1) if races else 1
                    races.append(r)
    return races


if __name__ == '__main__':
    for f in sys.argv[1:]:
        rs = parse_pdf(f)
        print('==', f, 'レース', len(rs))
        for r in rs:
            hs = r['馬']; win = [h for h in hs if h['着順'] == 1]
            ok_n = r['頭数'] == len([h for h in hs if h['状態'] not in ('出走取消', '取消', '競走除外', '除外')])
            ok_w = bool(win and win[0]['単勝オッズ'] and r['払戻'].get('単勝') and abs(win[0]['単勝オッズ'] * 100 - r['払戻']['単勝'][0]) < 1)
            print(f"{r['年月日']} {r['場']}{r['R']}R {r['芝ダ']}{r['距離']} {r['天候']}{r['馬場']} {r['条件'][:12]} 頭{r['頭数']}/{len(hs)} 頭数{'○' if ok_n else '×'} 単勝{'○' if ok_w else '×'} "
                  f"角{list(r['角'].keys())} 払戻{ {k: len(v) for k, v in r['払戻'].items()} }")
            if r['R'] == 1:
                for h in hs[:3]: print('   ', h)
