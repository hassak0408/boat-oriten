"""中央競馬：相手との勝ち負けから作る材料（検証計画「的中率の研究：M8」）。どちらも、その日より前の結果だけで作る（オッズ・人気は使わない）。
add_elo(H, KEY)   E：強さの点数。出た馬どうしの着順の勝ち負けで点数を動かす（始め1500、動かす大きさは4走目まで100・5走目から50）。
                  騎手・調教師の点数は、馬の点数から見込まれる着順より良かったか悪かったかで動かす（大きさ4）。同じ日のレースは、その日の前の点数で見込む。
add_after(H, KEY) V：前走（と前3走）でいっしょに走った馬が、そのあと今日より前に走ったレースの結果。
H は jfeat.build の表（日・馬・騎手・調教師・芝ダ・着・着率・3着内・指数・予測 を持つ）。返すのは（H, 足した材料の名前）。"""
import numpy as np, pandas as pd

K_NEW, K_OLD, K_HUMAN, START = 100.0, 50.0, 4.0, 1500.0


def add_elo(H, KEY, jk='騎手', tr='調教師', sd='芝ダ', rel=True):
    """jk・tr・sd は騎手・調教師・芝ダの列の名前（tr・sd は None なら作らない。地方は調教師・芝ダ別を作らない）。rel=False ならレースの中での差は作らない"""
    H = H.copy(); _jk, _tr, _sd = jk, tr, sd
    n = len(H)
    eh, es, ej, et = (np.full(n, np.nan) for _ in range(4))
    RH, RS, RJ, RT, CNT = {}, {}, {}, {}, {}
    pos = np.arange(n)
    day = H['日'].values; horse = H['馬'].astype(str).values; jk = H[_jk].astype(str).values
    tr = H[_tr].astype(str).values if _tr else np.full(n, ''); sd = H[_sd].astype(str).values if _sd else np.full(n, '')
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
            for which in ((0, 1) if _sd else (0,)):
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
    H['E馬'], H['E騎'] = eh, ej; EF = ['E馬', 'E騎']
    if _sd: H['E馬芝ダ'] = es; EF.append('E馬芝ダ')
    if _tr: H['E調'] = et; EF.append('E調')
    if not rel: return H, EF
    return add_elo_rel(H, KEY, EF)


def add_elo_rel(H, KEY, EF):
    """レースの中での差（H は見込みを出すレースの行だけでもよい）"""
    g = H.groupby(KEY, sort=False)
    H['E馬平均差'] = H['E馬'] - g['E馬'].transform('mean')
    H['E馬最高差'] = g['E馬'].transform('max') - H['E馬']
    H['E馬順率'] = g['E馬'].rank(ascending=False, method='average') / g['E馬'].transform('count')
    if 'E馬芝ダ' in H: H['E芝ダ平均差'] = H['E馬芝ダ'] - g['E馬芝ダ'].transform('mean')
    H['E騎平均差'] = H['E騎'] - g['E騎'].transform('mean')
    return H, [c for c in ['E馬', 'E馬芝ダ', 'E騎', 'E調', 'E馬平均差', 'E馬最高差', 'E馬順率', 'E芝ダ平均差', 'E騎平均差'] if c in H]


