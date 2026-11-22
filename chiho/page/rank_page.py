"""中央のページを作る：python rank_page.py 一覧.json 一覧.txt 出力.html
一覧（jpipe の .json）に、.txt の「3組のどれか」と、展開予想・短評（jra_extra）を足して、rank_template.html に入れる。
2026-11-23 に作業場所が消えたので、公開中のページから型紙を取り戻して作り直した（note_jra.py・wrap.py の分は型紙に入れた）。"""
import json, os, re, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import jra_extra
src, txt, out = sys.argv[1:4]
o = json.load(open(src, encoding='utf-8'))
cur = None; any3 = {}
for ln in open(txt, encoding='utf-8'):
    m = re.match(r'^(\S+?)(\d+)R \d{1,2}:\d{2} ', ln)
    if m: cur = (m.group(1), int(m.group(2))); continue
    m = re.search(r'（3組のどれか (\d+)%）', ln)
    if m and cur: any3[cur] = int(m.group(1))
for r in o['レース']:
    if (r['場'], int(r['R'])) in any3: r['三組'] = any3[(r['場'], int(r['R']))]
jra_extra.add(o)
d = dt.datetime.strptime(o['日付'], '%Y%m%d'); wd = '月火水木金土日'[d.weekday()]
title = f'中央 能力ランキング {d.month}月{d.day}日（{wd}）'
tpl = open(os.path.join(HERE, 'rank_template.html'), encoding='utf-8').read()
html = tpl.replace('__TITLE__', title).replace('__DATA__', json.dumps(o, ensure_ascii=False).replace('</', '<\\/'))
open(out, 'w', encoding='utf-8').write(html)
print('書いた', out, len(html.encode()), 'バイト', len(o['レース']), 'レース／題', title, '／3組', len(any3), '／足しの元', o['足しの元'],
      '／展開の型', sum(1 for r in o['レース'] for h in r['馬'] if h.get('展開型')), '頭・逃げ型', sum(1 for r in o['レース'] for h in r['馬'] if h.get('逃げ型')), '頭')
