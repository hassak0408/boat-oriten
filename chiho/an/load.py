"""chiho/data/race/YYYYMM/ の3つのCSV（レース一覧・払戻・出馬表）を読んで、1つの表にまとめる。"""
import glob, gzip, os, pandas as pd

D = os.path.join(os.path.dirname(__file__), '..', 'data')

def _read(kind, pat):
    fs = sorted(glob.glob(f'{D}/{kind}/*/*{pat}*.csv.gz'))
    if not fs: return pd.DataFrame()
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in fs], ignore_index=True)

def races():
    r = _read('race', 'racelist')
    r['頭数'] = pd.to_numeric(r['頭数'], errors='coerce')
    return r.drop_duplicates(['競馬場', '競走年月日', 'レース番号'])

def payback():
    return _read('race', 'payback')

def horses():
    h = _read('race', 'horselist')
    for c in ['馬番', '枠番', '着順', '人気', '齢', '負担重量', '馬体重']:
        h[c] = pd.to_numeric(h[c], errors='coerce')
    return h

def odds():
    o = _read('odds', 'odds')
    for c in ['オッズ', 'オッズ（最大）', '人気']:
        o[c] = pd.to_numeric(o[c], errors='coerce')
    return o
