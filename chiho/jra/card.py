"""中央競馬の今日の出馬表（JRA公式サイト）を読んで、STORE/jra/card/日付.csv.gz に置く（1頭1行。レースの列も入れる）。
1) 出馬表の入口（pw01dli00）→ 今日の開催（pw01drl…）→ 開催ごとの全部のレースの出馬表（pw01des…）：枠・馬番・馬名・性齢・斤量・騎手・調教師
2) レースごとの出馬表（pw01dde…）：馬主・生産者・調教師の所属・父・母・母の父
オッズは読まない（予測に使わないため）。読み込みは10秒に1回まで。
使い方：python chiho/jra/card.py STORE [日付YYYYMMDD]   → 開催が無い日は何も置かない"""
import os, re, sys, html, time, datetime as dt, requests, pandas as pd

BASE = 'https://www.jra.go.jp'
UA = 'Mozilla/5.0 (personal research; 1 request / 10s)'
S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last = [0.0]
PLACE = {'01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京', '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉'}
CLS = {'新馬': '新馬', '未出走': '新馬', '未勝利': '未勝利', '1勝クラス': '1勝', '2勝クラス': '2勝', '3勝クラス': '3勝', 'オープン': 'オープン'}
JST = dt.timezone(dt.timedelta(hours=9))


def fetch(path, cname=None, get=False):
    for k in range(3):
        w = last[0] + 10 - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        try:
            r = S.get(f'{BASE}{path}?CNAME={cname}', timeout=60) if get else S.post(BASE + path, data={'cname': cname}, timeout=60)
            if r.status_code == 200: return r.content.decode('cp932', errors='replace')
            print('読めない', r.status_code, cname, flush=True)
        except requests.RequestException as e:
            print('通信エラー', type(e).__name__, flush=True)
        time.sleep(30)
    return None


