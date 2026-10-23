"""1頭1行の表を作る：レース前に分かる材料と、単勝・複勝の払戻（100円あたり）。
- 取消・除外・取止めは返還なので行に入れない。競走中止・失格は走って負けた扱い（払戻0）。
- 同着で払戻の行が増えるレースは、全部の行を見る。
- 前走などは同じ馬（馬名＋生年月日）の、このデータ（盛岡・水沢・園田・姫路・笠松）の中の前のレース。
- 騎手・調教師の成績は前の日までの365日（同じ日のレースは入れない）。
- 今のレースの人気・オッズは材料に入れない（「人気」の列は答え合わせ用に残す）。
使い方：python feat.py → /tmp/chiho_feat.pkl"""
import re, sys, time, numpy as np, pandas as pd
from load import _read

KEY = ['競馬場', '競走年月日', 'レース番号']
LOSE_STATUS = {'競走中止', '失格'}


def num(x):
    try:
        return float(str(x).replace(',', '').replace('+', ''))
    except ValueError:
        return np.nan


def tsec(t):
    t = str(t)
    if ':' in t:
        t = re.sub(r'[^0-9:.]', '', t)
        try:
            m, s = t.split(':'); return int(m) * 60 + float(s)
        except ValueError:
            return np.nan
    if t.isdigit() and len(t) >= 3:
        return int(t[:-3] or 0) * 60 + int(t[-3:-1]) + int(t[-1]) / 10
    return np.nan


def corner_pos(s):
    """'2,4,(6,5),9,3' → {2:1,4:2,6:3,5:3,9:5,3:6}"""
    out, rank = {}, 1
    for grp in re.findall(r'\(([^)]*)\)|([0-9]+)', str(s).replace('-', ',').replace('=', ',')):
        nums = [int(x) for x in re.findall(r'[0-9]+', grp[0] or grp[1])]
        for n in nums:
            out[n] = rank
        rank += len(nums)
    return out


def rec4(s):
    p = s.str.split('-', expand=True)
    p = p.reindex(columns=range(4)).apply(pd.to_numeric, errors='coerce')
    return p[0], p[1], p[2], p[3]


def payouts(P):
    parts = []
    for kind, pairs in (('単', [('単勝組番', '単勝払戻金（円）')]),
                        ('複', [(f'複勝組番{i}', f'複勝払戻金{i}（円）') for i in (1, 2, 3)])):
        for bc, pc in pairs:
            x = P[KEY + [bc, pc]].copy(); x.columns = KEY + ['馬番', '払']
            x['券'] = kind; parts.append(x)
    X = pd.concat(parts, ignore_index=True)
    X['馬番'] = pd.to_numeric(X['馬番'], errors='coerce'); X['払'] = X['払'].map(num)
    X = X.dropna(subset=['馬番', '払']).drop_duplicates(KEY + ['券', '馬番'])
    T = X.pivot_table(index=KEY + ['馬番'], columns='券', values='払', aggfunc='sum').reset_index()
    T.columns.name = None
    race_win = X[X['券'] == '単'].groupby(KEY).size().rename('単あり')
    race_fuku = X[X['券'] == '複'].groupby(KEY).size().rename('複あり')
    return T, race_win, race_fuku


def roll365(H, ent, cols):
    """ent ごとに、前の日までの365日の合計（同じ日は入れない）"""
    D = H.groupby([ent, '日'])[cols].sum().reset_index().sort_values([ent, '日'])
    out = []
    for e, g in D.groupby(ent, sort=False):
        d = g['日'].values.astype('datetime64[D]').astype(np.int64)
        c = np.vstack([np.zeros(len(cols))] + [g[cols].values]).cumsum(axis=0)
        lo = np.searchsorted(d, d - 365, side='left'); hi = np.arange(len(d))  # [d-365, d)
        out.append(pd.DataFrame(c[hi] - c[lo], columns=cols).assign(**{ent: e, '日': g['日'].values}))
    return pd.concat(out, ignore_index=True)


