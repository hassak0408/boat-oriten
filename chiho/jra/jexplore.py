"""中央競馬：JRA公式サイトのページの形を確かめる（血統を集める前の下調べ。読み込みは5秒に1回まで）。
読んだページを STORE/jra/explore/ に置く（非公開の置き場。下調べが終わったら消す）。
使い方：python chiho/jra/jexplore.py STORE 手順…
  手順の書き方：S:cname（accessS.html に POST）／U:cname（accessU.html に POST）／D:cname（accessD.html に POST）／G:パス?CNAME=…（GET）
  特別な手順：horse（今の出馬表から馬のページを3つ読む）、F:頭の文字（前のページの、その文字で始まる最初のリンクを読む）"""
import os, re, sys, time, requests

BASE = 'https://www.jra.go.jp'
S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0 (personal research; 1 request / 5s)', 'Accept-Language': 'ja'})
last = [0.0]
store = sys.argv[1]; out = f'{store}/jra/explore'; os.makedirs(out, exist_ok=True)


def get(method, path, cname):
    w = last[0] + 5 - time.time()
    if w > 0: time.sleep(w)
    last[0] = time.time()
    try:
        r = S.post(BASE + path, data={'cname': cname}, timeout=60) if method == 'POST' else S.get(BASE + path, timeout=60)
        print(method, path, cname, r.status_code, len(r.content), flush=True)
        return r.content.decode('cp932', errors='replace') if r.status_code == 200 else None
    except requests.RequestException as e:
        print('通信エラー', type(e).__name__, flush=True); return None


def save(name, page):
    if page is None: return
    name = re.sub(r'[^0-9A-Za-z_.-]', '_', name)[:120]
    open(f'{out}/{name}.html', 'w', encoding='utf-8').write(page)


prev = ''
for step in sys.argv[2:]:
    if step == 'horse':
        top = get('POST', '/JRADB/accessD.html', 'pw01dli00/F3'); save('dli00', top)
        drl = re.findall(r"doAction\('/JRADB/accessD.html',\s*'(pw01drl[0-9A-F/]+)'\)", top or '')
        if not drl: continue
        rl = get('POST', '/JRADB/accessD.html', drl[0]); save('drl', rl)
        des = re.search(r"doAction\('/JRADB/accessD.html',\s*'(pw01des\d+/[0-9A-F]{2})'\)", rl or '')
        if not des: continue
        dp = get('POST', '/JRADB/accessD.html', des.group(1)); save('des', dp)
        links = re.findall(r'href="([^"]*CNAME=pw01dud[0-9A-F/]+)"', dp or '')
        print('馬のリンク', len(links), links[:3], flush=True)
        for h in links[:3]:
            save('dud_' + h.split('CNAME=')[1], get('GET', h if h.startswith('/') else '/JRADB/' + h.split('/JRADB/')[-1], ''))
        continue
    kind, arg = step.split(':', 1)
    if kind == 'F':      # 前のページのリンクをたどる（doAction でも href でも）
        m = re.search(r"doAction\('(/JRADB/access\w+\.html)',\s*'(%s[0-9A-Fa-f/]*)'\)" % re.escape(arg), prev)
        h = re.search(r'href="(/JRADB/access\w+\.html\?CNAME=%s[0-9A-Fa-f/]*)"' % re.escape(arg), prev)
        if m: pg = get('POST', m.group(1), m.group(2)); save('F_' + m.group(2), pg)
        elif h: pg = get('GET', h.group(1), ''); save('F_' + h.group(1).split('CNAME=')[1], pg)
        else: print('たどるリンクが無い', arg, flush=True); continue
    elif kind == 'G': pg = get('GET', arg, ''); save('G_' + arg.split('CNAME=')[-1], pg)
    else: pg = get('POST', {'S': '/JRADB/accessS.html', 'U': '/JRADB/accessU.html', 'D': '/JRADB/accessD.html'}[kind], arg); save(f'{kind}_' + arg, pg)
    prev = pg or ''
