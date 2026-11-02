"""地方（全部の場、ばんえいを除く）：N1 印ごとの単勝（検証計画「地方（全部の場）：値段がずれる所を探す」）。
使い方：python nbias.py DATA_ALL（chiho-keiba の data_all）"""
import sys, glob, re, numpy as np, pandas as pd
from feat import tsec, corner_pos, rec4
KEY = ['競馬場', '競走年月日', 'レース番号']
SOUTH = {'大井', '川崎', '船橋', '浦和'}
root = sys.argv[1]
HC = KEY + ['枠番', '馬番', '馬名', '性', '生年月日', '騎手名', '騎手所属', '負担重量', '馬体重', '馬体重増減', '全成績', '着順', '着差', '上がり3F', '人気']
hs, ps, rs = [], [], []
for d in sorted(glob.glob(f'{root}/race/2*')):
    for f in glob.glob(f'{d}/*horselist*.csv.gz'): hs.append(pd.read_csv(f, dtype=str, keep_default_na=False, usecols=HC))
    for f in glob.glob(f'{d}/*payback*.csv.gz'): ps.append(pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['単勝組番', '単勝払戻金（円）']))
    for f in glob.glob(f'{d}/*racelist*.csv.gz'): rs.append(pd.read_csv(f, dtype=str, keep_default_na=False, usecols=KEY + ['距離', 'コーナー通過順1']))
H = pd.concat(hs, ignore_index=True); P = pd.concat(ps, ignore_index=True); R = pd.concat(rs, ignore_index=True)
del hs, ps, rs
H = H[H['競馬場'] != '帯広ば'].drop_duplicates(KEY + ['馬番'], keep='last')
P = P[P['単勝組番'] != ''].drop_duplicates(KEY + ['単勝組番'])
dh = P.groupby(KEY).size(); P = P.set_index(KEY).loc[dh[dh == 1].index].reset_index()       # 同着のレースは除く
P['払'] = pd.to_numeric(P['単勝払戻金（円）'].str.replace(',', ''), errors='coerce') / 100
P['馬番'] = pd.to_numeric(P['単勝組番'], errors='coerce')
R = R.drop_duplicates(KEY); R['距離'] = pd.to_numeric(R['距離'], errors='coerce')
H['着'] = pd.to_numeric(H['着順'], errors='coerce')
H = H[H['着'].notna() | H['着差'].isin(['競走中止', '失格'])].copy()
H = H.merge(P[KEY].drop_duplicates().assign(単あり=1), on=KEY, how='inner').drop(columns='単あり')
for c in ('馬番', '枠番', '人気', '馬体重'): H[c] = pd.to_numeric(H[c], errors='coerce')
H['増減'] = pd.to_numeric(H['馬体重増減'].str.replace('+', '', regex=False), errors='coerce')
H = H.merge(P[KEY + ['馬番', '払']], on=KEY + ['馬番'], how='left'); H['払'] = H['払'].fillna(0.0)
H = H.merge(R[KEY + ['距離', 'コーナー通過順1']], on=KEY, how='left')
H['n'] = H.groupby(KEY)['馬番'].transform('size')
H['着x'] = H['着'].fillna(H['n']); H['着率'] = H['着x'] / H['n']; H['勝'] = (H['着'] == 1).astype(int)
H['上り'] = pd.to_numeric(H['上がり3F'], errors='coerce'); H['上り順'] = H.groupby(KEY)['上り'].rank(method='min')
cp = {k: corner_pos(s) for k, s in zip(map(tuple, H[KEY].drop_duplicates().values), H.drop_duplicates(KEY)['コーナー通過順1'])}
H['初角'] = [cp.get(tuple(k), {}).get(int(b)) for k, b in zip(H[KEY].values, H['馬番'])]
H['初角'] = pd.to_numeric(H['初角'], errors='coerce')
H['減量印'] = H['負担重量'].str.contains(r'[☆▲△◇★]', regex=True)
a, b, c, e = rec4(H['全成績']); H['全走'] = a + b + c + e
H['日'] = pd.to_datetime(H['競走年月日']); H['年'] = H['日'].dt.year
H['馬'] = H['馬名'] + '|' + H['生年月日']; H['騎'] = H['騎手名'] + '|' + H['騎手所属']
H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
g = H.groupby('馬', sort=False)
for col, nm in (('着x', '着x1'), ('着率', '着率1'), ('人気', '前人気'), ('日', '前日'), ('距離', '前距離'), ('競馬場', '前場'), ('騎', '前騎'),
                ('初角', '前初角'), ('上り順', '前上り順')):
    H[nm] = g[col].shift(1)