def text(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def cell(block, cls):
    m = re.search(r'<(?:td|div|p|span|li)[^>]*class="[^"]*\b%s\b[^"]*"[^>]*>(.*?)</(?:td|div|p|span|li)>' % re.escape(cls), block, re.S)
    return text(m.group(1)) if m else ''


def parse_des(page, ymd):
    """開催の全部のレースの出馬表 → 馬の行のリスト"""
    out = []
    for m in re.finditer(r'<li id="syutsuba_(\d+)R">(.*?)(?=<li id="syutsuba_\d+R">|</ul>\s*</div>\s*<!--|\Z)', page, re.S):
        rno, b = int(m.group(1)), m.group(2)
        dl_ = text(re.search(r'<div class="cell date">(.*?)</div>', b, re.S).group(1)) if '<div class="cell date">' in b else ''
        mm = re.search(r'(\d+)回(\S+?)(\d+)日', dl_)
        kai, place, nichi = (int(mm.group(1)), mm.group(2), int(mm.group(3))) if mm else (None, '', None)
        tm = re.search(r'発走時刻：\s*<strong>(\d+)時(\d+)分', b)
        title = b[b.find('<div class="race_title">'):b.find('<ul class="prize">')] if '<div class="race_title">' in b else b
        name = cell(title, 'race_name')
        grade = ''
        for g in re.findall(r'alt="([^"]*)"', title):
            g2 = g.replace('Ｇ', 'G').replace('Ⅰ', 'I').replace('Ⅱ', 'II').replace('Ⅲ', 'III')
            if re.fullmatch(r'G(I{1,3})', g2): grade = g2
            elif 'リステッド' in g or g2 == 'L': grade = 'L'
        cls = cell(title, 'class'); rule = cell(title, 'rule')
        cm = re.search(r'([\d,]+)\s*メートル.*?（([^）]*)）', text(re.search(r'<div class="cell course">(.*?)</div>', title, re.S).group(1)) if 'cell course' in title else '')
        dist = int(cm.group(1).replace(',', '')) if cm else None
        course = cm.group(2) if cm else ''
        surf = '障害' if '障害' in course or '障害' in name else ('芝' if course.startswith('芝') else 'ダート' if course.startswith('ダ') else '')
        pm = re.search(r'本賞金.*?<li><span class="cap">1着</span><span class="num">([\d,]+)</span>', b, re.S)
        prize = int(pm.group(1).replace(',', '')) * 10000 if pm else None
        race = dict(年月日=ymd, 場=place, 回=kai, 日目=nichi, R=rno, レース名=name, 芝ダ=surf, コース=f'({course})', 距離=dist,
                    条件=CLS.get(cls, 'オープン' if cls else ''), 年齢=cell(title, 'category'), 重量=cell(title, 'weight'),
                    牝限=int('牝' in rule), 格=grade, 発走=(f'{int(tm.group(1)):02d}{int(tm.group(2)):02d}' if tm else ''), 賞金=prize)
        rows = re.findall(r'<tr>(.*?)</tr>', b[b.find('<tbody'):], re.S)
        hs = []
        for r in rows:
            num = cell(r, 'num')
            if not num.isdigit(): continue
            wk = re.search(r'alt="枠(\d)', r)
            hm = re.search(r'<td class="horse">.*?<a href="[^"]*CNAME=pw01dud00(\d+)/[^"]*">(.*?)</a>', r, re.S)
            age = cell(r, 'age'); sm = re.match(r'(牡|牝|セ)(\d+)', age)
            jk = re.search(r'<td class="jockey">(.*?)</td>', r, re.S); jt = jk.group(1) if jk else ''
            mark = ''.join(re.findall(r'class="mark jockey">([^<]*)<', jt))
            wt = re.search(r'([\d.]+)', cell(r, 'weight'))
            st = next((s for s in ('出走取消', '競走除外', '取消', '除外') if s in text(r)), '')
            hs.append(dict(枠=int(wk.group(1)) if wk else None, 馬番=int(num), 馬ID=hm.group(1) if hm else '', 馬名=text(hm.group(2)) if hm else '',
                           性=sm.group(1) if sm else '', 齢=int(sm.group(2)) if sm else None, 斤量=float(wt.group(1)) if wt else None,
                           騎手=re.sub(r'\s+', '', text(re.sub(r'<span[^>]*class="mark jockey"[^>]*>.*?</span>', '', jt, flags=re.S))),
                           減量=mark[:1], 調教師=re.sub(r'\s+', '', cell(r, 'trainer')), 状態=st))
        race['頭数'] = len([h for h in hs if not h['状態']])
        out += [dict(race, **h) for h in hs]
    return out


def parse_dde(page):
    """1レースの出馬表 → 馬番ごとの {馬主, 生産, 所属, 父, 母, 母父}"""
    out = {}
    for r in re.findall(r'<tr>(.*?)</tr>', page[page.find('<tbody'):], re.S):
        num = cell(r, 'num')
        if not num.isdigit(): continue
        tr = re.search(r'<p class="trainer">(.*?)</p>', r, re.S)
        div = re.search(r'<span class="division">\((.*?)\)</span>', r)
        bm = re.search(r'<span class="bloodmare">\(母の父：(.*?)\)</span>', r)
        mare = re.search(r'<li class="mare"><span>母：</span>(.*?)<span', r, re.S)
        sire = re.search(r'<li class="sire"><span>父：</span>(.*?)</li>', r, re.S)
        out[int(num)] = dict(馬主=re.sub(r'\s+', '', cell(r, 'owner')), 生産=re.sub(r'\s+', '', cell(r, 'breeder')),
                             所属=div.group(1) if div else '', 父=text(sire.group(1)) if sire else '',
                             母=text(mare.group(1)) if mare else '', 母父=text(bm.group(1)) if bm else '')
    return out


def main():
    store = sys.argv[1]
    ymd = sys.argv[2] if len(sys.argv) > 2 else dt.datetime.now(JST).strftime('%Y%m%d')
    top = fetch('/JRADB/accessD.html', 'pw01dli00/F3')
    if top is None: print('入口が読めない', flush=True); sys.exit(1)
    meets = sorted(set(re.findall(r"doAction\('/JRADB/accessD.html',\s*'(pw01drl\d{2}(\d{2})\d{4}\d{2}\d{2}(%s)/[0-9A-F]{2})'\)" % ymd, top)))
    if not meets: print('今日の開催は無い', ymd, flush=True); return
    rows = []
    for cname, pl, _ in meets:
        rl = fetch('/JRADB/accessD.html', cname)
        if rl is None: continue
        des = re.search(r"doAction\('/JRADB/accessD.html',\s*'(pw01des\d+/[0-9A-F]{2})'\)", rl)
        dde = sorted(set(re.findall(r'accessD\.html\?CNAME=(pw01dde\d+/[0-9A-F]{2})', rl)))
        if not des: print('全部のレースの出馬表が無い', PLACE.get(pl, pl), flush=True); continue
        page = fetch('/JRADB/accessD.html', des.group(1))
        if page is None: continue
        hs = parse_des(page, ymd)
        print(PLACE.get(pl, pl), 'レース', len(set(h['R'] for h in hs)), '頭', len(hs), '／1レースのページ', len(dde), flush=True)
        more = {}
        for c in dde:
            rno = int(c[len('pw01dde01') + 2 + 4 + 2 + 2:][:2])      # pw01dde01 場 年 回 日 R 日付
            p = fetch('/JRADB/accessD.html', c, get=True)
            if p: more[rno] = parse_dde(p)
        for h in hs:
            h.update(more.get(h['R'], {}).get(h['馬番'], {}))
        rows += hs
    if not rows: print('出馬表が読めなかった', flush=True); sys.exit(1)
    D = pd.DataFrame(rows)
    os.makedirs(f'{store}/jra/card', exist_ok=True)
    D.to_csv(f'{store}/jra/card/{ymd}.csv.gz', index=False)
    print('置いた', f'jra/card/{ymd}.csv.gz', len(D), '行', D['場'].unique().tolist(), flush=True)


if __name__ == '__main__':
    main()
