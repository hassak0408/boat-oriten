"""中央競馬の成績表（JRA公式サイトのPDF）を年ごとに落として読み、レースと馬の表（CSV、gzip）にして STORE/jra/data/年/ に置く。PDFそのものは残さない。
- 読み込みは10秒に1回まで。読み終わった日は index.json に記録し、次の回は飛ばす（その年の一覧のページだけは毎回読む）。
- 環境変数 LIMIT_MIN（分）を過ぎたら止めて、残りの数を出す（GITHUB_OUTPUT の left）。
使い方：python chiho/jra/dl.py STORE 年 [年 ...]"""
import os, re, io, sys, csv, gzip, json, time, tempfile, subprocess, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse
BASE = 'https://www.jra.go.jp'
UA = 'Mozilla/5.0 (personal research; JRA race result PDFs, 1 request / 10s)'
GAP = 10
S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
last = [0.0]
RC = ['年月日', '場', '回', '日目', 'R', 'レース名', '芝ダ', 'コース', '距離', '天候', '馬場', '条件', '年齢', '重量', '牝限', '格', '発走', '頭数', '上り3F', '賞金',
      '角', '払戻', '見出し']
HC = ['年月日', '場', 'R', '行', '枠', '馬番', '馬名', '性', '齢', '毛色', '斤量', '騎手', '減量', '馬主', '調教師', '産地', '生産', 'ブリンカー', '馬体重', '増減',
      'タイム', '着差', '単勝オッズ', '人気', '状態', '着順']
GIT_ID = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com']


def get(url):
    for k in range(3):
        w = last[0] + GAP - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        try:
            r = S.get(url, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504): time.sleep(60 * (k + 1)); continue
            return r
        except requests.RequestException as e:
            print('通信エラー', type(e).__name__, flush=True); time.sleep(60)
    return None


def save(store, msg):
    def run(*a): return subprocess.run(['git', '-C', store] + GIT_ID + list(a), capture_output=True, text=True)
    run('add', 'jra')
    if run('diff', '--cached', '--quiet').returncode == 0: return
    run('commit', '-q', '-m', msg)
    for _ in range(5):
        if run('push', '-q', 'origin', 'HEAD:main').returncode == 0: print('保存した', flush=True); return
        run('fetch', '-q', '--depth', '20', 'origin', 'main'); r = run('rebase', '-q', 'origin/main')
        if r.returncode != 0: run('rebase', '--abort')
        time.sleep(5)
    print('保存できなかった', flush=True)


def write(path, head, rows):
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)


def main():
    store = sys.argv[1]; years = sys.argv[2:]
    limit = float(os.environ.get('LIMIT_MIN', '320')) * 60; mx = int(os.environ.get('MAX_FILES', '0') or 0)
    t0 = time.time(); last_save = time.time(); left = 0; n_done = 0
    for y in years:
        out = f'{store}/jra/data/{y}'; os.makedirs(out, exist_ok=True)
        ip = f'{out}/index.json'; idx = json.load(open(ip, encoding='utf-8')) if os.path.exists(ip) else {}
        r = get(f'{BASE}/datafile/seiseki/report/{y}.html')
        if r is None or r.status_code != 200: print(y, '一覧を読めない', flush=True); left += 1; continue
        r.encoding = r.apparent_encoding or 'utf-8'
        names = sorted(set(re.findall(r'(%s-\d+[a-z]+\d+)\.pdf' % y, r.text)))
        print(y, 'PDFの数', len(names), 'うち済み', sum(1 for n in names if idx.get(n, {}).get('済')), flush=True)
        for name in names:
            if idx.get(name, {}).get('済'): continue
            if time.time() - t0 > limit or (mx and n_done >= mx): left += 1; continue
            p = get(f'{BASE}/datafile/seiseki/report/{y}/{name}.pdf')
            rec = {'済': False}
            if p is None or p.status_code != 200 or p.content[:4] != b'%PDF':
                rec['エラー'] = f'読めない {getattr(p, "status_code", None)}'; idx[name] = rec; continue
            idx[name] = process(name, p.content, out)
            if not idx[name]['済']: continue
            n_done += 1
            json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
            if time.time() - last_save > 1800: save(store, f'中央競馬の成績表（途中） {y}'); last_save = time.time()
        json.dump(idx, open(ip, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    save(store, '中央競馬の成績表 ' + ' '.join(years))
    print('残り', left, flush=True)
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write(f'left={left}\n')


def process(name, content, out):
    """1日分のPDFを読んで、レースと馬の表を書く。index.json に入れる記録を返す"""
    d = tempfile.mkdtemp(); path = os.path.join(d, name + '.pdf')
    try:
        open(path, 'wb').write(content)
        rs = parse.parse_pdf(path)
    except Exception as e:
        return {'済': False, 'エラー': repr(e)[:200]}
    finally:
        try: os.remove(path); os.rmdir(d)
        except OSError: pass
    rows_r, rows_h, bad = [], [], []
    for x in rs:
        rows_r.append([x.get(c) if c not in ('角', '払戻') else json.dumps(x.get(c), ensure_ascii=False) for c in RC])
        for h in x['馬']:
            rows_h.append([x['年月日'], x['場'], x['R']] + [h.get(c) for c in HC[3:]])
        n_ok = len([h for h in x['馬'] if h['状態'] not in ('出走取消', '取消', '競走除外', '除外')])
        if x['頭数'] != n_ok or '読めない' in x['払戻'] or not x['払戻']: bad.append(x['R'])
    write(f'{out}/{name}_races.csv.gz', RC, rows_r); write(f'{out}/{name}_horses.csv.gz', HC, rows_h)
    print(name, 'レース', len(rs), '頭', len(rows_h), '合わない', bad, flush=True)
    return {'済': True, 'レース': len(rs), '頭': len(rows_h), '合わないレース': bad, 'バイト': len(content)}


if __name__ == '__main__':
    main()
