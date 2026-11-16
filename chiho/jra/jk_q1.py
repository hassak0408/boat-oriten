"""中央競馬：見込みの偏りの直し Q1（検証計画「的中率の研究その2」）。AIの最終の1着の見込み p に、馬の区分ごとの値を掛けて、レースの中で足して1に直す：
log p' = log p + Σ θ（区分）。区分は市場の材料を使わない（齢・間隔・芝ダ変更・距離の変更・前走の着順・クラスの上がり下がり・走数）。新馬は直さない。
θ はレースの中で勝ち馬を当てる形（条件つきロジット、少しだけ縮める）で学ぶ。
使い方（確かめと値の決め直し）：python jk_q1.py 見込み.pkl（jra_refit.py の出力） STORE [write]
  write を付けると、全部の期間で決めた値を jra_fix.json の「偏りの直し」に書き、見込み.pkl の p1 を直したものに替える（馬連の直し jpair.py をそのあとで作り直す）。"""
import os, sys, json, numpy as np, pandas as pd

NEEDS = ['齢', '間隔', '芝ダ変更', '距離差', '着率1', 'クラス差', '走数', '新馬']


def keys(X, kind='jra'):
    """行ごとの区分の名前。空は「無」。kind：jra（中央）・nar（地方）"""
    def cut(s, bins, labs): return pd.cut(pd.to_numeric(s, errors='coerce'), bins, labels=labs).astype(object).where(s.notna(), '無')
    num = lambda c: pd.to_numeric(X[c], errors='coerce')
    K = pd.DataFrame(index=X.index)
    K['齢'] = num('齢').clip(upper=7 if kind == 'jra' else 8).map(lambda v: '無' if v != v else f'{int(v)}歳')
    K['前走'] = cut(X['着率1'], [-.01, .1, .25, .5, .75, 1.01], ['1着近く', '上位', '中', '下位', '大敗'])
    K['クラス'] = np.sign(num('クラス差')).map(lambda v: '無' if v != v else {-1: '降級', 0: '同じ', 1: '昇級'}[int(v)])
    if kind == 'jra':
        K['間隔'] = cut(X['間隔'], [-1, 14, 35, 63, 119, 179, 99999], ['〜2週', '3〜5週', '6〜9週', '10〜17週', '18〜25週', '半年〜'])
        K['芝ダ変更'] = num('芝ダ変更').map(lambda v: '無' if v != v else ('替わる' if v == 1 else '同じ'))
        K['距離'] = cut(X['距離差'], [-99999, -400, -1, 0, 399, 99999], ['400m〜短く', '短く', '同じ', '長く', '400m〜長く'])
        r = num('走数'); K['走数'] = np.where(r == 0, '中央で初', np.where(r <= 2, '1〜2走', '3走〜'))
    else:
        K['間隔'] = cut(X['間隔'], [-1, 9, 20, 35, 63, 119, 99999], ['〜9日', '10〜20日', '3〜5週', '6〜9週', '10〜17週', '18週〜'])
        K['距離'] = cut(X['距離差'], [-99999, -300, -1, 0, 299, 99999], ['300m〜短く', '短く', '同じ', '長く', '300m〜長く'])
        r = num('五場走数'); K['走数'] = np.where(r == 0, '5場で初', np.where(r <= 2, '1〜2走', '3走〜'))
        K['前走外'] = num('前走外').map(lambda v: '無' if v != v else ('外' if v == 1 else '5場'))
    return K


NEEDS_NAR = ['齢', '間隔', '距離差', '着率1', 'クラス差', '五場走数', '前走外']


def score(X, TH, kind='jra'):
    """Σ θ（中央の新馬は0）"""
    K = keys(X, kind); s = np.zeros(len(X))
    for c in K.columns: s += K[c].map(lambda v, c=c: TH.get(f'{c}・{v}', 0.0)).values.astype(float)
    if kind == 'jra': s = np.where(pd.to_numeric(X['新馬'], errors='coerce').fillna(0).values == 1, 0.0, s)
    return s


def apply(p1, X, TH, grp, kind='jra'):
    """1着：p1（Series）に掛けて、レース（grp）の中で足して1に直す"""
    v = p1 * np.exp(score(X, TH, kind)); return v / v.groupby(grp).transform('sum')


def apply3(p3, X, TH, grp, n, kind='jra'):
    """3着内：log(p/(1−p)) に Σθ を足し、レースの中で足して min(3, 頭数) に直す"""
    q = p3.clip(1e-4, 0.97); v = 1 / (1 + (1 - q) / q * np.exp(-score(X, TH, kind)))
    return (v * np.minimum(3, n) / v.groupby(grp).transform('sum')).clip(1e-4, 0.97)


