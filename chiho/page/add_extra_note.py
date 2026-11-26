"""地方のページ（nar_page.py で作った HTML）の見方に、5場の外の場（名古屋など）は参考だという説明を足す。
使い方：python add_extra_note.py ページ.html 場の名前…（例：名古屋）"""
import sys
p, places = sys.argv[1], sys.argv[2:]
s = open(p, encoding='utf-8').read(); old = '<summary>見方</summary>\n      <ul>'
if s.count(old) != 1: raise SystemExit('見方の欄が見つからない')
nm = '・'.join(places)
li = (f'\n        <li><b>{nm}は参考です</b>：{nm}は5場（盛岡・水沢・園田・姫路・笠松）の外です。AIは名古屋と金沢の過去のレースで学ばせ、5場と同じ作り方で出しました。'
      f'ただ、5場で決めた直しや印が{nm}でも効くかは、確かめていません。{nm}では「来やすい型」の印は、これまでの確かめで効かなかったので出していません。'
      '「来にくい型」（買わない方がいい型）はどの場でも効いていたので、出しています。</li>')
open(p, 'w', encoding='utf-8').write(s.replace(old, old + li)); print('足した', nm)
