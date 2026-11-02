"""中央競馬の発売票数（JRA公式サイトのPDF。掲載は約60日）を読んで、組ごとの票数の表にする（検証計画 J4）。
- 1レースの最初のページにある 単勝・複勝・枠連・馬連・馬単・ワイド を読む（3連複・3連単は次のページにまたがるので読まない）。
- 馬番の丸数字はレースごとに字の番号が変わるので、単勝の並び（馬番の順）から、字の番号→馬番を作る。
- 当たりの組は一覧で「★★★★」になり、票数は「的中」のところに書いてある。
使い方：python hyo.py STORE 年 [年 ...]（一覧のページから新しい発売票数のPDFを落として STORE/jra/hyo/年/ に置く）
        python hyo.py --test PDF（読めるか確かめるだけ）"""
import os, re, sys, csv, gzip, json, time, tempfile
import pdfplumber
SEC = [('単勝', '単勝票数'), ('複勝', '複勝票数'), ('枠連', '枠連票数'), ('馬連', '普通馬連票数'), ('馬単', '馬単票数'), ('ワイド', 'ワイド【拡大馬連】票数'),
       ('3連複', '3連複票数'), ('3連単', '3連単票数')]
PLACE = {'札幌': '札幌', '函館': '函館', '福島': '福島', '新潟': '新潟', '東京': '東京', '中山': '中山', '中京': '中京', '京都': '京都', '阪神': '阪神', '小倉': '小倉'}


def dec(t):
    return re.sub(r'\(cid:(\d+)\)', lambda m: str(int(m.group(1)) - 9872) if 9872 <= int(m.group(1)) <= 9881 else f'[{m.group(1)}]', t)


def parse_page(t):
    m = re.search(r'(\d{4})年 第(\d+)回(\S+?)競馬第(\d+)日 （(\d+)月(\d+)日 \S+?）\s*第(\d+)競走', t)
    if not m or '単勝票数' not in t: return None
    y, kai, place, nichi, mon, day, rno = m.groups()
    race = dict(年月日=f'{int(y):04d}{int(mon):02d}{int(day):02d}', 場=place, R=int(rno), 回=int(kai), 日目=int(nichi))
    # 券ごとに切り分ける
    pos = sorted((t.find(lab), kind, lab) for kind, lab in SEC if t.find(lab) >= 0)
    parts = {}
    for k, (p, kind, lab) in enumerate(pos):
        end = pos[k + 1][0] if k + 1 < len(pos) else len(t)
        parts[kind] = t[p + len(lab):end]
    # 単勝の並び → 字の番号から馬番へ
    s = parts.get('単勝', '')
    first, _, rest = s.partition('\n')
    order = re.findall(r'(\[\d+\]) ?(\d+|★★★★|―)', rest)       # 「―」は取消の馬（並びには入っている）
    gmap = {g: i + 1 for i, (g, _) in enumerate(order)}
    race['_順'] = [g for g, _ in order]
    out = []
    for kind, s in parts.items():
        if kind in ('3連複', '3連単'): continue
        first, _, rest = s.partition('\n')
        tm = re.search(r'計 (\d+)', first); total = int(tm.group(1)) if tm else None
        hits = {}
        if kind == '枠連':
            for a, b, v in re.findall(r'（(\d)−(\d)）\s?(\d+)（\d+番人気）', first): hits[(int(a), int(b))] = int(v)
            items = [((int(a), int(b)), v) for a, b, v in re.findall(r'（(\d)−(\d)）\s?(\d+|★★★★|―)', rest)]
        else:
            for gs, v in re.findall(r'((?:\[\d+\])+) (\d+)（\d+番人気）', first):
                hits[tuple(gmap.get(g, -1) for g in re.findall(r'\[\d+\]', gs))] = int(v)
            items = [(tuple(gmap.get(g, -1) for g in re.findall(r'\[\d+\]', gs)), v) for gs, v in re.findall(r'((?:\[\d+\])+) ?(\d+|★★★★|―)', rest)]
        seen = set()
        for combo, v in items:
            if combo in seen: continue
            seen.add(combo)
            if v == '―': continue                 # 取消の馬を含む組
            votes = hits.get(combo) if v == '★★★★' else int(v)
            out.append(dict(券=kind, 組='-'.join(map(str, combo)), 票数=votes, 計=total, 的中=int(combo in hits)))
        for combo, v in hits.items():          # 一覧に無い当たり（念のため）
            if combo not in seen: out.append(dict(券=kind, 組='-'.join(map(str, combo)), 票数=v, 計=total, 的中=1))
    race['票'] = out
    return race


def parse_pdf(path):
    races = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            r = parse_page(dec(p.extract_text() or ''))
            if r: races.append(r)
    return races


HC = ['年月日', '場', 'R', '券', '組', '票数', '計', '的中']


def write(path, races):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(HC)
        for r in races:
            for x in r['票']:
                w.writerow([r['年月日'], r['場'], r['R'], x['券'], x['組'], x['票数'], x['計'], x['的中']])


def main():
    if sys.argv[1] == '--test':
        for f in sys.argv[2:]:
            rs = parse_pdf(f)
            print(f, 'レース', len(rs))
            for r in rs[:2]:
                c = {}
                for x in r['票']: c[x['券']] = c.get(x['券'], 0) + 1
                print(' ', r['年月日'], r['場'], r['R'], '馬', len(r['_順']), c, [x for x in r['票'] if x['券'] == '単勝'][:3])
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dl                                   # 読み込みの間（10秒）と保存のしかたは成績表と同じ
    store = sys.argv[1]; years = sys.argv[2:]
    for y in years:
        out = f'{store}/jra/hyo/{y}'; os.makedirs(out, exist_ok=True)
        ip = f'{out}/index.json'; idx = json.load(open(ip, encoding='utf-8')) if os.path.exists(ip) else {}
        r = dl.get(f'{dl.BASE}/datafile/seiseki/report/{y}.html')
        if r is None or r.status_code != 200: print(y, '一覧を読めない', flush=True); continue
        names = sorted(set(re.findall(r'(%s\d{4}-hyo-[a-z]+)\.pdf' % y, r.text)))
        print(y, '発売票数のPDF', len(names), 'うち済み', sum(1 for n in names if idx.get(n, {}).get('済')), flush=True)
        for name in names:
            if idx.get(name, {}).get('済'): continue
            p = dl.get(f'{dl.BASE}/datafile/seiseki/report/{y}/{name}.pdf')
            if p is None or p.status_code != 200 or p.content[:4] != b'%PDF':
                idx[name] = {'済': False, 'エラー': f'読めない {getattr(p, "status_code", None)}'}; continue
            d = tempfile.mkdtemp(); path = os.path.join(d, name + '.pdf')
            try:
                open(path, 'wb').write(p.content); rs = parse_pdf(path)
                write(f'{out}/{name}.csv.gz', rs)
                idx[name] = {'済': True, 'レース': len(rs), '行': sum(len(x['票']) for x in rs)}
                print(name, 'レース', len(rs), flush=True)
            except Exception as e:
                idx[name] = {'済': False, 'エラー': repr(e)[:200]}
            finally:
                try: os.remove(path); os.rmdir(d)
                except OSError: pass
            json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    dl.save(store, '中央競馬の発売票数 ' + ' '.join(years))


if __name__ == '__main__':
    main()