def fit1(D, kind, gcol='g', lam=1e-4):
    """1着の値 θ を決める（条件つきロジット）。D は p1・勝・gcol（レースの番号）と区分の元の列を持つ。返すのは {区分・名前: θ}"""
    from scipy.optimize import minimize
    D = D.sort_values(gcol).reset_index(drop=True); g = pd.factorize(D[gcol])[0]; n = g.max() + 1
    K = keys(D, kind); X = pd.get_dummies(pd.DataFrame({c: c + '・' + K[c].astype(str) for c in K.columns}), prefix='', prefix_sep='').astype(float)
    Xv = X.values.copy()
    if kind == 'jra': Xv[(pd.to_numeric(D['新馬'], errors='coerce') == 1).values] = 0
    y = D['勝'].values.astype(float); lp = np.log((D['p1'] / D.groupby(gcol)['p1'].transform('sum')).values); st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]

    def f(t):
        s = lp + Xv @ t; s = s - np.maximum.reduceat(s, st)[g]; e = np.exp(s); p = e / np.bincount(g, e, n)[g]
        return -np.log(p[y == 1]).sum() / n + lam * (t ** 2).sum(), (Xv.T @ (p - y)) / n + 2 * lam * t
    t = minimize(f, np.zeros(Xv.shape[1]), jac=True, method='L-BFGS-B').x
    return {c: round(float(v), 4) for c, v in zip(X.columns, t)}


if __name__ == '__main__':
    from scipy.optimize import minimize
    HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
    import jfeat
    P, ST = sys.argv[1], sys.argv[2]; WRITE = len(sys.argv) > 3
    KEY = ['年月日', '場', 'R']
    D = pd.read_pickle(P)
    H = jfeat.build(f'{ST}/jra/data', verbose=False) if not os.path.exists(os.environ.get('H_PKL', '')) else pd.read_pickle(os.environ['H_PKL'])
    H = H.loc[~H['予測'], KEY + ['馬番'] + NEEDS]
    for X in (D, H): X['馬番'] = pd.to_numeric(X['馬番']).astype(int); X['R'] = X['R'].astype(str)
    D = D.merge(H, on=KEY + ['馬番'], how='left'); D['g'] = D.groupby(KEY, sort=False).ngroup(); D = D.sort_values('g').reset_index(drop=True)
    K = keys(D); new = (D['新馬'] == 1).values
    X = pd.get_dummies(pd.DataFrame({c: c + '・' + K[c].astype(str) for c in K.columns}), prefix='', prefix_sep='').astype(float)
    Xv = X.values.copy(); Xv[new] = 0
    g = D['g'].values; y = D['勝'].values.astype(float); p0 = (D['p1'] / D.groupby('g')['p1'].transform('sum')).values; lp = np.log(p0)

    def soft(s, gg):
        n = gg.max() + 1; s = s - np.maximum.reduceat(s, np.r_[0, np.flatnonzero(np.diff(gg)) + 1])[gg]; e = np.exp(s); return e / np.bincount(gg, e, n)[gg]

    def fit(m, lam=1e-4):
        Xm, lpm, ym = Xv[m], lp[m], y[m]; gm = pd.factorize(g[m])[0]; n = gm.max() + 1

        def f(t):
            p = soft(lpm + Xm @ t, gm); return -np.log(p[ym == 1]).sum() / n + lam * (t ** 2).sum(), (Xm.T @ (p - ym)) / n + 2 * lam * t
        return minimize(f, np.zeros(Xv.shape[1]), jac=True, method='L-BFGS-B').x
    l1 = lambda p, m: float(-np.log(p[m & (y == 1)]).mean())
    A = (D['年'] <= 2023).values; B = (D['年'] >= 2024).values; ok = True
    for fm, tm, lab in ((A, B, '2021〜23で決めて2024〜26'), (B, A, '2024〜26で決めて2021〜23')):
        p = soft(lp + Xv @ fit(fm), g); d = l1(p, tm) - l1(p0, tm); ok &= d <= -0.0005
        print(f'{lab}：1着の当て分け {l1(p0, tm):.5f}→{l1(p, tm):.5f}（{d:+.5f}）')
    print('条件（両方の向きで 0.0005 以上下がる）：', '満たす' if ok else '届かない')
    t = fit(A | B); TH = {c: round(float(v), 4) for c, v in zip(X.columns, t)}
    print('全部の期間で決めた掛ける値（1から4%より離れたもの）：', {k: round(float(np.exp(v)), 3) for k, v in TH.items() if abs(np.exp(v) - 1) > 0.04})
    D['p1q'] = apply(pd.Series(p0), D, TH, D['g']).values
    print('道具（apply）で直した見込みが、学んだ式と同じか：', bool(np.allclose(D['p1q'].values, soft(lp + Xv @ np.array([TH[c] for c in X.columns]), g), atol=1e-9)))
    if WRITE and ok:
        J = json.load(open(f'{HERE}/jra_fix.json', encoding='utf-8'))
        J['偏りの直し'] = {'値': TH, '作り方': '検証計画「的中率の研究その2」Q1。AIの最終の1着の見込み（枠の付け直しのあと）に exp(Σ値) を掛けて足して1に直す。新馬は直さない。値は2021〜2026年の全部で決めた（jk_q1.py）'}
        json.dump(J, open(f'{HERE}/jra_fix.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        O = pd.read_pickle(P); O['馬番'] = pd.to_numeric(O['馬番']).astype(int); O['R'] = O['R'].astype(str)
        O = O.merge(D[KEY + ['馬番', 'p1q']], on=KEY + ['馬番'], how='left'); O['p1'] = O['p1q'].fillna(O['p1']); O.drop(columns='p1q').to_pickle(P)
        print('書いた（jra_fix.json・見込みの表の p1）')
