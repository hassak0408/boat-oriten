"""地方のページを作る：python nar_page.py STORE 日付 出力.html [一覧の名前（既定：日付_mid.json があればそれ、無ければ 日付.json）]
朝の一覧（chiho-pick の .json）か昼の見直し（mid.py の _mid.json）に、レース表（レース名・馬場）と .txt の「3組のどれか」を足して、nar_template.html に入れる。
2026-11-23 に作業場所が消えたので、公開中のページ（11/19 の版）から型紙を取り戻して作り直した。"""
import json, os, re, sys, datetime as dt
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
store, day, out = sys.argv[1:4]
src = sys.argv[4] if len(sys.argv) > 4 else (f'{day}_mid.json' if os.path.exists(f'{store}/data/picks/{day}_mid.json') else f'{day}.json')
o = json.load(open(f'{store}/data/picks/{src}', encoding='utf-8'))
cur = None; any3 = {}
for ln in open(f'{store}/data/picks/{day}.txt', encoding='utf-8'):
    m = re.match(r'^(\S+?) (\d+)R ', ln)
    if m: cur = (m.group(1), int(m.group(2))); continue
    m = re.search(r'（3組のどれか (\d+)%）', ln)
    if m and cur: any3[cur] = int(m.group(1))
RL = pd.read_csv(f'{store}/data/daily/{day}/race_racelist.csv.gz', dtype=str)
info = {(p, int(r)): (n, b, s) for p, r, n, b, s in zip(RL['競馬場'], RL['レース番号'], RL['レース名'].fillna(''), RL['馬場'].fillna(''), RL['芝ダート区分'].fillna(''))}
for r in o['レース']:
    n, b, s = info.get((r['場'], int(r['R'])), ('', '', ''))
    r['レース名'] = n; r['馬場'] = b; r['芝ダ'] = 'ダ' if s.startswith('ダ') else (s or 'ダ')
    if (r['場'], int(r['R'])) in any3: r['三組'] = any3[(r['場'], int(r['R']))]
    if not all('順位' in h for h in r['馬']):
        for k, h in enumerate(r['馬'], start=1): h['順位'] = k
d = dt.datetime.strptime(o['日付'], '%Y%m%d'); wd = '月火水木金土日'[d.weekday()]
title = f'地方 評価一覧 {d.month}月{d.day}日（{wd}）'
tpl = open(os.path.join(HERE, 'nar_template.html'), encoding='utf-8').read()
html = tpl.replace('__TITLE__', title).replace('__DATA__', json.dumps(o, ensure_ascii=False).replace('</', '<\\/'))
open(out, 'w', encoding='utf-8').write(html)
print('書いた', out, len(html.encode()), 'バイト／元', src, '／', len(o['レース']), 'レース／題', title, '／3組', len(any3), '／昼の見直し', (o.get('昼の見直し') or {}).get('時刻', 'なし'))