def build(verbose=True):
    t0 = time.time()
    R = _read('race', 'racelist').drop_duplicates(KEY)
    P = _read('race', 'payback')
    H = _read('race', 'horselist')
    if verbose: print('読み込み', len(R), len(P), len(H), round(time.time() - t0), '秒', flush=True)
    H['着'] = pd.to_numeric(H['着順'], errors='coerce')
    st = H['着差'].where(H['着'].isna(), '')
    H = H[H['着'].notna() | st.isin(LOSE_STATUS)].copy()
    H['中止'] = H['着'].isna()
    H['減量'] = H['負担重量'].str.contains(r'[☆▲△◇★]', regex=True).astype(float)
    H['負担重量'] = H['負担重量'].str.replace(r'[^0-9.]', '', regex=True)
    for c in ['馬番', '枠番', '齢', '負担重量', '馬体重', '人気']:
        H[c] = pd.to_numeric(H[c], errors='coerce')
    H['馬体重増減'] = H['馬体重増減'].map(num)
    H = H.dropna(subset=['馬番'])
    H['n'] = H.groupby(KEY)['馬番'].transform('size')
    H['着x'] = H['着'].fillna(H['n'])          # 中止・失格は最下位として前走に使う
    # 払戻
    T, rw, rf = payouts(P)
    H = H.merge(T, on=KEY + ['馬番'], how='left')
    H = H.merge(rw.reset_index(), on=KEY, how='left').merge(rf.reset_index(), on=KEY, how='left')
    H = H[H['単あり'].notna()].copy()        # 不成立・取りやめのレースは外す
    H['単払'] = H['単'].fillna(0.0) / 100
    H['複払'] = np.where(H['複あり'].notna(), H['複'].fillna(0.0) / 100, np.nan)
    H['勝'] = (H['着'] == 1).astype(int); H['3着内'] = (H['着'] <= 3).astype(int)
    # レース
    R['距離'] = pd.to_numeric(R['距離'], errors='coerce')
    R['賞金'] = pd.to_numeric(R['1着賞金(円)'], errors='coerce')
    R['時'] = pd.to_numeric(R['発走時刻'], errors='coerce') // 100
    R['上がり3Fレース'] = pd.to_numeric(R['上がり3F'], errors='coerce')
    cp = dict(zip(map(tuple, R[KEY].values), R['コーナー通過順1'].map(corner_pos)))
    H = H.merge(R[KEY + ['距離', '賞金', '時', '馬場', '天候']], on=KEY, how='left')
    H['日'] = pd.to_datetime(H['競走年月日'])
    H['年'] = H['日'].dt.year; H['月'] = H['日'].dt.month
    # 走りの記録（前走として使う）
    H['sec'] = H['タイム'].map(tsec)
    H['差'] = H['sec'] - H.groupby(KEY)['sec'].transform('min')
    H['上り'] = pd.to_numeric(H['上がり3F'], errors='coerce')
    H['上り順率'] = H.groupby(KEY)['上り'].rank(method='min') / H['n']
    H['初角'] = [cp.get(tuple(k), {}).get(int(b)) for k, b in zip(H[KEY].values, H['馬番'])]
    H['初角率'] = pd.to_numeric(H['初角'], errors='coerce') / H['n']
    H['着率'] = H['着x'] / H['n']
    # 出馬表の成績（レース前の数字）
    for col, pre in (('全成績', '全'), ('当競馬場成績', '当場'), ('うち当距離成績', '当距'), ('騎手成績', '組')):
        a, b, c, d = rec4(H[col]); n = a + b + c + d
        H[pre + '走'] = n; H[pre + '勝率'] = a / n.where(n > 0); H[pre + '3率'] = (a + b + c) / n.where(n > 0)
    H['最高T'] = H['最高タイム'].map(tsec); H['最高T良'] = H['最高タイム良馬場'].map(tsec)
    H['最高T差'] = H['最高T'] - H.groupby(KEY)['最高T'].transform('min')
    H['最高T順率'] = H.groupby(KEY)['最高T'].rank(method='min') / H['n']
    H['馬体重差'] = H['馬体重'] - H.groupby(KEY)['馬体重'].transform('mean')
    H['馬番率'] = H['馬番'] / H['n']
    # 前走まで
    H['馬'] = H['馬名'] + '|' + H['生年月日']
    H['騎'] = H['騎手名'] + '|' + H['騎手所属']
    H['調'] = H['調教師'] + '|' + H['調教師所属']
    H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
    g = H.groupby('馬', sort=False)
    for k in range(1, 6):
        for c in ['着x', '着率', '差', '上り順率', '初角率']:
            H[f'{c}{k}'] = g[c].shift(k)
    for c, nm in (('人気', '前人気'), ('日', '前日'), ('距離', '前距離'), ('賞金', '前賞金'),
                  ('競馬場', '前場'), ('騎', '前騎'), ('n', '前n'), ('負担重量', '前斤量')):
        H[nm] = g[c].shift(1)
    H['走数'] = g.cumcount()
    H['間隔'] = (H['日'] - H['前日']).dt.days
    H['距離差'] = H['距離'] - H['前距離']
    H['賞金比'] = H['賞金'] / H['前賞金']
    H['場変更'] = (H['前場'].notna() & (H['前場'] != H['競馬場'])).astype(float).where(H['前場'].notna())
    H['乗替'] = (H['前騎'] != H['騎']).astype(float).where(H['前騎'].notna())
    H['斤量差'] = H['負担重量'] - H['前斤量']
    H['前人気率'] = H['前人気'] / H['前n']
    H['前人気着差'] = H['前人気'] - H['着x1']
    H['過去3差'] = H[['差1', '差2', '差3']].mean(axis=1)
    H['過去3着率'] = H[['着率1', '着率2', '着率3']].mean(axis=1)
    H['過去3角'] = H[['初角率1', '初角率2', '初角率3']].mean(axis=1)
    H['過去3上り'] = H[['上り順率1', '上り順率2', '上り順率3']].mean(axis=1)
    H['最小差5'] = H[[f'差{k}' for k in range(1, 6)]].min(axis=1)
    H['最良着2_5'] = H[[f'着x{k}' for k in range(2, 6)]].min(axis=1)
    # 騎手・調教師の365日
    H['乗'] = 1
    H['複乗'] = H['複払'].notna().astype(int); H['複払0'] = H['複払'].fillna(0)
    cols = ['乗', '勝', '3着内', '単払', '複払0', '複乗']
    for ent, pre in (('騎', '騎'), ('調', '調')):
        S = roll365(H, ent, cols)
        S[pre + '数'] = S['乗']; S[pre + '勝率'] = S['勝'] / S['乗'].where(S['乗'] > 0)
        S[pre + '3率'] = S['3着内'] / S['乗'].where(S['乗'] > 0)
        S[pre + '単回'] = S['単払'] / S['乗'].where(S['乗'] > 0)
        S[pre + '複回'] = S['複払0'] / S['複乗'].where(S['複乗'] > 0)
        H = H.merge(S[[ent, '日', pre + '数', pre + '勝率', pre + '3率', pre + '単回', pre + '複回']], on=[ent, '日'], how='left')
    # レースの中の順位
    for c in ['過去3差', '騎勝率', '全勝率', '全3率', '調勝率']:
        asc = c in ('過去3差',)
        H[c + '順率'] = H.groupby(KEY)[c].rank(ascending=asc, method='min') / H['n']
    H = H.copy()
    if verbose: print('できあがり', len(H), '行', round(time.time() - t0), '秒', flush=True)
    return H


