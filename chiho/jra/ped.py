"""中央競馬の血統を集める（JRA公式サイト。検証計画「中央：血統」）。
1) ses：過去のレース結果。月のページ（pw01skl10年月/チェック。チェックは検索のページの objParam）→ 開催のページ（pw01srl…）
   → 全てのレースのページ（pw01ses…）。1頭1行で、馬ID・馬のページ・推定上り・通過順位・馬体重・人気なども残す。
   → STORE/jra/ses/年/年-回場日.csv.gz（成績表の表と同じ名前）。新しい月から。2016年1月まで。
2) horse：馬のページ（pw01dud…）。父・母・母の父・母の母（とそのID）・生年月日・生産牧場・毛色・性別。
   → STORE/jra/horse/生まれ年.csv.gz（馬IDの頭4けた）。最近走った馬から。
読み込みは4秒に1回まで。環境変数 LIMIT_MIN（分）を過ぎたら止め、残りの数を GITHUB_OUTPUT の left に出す。30分ごとに保存する。
使い方：python chiho/jra/ped.py STORE [ses|horse|all]"""
import os, re, sys, csv, gzip, glob, json, html, time, subprocess, datetime as dt, requests

BASE = 'https://www.jra.go.jp'
S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0 (personal research; 1 request / 4s)', 'Accept-Language': 'ja'})
GAP = 4.0
JST = dt.timezone(dt.timedelta(hours=9))
CODE = {'01': ('sapporo', '札幌'), '02': ('hakodate', '函館'), '03': ('fukushima', '福島'), '04': ('niigata', '新潟'), '05': ('tokyo', '東京'),
        '06': ('nakayama', '中山'), '07': ('chukyo', '中京'), '08': ('kyoto', '京都'), '09': ('hanshin', '阪神'), '10': ('kokura', '小倉')}
GIT_ID = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com']
SES_COLS = ['年月日', '場', '回', '日目', 'R', '着順', '枠', '馬番', '馬名', '馬ID', '馬のページ', '性齢', '斤量', '騎手', 'タイム', '着差', '通過', '推定上り',
            '馬体重', '増減', '調教師', '人気']
HORSE_COLS = ['馬ID', '馬名', '父', '父ID', '母', '母ID', '母父', '母母', '母母ID', '生年月日', '生産牧場', '毛色', '性別', '読んだ日']
last = [0.0]
t0 = time.time()
store = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
limit = float(os.environ.get('LIMIT_MIN', '320')) * 60


def fetch(method, path, cname=''):
    for k in range(3):
        w = last[0] + GAP - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        try:
            r = S.post(BASE + path, data={'cname': cname}, timeout=60) if method == 'POST' else S.get(BASE + path, timeout=60)
            if r.status_code == 200:
                t = r.content.decode('cp932', errors='replace')
                if 'パラメータエラー' in t[:4000]: print('パラメータエラー', path, cname, flush=True); return None
                return t
            print('読めない', r.status_code, path, cname, flush=True)
        except requests.RequestException as e:
            print('通信エラー', type(e).__name__, flush=True)
        time.sleep(30)
    return None


