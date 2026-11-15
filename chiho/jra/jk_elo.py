"""中央競馬：相手との勝ち負けから作る材料（検証計画「的中率の研究：M8」）。どちらも、その日より前の結果だけで作る（オッズ・人気は使わない）。
add_elo(H, KEY)   E：強さの点数。出た馬どうしの着順の勝ち負けで点数を動かす（始め1500、動かす大きさは4走目まで100・5走目から50）。
                  騎手・調教師の点数は、馬の点数から見込まれる着順より良かったか悪かったかで動かす（大きさ4）。同じ日のレースは、その日の前の点数で見込む。
add_after(H, KEY) V：前走（と前3走）でいっしょに走った馬が、そのあと今日より前に走ったレースの結果。
H は jfeat.build の表（日・馬・騎手・調教師・芝ダ・着・着率・3着内・指数・予測 を持つ）。返すのは（H, 足した材料の名前）。"""
import numpy as np, pandas as pd

K_NEW, K_OLD, K_HUMAN, START = 100.0, 50.0, 4.0, 1500.0


def add_elo(H, KEY):
    H = H.copy()
    n = len(H)
    eh, es, ej, et = (np.full(n, np.nan) for _ in range(4))
    RH, RS, RJ, RT, CNT = {}, {}, {}, {}, {}
    pos = np.arange(n)
    day = H['日'].values; horse = H['馬'].values; jk = H['騎手'].values; tr = H['調教師'].values; sd = H['芝ダ'].values
    fin = pd.to_numeric(H['着'], errors='coerce').values; pred = H['予測'].values.astype(bool)
    rid = H.groupby(KEY, sort=False).ngroup().values
    order = np.lexsort((rid, day))                       # 日 → レース の順
    d_sorted = day[order]
    cuts = np.flatnonzero(np.r_[True, d_sorted[1:] != d_sorted[:-1], True])
    for a, b in zip(cuts[:-1], cuts[1:]):
        idx = order[a:b]
        # その日の前の点数を書く（走ったことのない馬は空）
        for i in idx:
            h = horse[i]
            if h in RH: eh[i] = RH[h]
            v = RS.get((h, sd[i]))
            if v is not None: es[i] = v
            ej[i] = RJ.get(jk[i], 0.0); et[i] = RT.get(tr[i], 0.0)
        # その日の結果で動かす（まとめて。同じ日の別のレースは前の点数のまま見込む）
        upd = []
        r_day = rid[idx]
        for r in np.unique(r_day):
            ii = idx[r_day == r]; ii = ii[~np.isnan(fin[ii]) & ~pred[ii]]
            m = len(ii)
            if m < 2: continue
            f = fin[ii]
            for which in (0, 1):
                R = np.array([(RH.get(horse[i], START) if which == 0 else RS.get((horse[i], sd[i]), RH.get(horse[i], START))) for i in ii])
                E = (1.0 / (1.0 + 10 ** ((R[None, :] - R[:, None]) / 400.0))).sum(axis=1) - 0.5      # 自分との組（0.5）を引く
                E = E / (m - 1)
                S = ((f[None, :] > f[:, None]).sum(axis=1) + 0.5 * ((f[None, :] == f[:, None]).sum(axis=1) - 1)) / (m - 1)
                for k, i in enumerate(ii):
                    kk = K_NEW if CNT.get(horse[i], 0) < 4 else K_OLD
                    upd.append((which, i, R[k] + kk * (S[k] - E[k]), S[k] - E[k]))
        for which, i, newr, res in upd:
            if which == 0:
                RH[horse[i]] = newr; CNT[horse[i]] = CNT.get(horse[i], 0) + 1
                RJ[jk[i]] = RJ.get(jk[i], 0.0) + K_HUMAN * res; RT[tr[i]] = RT.get(tr[i], 0.0) + K_HUMAN * res
            else:
                RS[(horse[i], sd[i])] = newr
    H['E馬'], H['E馬芝ダ'], H['E騎'], H['E調'] = eh, es, ej, et
    g = H.groupby(KEY, sort=False)
    H['E馬平均差'] = H['E馬'] - g['E馬'].transform('mean')
    H['E馬最高差'] = g['E馬'].transform('max') - H['E馬']
    H['E馬順率'] = g['E馬'].rank(ascending=False, method='average') / g['E馬'].transform('count')
    H['E芝ダ平均差'] = H['E馬芝ダ'] - g['E馬芝ダ'].transform('mean')
    H['E騎平均差'] = H['E騎'] - g['E騎'].transform('mean')
    return H, ['E馬', 'E馬芝ダ', 'E騎', 'E調', 'E馬平均差', 'E馬最高差', 'E馬順率', 'E芝ダ平均差', 'E騎平均差']


