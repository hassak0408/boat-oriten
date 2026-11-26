"""5場の一覧（store）に、5場の外の場の参考の一覧（nk_pipeo.py の出力）を足して、ページを作るための一時の置き場を作る。
外の場の馬は「来やすい型」の印を消す（OV1 で、その場では効かなかった）。「来にくい型」は残す。
使い方：python merge_extra.py STORE EXTRA_OUT 日付 TMP   → TMP/data/picks/日付.json・.txt と TMP/data/daily/日付/race_racelist.csv.gz"""
import os, sys, json, glob, pandas as pd
store, extra, day, tmp = sys.argv[1:5]
fa = f'{store}/data/picks/{day}.json'
A = json.load(open(fa, encoding='utf-8')) if os.path.exists(fa) else {'レース': [], '作った時刻': ''}      # 5場に開催が無い日は外の場だけ
B = json.load(open(f'{extra}/data/picks/{day}.json', encoding='utf-8'))
for r in B['レース']:
    for h in r['馬']:
        if '来やすい' in (h.get('型') or ''): h['型'] = ''
places = sorted(set(r['場'] for r in B['レース']))
A['レース'] = A['レース'] + B['レース']; A['作った時刻'] = f"{A.get('作った時刻', '')}（{'・'.join(places)}は {B.get('作った時刻', '')}）"
os.makedirs(f'{tmp}/data/picks', exist_ok=True); os.makedirs(f'{tmp}/data/daily/{day}', exist_ok=True)
json.dump(A, open(f'{tmp}/data/picks/{day}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
ta = f'{store}/data/picks/{day}.txt'
open(f'{tmp}/data/picks/{day}.txt', 'w', encoding='utf-8').write((open(ta, encoding='utf-8').read() if os.path.exists(ta) else '') + '\n' + open(f'{extra}/data/picks/{day}.txt', encoding='utf-8').read())
ra = f'{store}/data/daily/{day}/race_racelist.csv.gz'
R1 = pd.read_csv(ra, dtype=str) if os.path.exists(ra) else None
R2 = pd.read_csv(glob.glob(f'{store}/data_all/race/{day[:6]}/*racelist*')[0], dtype=str)
R2 = R2[R2['競馬場'].isin(places) & (R2['競走年月日'] == day)]
(pd.concat([R1, R2[[c for c in R1.columns if c in R2.columns]]], ignore_index=True) if R1 is not None else R2).to_csv(f'{tmp}/data/daily/{day}/race_racelist.csv.gz', index=False, compression='gzip')
print('足した場', places, 'レース', len(B['レース']), '／合わせて', len(A['レース']))
