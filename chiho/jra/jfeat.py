"""中央競馬：1頭1行の表（レース前に分かる材料と結果）。JRA公式の成績表を読んだ表（STORE/jra/data/年/*_races.csv.gz・*_horses.csv.gz）から作る。
- 障害のレースは除く。取消・除外は行に入れない。競走中止・失格は走って負けた扱い（最下位）。
- 前走などは同じ馬（馬名）の前のレース。騎手・調教師の成績は前の日までの365日、馬主・生産者は前の日までの全部。
- 今のレースの人気・オッズは材料に入れない（「人気」「単勝オッズ」の列は答え合わせ用に残す）。
- card（今日の出馬表、結果なし）を渡すと、その行は「予測」が True になる。
使い方：python jfeat.py STORE/jra/data 出力.pkl"""
import os, re, sys, glob, json, time, warnings, numpy as np, pandas as pd
warnings.simplefilter('ignore', pd.errors.PerformanceWarning)

KEY = ['年月日', '場', 'R']
CLV = {'新馬': 0, '未勝利': 1, '1勝': 2, '2勝': 3, '3勝': 4, 'オープン': 5}
GRADE = {'L': 0.5, 'GIII': 1.0, 'GⅢ': 1.0, 'GII': 2.0, 'GⅡ': 2.0, 'GI': 3.0, 'GⅠ': 3.0}
CANCEL = ('出走取消', '取消', '競走除外', '除外')
MARK = r'[▲△☆◇★]'


def clean_name(s):
    """馬名：取消の（○頭）や外国の馬の英名・国名を取る"""
    s = re.sub(r'\(\d+頭\)', '', str(s)).replace('〓', '')
    return s.split('(')[0].strip()


def clean_person(s):
    """騎手・調教師・馬主・生産者：印・空白・国名・会社の印を取る。読めない字（〓）はそのまま残す（同じ人は同じ形になる）"""
    s = str(s) if isinstance(s, str) else ''
    s = re.sub(MARK, '', s)
    s = re.sub(r'\((?:株|有|豪|英|仏|愛|独|伊|米|香|南ア|新|加|首|UAE)\)', '', s)
    s = s.replace('株式会社', '').replace('有限会社', '').replace('合同会社', '').replace(' ', '').replace('　', '')
    s = re.sub(r'氏$', '', s)
    s = re.sub(r'^〓+|〓+$', '', s)          # 頭や後ろの（株）（有）が読めない字になったもの
    return s


def read_all(root, years=None):
    rs, hs = [], []
    for y in sorted(os.listdir(root)):
        if not y.isdigit() or (years and int(y) not in years): continue
        for f in sorted(glob.glob(f'{root}/{y}/*_races.csv.gz')):
            rs.append(pd.read_csv(f, dtype=str, keep_default_na=False))
            hf = f.replace('_races.csv.gz', '_horses.csv.gz')
            if os.path.exists(hf): hs.append(pd.read_csv(hf, dtype=str, keep_default_na=False))
    R = pd.concat(rs, ignore_index=True) if rs else pd.DataFrame()
    H = pd.concat(hs, ignore_index=True) if hs else pd.DataFrame()
    return R, H


def num(s):
    return pd.to_numeric(s, errors='coerce')


def corner_lists(js):
    try: d = json.loads(js) if isinstance(js, str) and js else {}
    except ValueError: d = {}
    return {int(k): v for k, v in d.items()}


def prep_races(R):
    R = R.copy()
    R['R'] = num(R['R']).astype('Int64')
    R = R.drop_duplicates(KEY, keep='last')
    R['距離'] = num(R['距離']); R['賞金'] = num(R['賞金'])
    R['時'] = num(R['発走']) // 100
    R['格n'] = R['格'].map(GRADE).fillna(0)
    R['クラス'] = R['条件'].map(CLV).astype(float) + R['格n']
    R['新馬'] = (R['条件'] == '新馬').astype(float)
    R['牝限'] = num(R['牝限']).fillna(0)
    R['ハンデ'] = (R['重量'] == 'ハンデ').astype(float)
    R['年齢c'] = R['年齢'].map({'2歳': 2, '3歳': 3, '3歳以上': 4, '4歳以上': 5})
    R['上り3Fレース'] = num(R['上り3F'])
    return R


