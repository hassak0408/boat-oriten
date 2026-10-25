"""中央競馬（JRA公式サイトの成績表PDF）の下調べ：年ごとの一覧のページから成績表のPDFの場所を集め、いくつかだけ落とす。
置き場所は非公開のリポジトリ（STORE/jra/）。読み込みは10秒に1回まで。
使い方：python chiho/jra/sample.py STORE 年 [年 ...]"""
import os, re, sys, json, time, requests
BASE = 'https://www.jra.go.jp'
UA = 'Mozilla/5.0 (personal research; JRA race result PDFs, 1 request / 10s)'
S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last = [0.0]
def get(url):
    w = last[0] + 10 - time.time()
    if w > 0: time.sleep(w)
    last[0] = time.time()
    r = S.get(url, timeout=120); print(r.status_code, len(r.content), url, flush=True); return r
store = sys.argv[1]; years = sys.argv[2:]
os.makedirs(f'{store}/jra/index', exist_ok=True); os.makedirs(f'{store}/jra/sample', exist_ok=True)
for y in years:
    r = get(f'{BASE}/datafile/seiseki/report/{y}.html')
    if r.status_code != 200: continue
    r.encoding = r.apparent_encoding or 'utf-8'
    links = sorted(set(re.findall(r'/datafile/seiseki/report/%s/[^"\'\s>]+\.pdf' % y, r.text)))
    json.dump({'年': y, 'PDF': links, '数': len(links)}, open(f'{store}/jra/index/{y}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(y, 'PDFの数', len(links), links[:3], flush=True)
    for u in (links[:1] + links[len(links) // 2: len(links) // 2 + 1]):
        p = get(BASE + u)
        if p.status_code == 200 and p.content[:4] == b'%PDF':
            open(f'{store}/jra/sample/{os.path.basename(u)}', 'wb').write(p.content)
