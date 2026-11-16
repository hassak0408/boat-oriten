"""中央競馬の締切前のオッズ（JRA公式サイトのオッズのページ）を、発走の約10分前と約3分前に読んで、STORE/jra/odds/日付.csv.gz に足していく。
読むのは単勝・複勝（pw151ou…）とワイド（pw155ou…）。評価（予測）には使わない。ワイドなどの「値段の甘い所」を前向きに確かめるための記録（検証計画 WD7・WD8・PL2）。
読み込みは10秒に1回まで。開催のページ（pw15orl…）から各レースのページの名前を拾う。発走時刻は出馬表（jra/card/日付.csv.gz）のもの。
使い方：python chiho/jra/jodds.py STORE 日付YYYYMMDD [動かす分（既定 330）] [test（発走に関わらず、はじめの2レースを今すぐ1回読む。作りの確かめ用）]
  終わったとき、まだ読んでいないレースが残っていれば STORE/jra/odds/日付.more を置く（仕組みの方が続きを動かす）。"""
import os, re, sys, time, datetime as dt, requests, pandas as pd

BASE = 'https://www.jra.go.jp'; UA = 'Mozilla/5.0 (personal research; 1 request / 10s)'
S = requests.Session(); S.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})
JST = dt.timezone(dt.timedelta(hours=9)); last = [0.0]
PLACE = {'01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京', '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉'}
TARGETS = (10, 3)      # 発走の何分前に読むか


def fetch(cname):
    for k in range(3):
        w = last[0] + 10 - time.time()
        if w > 0: time.sleep(w)
        last[0] = time.time()
        try:
            r = S.post(BASE + '/JRADB/accessO.html', data={'cname': cname}, timeout=60)
            if r.status_code == 200: return r.content.decode('cp932', errors='replace')
            print('読めない', r.status_code, cname, flush=True)
        except requests.RequestException as e:
            print('通信エラー', type(e).__name__, flush=True)
        time.sleep(20)
    return None


def parse_tan(page):
    """単勝・複勝：[(賭式, 馬番, '', オッズ, 最大)]"""
    out = []
    for m in re.finditer(r'<td class="num">(\d+)</td>(.*?)</tr>', page, re.S):
        b = m.group(2); t = re.search(r'class="odds_tan[^"]*"[^>]*>(?:\s*<[^>]+>)*\s*([\d.]+)', b); f = re.search(r'class="odds_fuku".*?class="min">(?:\s*<[^>]+>)*\s*([\d.]+).*?class="max">(?:\s*<[^>]+>)*\s*([\d.]+)', b, re.S)
        if t: out.append(('単勝', int(m.group(1)), '', float(t.group(1)), ''))
        if f: out.append(('複勝', int(m.group(1)), '', float(f.group(1)), float(f.group(2))))
    return out


def parse_wide(page):
    """ワイド：[(賭式, 馬番1, 馬番2, 下の値, 上の値)]"""
    out = []
    for m in re.finditer(r'<table class="[^"]*\bwide\b[^"]*">\s*<caption>(\d+)</caption>(.*?)</table>', page, re.S):
        a = int(m.group(1))
        for r in re.finditer(r'<th scope="row">(\d+)</th>\s*<td class="odds">.*?class="min">(?:\s*<[^>]+>)*\s*([\d.]+).*?class="max">(?:\s*<[^>]+>)*\s*([\d.]+)', m.group(2), re.S):
            out.append(('ワイド', a, int(r.group(1)), float(r.group(2)), float(r.group(3))))
    return out


def main():
    store, day = sys.argv[1], sys.argv[2]
    budget = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != 'test' else 330.0; test = 'test' in sys.argv[3:]
    t0 = time.time(); od = f'{store}/jra/odds'; os.makedirs(od, exist_ok=True); path = f'{od}/{day}.csv.gz'; more = f'{od}/{day}.more'
    if os.path.exists(more): os.remove(more)
    cp = f'{store}/jra/card/{day}.csv.gz'
    if not os.path.exists(cp): print('出馬表が無い（開催なし）'); return
    C = pd.read_csv(cp, dtype=str, keep_default_na=False)[['場', 'R', '発走']].drop_duplicates(['場', 'R'])
    post = {(p, int(r)): dt.datetime.strptime(day + t.zfill(4), '%Y%m%d%H%M').replace(tzinfo=JST) for p, r, t in zip(C['場'], C['R'], C['発走']) if t}
    old = pd.read_csv(path, dtype=str, keep_default_na=False) if os.path.exists(path) else None
    done = set(zip(old['場'], old['R'].astype(int), old['回目'])) if old is not None else set()
    now = lambda: dt.datetime.now(JST)
    todo = lambda: [(k, tg) for k in post for tg in TARGETS if (k[0], k[1], str(tg)) not in done and now() < post[k]]
    if not test and not todo(): print('読むレースが残っていない'); return
    # 各レースのページの名前
    top = fetch('pw15oli00/6D'); names = {}
    for cn in sorted(set(re.findall(r"'(pw15orl\d+%s/[0-9A-F]{2})'" % day, top or ''))):
        rl = fetch(cn) or ''
        for kind, c in re.findall(r"'(pw15[15]ou)(\d+%sZ/[0-9A-F]{2})'" % day, rl):
            pl = PLACE.get(c[2:4]); rno = int(c[12:14]); names.setdefault((pl, rno), {})[kind] = kind + c
    print('開催のページから拾ったレース', len(names), '／出馬表のレース', len(post), flush=True)
    rows = []

    def snap(k, tg):
        got = 0
        for kind, parse in (('pw151ou', parse_tan), ('pw155ou', parse_wide)):
            cn = names.get(k, {}).get(kind)
            if not cn: continue
            page = fetch(cn); t = now()
            for b, n1, n2, o, mx in (parse(page) if page else []):
                rows.append(dict(取得=t.strftime('%Y-%m-%d %H:%M:%S'), 発走まで分=round((post[k] - t).total_seconds() / 60, 1) if k in post else '', 場=k[0], 年月日=day, R=k[1], 回目=str(tg), 賭式=b, 番号1=n1, 番号2=n2, オッズ=o, 最大=mx)); got += 1
        done.add((k[0], k[1], str(tg))); print(k[0], k[1], 'R', tg, '分前の回', '行', got, flush=True)

    def save():
        if not rows: return
        new = pd.DataFrame(rows).astype(str); out = pd.concat([old, new], ignore_index=True) if old is not None else new
        out.to_csv(path, index=False, compression='gzip')

    if test:
        for k in sorted(names)[:2]: snap(k, 'test')
        save(); print('試し：行', len(rows), pd.DataFrame(rows).groupby(['場', 'R', '賭式']).size().to_dict()); return
    while time.time() - t0 < budget * 60:
        due = sorted(((post[k] - dt.timedelta(minutes=tg), k, tg) for k, tg in todo()), key=lambda x: x[0])
        if not due: break
        when, k, tg = due[0]
        w = (when - now()).total_seconds()
        if w > 0:
            if time.time() - t0 + w > budget * 60: break
            time.sleep(min(w, 60)); continue
        snap(k, tg); save()
    save()
    if todo(): open(more, 'w').write('1'); print('続きあり', len(todo()))
    else: print('全部読んだ')


if __name__ == '__main__':
    main()
