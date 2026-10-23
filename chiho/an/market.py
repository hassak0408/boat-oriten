"""手順1：全部買ったら何%か（券種別×場×年）。単勝・複勝は人気別も。
全部買い＝その券種の全部の組を100円ずつ買ったときの回収。組の数は出走頭数から（枠の券は出馬表の枠番から）。"""
import sys, math, itertools, pandas as pd, numpy as np
from collections import Counter
from load import races, payback, horses

KEY = ['競馬場', '競走年月日', 'レース番号']

def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan

def bet_sums(pb):
    """1レースの券種ごとの払戻の合計（同着で行が増えるので、同じ組・同じ払戻は1回だけ数える）"""
    out = {}
    spec = {
        '単勝': [('単勝組番', '単勝払戻金（円）')],
        '複勝': [(f'複勝組番{i}', f'複勝払戻金{i}（円）') for i in (1, 2, 3)],
        '枠複': [(('枠複組番1', '枠複組番2'), '枠複払戻金（円）')],
        '枠単': [(('枠単組番1', '枠単組番2'), '枠単払戻金（円）')],
        '馬複': [(('馬複組番1', '馬複組番2'), '馬複払戻金（円）')],
        '馬単': [(('馬単組番1', '馬単組番2'), '馬単払戻金（円）')],
        'ワイド': [((f'ワイド組番{i}馬番1', f'ワイド組番{i}馬番2'), f'ワイド払戻金{i}（円）') for i in (1, 2, 3)],
        '3連複': [(('３連複組番馬番1', '３連複組番馬番2', '３連複組番馬番3'), '３連複払戻金（円）')],
        '3連単': [(('３連単組番馬番1', '３連単組番馬番2', '３連単組番馬番3'), '３連単払戻金（円）')],
    }
    for b, cols in spec.items():
        seen = set(); tot = 0.0
        for _, row in pb.iterrows():
            for kc, pc in cols:
                k = tuple(row[c] for c in kc) if isinstance(kc, tuple) else (row[kc],)
                p = num(row[pc])
                if not k[0] or np.isnan(p): continue
                if (k, p) in seen: continue
                seen.add((k, p)); tot += p
        out[b] = tot
    return out

def n_combos(b, n, waku_counts):
    if b in ('単勝', '複勝'): return n
    if b in ('馬複', 'ワイド'): return math.comb(n, 2)
    if b == '馬単': return n * (n - 1)
    if b == '3連複': return math.comb(n, 3)
    if b == '3連単': return n * (n - 1) * (n - 2)
    ws = [w for w, c in waku_counts.items() if c > 0]
    if b == '枠複': return math.comb(len(ws), 2) + sum(1 for w in ws if waku_counts[w] >= 2)
    if b == '枠単': return len(ws) * (len(ws) - 1) + sum(1 for w in ws if waku_counts[w] >= 2)

def main():
    R, P, H = races(), payback(), horses()
    Hs = H[H['着順'].notna() & (H['着順'] > 0)]
    nrun = Hs.groupby(KEY).size().rename('n')
    waku = Hs.groupby(KEY)['枠番'].apply(lambda s: Counter(s.dropna().astype(int)))
    rows = []
    for k, pb in P.groupby(KEY):
        if k not in nrun.index: continue
        n = int(nrun[k]); s = bet_sums(pb)
        if s['単勝'] == 0: continue  # 中止・不成立
        for b, tot in s.items():
            c = n_combos(b, n, waku[k])
            if not c or tot == 0: continue
            if b == '複勝' and n <= 4: continue
            rows.append(dict(場=k[0], 年=k[1][:4], 券=b, 頭数=n, 買=c * 100, 払=tot))
    T = pd.DataFrame(rows)
    T['場2'] = T['場'].replace({'盛岡': '岩手', '水沢': '岩手'})
    order = ['単勝', '複勝', '枠複', '枠単', '馬複', '馬単', 'ワイド', '3連複', '3連単']
    def tab(by):
        g = T.groupby(by + ['券'])[['払', '買']].sum(); g['回収'] = (g['払'] / g['買'] * 100).round(1)
        return g['回収'].unstack('券').reindex(columns=order)
    pd.set_option('display.width', 200)
    print('レース数', T.drop_duplicates(['場', '年', '頭数', '払']).shape[0] if False else len(P.drop_duplicates(KEY)))
    print('\n■ 全体'); print(tab([]) if False else (T.groupby('券')[['払','買']].sum().assign(回収=lambda d: (d['払']/d['買']*100).round(1))['回収'].reindex(order)))
    print('\n■ 場ごと'); print(tab(['場']))
    print('\n■ 年ごと'); print(tab(['年']))
    T['頭数帯'] = pd.cut(T['頭数'], [0, 7, 9, 11, 18], labels=['〜7', '8-9', '10-11', '12〜'])
    print('\n■ 頭数ごと'); print(tab(['頭数帯']))
    # 単勝・複勝の人気別
    W = P.drop_duplicates(KEY)[KEY + ['単勝組番', '単勝払戻金（円）']]
    X = Hs.merge(P.groupby(KEY).first().reset_index()[KEY + ['単勝組番', '単勝払戻金（円）'] + [f'複勝組番{i}' for i in (1,2,3)] + [f'複勝払戻金{i}（円）' for i in (1,2,3)]], on=KEY)
    X = X.merge(nrun.reset_index(), on=KEY)
    X['単払'] = np.where(X['馬番'].astype('Int64').astype(str) == X['単勝組番'], X['単勝払戻金（円）'].map(num), 0)
    fk = sum(np.where(X['馬番'].astype('Int64').astype(str) == X[f'複勝組番{i}'], X[f'複勝払戻金{i}（円）'].map(num), 0) for i in (1, 2, 3))
    X['複払'] = np.where(X['n'] > 4, fk, np.nan)
    X['人気帯'] = X['人気'].clip(upper=8).astype('Int64').astype(str).replace({'8': '8〜'})
    g = X.groupby('人気帯').agg(頭=('単払', 'size'), 勝率=('着順', lambda s: round((s == 1).mean() * 100, 1)), 単勝=('単払', lambda s: round(s.mean(), 1)), 複勝=('複払', lambda s: round(s.mean(), 1)))
    print('\n■ 人気別（単勝・複勝の回収）'); print(g)
    T.to_csv('/tmp/chiho_market_rows.csv', index=False)

if __name__ == '__main__':
    main()
