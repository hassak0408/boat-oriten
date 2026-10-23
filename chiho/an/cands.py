"""手順2：先に決めた5つの候補（検証計画 C1〜C5）を、単勝・複勝の回収で数える。
比べる相手は、同じ年・同じ場の全部の馬（1頭100円ずつ）。
筋あり＝2016〜2025年（C5は2017〜2025年）のうち8割以上の年で全部より上、かつ通算で全部＋5ポイント以上。"""
import re, numpy as np, pandas as pd
from load import races, payback, horses

KEY = ['競馬場', '競走年月日', 'レース番号']
def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan

def tsec(t):
    t = str(t)
    if not t.isdigit() or len(t) < 3: return np.nan
    return int(t[:-3] or 0) * 60 + int(t[-3:-1]) + int(t[-1]) / 10

def corner_pos(s):
    """'2,4,(6,5),9,3' → {2:1,4:2,6:3,5:3,9:5,3:6}"""
    out, rank = {}, 1
    for grp in re.findall(r'\(([^)]*)\)|([0-9]+)', s.replace('-', ',').replace('=', ',')):
        nums = [int(x) for x in re.findall(r'[0-9]+', grp[0] or grp[1])]
        for n in nums: out[n] = rank
        rank += len(nums)
    return out

def build():
    R, P, H = races(), payback(), horses()
    H = H[H['着順'].notna()].copy()
    H = H[H['着順'] > 0]
    P1 = P.groupby(KEY).first().reset_index()
    H = H.merge(P1[KEY + ['単勝組番', '単勝払戻金（円）'] + [f'複勝組番{i}' for i in (1, 2, 3)] + [f'複勝払戻金{i}（円）' for i in (1, 2, 3)]], on=KEY, how='inner')
    ban = H['馬番'].astype('Int64').astype(str)
    H['単払'] = np.where(ban == H['単勝組番'], H['単勝払戻金（円）'].map(num), 0.0)
    H['n'] = H.groupby(KEY)['馬番'].transform('size')
    fk = sum(np.where(ban == H[f'複勝組番{i}'], H[f'複勝払戻金{i}（円）'].map(num), 0.0) for i in (1, 2, 3))
    H['複払'] = np.where(H['n'] > 4, fk, np.nan)
    H = H[P1.set_index(KEY).loc[list(map(tuple, H[KEY].values)), '単勝払戻金（円）'].map(num).fillna(0).values > 0] if False else H
    H['sec'] = H['タイム'].map(tsec)
    H['差'] = H['sec'] - H.groupby(KEY)['sec'].transform('min')
    cp = R.set_index(KEY)['コーナー通過順1'].map(corner_pos)
    H['初角'] = [cp.get(tuple(k), {}).get(int(b)) if pd.notna(b) else np.nan for k, b in zip(H[KEY].values, H['馬番'])]
    H['初角率'] = H['初角'] / H['n']
    H['日'] = pd.to_datetime(H['競走年月日'])
    H['馬'] = H['馬名'] + '|' + H['生年月日']
    H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
    g = H.groupby('馬')
    for k in range(1, 6):
        H[f'着{k}'] = g['着順'].shift(k); H[f'差{k}'] = g['差'].shift(k); H[f'角{k}'] = g['初角率'].shift(k)
    H['前日'] = g['日'].shift(1)
    H['過去3差'] = H[['差1', '差2', '差3']].mean(axis=1)
    H['過去3角'] = H[['角1', '角2', '角3']].mean(axis=1)
    H['走数'] = g.cumcount()
    tot = H['全成績'].str.split('-', expand=True).apply(pd.to_numeric, errors='coerce').sum(axis=1)
    H['全走'] = tot
    H['年'] = H['競走年月日'].str[:4]
    # 騎手：その場の前の年の勝率（100騎乗以上）上位3人
    H['騎'] = H['騎手名'] + '|' + H['騎手所属']
    jy = H.groupby(['競馬場', '年', '騎']).agg(n=('着順', 'size'), w=('着順', lambda s: (s == 1).sum())).reset_index()
    jy = jy[jy['n'] >= 100]; jy['率'] = jy['w'] / jy['n']
    jy['順'] = jy.groupby(['競馬場', '年'])['率'].rank(ascending=False, method='first')
    top = jy[jy['順'] <= 3].copy(); top['年'] = (top['年'].astype(int) + 1).astype(str)
    H = H.merge(top[['競馬場', '年', '騎']].assign(上位騎手=True), on=['競馬場', '年', '騎'], how='left')
    H['上位騎手'] = H['上位騎手'].fillna(False).astype(bool)
    # 候補
    rk = H.groupby(KEY)['過去3差'].rank(method='min')
    H['C1'] = (rk <= 2) & H['過去3差'].notna() & (H['人気'] >= 4)
    H['C2'] = (H['着1'] >= 6) & (H[['着2', '着3', '着4', '着5']] <= 3).any(axis=1)
    H['C3'] = H['上位騎手']
    ak = H.groupby(KEY)['過去3角'].rank(method='first')
    H['C4'] = (ak == 1) & H['過去3角'].notna()
    H['C5'] = (H['走数'] == 0) & (H['全走'] >= 3) & (H['齢'] >= 3) & (H['年'] >= '2017')
    return H

def judge(H):
    rows = []
    for c in ['C1', 'C2', 'C3', 'C4', 'C5']:
        y0 = '2017' if c == 'C5' else '2016'
        for bet, col in (('単勝', '単払'), ('複勝', '複払')):
            D = H[(H['年'] >= y0) & (H['年'] <= '2025') & H[col].notna()]
            by = D.groupby('年').apply(lambda d: pd.Series({'全': d[col].mean(), '候': d.loc[d[c], col].mean(), '頭': d[c].sum()}))
            up = (by['候'] > by['全']).sum(); ny = len(by)
            all_ = D[col].mean(); cand = D.loc[D[c], col].mean()
            ok = (up >= np.ceil(0.8 * ny)) and (cand >= all_ + 5)
            D26 = H[(H['年'] == '2026') & H[col].notna()]
            rows.append(dict(候補=c, 券=bet, 頭=int(D[c].sum()), 候補の回収=round(cand, 1), 全部=round(all_, 1),
                             上回った年=f'{up}/{ny}', 筋あり='○' if ok else '×',
                             年ごと='・'.join(f"{v:.0f}" for v in by['候']),
                             y2026=round(D26.loc[D26[c], col].mean(), 1)))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 20)
    H = build()
    H.to_pickle('/tmp/chiho_H.pkl')
    print(judge(H).to_string(index=False))
