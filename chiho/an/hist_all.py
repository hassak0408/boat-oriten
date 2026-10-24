"""B3：全部の場の前の成績（検証計画「B3：全部の場の前の成績を足す」）。
全部の場のレース情報（data_all/race、環境変数 CHIHO_ALL）で、馬ごとの前のレースを5場の外も含めて並べ直し、
B2と同じ作り方で前の成績の材料を作る。5場のレースの行だけを /tmp/chiho_hist_all.pkl に置く（feat3.py が B2 の材料の表に入れ替える）。"""
import os, glob, time, numpy as np, pandas as pd
from feat import tsec, corner_pos, rec4, LOSE_STATUS, num
from feat2 import cls
KEY = ['競馬場', '競走年月日', 'レース番号']
ALL = os.environ.get('CHIHO_ALL', '/home/claude/chiho-keiba/data_all')
FIVE = ['盛岡', '水沢', '園田', '姫路', '笠松']
t0 = time.time()
def log(*a): print(f'[{time.time() - t0:5.0f}秒]', *a, flush=True)

HC = KEY + ['馬番', '馬名', '生年月日', '騎手名', '騎手所属', '負担重量', '全成績', '着順', 'タイム', '着差', '上がり3F', '人気']
RC = KEY + ['距離', '1着賞金(円)', '馬場', 'レース名', '競走種類名称', 'コーナー通過順1']
hs, rs, ws = [], [], []
for d in sorted(glob.glob(f'{ALL}/race/2*')):
    for f in glob.glob(f'{d}/*racelist*.csv.gz'): rs.append(pd.read_csv(f, dtype=str, keep_default_na=False, usecols=RC))
    for f in glob.glob(f'{d}/*payback*.csv.gz'):
        p = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['単勝組番'])
        ws.append(p[p['単勝組番'] != ''][KEY].drop_duplicates())
    for f in glob.glob(f'{d}/*horselist*.csv.gz'):
        h = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=HC)
        h['着'] = pd.to_numeric(h['着順'], errors='coerce')
        st = h['着差'].where(h['着'].isna(), '')
        h = h[h['着'].notna() | st.isin(LOSE_STATUS)].copy()
        h['中止'] = h['着'].isna()
        h['馬'] = h['馬名'] + '|' + h['生年月日']; h['騎'] = h['騎手名'] + '|' + h['騎手所属']
        h['馬番'] = pd.to_numeric(h['馬番'], errors='coerce'); h['人気'] = pd.to_numeric(h['人気'], errors='coerce')
        h['負担重量'] = pd.to_numeric(h['負担重量'].str.replace(r'[^0-9.]', '', regex=True), errors='coerce')
        a, b, c, e = rec4(h['全成績']); h['全走'] = a + b + c + e
        h['sec'] = h['タイム'].map(tsec); h['上り'] = pd.to_numeric(h['上がり3F'], errors='coerce')
        hs.append(h[KEY + ['馬番', '馬', '騎', '負担重量', '全走', '着', '中止', 'sec', '上り', '人気']])
R = pd.concat(rs, ignore_index=True).drop_duplicates(KEY); W = pd.concat(ws, ignore_index=True).drop_duplicates()
H = pd.concat(hs, ignore_index=True); del hs, rs, ws
log('読み込み', 'レース', len(R), '頭', len(H))
H = H.merge(W.assign(単あり=1), on=KEY, how='left'); H = H[H['単あり'].notna()].drop(columns='単あり')   # 不成立・取りやめは外す（B2と同じ）
H = H.dropna(subset=['馬番'])
for c in ('馬', '騎', '競馬場'): H[c] = H[c].astype('category')
H['n'] = H.groupby(KEY, observed=True)['馬番'].transform('size')
H['着x'] = H['着'].fillna(H['n'])
R['距離'] = pd.to_numeric(R['距離'], errors='coerce'); R['賞金'] = pd.to_numeric(R['1着賞金(円)'], errors='coerce')
R['クラス'] = R['レース名'].map(cls); R['格'] = R['競走種類名称'].map({'普通': 0, '特別': 1, '準重賞': 2, '重賞': 3})
cp = dict(zip(map(tuple, R[KEY].values), R['コーナー通過順1'].map(corner_pos)))
H = H.merge(R[KEY + ['距離', '賞金', '馬場', 'クラス', '格']], on=KEY, how='left')
H['日'] = pd.to_datetime(H['競走年月日']); H['年'] = H['日'].dt.year
H['差'] = H['sec'] - H.groupby(KEY, observed=True)['sec'].transform('min')
H['上り順率'] = H.groupby(KEY, observed=True)['上り'].rank(method='min') / H['n']
H['初角'] = [cp.get(tuple(k), {}).get(int(b)) for k, b in zip(H[KEY].astype(str).values, H['馬番'])]
H['初角率'] = pd.to_numeric(H['初角'], errors='coerce') / H['n']
H['着率'] = H['着x'] / H['n']
log('レースの記録')
# タイムの指数（B2と同じ作り方。基準は全部の場の2016〜2019年の勝ち馬）
W1 = H[(H['着'] == 1) & H['sec'].notna()]
s1 = W1[W1['年'] <= 2019].groupby(['競馬場', '距離', '馬場'], observed=True)['sec'].median()
s2 = W1[W1['年'] <= 2019].groupby(['競馬場', '距離'], observed=True)['sec'].median()
s1 = s1.to_dict(); s2 = s2.to_dict()
H['基準'] = [s1.get((p, q, r), s2.get((p, q), np.nan)) for p, q, r in zip(H['競馬場'], H['距離'], H['馬場'])]
W1 = H[(H['着'] == 1) & H['sec'].notna()].copy(); W1['ずれ'] = (W1['sec'] - W1['基準']) / W1['距離'] * 1000
var = W1.groupby(['競馬場', '日'], observed=True)['ずれ'].median().rename('当日の速さ').reset_index()
H = H.merge(var, on=['競馬場', '日'], how='left')
H['指数'] = (H['基準'] - H['sec']) / H['距離'] * 1000 + H['当日の速さ']
H.loc[H['中止'] == True, '指数'] = np.nan
log('タイムの指数')
# 馬ごとに前のレースを並べる（全部の場）
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
g = H.groupby('馬', sort=False, observed=True)
for k in range(1, 6):
    for c in ['着x', '着率', '差', '上り順率', '初角率']:
        H[f'{c}{k}'] = g[c].shift(k)