def text(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


def cell(block, cls):
    m = re.search(r'<td[^>]*class="%s"[^>]*>(.*?)</td>' % re.escape(cls), block, re.S)
    return text(m.group(1)) if m else ''


def save(msg):
    def run(*a): return subprocess.run(['git', '-C', store] + GIT_ID + list(a), capture_output=True, text=True)
    run('add', 'jra')      # jra/ses と jra/horse（無い方があっても止まらないように、jra ごと足す）
    if run('diff', '--cached', '--quiet').returncode == 0: return
    run('commit', '-q', '-m', msg)
    for _ in range(5):
        if run('push', '-q', 'origin', 'HEAD:main').returncode == 0: print('保存した', round((time.time() - t0) / 60), '分', flush=True); return
        run('fetch', '-q', '--depth', '20', 'origin', 'main'); r = run('rebase', '-q', 'origin/main')
        if r.returncode != 0: run('rebase', '--abort')
        time.sleep(5)
    print('保存できなかった', flush=True)


def write(path, head, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)


def read(path):
    if not os.path.exists(path): return []
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        r = csv.reader(f); next(r, None); return list(r)


def parse_ses(page, ymd, place, kai, nichi):
    rows = []
    parts = re.split(r'<[^>]+id="race_result_(\d+)R"', page)
    for i in range(1, len(parts), 2):
        rno, b = int(parts[i]), parts[i + 1]
        tb = b[b.find('<tbody'):b.find('</tbody>')]
        for tr in re.findall(r'<tr>(.*?)</tr>', tb, re.S):
            hm = re.search(r'CNAME=(pw01dud\d{2}(\d{10})/[0-9A-F]{2})"\s*>(.*?)</a>', tr, re.S)
            if not hm: continue
            corner = {k: int(v) for k, v in re.findall(r'<li title="(\d)コーナー通過順位">\s*(\d+)\s*</li>', tr)}
            hw = re.search(r'<td class="h_weight">\s*(\d+)\s*<span>\(([^)]*)\)</span>', tr)
            wk = re.search(r'alt="枠(\d)', tr)
            rows.append([ymd, place, kai, nichi, rno, cell(tr, 'place'), wk.group(1) if wk else '', cell(tr, 'num'), text(hm.group(3)), hm.group(2), hm.group(1),
                         cell(tr, 'age'), cell(tr, 'weight'), cell(tr, 'jockey'), cell(tr, 'time'), cell(tr, 'margin'), json.dumps(corner),
                         cell(tr, 'f_time'), hw.group(1) if hw else '', hw.group(2) if hw else '', cell(tr, 'trainer'), cell(tr, 'pop')])
    return rows


def parse_horse(page, hid):
    d = {}
    for k, v in re.findall(r'<dt>\s*(.*?)\s*</dt>\s*<dd>(.*?)</dd>', page, re.S):
        k = text(k)
        if k in d: continue
        vid = re.search(r'pw01dud\d{2}(\d{10})/', v)
        d[k] = (text(re.sub(r'<span class="sanku">.*?</span>', '', v, flags=re.S)), vid.group(1) if vid else '')
    nm = re.search(r'<span class="txt"><span class="opt">[^<]*</span>([^<]+)', page)
    g = lambda k, i=0: d.get(k, ('', ''))[i]
    return [hid, text(nm.group(1)) if nm else '', g('父'), g('父', 1), g('母'), g('母', 1), g('母の父'), g('母の母'), g('母の母', 1),
            g('生年月日'), g('生産牧場'), g('毛色'), g('性別'), dt.datetime.now(JST).strftime('%Y%m%d')]


def time_up(): return time.time() - t0 > limit


def run_ses():
    top = fetch('POST', '/JRADB/accessS.html', 'pw01skl00999999/B3')
    obj = dict(re.findall(r'objParam\["(\d{4})"\]="([0-9A-F]{2})"', top or ''))
    now = dt.datetime.now(JST); y, m = now.year, now.month; months = []
    while (y, m) >= (2016, 1):
        k = f'{y % 100:02d}{m:02d}'
        if k in obj: months.append((y, m, f'pw01skl10{y}{m:02d}/{obj[k]}'))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    print('月', len(months), flush=True)
    left = 0; last_save = time.time(); n_done = 0
    for y, m, cname in months:
        if time_up(): left += 1; continue
        page = fetch('POST', '/JRADB/accessS.html', cname)
        if not page: continue
        srl = sorted(set(re.findall(r"doAction\('/JRADB/accessS.html',\s*'(pw01srl10(\d{2})(\d{4})(\d{2})(\d{2})(\d{8})/[0-9A-F]{2})'\)", page)))
        for cn, pl, yy, kai, nichi, ymd in srl:
            if pl not in CODE: continue
            name = f'{yy}-{int(kai)}{CODE[pl][0]}{int(nichi)}'; path = f'{store}/jra/ses/{yy}/{name}.csv.gz'
            if os.path.exists(path): continue
            if time_up(): left += 1; continue
            sp = fetch('POST', '/JRADB/accessS.html', cn)
            ses = re.search(r"doAction\('/JRADB/accessS.html',\s*'(pw01ses10\d+/[0-9A-F]{2})'\)", sp or '')
            if not ses: print('全てのレースのリンクが無い', name, flush=True); continue
            pg = fetch('POST', '/JRADB/accessS.html', ses.group(1))
            rows = parse_ses(pg or '', ymd, CODE[pl][1], int(kai), int(nichi))
            if not rows: print('馬が読めない', name, flush=True); continue
            write(path, SES_COLS, rows); n_done += 1
            print(name, 'レース', len(set(r[4] for r in rows)), '頭', len(rows), flush=True)
            if time.time() - last_save > 1800: save(f'中央競馬の過去のレース結果（途中） {y}年{m}月'); last_save = time.time()
    save('中央競馬の過去のレース結果'); print('開催', n_done, '残り（月）', left, flush=True)
    return left


def run_horse():
    seen, latest = {}, {}
    for f in glob.glob(f'{store}/jra/ses/*/*.csv.gz'):
        for r in read(f):
            hid, cn, ymd = r[9], r[10], r[0]
            if ymd >= latest.get(hid, ''): latest[hid] = ymd; seen[hid] = cn
    have = {}
    for f in glob.glob(f'{store}/jra/horse/*.csv.gz'):
        for r in read(f): have[r[0]] = r
    todo = sorted((h for h in seen if h not in have), key=lambda h: latest[h], reverse=True)
    print('馬', len(seen), '読んだ', len(have), 'これから', len(todo), flush=True)
    new = {}; last_save = time.time(); left = 0

    def flush():
        for pre in sorted({h[:4] for h in new}):
            path = f'{store}/jra/horse/{pre}.csv.gz'
            cur = {r[0]: r for r in read(path)}; cur.update({h: r for h, r in new.items() if h[:4] == pre})
            write(path, HORSE_COLS, sorted(cur.values()))
        new.clear()
    for i, hid in enumerate(todo):
        if time_up(): left = len(todo) - i; break
        pg = fetch('GET', '/JRADB/accessU.html?CNAME=' + seen[hid])
        if not pg: continue
        row = parse_horse(pg, hid)
        if not row[2]: print('父が読めない', hid, flush=True)
        new[hid] = row
        if (i + 1) % 500 == 0: print('馬', i + 1, '/', len(todo), round((time.time() - t0) / 60), '分', flush=True)
        if time.time() - last_save > 1800: flush(); save(f'中央競馬の血統（途中） {i + 1}頭'); last_save = time.time()
    flush(); save('中央競馬の血統'); print('残り（馬）', left, flush=True)
    return left


left = 0
if mode in ('ses', 'all'): left += run_ses()
if mode in ('horse', 'all') and not time_up(): left += run_horse()
elif mode in ('horse', 'all'): left += 1
gh = os.environ.get('GITHUB_OUTPUT')
if gh: open(gh, 'a').write(f'left={left}\n')
print('残り', left, round((time.time() - t0) / 60), '分', flush=True)
