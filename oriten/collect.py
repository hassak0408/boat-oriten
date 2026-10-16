"""ある場の、ある期間のオリジナル展示を集める。
使い方: python -m oriten.collect --venue 10 --start 2026-01-01 --end 2026-10-15 --out out
開催日の一覧（schedule/race_days.csv）にある日だけ、1〜12Rを読む。1Rも12Rも表が無い日は「その日は無し」とする。
"""
import argparse, csv, gzip, json, os, time, datetime as dt
from .venues import VENUES
from .net import Fetcher
from .parse import parse_page

FIELDS = ['date', 'venue', 'race', 'lane', 'reg', 'ex', 'lap', 'lap_kind', 'turn', 'straight']

def race_days(path, venue, start, end):
    days = []
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if int(row['venue']) == venue and start <= row['date'] <= end:
                days.append(row['date'])
    return sorted(set(days))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--venue', type=int, required=True)
    ap.add_argument('--start', required=True); ap.add_argument('--end', required=True)
    ap.add_argument('--schedule', default='schedule/race_days.csv')
    ap.add_argument('--days', default='', help='日付をカンマで直接（開催日の一覧を使わない）')
    ap.add_argument('--out', default='out'); ap.add_argument('--interval', type=float, default=1.5)
    ap.add_argument('--max-minutes', type=float, default=330)
    ap.add_argument('--raw', type=int, default=1, help='1なら元のページも保存（あとで読み直せるように）')
    a = ap.parse_args()
    v = VENUES[a.venue]; t0 = time.time()
    days = a.days.split(',') if a.days else race_days(a.schedule, a.venue, a.start, a.end)
    os.makedirs(f'{a.out}/csv', exist_ok=True); os.makedirs(f'{a.out}/log', exist_ok=True)
    tag = f'{a.venue:02d}_{a.start}_{a.end}'
    out_csv = f'{a.out}/csv/{tag}.csv'; out_log = f'{a.out}/log/{tag}.jsonl'
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv, encoding='utf-8') as f:
            done = {(r['date'], int(r['race'])) for r in csv.DictReader(f)}
    fcsv = open(out_csv, 'a', newline='', encoding='utf-8'); w = csv.DictWriter(fcsv, fieldnames=FIELDS)
    if os.path.getsize(out_csv) == 0:
        w.writeheader()
    flog = open(out_log, 'a', encoding='utf-8')
    F = Fetcher(a.interval); n_pages = n_rows = 0
    print(f'{v["name"]}（{a.venue}） {len(days)}日', flush=True)
    for d in days:
        ymd = d.replace('-', '')
        empty_first = None
        for r in range(1, 13):
            if (d, r) in done:
                continue
            if time.time() - t0 > a.max_minutes * 60:
                print('時間切れ（続きは同じ指定でもう一度動かすと、済んだ分を飛ばして続ける）', flush=True)
                fcsv.close(); flog.close(); return
            url = v['url'].format(d=ymd, r=r)
            code, html = F.get(url); n_pages += 1
            rows, memo = parse_page(html) if code == 200 else ([], f'取得失敗 {code} {html if code is None else ""}')
            if a.raw and code == 200:
                p = f'{a.out}/raw/{a.venue:02d}/{ymd}'; os.makedirs(p, exist_ok=True)
                with gzip.open(f'{p}/{r:02d}.html.gz', 'wt', encoding='utf-8') as g:
                    g.write(html)
            for x in rows:
                w.writerow(dict(date=d, venue=a.venue, race=r, **x)); n_rows += 1
            flog.write(json.dumps(dict(date=d, race=r, code=code, n=len(rows), memo=memo), ensure_ascii=False) + '\n')
            if r == 1:
                empty_first = (len(rows) == 0)
            if r == 2 and empty_first and len(rows) == 0:
                # 1R・2Rとも表が無い日は、12Rだけ見て無ければ飛ばす
                code, html = F.get(v['url'].format(d=ymd, r=12)); n_pages += 1
                rows12, memo12 = parse_page(html) if code == 200 else ([], 'x')
                if not rows12:
                    flog.write(json.dumps(dict(date=d, race=0, code=code, n=0, memo='この日は表なし'), ensure_ascii=False) + '\n')
                    break
        fcsv.flush(); flog.flush()
        print(f'  {d} 済み（累計 {n_pages}ページ・{n_rows}行・{(time.time()-t0)/60:.1f}分）', flush=True)
    fcsv.close(); flog.close()
    print(f'おわり {n_pages}ページ・{n_rows}行・{(time.time()-t0)/60:.1f}分', flush=True)

if __name__ == '__main__':
    main()