def add_after(H, KEY, detail=False):
    H = H.copy()
    H['_rid'] = H.groupby(KEY, sort=False).ngroup()
    H['_row'] = np.arange(len(H))
    fin = pd.to_numeric(H['着'], errors='coerce')
    H['_fin'] = fin
    A = H.loc[fin.notna() & ~H['予測'].astype(bool), ['_rid', '馬', '日', '着率', '3着内', '指数', '_fin', '勝']].sort_values(['馬', '日'])
    gh = A.groupby('馬', sort=False)
    A['次日'] = gh['日'].shift(-1); A['次着率'] = gh['着率'].shift(-1); A['次3'] = gh['3着内'].shift(-1); A['次指数差'] = gh['指数'].shift(-1) - A['指数']; A['次勝'] = gh['勝'].shift(-1)
    A = A[A['次日'].notna()][['_rid', '馬', '次日', '次着率', '次3', '次指数差', '次勝', '_fin']].rename(columns={'馬': '相手', '_fin': '相手着'})
    # 自分の前1〜3走のレース（走ったレースだけ。今日の行も含めて、馬ごとに日の順）
    T = H[['_row', '馬', '日', '_rid']].sort_values(['馬', '日'], kind='stable')
    ran = (fin.notna() & ~H['予測'].astype(bool)).reindex(T.index).values
    G = np.cumsum(ran) - ran                                   # 並べた表で、この行より前にある「走った行」の数
    G0 = pd.Series(G, index=T.index).groupby(T['馬'], sort=False).transform('first').values      # その馬の始まり
    ran_rid = T['_rid'].values[ran]; ran_fin = fin.reindex(T.index).values[ran]
    parts = []
    for k in (1, 2, 3):                                        # 前に走った k 番目のレース（中止などの行は飛ばす）
        ok = (G - k) >= G0
        X = pd.DataFrame({'_row': T['_row'].values[ok], '馬': T['馬'].values[ok], '日': T['日'].values[ok], '_rid': ran_rid[(G - k)[ok]], '自着': ran_fin[(G - k)[ok]]})
        M = X.merge(A, on='_rid', how='inner')
        M = M[(M['相手'] != M['馬']) & (M['次日'] < M['日'])]
        M['k'] = k; parts.append(M[['_row', 'k', '次着率', '次3', '次指数差', '次勝', '相手着', '自着']])
    M = pd.concat(parts, ignore_index=True)
    one = M[M['k'] == 1].groupby('_row').agg(後数1=('次3', 'size'), 後着率1=('次着率', 'mean'), 後3率1=('次3', 'mean'), 後指数差1=('次指数差', 'mean'))
    all3 = M.groupby('_row').agg(後数3=('次3', 'size'), 後着率3=('次着率', 'mean'), 後3率3=('次3', 'mean'), 後指数差3=('次指数差', 'mean'))
    H = H.join(one, on='_row').join(all3, on='_row')
    H['後数1'] = H['後数1'].fillna(0); H['後数3'] = H['後数3'].fillna(0)
    VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
    V2 = []
    if detail:      # V2：自分が先着した相手（下）・先着された相手（上）に分ける。そのあと勝った相手の数
        for nm, m in (('上', M['相手着'] < M['自着']), ('下', M['相手着'] > M['自着'])):
            a3 = M[m].groupby('_row').agg(**{f'後{nm}数3': ('次3', 'size'), f'後{nm}3率3': ('次3', 'mean'), f'後{nm}着率3': ('次着率', 'mean')})
            a1 = M[m & (M['k'] == 1)].groupby('_row').agg(**{f'後{nm}3率1': ('次3', 'mean')})
            H = H.join(a3, on='_row').join(a1, on='_row'); H[f'後{nm}数3'] = H[f'後{nm}数3'].fillna(0)
            V2 += [f'後{nm}数3', f'後{nm}3率3', f'後{nm}着率3', f'後{nm}3率1']
        w = M.groupby('_row').agg(後勝数3=('次勝', 'sum')); w1 = M[M['k'] == 1].groupby('_row').agg(後勝数1=('次勝', 'sum'))
        H = H.join(w, on='_row').join(w1, on='_row'); H['後勝数3'] = H['後勝数3'].fillna(0); H['後勝数1'] = H['後勝数1'].fillna(0)
        V2 += ['後勝数3', '後勝数1']
    H = H.drop(columns=['_rid', '_row', '_fin'])
    return (H, VF, V2) if detail else (H, VF)