H['走数'] = g.cumcount()
H['最良着2_5'] = pd.concat([g['着x'].shift(k) for k in range(2, 6)], axis=1).min(axis=1)
H['間隔'] = (H['日'] - H['前日']).dt.days; H['距離差'] = H['距離'] - H['前距離']
wins = H.groupby(['競馬場', '年', '騎'])['勝'].sum().reset_index()
top = {(p, y + 1): set(x.nlargest(10, '勝')['騎']) for (p, y), x in wins.groupby(['競馬場', '年'])}
H['騎上'] = [j in top[(p, y)] if (p, y) in top else np.nan for p, y, j in zip(H['競馬場'], H['年'], H['騎'])]
H['前騎上'] = [(j in top[(p, y)]) if ((p, y) in top and isinstance(j, str)) else np.nan for p, y, j in zip(H['競馬場'], H['年'], H['前騎'])]
seg = {
    '①上位騎手へ乗り替わり': (H['前騎'].notna()) & (H['前騎'] != H['騎']) & (H['騎上'] == True) & (H['前騎上'] == False),
    '②上位騎手から乗り替わり': (H['前騎'].notna()) & (H['前騎'] != H['騎']) & (H['騎上'] == False) & (H['前騎上'] == True),
    '③減量騎手': H['減量印'],
    '④前走大敗でも2〜5走前に3着内': (H['着率1'] > 0.6) & (H['最良着2_5'] <= 3),
    '⑤前走1番人気で4着以下': (H['前人気'] == 1) & (H['着x1'] >= 4),
    '⑥90日以上の休み明け': H['間隔'] >= 90,
    '⑦馬体重10kg以上増': H['増減'] >= 10,
    '⑧馬体重10kg以上減': H['増減'] <= -10,
    '⑨距離200m以上短縮': H['距離差'] <= -200,
    '⑩距離200m以上延長': H['距離差'] >= 200,
    '⑪前走と違う場': H['前場'].notna() & (H['前場'] != H['競馬場']),
    '⑫地方で初めて走る馬（前の成績あり）': (H['走数'] == 0) & (H['全走'] > 0),
    '⑬牝馬': H['性'] == '牝',
    '⑭外枠（7・8枠）': H['枠番'] >= 7,
    '⑮前走で逃げた': H['前初角'] == 1,
    '⑯前走の上がり1位': H['前上り順'] == 1,
    '⑰前走の上がり1位なのに4着以下': (H['前上り順'] == 1) & (H['着x1'] >= 4),
    '⑱前走2着': H['着x1'] == 2,
    '（参考）全部': pd.Series(True, index=H.index),
}


def boot(pay, day, B=2000):
    x = pd.DataFrame({'d': day, 's': pay}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


H['群'] = np.where(H['競馬場'].isin(SOUTH), '南関東', 'ほかの10場')
rows = []
for name, m in seg.items():
    for grp in ('南関東', 'ほかの10場'):
        for lab, pm in (('2016〜2021', H['年'] <= 2021), ('2022〜2026', H['年'] >= 2022)):
            X = H[m.fillna(False).astype(bool) & pm & (H['群'] == grp)]
            if len(X) < 100: continue
            lo, hi = boot(X['払'].values, X['競走年月日'].values)
            by = X.groupby('年')['払'].mean() * 100
            rows.append({'印': name, '場': grp, '期間': lab, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '人気の平均': round(X['人気'].mean(), 1),
                         '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo:.0f}〜{hi:.0f}）", '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 80); pd.set_option('display.max_rows', 200)
print(pd.DataFrame(rows).to_string(index=False))