def add_after(H, KEY, detail=False, chunk=150000):
    """メモリを食わないように、馬は番号にして、行を分けて相手とつなぎ、行ごとの和と数だけをためる"""
    H = H.copy()
    n = len(H)
    rid = H.groupby(KEY, sort=False).ngroup().values.astype(np.int64)
    hc = pd.factorize(H['馬'].astype(str))[0].astype(np.int64)
    day = H['日'].values.astype('datetime64[D]').astype(np.int64)
    fin = pd.to_numeric(H['着'], errors='coerce').values.astype(float)
    ran = ~np.isnan(fin) & ~H['予測'].values.astype(bool)
    T = pd.DataFrame({'row': np.arange(n), 'h': hc, 'd': day, 'rid': rid, 'fin': fin, 'ran': ran,
                      'cr': H['着率'].values.astype(float), 't3': H['3着内'].values.astype(float), 'ix': H['指数'].values.astype(float),
                      'w': H['勝'].values.astype(float)}).sort_values(['h', 'd'], kind='stable').reset_index(drop=True)
    # 相手の表：走った行だけ。その馬の次に走ったレースの日と結果
    A = T[T['ran']].copy(); g = A.groupby('h', sort=False)
    A['nd'] = g['d'].shift(-1); A['ncr'] = g['cr'].shift(-1); A['n3'] = g['t3'].shift(-1); A['nix'] = g['ix'].shift(-1) - A['ix']; A['nw'] = g['w'].shift(-1)
    A = A[A['nd'].notna()][['rid', 'h', 'fin', 'nd', 'ncr', 'n3', 'nix', 'nw']].rename(columns={'h': 'oh', 'fin': 'ofin'})
    # 自分の前に走った k 番目のレース（中止などの行は飛ばす）
    r = T['ran'].values
    G = np.cumsum(r) - r
    G0 = pd.Series(G).groupby(T['h'].values, sort=False).transform('first').values
    ran_rid = T['rid'].values[r]; ran_fin = T['fin'].values[r]
    names = ['c', 'scr', 's3', 'cix', 'six', 'sw'] + (['cu', 'u3', 'ucr', 'cd', 'd3', 'dcr'] if detail else [])
    acc = {k: {nm: np.zeros(n) for nm in names} for k in (1, 3)}      # 1＝前走だけ、3＝前3走をまとめたもの
    rows_all = T['row'].values; h_all = T['h'].values; d_all = T['d'].values
    for k in (1, 2, 3):
        ok = np.flatnonzero((G - k) >= G0)
        for a0 in range(0, len(ok), chunk):
            ii = ok[a0:a0 + chunk]
            X = pd.DataFrame({'row': rows_all[ii], 'h': h_all[ii], 'd': d_all[ii], 'rid': ran_rid[(G - k)[ii]], 'sfin': ran_fin[(G - k)[ii]]})
            M = X.merge(A, on='rid', how='inner')
            M = M[(M['oh'] != M['h']) & (M['nd'] < M['d'])]
            if not len(M): continue
            rw = M['row'].values
            vals = {'c': np.ones(len(M)), 'scr': M['ncr'].values, 's3': M['n3'].values, 'cix': M['nix'].notna().values.astype(float),
                    'six': M['nix'].fillna(0).values, 'sw': M['nw'].values}
            if detail:
                up = (M['ofin'].values < M['sfin'].values).astype(float); dn = (M['ofin'].values > M['sfin'].values).astype(float)
                vals.update({'cu': up, 'u3': up * M['n3'].values, 'ucr': up * M['ncr'].values, 'cd': dn, 'd3': dn * M['n3'].values, 'dcr': dn * M['ncr'].values})
            for nm in names:
                b = np.bincount(rw, weights=vals[nm], minlength=n)
                acc[3][nm] += b
                if k == 1: acc[1][nm] += b
    div = lambda x, c: np.where(c > 0, x / np.where(c > 0, c, 1), np.nan)
    for k in (1, 3):
        q = acc[k]
        H[f'後数{k}'] = q['c']; H[f'後着率{k}'] = div(q['scr'], q['c']); H[f'後3率{k}'] = div(q['s3'], q['c']); H[f'後指数差{k}'] = div(q['six'], q['cix'])
    VF = ['後数1', '後着率1', '後3率1', '後指数差1', '後数3', '後着率3', '後3率3', '後指数差3']
    if not detail: return H, VF
    # V2：自分が先着した相手（下）・先着された相手（上）に分ける。そのあと勝った相手の数
    V2 = []
    for nm, cc, c3, ccr in (('上', 'cu', 'u3', 'ucr'), ('下', 'cd', 'd3', 'dcr')):
        H[f'後{nm}数3'] = acc[3][cc]; H[f'後{nm}3率3'] = div(acc[3][c3], acc[3][cc]); H[f'後{nm}着率3'] = div(acc[3][ccr], acc[3][cc]); H[f'後{nm}3率1'] = div(acc[1][c3], acc[1][cc])
        V2 += [f'後{nm}数3', f'後{nm}3率3', f'後{nm}着率3', f'後{nm}3率1']
    H['後勝数3'] = acc[3]['sw']; H['後勝数1'] = acc[1]['sw']; V2 += ['後勝数3', '後勝数1']
    return H, VF, V2
