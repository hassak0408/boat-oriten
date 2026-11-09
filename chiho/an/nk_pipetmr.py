"""試し：まだ毎日の記録（朝の出馬表）が無い先の日の一覧を、月ごとのデータ（全部の場、STORE/data_all）に入っている先の日の出馬表から作る。
本物の毎日の記録（STORE/data/daily）は書きかえない。作業用の置き場（/tmp/nar_tmr）に、data/race と毎日の記録への近道と、その日の出馬表を置いて pipe.py を動かす。
出力は STORE/data/exp/picks/日付.json・.txt（本物の一覧は上書きしない）と、ページのレース名用の STORE/data/exp/picks/日付_racelist.csv.gz。
前の日に作るので、そのあとの取消などは入らない。当日の朝の一覧（chiho-pick）が出たら、そちらが本物。
使い方：python nk_pipetmr.py STORE 日付YYYYMMDD（GitHub の方の chiho-exp で動かす）"""
import os, sys, glob, runpy, shutil, pandas as pd

store, day = os.path.abspath(sys.argv[1]), sys.argv[2]
FIVE = {'盛岡', '水沢', '園田', '姫路', '笠松'}
T = '/tmp/nar_tmr'
shutil.rmtree(T, ignore_errors=True); os.makedirs(f'{T}/data/daily/{day}')
os.symlink(f'{store}/data/race', f'{T}/data/race')
for d in glob.glob(f'{store}/data/daily/2*'):
    b = os.path.basename(d)
    if b != day: os.symlink(d, f'{T}/data/daily/{b}')
os.makedirs(f'{store}/data/exp/picks', exist_ok=True)
for kind in ('racelist', 'horselist'):
    x = pd.read_csv(glob.glob(f'{store}/data_all/race/{day[:6]}/*{kind}*.csv.gz')[0], dtype=str, keep_default_na=False)
    y = x[x['競馬場'].isin(FIVE) & (x['競走年月日'] == day)]
    print(kind, len(y), y['競馬場'].value_counts().to_dict(), flush=True)
    y.to_csv(f'{T}/data/daily/{day}/race_{kind}_am.csv.gz', index=False, compression='gzip')
    if kind == 'racelist':
        y.to_csv(f'{store}/data/exp/picks/{day}_racelist.csv.gz', index=False, compression='gzip')
os.environ['CHIHO_DATA'] = f'{T}/data'
os.environ.setdefault('CHIHO_ALL', f'{store}/data_all')
os.environ['PICKS_DIR'] = 'data/exp/picks'
sys.argv = ['pipe.py', store, day]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipe.py'), run_name='__main__')
