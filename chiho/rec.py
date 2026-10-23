"""地方競馬の毎日の記録（盛岡・水沢・園田・姫路・笠松）。データは STORE（非公開のリポジトリ）にだけ置く。
- 当日のレース情報（レース一覧・出馬表・払戻）を30分ごとに読み、対象の場の分を STORE/data/daily/YYYYMMDD/ に置く。
  その日最初に読んだ分（朝の出馬表）は race_*_am.csv.gz として残し、あとは race_*.csv.gz を上書きする（最後の回が結果入り）。
- 当日のオッズ（中間オッズ）は、発走の16分前〜1分後のレースがある時だけ5分ごとに読み、そのレースの分だけを
  ファイルの作成時刻・発走まで分つきで odds_snap.csv.gz に足していく。
  残す賭式は 単勝・複勝・枠複・馬複・馬単・ワイド・3連複（3連単は量が多いので残さない）。
- サイトへの読み込みは、どれも2分以上あける（説明書の目安：当日ファイルは約2分に1回まで）。
- 30分ごとと最後に STORE へ保存する。最終レースの20分後に結果入りのレース情報を読んで終わる。
使い方：python chiho/rec.py STORE 最大の分 [--once]
  --once：1回だけ両方を読み、STORE/data/daily_test/ に置いて保存する（試し用。オッズは全レースの分）"""
import os, io, sys, csv, gzip, json, time, zipfile, subprocess, datetime as dt, re
import requests

BASE = 'https://www.keiba.go.jp/KeibaWeb/DataDownload/'
TRACKS = ['盛岡', '水沢', '園田', '姫路', '笠松']
KEEP_BETS = ('単勝', '複勝', '枠複', '馬複', '馬単', 'ワイド', '３連複', '3連複')
UA = 'Mozilla/5.0 (personal research; daily files, odds every 5 min only around post time, race info every 30 min)'
JST = dt.timezone(dt.timedelta(hours=9))
END = os.environ.get('END', '21:40')          # この時刻を過ぎたら終わる
ODDS_EVERY, RACE_EVERY, SAVE_EVERY, MIN_GAP, RETRY = 300, 1800, 1800, 120, 600
WIN_BEFORE, WIN_AFTER, AFTER_LAST = 16, 1, 20  # オッズを残す範囲（発走の何分前〜何分後）、最終レースの何分後に終わるか

S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last_req = [0.0]


def now():
    return dt.datetime.now(JST)


def get(url):
    w = last_req[0] + MIN_GAP - time.time()
    if w > 0: time.sleep(w)
    last_req[0] = time.time()
    try:
        r = S.get(url, timeout=120)
    except requests.RequestException as e:
        print('通信エラー', type(e).__name__, flush=True); return None, None
    if r.status_code != 200 or not r.content.startswith(b'PK'):
        print('読めなかった', r.status_code, r.content[:120], flush=True); return None, None
    m = re.search(r'_(\d{9,11})_', r.headers.get('Content-Disposition', ''))
    ts = dt.datetime.fromtimestamp(int(m.group(1)), JST) if m else now()
    return zipfile.ZipFile(io.BytesIO(r.content)), ts


def read_csvs(zf):
    out = []
    for name in zf.namelist():
        if not name.lower().endswith('.csv'): continue
        b = zf.read(name)
        for enc in ('utf-8-sig', 'cp932'):
            try: text = b.decode(enc); break
            except UnicodeDecodeError: continue
        else:
            text = b.decode('cp932', 'replace')
        rows = list(csv.reader(io.StringIO(text)))
        if rows: out.append((os.path.basename(name), rows))
    return out


def kind_of(name, head):
    h = set(head)
    if '発走時刻' in h: return 'racelist'
    if '単勝組番' in h or any('払戻' in c for c in head): return 'payback'
    if '馬名' in h: return 'horselist'
    if '賭式' in h: return 'odds'
    return re.sub(r'[^0-9A-Za-z]+', '_', name).strip('_') or 'other'


def keep_tracks(rows):
    head, body = rows[0], rows[1:]
    i = head.index('競馬場') if '競馬場' in head else None
    return head, [x for x in body if i is None or (len(x) > i and any(t in x[i] for t in TRACKS))]


