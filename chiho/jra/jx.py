"""中央競馬：J4 券の間の値段のずれ（単勝と馬連・馬単）。発売票数（確定）から、単勝の票数で出した組の確率（ハービル式）×馬連・馬単のオッズ＝r を出し、
rの帯ごとに実際の当たりと回収を見る（地方のXと同じ見方）。最初の60日分は形を見るだけ（検証計画 J4）。
使い方：python jx.py STORE/jra"""
import sys, glob, re, numpy as np, pandas as pd
root = sys.argv[1]
V = pd.concat([pd.read_csv(f, dtype={'組': str}) for f in glob.glob(f'{root}/hyo/*/*.csv.gz')], ignore_index=True)
V['年月日'] = V['年月日'].astype(str)
# 平地だけ（成績表のコースに向きがあるもの）
R = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', 'コース', '払戻'])
               for f in glob.glob(f'{root}/data/*/*_races.csv.gz') if any(f'/{d[:4]}/' in f for d in V['年月日'].unique()[:1])], ignore_index=True)
R = R[R['コース'].str.contains('右|左|直')]
R['R'] = R['R'].astype(int)
V = V.merge(R[['年月日', '場', 'R']], on=['年月日', '場', 'R'])
TAKE = {'馬連': 0.775, '馬単': 0.75}
rows = []
for (d, p, r), g in V.groupby(['年月日', '場', 'R']):
    w = g[(g['券'] == '単勝') & g['票数'].notna() & (g['票数'] > 0)]
    if len(w) < 5: continue
    q = dict(zip(w['組'].astype(int), w['票数'] / w['票数'].sum()))
    rank = {h: i + 1 for i, h in enumerate(sorted(q, key=q.get, reverse=True))}
    for kind in ('馬連', '馬単'):
        x = g[(g['券'] == kind) & g['票数'].notna() & (g['票数'] > 0)]
        if not len(x): continue
        tot = x['計'].iloc[0]
        for c, v, hit in zip(x['組'], x['票数'], x['的中']):
            a, b = [int(z) for z in c.split('-')]
            if a not in q or b not in q: continue
            pij = q[a] * q[b] / (1 - q[a]) + (q[b] * q[a] / (1 - q[b]) if kind == '馬連' else 0)
            odds = np.floor(tot * TAKE[kind] / v * 10) / 10
            rows.append(dict(日=d, 場=p, R=r, 券=kind, ハービル=pij, 市場=v / tot, オッズ=odds, r=pij * odds, 的中=int(hit), 戻り=odds * int(hit),
                             人気の組=tuple(sorted((rank[a], rank[b])))))
X = pd.DataFrame(rows)
print('レース', X.groupby(['日', '場', 'R']).ngroups, '日', X['日'].nunique(), '組', len(X))
pd.set_option('display.width', 200)
for kind in ('馬連', '馬単'):
    Z = X[(X['券'] == kind) & (X['ハービル'] >= 0.02)]
    t = Z.groupby(pd.cut(Z['r'], [0, .6, .7, .8, .9, 1.0, 1.1, 1.2, 1.4, 1.7, 99]), observed=True).agg(
        組=('的中', 'size'), ハービル=('ハービル', 'mean'), 市場=('市場', 'mean'), 実際=('的中', 'mean'), 回収=('戻り', 'mean'))
    for c in ('ハービル', '市場', '実際'): t[c] = (t[c] * 100).round(2)
    t['回収'] = (t['回収'] * 100).round(1)
    print(f'\n■ {kind}：r（ハービル式の確率×オッズ）の帯ごと（ハービル式で2%以上の組）'); print(t.to_string())
    # 見込みの合い方：市場（票数の割合）とハービル式のどちらが実際に近いか
    Z2 = X[X['券'] == kind]
    for col in ('ハービル', '市場'):
        b = pd.cut(Z2[col], [0, .01, .02, .05, .1, .2, 1])
        t2 = Z2.groupby(b, observed=True).agg(組=('的中', 'size'), 見込み=(col, 'mean'), 実際=('的中', 'mean'))
        t2['見込み'] = (t2['見込み'] * 100).round(2); t2['実際'] = (t2['実際'] * 100).round(2)
        print(f'  {col}の見込みと実際：', t2.to_dict('index'))
# 人気の2頭の組（1-2番人気の馬連）で、rが高いとき
Z = X[(X['券'] == '馬連') & (X['人気の組'] == (1, 2))]
print('\n■ 1・2番人気の馬連：rの帯ごと'); print(Z.groupby(pd.cut(Z['r'], [0, .8, .9, 1.0, 1.1, 1.2, 99]), observed=True).agg(
    レース=('的中', 'size'), 実際=('的中', 'mean'), 回収=('戻り', 'mean')).round(3).to_string())