for c, nm in (('人気', '前人気'), ('日', '前日'), ('距離', '前距離'), ('賞金', '前賞金'), ('競馬場', '前場'), ('騎', '前騎'),
              ('n', '前n'), ('負担重量', '前斤量'), ('クラス', '前クラス'), ('格', '前格'), ('全走', '前の全走'), ('指数', '指数1')):
    H[nm] = g[c].shift(1)
H['走数'] = g.cumcount()
H['間隔'] = (H['日'] - H['前日']).dt.days
H['距離差'] = H['距離'] - H['前距離']; H['賞金比'] = H['賞金'] / H['前賞金']
fs, cs = H['前場'].astype(str), H['競馬場'].astype(str)
H['場変更'] = (fs != cs).astype(float).where(H['前場'].notna())
H['乗替'] = (H['前騎'].astype(str) != H['騎'].astype(str)).astype(float).where(H['前騎'].notna())
H['斤量差'] = H['負担重量'] - H['前斤量']; H['前人気率'] = H['前人気'] / H['前n']; H['前人気着差'] = H['前人気'] - H['着x1']
H['過去3差'] = H[['差1', '差2', '差3']].mean(axis=1); H['過去3着率'] = H[['着率1', '着率2', '着率3']].mean(axis=1)
H['過去3角'] = H[['初角率1', '初角率2', '初角率3']].mean(axis=1); H['過去3上り'] = H[['上り順率1', '上り順率2', '上り順率3']].mean(axis=1)
H['最小差5'] = H[[f'差{k}' for k in range(1, 6)]].min(axis=1); H['最良着2_5'] = H[[f'着x{k}' for k in range(2, 6)]].min(axis=1)
sh = g['指数'].shift(1)
H['指数最高3'] = sh.groupby(H['馬'], observed=True).transform(lambda s: s.rolling(3, min_periods=1).max())
H['指数平均3'] = sh.groupby(H['馬'], observed=True).transform(lambda s: s.rolling(3, min_periods=1).mean())
H['指数最高5'] = sh.groupby(H['馬'], observed=True).transform(lambda s: s.rolling(5, min_periods=1).max())
H['クラス差'] = H['クラス'] - H['前クラス']
H['外を挟む'] = np.where(H['前の全走'].isna(), np.nan, (H['全走'] - H['前の全走'] - 1).clip(lower=0))
H['初データ'] = (H['走数'] == 0).astype(float); H['外の走数'] = H['全走'] - H['走数']
places = sorted(H['競馬場'].astype(str).unique())
H['前場c'] = H['前場'].astype(str).map({p: i for i, p in enumerate(places)}).where(H['前場'].notna())
H['前走外'] = (~fs.isin(FIVE)).astype(float).where(H['前場'].notna())     # 前走が5場の外
H['外走5'] = sum((g['競馬場'].shift(k).astype(str).isin(places) & ~g['競馬場'].shift(k).astype(str).isin(FIVE)).astype(float) for k in range(1, 6))  # 5走前までの5場の外の数
log('前の成績')
COLS = [f'{c}{k}' for k in range(1, 6) for c in ['着x', '着率', '差', '上り順率', '初角率']] + \
       ['前人気', '前日', '前距離', '前賞金', '前場', '前騎', '前n', '前斤量', '走数', '間隔', '距離差', '賞金比', '場変更', '乗替', '斤量差',
        '前人気率', '前人気着差', '過去3差', '過去3着率', '過去3角', '過去3上り', '最小差5', '最良着2_5',
        '指数1', '指数最高3', '指数平均3', '指数最高5', '前クラス', 'クラス差', '前格', '外を挟む', '初データ', '外の走数', '前場c', '前走外', '外走5']
O = H[H['競馬場'].astype(str).isin(FIVE)][KEY + ['馬番'] + COLS].copy()
for c in KEY: O[c] = O[c].astype(str)
O['前場'] = O['前場'].astype(str).where(O['前場'].notna()); O['前騎'] = O['前騎'].astype(str).where(O['前騎'].notna())
O.to_pickle('/tmp/chiho_hist_all.pkl'); log('保存', len(O), '行', '全部の場の数', len(places))
print('前走が5場の外の割合（5場のレース、2021年以降）', round(O.loc[O['競走年月日'] >= '20210101', '前走外'].mean(), 3))
