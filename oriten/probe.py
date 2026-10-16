"""①分かっている場：何年前までさかのぼれるか ②まだ分からない場：オリジナル展示のページの場所を探す。
結果は probe/report.json と probe/samples/（まわり足を含むページだけ）に置く。"""
import csv, json, os, re, datetime as dt
from urllib.parse import urljoin, urlparse
import lxml.html
from .venues import VENUES, CANDIDATES, PATHS
from .net import Fetcher
from .parse import parse_page

KEYW = ('yosou', 'tenji', 'oriten', 'cyokuzen', 'chokuzen', 'original', 'before', 'race', 'raceinfo', 'data')

def load_days(path='schedule/race_days.csv'):
    days = {}
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            days.setdefault(int(row['venue']), []).append(row['date'])
    return {k: sorted(v) for k, v in days.items()}

def near(days, target):
    c = [d for d in days if d <= target]
    return c[-1] if c else None

def save(name, html):
    os.makedirs('probe/samples', exist_ok=True)
    with open(f'probe/samples/{name}.html', 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    D = load_days(); rep = {'history': {}, 'search': {}}
    F = Fetcher(1.0)
    # ① さかのぼれるか
    for v, cfg in VENUES.items():
        res = []
        for t in ['2026-10-15', '2025-10-10', '2024-10-10', '2023-10-10', '2022-10-10', '2021-10-10', '2021-04-10', '2020-10-10', '2019-10-10', '2018-10-10']:
            d = near(D.get(v, []), t)
            if not d:
                continue
            ok = False
            for r in (1, 6, 12):
                code, html = F.get(cfg['url'].format(d=d.replace('-', ''), r=r))
                rows, memo = parse_page(html) if code == 200 else ([], str(code))
                if rows:
                    ok = True
                    if t == '2026-10-15':
                        save(f'{v:02d}_{d}_{r}', html)
                    break
            res.append(dict(target=t, date=d, data=ok, n=len(rows) if ok else 0, memo=memo))
            print(cfg['name'], d, 'あり' if ok else 'なし', memo, flush=True)
        rep['history'][v] = res
    # ② ページの場所を探す
    for v, cfg in CANDIDATES.items():
        d = near(D.get(v, []), '2026-10-15'); ymd = d.replace('-', '') if d else None
        hits = []; tried = []
        cands = [s + p for s in cfg['sites'] for p in PATHS] + cfg.get('extra', [])
        for u in cands:
            url = u.format(d=ymd, r=1, r2='01')
            code, html = F.get(url, tries=1)
            rows, memo = parse_page(html) if code == 200 else ([], str(code))
            tried.append(dict(url=url, code=code, n=len(rows), memo=memo))
            if code == 200 and ('まわり' in (html or '')):
                save(f'{v:02d}_hit{len(hits)}', html); hits.append(dict(url=url, n=len(rows), memo=memo))
        # トップページからリンクとiframeをたどる
        links = []
        for s in cfg['sites']:
            code, html = F.get(s + '/', tries=1)
            if code != 200 or not html:
                tried.append(dict(url=s + '/', code=code)); continue
            save(f'{v:02d}_top', html)
            try:
                doc = lxml.html.fromstring(html)
            except Exception:
                continue
            for el in doc.xpath('//a[@href]|//iframe[@src]'):
                h = el.get('href') or el.get('src'); full = urljoin(s + '/', h)
                if urlparse(full).netloc.split(':')[0].endswith(urlparse(s).netloc.replace('www.', '')) and any(k in full.lower() for k in KEYW):
                    if full not in links:
                        links.append(full)
        for i, u in enumerate(links[:30]):
            code, html = F.get(u, tries=1)
            has = code == 200 and ('まわり' in (html or ''))
            tried.append(dict(url=u, code=code, has_mawari=has))
            if has:
                save(f'{v:02d}_link{i}', html); hits.append(dict(url=u, n=len(parse_page(html)[0])))
        rep['search'][v] = dict(name=cfg['name'], date=d, hits=hits, tried=tried, links=links[:60])
        print(cfg['name'], '見つかった' if hits else '見つからない', [h['url'] for h in hits][:3], flush=True)
    os.makedirs('probe', exist_ok=True)
    with open('probe/report.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