def build(root, card=None, verbose=True, years=None):
    """root：jra/data。card：今日の出馬表（レースの列と馬の列を1つにした表。結果なし）"""
    t0 = time.time()
    R, H = read_all(root, years)
    H['予測'] = False
    if card is not None and len(card):
        cr = card.drop_duplicates(KEY)[[c for c in R.columns if c in card.columns]]
        R = pd.concat([R, cr.astype(str)], ignore_index=True)
        ch = card[[c for c in H.columns if c in card.columns]].astype(str).assign(予測=True)
        H = pd.concat([H, ch], ignore_index=True)
    if verbose: print('読み込み レース', len(R), '馬', len(H), round(time.time() - t0), '秒', flush=True)
    R = prep_races(R)
    R = R[R['芝ダ'].isin(['芝', 'ダート'])]                # 障害を除く
    H['R'] = num(H['R']).astype('Int64')
    H = H[~H['状態'].isin(CANCEL)].copy()
    H['着'] = num(H['着順'])
    H = H[H['着'].notna() | H['状態'].isin(['競走中止', '中止', '失格']) | H['予測']].copy()
    for c in ['枠', '馬番', '齢', '斤量', '馬体重', '増減', 'タイム', '単勝オッズ', '人気', 'ブリンカー']:
        H[c] = num(H[c])
    H = H.dropna(subset=['馬番'])
    H['馬番'] = H['馬番'].astype(int)
    H = H.drop_duplicates(KEY + ['馬番'], keep='last')
    H = H.merge(R[KEY + ['回', '日目', '芝ダ', '距離', '馬場', '天候', '条件', '格', '格n', 'クラス', '新馬', '牝限', 'ハンデ', '年齢c', '時', '賞金',
                         '上り3Fレース', '角']], on=KEY, how='inner')
    H['馬'] = H['馬名'].map(clean_name)
    for c in ['騎手', '調教師', '馬主', '生産']:
        H[c] = H[c].map(clean_person)
    H['減量'] = H['減量'].isin(['▲', '△', '☆', '◇', '★']).astype(float)
    H['n'] = H.groupby(KEY)['馬番'].transform('size')
    H['中止'] = H['着'].isna() & ~H['予測']
    H['着x'] = H['着'].fillna(H['n'])
    H['勝'] = (H['着'] == 1).astype(int); H['3着内'] = (H['着'] <= 3).astype(int)
    H['単払'] = np.where(H['着'] == 1, H['単勝オッズ'].fillna(0), 0.0)
    H['日'] = pd.to_datetime(H['年月日'], format='%Y%m%d')
    H['年'] = H['日'].dt.year; H['月'] = H['日'].dt.month
    # 走りの記録（前走として使う）
    H['差'] = H['タイム'] - H.groupby(KEY)['タイム'].transform('min')
    H.loc[H['中止'], '差'] = np.nan
    H['着率'] = H['着x'] / H['n']
    cl = {k: corner_lists(v) for k, v in zip(map(tuple, R[KEY].values), R['角'])}
    first, last = [], []
    for k, b in zip(map(tuple, H[KEY].values), H['馬番']):
        d = cl.get(k, {})
        f = d[min(d)] if d else []; l = d[max(d)] if d else []
        first.append(f.index(b) + 1 if b in f else np.nan); last.append(l.index(b) + 1 if b in l else np.nan)
    H['初角'] = first; H['終角'] = last
    H['初角率'] = H['初角'] / H['n']; H['終角率'] = H['終角'] / H['n']
    H['先頭'] = (H['初角'] == 1).astype(float).where(H['初角'].notna())
    H['先行'] = (H['初角'] <= 3).astype(float).where(H['初角'].notna())
    H['上げ'] = H['終角'] - H['着x']
    # タイムの指数（基準：2016〜2018年の勝ち馬のタイムの中央値。その日の速さ：その日・その場・芝ダの勝ち馬のずれの中央値）
    W1 = H[(H['着'] == 1) & H['タイム'].notna() & (H['年'] <= 2018)]
    s1 = W1.groupby(['場', '芝ダ', '距離', '馬場'])['タイム'].median(); s2 = W1.groupby(['場', '芝ダ', '距離'])['タイム'].median()
    H['基準'] = [s1.get((a, b, c, d), s2.get((a, b, c), np.nan)) for a, b, c, d in zip(H['場'], H['芝ダ'], H['距離'], H['馬場'])]
    W = H[(H['着'] == 1) & H['タイム'].notna()].copy(); W['ずれ'] = (W['タイム'] - W['基準']) / W['距離'] * 1000
    var = W.groupby(['場', '日', '芝ダ'])['ずれ'].median().rename('当日の速さ').reset_index()
    H = H.merge(var, on=['場', '日', '芝ダ'], how='left')
    H['指数'] = (H['基準'] - H['タイム']) / H['距離'] * 1000 + H['当日の速さ']
    H.loc[H['中止'], '指数'] = np.nan
    if verbose: print('走りの記録', round(time.time() - t0), '秒', flush=True)

    # 前走まで
    H = H.sort_values(['馬', '日', 'R']).reset_index(drop=True)
    g = H.groupby('馬', sort=False)
    for k in range(1, 6):
        for c in ['着x', '着率', '差', '指数']:
            H[f'{c}{k}'] = g[c].shift(k)
    for k in range(1, 4):
        H[f'初角率{k}'] = g['初角率'].shift(k)
    for c, nm in (('人気', '前人気'), ('日', '前日'), ('距離', '前距離'), ('賞金', '前賞金'), ('場', '前場'), ('騎手', '前騎'),
                  ('n', '前n'), ('斤量', '前斤量'), ('芝ダ', '前芝ダ'), ('クラス', '前クラス'), ('馬体重', '前馬体重'),
                  ('ブリンカー', '前ブリンカー'), ('終角率', '終角率1'), ('上げ', '上げ1'), ('格n', '前格')):
        H[nm] = g[c].shift(1)
    H['走数'] = g.cumcount()
    H['間隔'] = (H['日'] - H['前日']).dt.days
    H['距離差'] = H['距離'] - H['前距離']
    H['賞金比'] = H['賞金'] / H['前賞金']
    H['場変更'] = (H['前場'] != H['場']).astype(float).where(H['前場'].notna())
    H['芝ダ変更'] = (H['前芝ダ'] != H['芝ダ']).astype(float).where(H['前芝ダ'].notna())
    H['乗替'] = (H['前騎'] != H['騎手']).astype(float).where(H['前騎'].notna())
    H['斤量差'] = H['斤量'] - H['前斤量']
    H['クラス差'] = H['クラス'] - H['前クラス']          # プラス＝上のクラスへ（昇級）
    H['前人気率'] = H['前人気'] / H['前n']
    H['前人気着差'] = H['前人気'] - H['着x1']
    H['過去3差'] = H[['差1', '差2', '差3']].mean(axis=1)
    H['過去3着率'] = H[['着率1', '着率2', '着率3']].mean(axis=1)
    H['過去3角'] = H[['初角率1', '初角率2', '初角率3']].mean(axis=1)
    H['最小差5'] = H[[f'差{k}' for k in range(1, 6)]].min(axis=1)
    H['最良着2_5'] = H[[f'着x{k}' for k in range(2, 6)]].min(axis=1)
    H['指数最高3'] = H[['指数1', '指数2', '指数3']].max(axis=1)
    H['指数平均3'] = H[['指数1', '指数2', '指数3']].mean(axis=1)
    H['指数最高5'] = H[[f'指数{k}' for k in range(1, 6)]].max(axis=1)
    for c in ['先頭', '先行']:
        H[c + '率5'] = g[c].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    H['上げ3'] = g['上げ'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    # 休み明け（90日以上あいた）から何戦目か
    brk = (H['間隔'].isna() | (H['間隔'] >= 90)).astype(int)
    H['叩き'] = brk.groupby(H['馬']).cumsum()
    H['叩き戦目'] = H.groupby(['馬', '叩き']).cumcount() + 1
    # これまでの成績（前のレースまで）：全部・同じ芝ダ・同じ場・同じ距離（±200m）
    H['_1'] = 1
    for nm, keys in (('全', ['馬']), ('芝ダ', ['馬', '芝ダ']), ('当場', ['馬', '場', '芝ダ'])):
        gg = H.groupby(keys, sort=False)
        n_ = gg['_1'].cumsum() - H['_1']; w_ = gg['勝'].cumsum() - H['勝']; t_ = gg['3着内'].cumsum() - H['3着内']
        H[nm + '走'] = n_; H[nm + '勝率'] = w_ / n_.where(n_ > 0); H[nm + '3率'] = t_ / n_.where(n_ > 0)
    H['距帯'] = (H['距離'] // 400).astype('Int64')
    gg = H.groupby(['馬', '芝ダ', '距帯'], sort=False)
    n_ = gg['_1'].cumsum() - H['_1']; t_ = gg['3着内'].cumsum() - H['3着内']
    H['当距走'] = n_; H['当距3率'] = t_ / n_.where(n_ > 0)
    H['賞金獲得'] = np.where(H['着'] <= 5, H['賞金'] * np.select([H['着'] == 1, H['着'] == 2, H['着'] == 3, H['着'] == 4, H['着'] == 5],
                                                                [1, 0.4, 0.25, 0.15, 0.1], 0), 0)
    H['獲得計'] = H.groupby('馬', sort=False)['賞金獲得'].cumsum() - H['賞金獲得']
    if verbose: print('前走まで', round(time.time() - t0), '秒', flush=True)

    # 騎手・調教師の365日、馬主・生産者の全部（前の日まで）
    H = H.sort_values(['日'] + KEY).reset_index(drop=True)
    for ent, pre, days in (('騎手', '騎', 365), ('調教師', '調', 365), ('馬主', '主', None), ('生産', '牧', None)):
        S = prior(H, ent, days)
        k = 20; m1 = H['勝'].mean(); m3 = H['3着内'].mean()
        H[pre + '数'] = S['n'].values
        H[pre + '勝率'] = ((S['w'] + k * m1) / (S['n'] + k)).values
        H[pre + '3率'] = ((S['t'] + k * m3) / (S['n'] + k)).values
        if pre in ('騎', '調'):
            H[pre + '単回'] = (S['p'] / S['n'].where(S['n'] > 0)).values
    # 騎手のこの場・この芝ダでの成績（365日）
    H['騎場'] = H['騎手'] + '|' + H['場'] + '|' + H['芝ダ']
    S = prior(H, '騎場', 365); k = 20
    H['騎場3率'] = ((S['t'] + k * H['3着内'].mean()) / (S['n'] + k)).values
    # レースの中の順位
    for c, asc in (('過去3差', True), ('騎勝率', False), ('全3率', False), ('調勝率', False), ('指数最高3', False), ('指数1', False),
                   ('獲得計', False), ('主勝率', False), ('牧勝率', False)):
        H[c + '順率'] = H.groupby(KEY)[c].rank(ascending=asc, method='min') / H['n']
    H['指数最高3差'] = H.groupby(KEY)['指数最高3'].transform('max') - H['指数最高3']
    H['逃げ型'] = (H['先頭率5'] >= 0.4).astype(int)
    H['他の逃げ型'] = H.groupby(KEY)['逃げ型'].transform('sum') - H['逃げ型']
    H['先頭率5順'] = H.groupby(KEY)['先頭率5'].rank(ascending=False, method='min')
    H['過去3角順'] = H.groupby(KEY)['過去3角'].rank(method='min')
    H['馬番率'] = H['馬番'] / H['n']
    for c, src in (('場c', '場'), ('芝ダc', '芝ダ'), ('馬場c', '馬場'), ('天候c', '天候'), ('性c', '性')):
        H[c] = H[src].map(CATS[c]).astype(float)
    H = H.copy()
    if verbose: print('できあがり', len(H), '行', round(time.time() - t0), '秒', flush=True)
    return H


CATS = {'場c': {p: i for i, p in enumerate(['札幌', '函館', '福島', '新潟', '東京', '中山', '中京', '京都', '阪神', '小倉'])},
        '芝ダc': {'芝': 0, 'ダート': 1}, '馬場c': {'良': 0, '稍重': 1, '重': 2, '不良': 3},
        '天候c': {'晴': 0, '曇': 1, '小雨': 2, '雨': 3, '小雪': 4, '雪': 5}, '性c': {'牡': 0, '牝': 1, 'セ': 2}}


def prior(H, ent, days=None):
    """ent ごとに、前の日までの（days 日の、または全部の）乗った数・勝ち・3着内・単勝の払戻の合計。H は日の順に並んでいること"""
    X = H[[ent, '日', '勝', '3着内', '単払']].copy(); X['_n'] = 1
    X = X[~H['予測']] if '予測' in H else X
    day = X.groupby([ent, '日'])[['_n', '勝', '3着内', '単払']].sum().reset_index().sort_values([ent, '日'])
    day[['c_n', 'c_w', 'c_t', 'c_p']] = day.groupby(ent)[['_n', '勝', '3着内', '単払']].cumsum().values
    Q = H[[ent, '日']].reset_index()
    out = pd.DataFrame(0.0, index=H.index, columns=['n', 'w', 't', 'p'])
    M = pd.merge_asof(Q.sort_values('日'), day[[ent, '日', 'c_n', 'c_w', 'c_t', 'c_p']].sort_values('日'), on='日', by=ent,
                      allow_exact_matches=False).set_index('index')
    if days:
        Q2 = Q.copy(); Q2['日'] = Q2['日'] - pd.Timedelta(days=days)
        M2 = pd.merge_asof(Q2.sort_values('日'), day[[ent, '日', 'c_n', 'c_w', 'c_t', 'c_p']].sort_values('日'), on='日', by=ent,
                           allow_exact_matches=False).set_index('index')
        # [日−days, 日) ＝（日の前の日までの合計）−（日−days の前の日までの合計）
        for a, b in (('n', 'c_n'), ('w', 'c_w'), ('t', 'c_t'), ('p', 'c_p')):
            out[a] = (M[b].fillna(0) - M2[b].reindex(M.index).fillna(0)).reindex(H.index).values
    else:
        for a, b in (('n', 'c_n'), ('w', 'c_w'), ('t', 'c_t'), ('p', 'c_p')):
            out[a] = M[b].fillna(0).reindex(H.index).values
    return out


FEATS = ['場c', '芝ダc', '馬場c', '天候c', '性c', '月', '時', '距離', 'n', '賞金', 'クラス', '新馬', '牝限', 'ハンデ', '年齢c',
         '枠', '馬番', '馬番率', '齢', '斤量', '減量',
         '走数', '間隔', '距離差', '賞金比', '場変更', '芝ダ変更', '乗替', '斤量差', 'クラス差', '前クラス', '前格', '前馬体重', '前ブリンカー',
         '着x1', '着率1', '差1', '指数1', '着x2', '差2', '指数2', '着x3', '差3', '指数3', '着x4', '着x5',
         '前人気', '前人気率', '前人気着差', '過去3差', '過去3着率', '過去3角', '最小差5', '最良着2_5',
         '指数最高3', '指数平均3', '指数最高5', '指数最高3差', '叩き戦目',
         '全走', '全勝率', '全3率', '芝ダ走', '芝ダ3率', '当場走', '当場3率', '当距走', '当距3率', '獲得計',
         '騎数', '騎勝率', '騎3率', '騎単回', '騎場3率', '調数', '調勝率', '調3率', '調単回', '主数', '主勝率', '主3率', '牧数', '牧勝率', '牧3率',
         '先頭率5', '先行率5', '終角率1', '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順',
         '過去3差順率', '騎勝率順率', '全3率順率', '調勝率順率', '指数最高3順率', '指数1順率', '獲得計順率', '主勝率順率', '牧勝率順率']
CATF = ['場c', '芝ダc', '馬場c', '天候c', '性c']

if __name__ == '__main__':
    H = build(sys.argv[1])
    H.to_pickle(sys.argv[2] if len(sys.argv) > 2 else '/tmp/jra_feat.pkl')
    A = H[H['年'] >= 2021] if (H['年'] >= 2021).any() else H
    print(A[FEATS].describe().T[['count', 'mean', 'min', 'max']].round(3).to_string())
