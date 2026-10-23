"""地方競馬情報サイトの「データダウンロード」（月ごとのZIP）を落として、対象の場だけCSV（gzip）で残す。
説明書（/pdf/manual/data_pdf_manual.pdf）の推奨（月次ファイルは1日1回まで）を守り、同じファイルは1回だけ読む。
1回ごとに20秒あける（robots.txt の Crawl-delay 10 より長く）。
環境変数：RACE_MONTHS / ODDS_MONTHS（YYYYMM の空白区切り、または YYYYMM-YYYYMM）、KEEP_RAW=1 でZIPの中身の見出しを記録。"""
import os, io, sys, time, zipfile, gzip, json, csv, re, requests

BASE = 'https://www.keiba.go.jp/KeibaWeb/DataDownload/'
VENUES = ['盛岡', '水沢', '園田', '姫路', '笠松']
UA = 'Mozilla/5.0 (personal research; monthly data download, 1 request / 20s)'
GAP = 20
OUT = 'chiho/data'

def months(spec):
    out = []
    for p in spec.split():
        if '-' in p:
            a, b = p.split('-'); y, m = int(a[:4]), int(a[4:])
            while y * 100 + m <= int(b):
                out.append(f'{y}{m:02d}'); m += 1
                if m > 12: y, m = y + 1, 1
        elif p: out.append(p)
    return out

def decode(b):
    for enc in ('utf-8-sig', 'cp932'):
        try: return b.decode(enc), enc
        except UnicodeDecodeError: pass
    return b.decode('cp932', 'replace'), 'cp932?'

S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last = [0.0]
def get(url):
    for k in range(3):
        w = last[0] + GAP - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        try:
            r = S.get(url, timeout=300)
        except requests.RequestException as e:
            print('通信エラー', e, flush=True); time.sleep(60); continue
        if r.status_code in (429, 500, 502, 503, 504):
            print('HTTP', r.status_code, flush=True); time.sleep(120 * (k + 1)); continue
        return r
    return None

def handle(kind, ym, report):
    out_dir = f'{OUT}/{kind}/{ym}'
    if os.path.exists(out_dir + '/done.json'):
        print(kind, ym, 'もう取ってある', flush=True); return
    url = f'{BASE}{"RaceDataDownload" if kind == "race" else "OddsDataDownload"}?type=monthly&k_year={ym[:4]}&k_month={int(ym[4:])}'
    r = get(url)
    rep = {'url': url}
    if r is None:
        rep['error'] = '読めなかった'; report[f'{kind}_{ym}'] = rep; return
    rep.update(code=r.status_code, ctype=r.headers.get('Content-Type'), bytes=len(r.content), disp=r.headers.get('Content-Disposition'))
    print(kind, ym, r.status_code, rep['ctype'], len(r.content), flush=True)
    if r.status_code != 200 or not r.content.startswith(b'PK'):
        rep['head'] = r.content[:300].decode('utf-8', 'replace'); report[f'{kind}_{ym}'] = rep; return
    os.makedirs(out_dir, exist_ok=True)
    zf = zipfile.ZipFile(io.BytesIO(r.content)); files = {}
    for idx, name in enumerate(zf.namelist()):
        if not name.lower().endswith('.csv'):
            files[name] = {'skip': True}; continue
        text, enc = decode(zf.read(name))
        rows = list(csv.reader(io.StringIO(text)))
        if not rows: continue
        head, body = rows[0], rows[1:]
        vcol = next((i for i, h in enumerate(head) if '競馬場' in h), None)
        keep = body if vcol is None else [x for x in body if len(x) > vcol and any(v in x[vcol] for v in VENUES)]
        safe = f'{idx:02d}_' + re.sub(r'[^0-9A-Za-z_.-]+', '_', os.path.basename(name)).strip('_')
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(head); w.writerows(keep)
        with gzip.open(f'{out_dir}/{safe}.gz', 'wt', encoding='utf-8', newline='') as f:
            f.write(buf.getvalue())
        files[name] = {'enc': enc, 'rows': len(body), 'kept': len(keep), 'venue_col': head[vcol] if vcol is not None else None, 'header': head}
    rep['files'] = files
    json.dump(rep, open(out_dir + '/done.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    report[f'{kind}_{ym}'] = {k: v for k, v in rep.items() if k != 'files'} | {'n_files': len(files)}

def main():
    os.makedirs(OUT, exist_ok=True)
    rp = f'{OUT}/report.json'
    report = json.load(open(rp, encoding='utf-8')) if os.path.exists(rp) else {}
    t0 = time.time(); limit = float(os.environ.get('LIMIT_MIN', '300')) * 60
    for kind, spec in (('race', os.environ.get('RACE_MONTHS', '')), ('odds', os.environ.get('ODDS_MONTHS', ''))):
        for ym in months(spec):
            if time.time() - t0 > limit:
                print('時間切れ。続きは次の回', flush=True); break
            try:
                handle(kind, ym, report)
            except Exception as e:
                report[f'{kind}_{ym}'] = {'error': repr(e)[:300]}; print('エラー', kind, ym, e, flush=True)
            json.dump(report, open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