FEATS = ['場c', '月', '時', '距離', '馬場c', '天候c', 'n', '賞金',
         '枠番', '馬番', '馬番率', '性c', '齢', '負担重量', '減量', '馬体重', '馬体重増減', '馬体重差',
         '全走', '全勝率', '全3率', '当場走', '当場勝率', '当場3率', '当距走', '当距勝率', '当距3率',
         '組走', '組勝率', '組3率', '最高T差', '最高T順率',
         '着x1', '着率1', '差1', '上り順率1', '初角率1', '着x2', '差2', '着x3', '差3',
         '前人気', '前人気率', '前人気着差', '走数', '間隔', '距離差', '賞金比', '場変更', '乗替', '斤量差',
         '過去3差', '過去3着率', '過去3角', '過去3上り', '最小差5', '最良着2_5',
         '騎数', '騎勝率', '騎3率', '騎単回', '騎複回', '調数', '調勝率', '調3率', '調単回', '調複回',
         '過去3差順率', '騎勝率順率', '全勝率順率', '全3率順率', '調勝率順率']
CATS = {'場c': '競馬場', '馬場c': '馬場', '天候c': '天候', '性c': '性'}


def add_cats(H):
    new = {}
    for c, src in CATS.items():
        v = H[src].astype('category').cat.codes.astype(float)
        new[c] = v.where(H[src].notna() & (H[src] != ''))
    return pd.concat([H.drop(columns=[c for c in CATS if c in H]), pd.DataFrame(new, index=H.index)], axis=1)


if __name__ == '__main__':
    H = add_cats(build())
    H.to_pickle(sys.argv[1] if len(sys.argv) > 1 else '/tmp/chiho_feat.pkl')
    print(H[FEATS].describe().T[['count', 'mean', 'min', 'max']].to_string())