def write_gz(path, head, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(head); w.writerows(body)


def fetch_race(day_dir, day):
    """当日のレース情報を読んで置く。発走予定 {(場, 日付, R): 時刻}（今日の分）を返す。読めなければ None。"""
    zf, ts = get(BASE + 'RaceDataDownload?type=daily')
    if zf is None: return None
    sched, info = {}, {}
    for name, rows in read_csvs(zf):
        head, body = keep_tracks(rows)
        kind = kind_of(name, head)
        info[kind] = {'元の名前': name, '行': len(body), '全体の行': len(rows) - 1}
        if kind == 'racelist' and '競馬場' in rows[0]:   # どの場の分が入っていたか（対象の場の名前の書き方の確かめ）
            ic = rows[0].index('競馬場'); cnt = {}
            for x in rows[1:]:
                if len(x) > ic: cnt[x[ic]] = cnt.get(x[ic], 0) + 1
            info[kind]['場ごとのレース'] = cnt
        write_gz(f'{day_dir}/race_{kind}.csv.gz', head, body)
        if not os.path.exists(f'{day_dir}/race_{kind}_am.csv.gz'):
            write_gz(f'{day_dir}/race_{kind}_am.csv.gz', head, body)
        if kind == 'racelist':
            ih, ir, it, idt = head.index('競馬場'), head.index('レース番号'), head.index('発走時刻'), head.index('競走年月日')
            for x in body:
                try:
                    if x[idt] != day: continue
                    hhmm = int(re.sub(r'\D', '', x[it])); d = dt.datetime.strptime(x[idt], '%Y%m%d').replace(tzinfo=JST)
                    sched[(x[ih], x[idt], x[ir])] = d.replace(hour=hhmm // 100, minute=hhmm % 100)
                except (ValueError, IndexError):
                    pass
    meta = {'取得': ts.isoformat(), '読んだ時刻': now().isoformat(), '今日のレース': len(sched), 'ファイル': info}
    json.dump(meta, open(f'{day_dir}/race_meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(now().strftime('%H:%M'), 'レース情報', ts.strftime('%H:%M:%S'), '今日のレース', len(sched),
          {k: v['行'] for k, v in info.items()}, flush=True)
    return sched


def fetch_odds(day_dir, sched, force=False):
    """発走の16分前〜1分後のレースがあれば中間オッズを読み、その分を足す。読み込みをしたら True。"""
    t = now()
    active = {k for k, post in sched.items() if -WIN_AFTER <= (post - t).total_seconds() / 60 <= WIN_BEFORE}
    if not active and not force: return False
    zf, ts = get(BASE + 'OddsDataDownload?type=daily')
    if zf is None: return True
    n, seen = 0, {}
    for name, rows in read_csvs(zf):
        head, body = keep_tracks(rows)
        if '賭式' not in head:
            print('オッズの見出しが違う', name, head[:12], flush=True); continue
        ih, ir, idt, ib = head.index('競馬場'), head.index('レース番号'), head.index('競走年月日'), head.index('賭式')
        path = f'{day_dir}/odds_snap.csv.gz'
        if os.path.exists(path):
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                old = next(csv.reader(f), None)
            if old and old[2:] != head:          # 見出しが前と違えば別のファイルにする
                path = f'{day_dir}/odds_snap_{len(head)}.csv.gz'
        new = not os.path.exists(path)
        with gzip.open(path, 'at', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            if new: w.writerow(['取得', '発走まで分'] + head)
            for x in body:
                k = (x[ih], x[idt], x[ir])
                if not force and k not in active: continue
                if not any(b == x[ib].strip() for b in KEEP_BETS): continue
                post = sched.get(k)
                mins = round((post - ts).total_seconds() / 60, 1) if post else ''
                w.writerow([ts.strftime('%Y-%m-%d %H:%M:%S'), mins] + x); n += 1
                seen[x[ib]] = seen.get(x[ib], 0) + 1
    print(now().strftime('%H:%M'), 'オッズ', ts.strftime('%H:%M:%S'), '対象のレース', len(active), '行', n, seen, flush=True)
    return True


def save(store, rel, msg):
    def run(*a): return subprocess.run(['git', '-C', store] + list(a), capture_output=True, text=True)
    if not os.path.isdir(f'{store}/{rel}'): return True
    run('add', rel)
    if run('diff', '--cached', '--quiet').returncode == 0: return True
    run('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-q', '-m', msg)
    for _ in range(5):
        r = run('push', '-q', 'origin', 'HEAD:main')
        if r.returncode == 0:
            print(now().strftime('%H:%M'), '保存した', flush=True); return True
        print('push できなかった', r.stderr[-300:], flush=True)
        run('fetch', '-q', '--depth', '5', 'origin', 'main'); r = run('rebase', '-q', 'origin/main')
        if r.returncode != 0: run('rebase', '--abort')
        time.sleep(5)
    print('保存できなかった', flush=True); return False


def output(**kv):
    print(' '.join(f'{k}={v}' for k, v in kv.items()), flush=True)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            for k, v in kv.items(): f.write(f'{k}={v}\n')


def main():
    store, minutes = sys.argv[1], float(sys.argv[2]); once = '--once' in sys.argv
    t0 = time.time(); day = now().strftime('%Y%m%d')
    rel = f'data/daily_test/{day}_{now():%H%M}' if once else f'data/daily/{day}'
    day_dir = f'{store}/{rel}'; os.makedirs(day_dir, exist_ok=True)
    if once:
        sched = fetch_race(day_dir, day)
        fetch_odds(day_dir, sched or {}, force=True)
        save(store, rel, f'毎日の記録の試し {day}')
        output(left=0, ymd=day); return
    eh, em = map(int, END.split(':')); end = now().replace(hour=eh, minute=em, second=0, microsecond=0)
    sched, last_race, last_odds, last_save, finished = None, -1e9, -1e9, time.time(), False
    while time.time() - t0 < minutes * 60 and now() < end:
        if sched is None or time.time() - last_race >= RACE_EVERY:
            s = fetch_race(day_dir, day); last_race = time.time()
            if s is not None: sched = s
            elif sched is None: last_race = time.time() - RACE_EVERY + RETRY   # 読めなければ10分後にもう一度
            if sched == {}:
                print('今日は対象の場のレースが無い', flush=True); finished = True; break
        if sched:
            if now() > max(sched.values()) + dt.timedelta(minutes=AFTER_LAST):
                fetch_race(day_dir, day); finished = True; break     # 結果入りを読んで終わる
            if time.time() - last_odds >= ODDS_EVERY and fetch_odds(day_dir, sched):
                last_odds = time.time()
        if time.time() - last_save >= SAVE_EVERY:
            save(store, rel, f'毎日の記録 {day}（途中）'); last_save = time.time()
        time.sleep(15)
    if not finished and now() >= end and sched:
        fetch_race(day_dir, day)
    save(store, rel, f'毎日の記録 {day}')
    if finished or now() >= end:
        left = 0
    else:
        left = max(1, sum(1 for p in (sched or {}).values() if p > now()))
    output(left=left, ymd=day)


if __name__ == '__main__':
    main()
