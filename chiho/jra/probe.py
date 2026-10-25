"""中央競馬の下調べ：JRA公式サイトのページをいくつか読んで、そのまま STORE/jra/probe/ に置く（中身を手元で確かめるため。確かめ終わったら消す）。
読み込みは10秒に1回まで。
使い方：python chiho/jra/probe.py STORE 手順 [手順 ...]
  get:URL                       そのページ（/ から始まるときは https://www.jra.go.jp を前につける）
  post:PATH:CNAME               JRAのデータのページ（例 post:/JRADB/accessD.html:pw01dli00/F3）
  crawl:PATH:CNAME:深さ:数      そのページから、同じ PATH への doAction のリンクを、1ページにつき「数」まで、「深さ」の段だけたどる"""
import os, re, sys, time, requests
BASE = 'https://www.jra.go.jp'
UA = 'Mozilla/5.0 (personal research; 1 request / 10s)'
S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last = [0.0]
LINK = re.compile(r"doAction\(\s*'(/JRADB/access\w+\.html)'\s*,\s*'([^']+)'\s*\)")


def wait():
    w = last[0] + 10 - time.time()
    if w > 0: time.sleep(w)
    last[0] = time.time()


def fname(*parts):
    return re.sub(r'[^0-9A-Za-z._-]+', '_', '_'.join(parts)).strip('_')[:150]


def keep(out, name, r):
    ext = '.pdf' if r.content[:4] == b'%PDF' else '.html'
    open(f'{out}/{name}{ext}', 'wb').write(r.content)
    print(r.status_code, len(r.content), name, flush=True)


def text(r):
    for enc in ('cp932', 'utf-8', 'euc_jp'):
        try: return r.content.decode(enc)
        except UnicodeDecodeError: pass
    return r.content.decode('cp932', errors='replace')


def post(path, cname):
    wait()
    return S.post(BASE + path, data={'cname': cname}, timeout=60)


def main():
    store = sys.argv[1]; out = f'{store}/jra/probe'; os.makedirs(out, exist_ok=True)
    for step in sys.argv[2:]:
        kind, _, rest = step.partition(':')
        try:
            if kind == 'get':
                url = rest if rest.startswith('http') else BASE + rest
                wait(); r = S.get(url, timeout=60); keep(out, fname('get', url.split('//', 1)[-1]), r)
            elif kind == 'post':
                path, cname = rest.split(':', 1); r = post(path, cname); keep(out, fname('post', path, cname), r)
            elif kind == 'crawl':
                path, cname, depth, many = rest.split(':'); depth = int(depth); many = int(many)
                seen = set(); level = [cname]
                for d in range(depth + 1):
                    nxt = []
                    for c in level:
                        if c in seen: continue
                        seen.add(c); r = post(path, c); keep(out, fname('crawl', path, c), r)
                        if d == depth: continue
                        got = []
                        for p, c2 in LINK.findall(text(r)):
                            if p == path and c2 not in seen and c2 not in got: got.append(c2)
                        print('  リンク', len(got), got[:12], flush=True)
                        nxt += got[:many]
                    level = nxt
        except Exception as e:
            print('失敗', step, repr(e)[:200], flush=True)


if __name__ == '__main__':
    main()
