"""地方：5場の外の場の今日の一覧（参考）。本番の pipe.py を、data_all（全部の場）から写したその場のまとまりのデータで動かす。
学ぶデータ：まとまりの場（例：名古屋・金沢）の、今日より前のレース（data_all/race の月ごとの表）。今日の出馬表：data_all/race の今月の表の、今日・予想する場の行。
5場で決めた直し（nar_fix.json など）はそのまま掛かるが、その場では確かめていない。出力：OUT/data/picks/日付.json・.txt（OUT は一時の置き場）。
使い方：python chiho/an/nk_pipeo.py STORE まとまりの番号 日付YYYYMMDD OUT   （まとまり：1＝名古屋、2＝金沢（どちらも名古屋と金沢で学ぶ）、3＝佐賀・高知、4＝門別、5＝南関東の4場）"""
import os, sys, glob, shutil, tempfile, runpy, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
GROUPS = {1: (['名古屋'], ['名古屋', '金沢']),                       # 名古屋（ページに参考で載せる）
          2: (['金沢'], ['名古屋', '金沢']),
          3: (['佐賀', '高知'], ['佐賀', '高知']),
          4: (['門別'], ['門別']),
          5: (['大井', '川崎', '船橋', '浦和'], ['大井', '川崎', '船橋', '浦和'])}   # 2〜5 は研究の記録（AIが窓口のオッズに足せるか）。ばんえいは入れない
store, gno, day, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
PRED, LEARN = GROUPS[gno]
tmp = tempfile.mkdtemp(); n = 0
for d in sorted(glob.glob(f'{store}/data_all/race/2*')):
    b = os.path.basename(d)
    if b > day[:6]: continue
    os.makedirs(f'{tmp}/race/{b}')
    for f in glob.glob(f'{d}/*.csv.gz'):
        X = pd.read_csv(f, dtype=str, keep_default_na=False)
        if '競馬場' in X.columns: X = X[X['競馬場'].isin(LEARN)]
        if '競走年月日' in X.columns: X = X[X['競走年月日'] < day]
        if 'horselist' in f: n += len(X)
        X.to_csv(f'{tmp}/race/{b}/{os.path.basename(f)}', index=False, compression='gzip')
    if os.path.exists(f'{d}/done.json'): shutil.copy(f'{d}/done.json', f'{tmp}/race/{b}/done.json')
RL = pd.read_csv(glob.glob(f'{store}/data_all/race/{day[:6]}/*racelist*')[0], dtype=str, keep_default_na=False)
HL = pd.read_csv(glob.glob(f'{store}/data_all/race/{day[:6]}/*horselist*')[0], dtype=str, keep_default_na=False)
RL = RL[RL['競馬場'].isin(PRED) & (RL['競走年月日'] == day)]; HL = HL[HL['競馬場'].isin(PRED) & (HL['競走年月日'] == day)]
if HL.empty: raise SystemExit(f'{day} の {PRED} の出馬表が無い')
os.makedirs(f'{tmp}/daily/{day}')
RL.to_csv(f'{tmp}/daily/{day}/race_racelist_am.csv.gz', index=False, compression='gzip')
HL.to_csv(f'{tmp}/daily/{day}/race_horselist_am.csv.gz', index=False, compression='gzip')
print('予想する場', PRED, '学ぶ場', LEARN, '馬の行（今日より前）', n, '今日のレース', RL['レース番号'].nunique(), flush=True)
os.makedirs(f'{out}/data/picks', exist_ok=True)
os.environ['CHIHO_DATA'] = tmp; os.environ['CHIHO_ALL'] = f'{store}/data_all'
import hist_all; hist_all.FIVE = list(LEARN)
sys.argv = ['pipe.py', out, day]
runpy.run_path(f'{HERE}/pipe.py', run_name='__main__')
