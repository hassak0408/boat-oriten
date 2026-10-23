"""モデルが市場に無い情報を持っているかの確かめ（ベンターの組み合わせ）。2026年3〜9月の単勝の確定オッズ。
見込み ∝ exp(a・log モデル + b・log 市場)。3〜6月で a・b を決め、7〜9月で対数損失を市場だけとくらべる。
a が0より大きく、7〜9月で市場だけより対数損失が小さければ、モデルは市場に無い情報を持っている。"""
import sys, numpy as np, pandas as pd
from scipy.optimize import minimize
from load import odds as load_odds
KEY = ['競馬場', '競走年月日', 'レース番号']
nm = sys.argv[1] if len(sys.argv) > 1 else 'B2'
H = pd.read_pickle('/tmp/chiho_feat2.pkl')[KEY + ['馬番', '勝', '単払', '人気', '年', '月']]
D = H[H['年'] == 2026].merge(pd.read_pickle(f'/tmp/chiho_win_{nm}.pkl'), on=KEY + ['馬番'])
O = load_odds(); W = O[(O['賭式'] == '単勝') & (O['オッズ'] > 0)].copy(); W['馬番'] = pd.to_numeric(W['番号1'], errors='coerce')
D = D.merge(W[KEY + ['馬番', 'オッズ']], on=KEY + ['馬番'], how='inner')
D = D[D.groupby(KEY)['馬番'].transform('size') == D.groupby(KEY)['勝'].transform('size')]
D = D[D.groupby(KEY)['勝'].transform('sum') == 1].copy()
D['lp'] = np.log((D['p'] / D.groupby(KEY)['p'].transform('sum')).clip(1e-6))
D['q'] = (1 / D['オッズ']); D['lq'] = np.log(D['q'] / D.groupby(KEY)['q'].transform('sum'))
D['rid'] = D.groupby(KEY).ngroup()


def nll(w, X, use):
    s = sum(wi * X[c].values for wi, c in zip(w, use))
    s = s - pd.Series(s).groupby(X['rid'].values).transform('max').values
    e = np.exp(s); z = pd.Series(e).groupby(X['rid'].values).transform('sum').values
    return -np.sum(np.log(e[X['勝'].values == 1] / z[X['勝'].values == 1])) / X['勝'].sum()


tr = D[D['月'] <= 6]; te = D[D['月'] >= 7]
print('レース', D['rid'].nunique(), '（3〜6月', tr['rid'].nunique(), '／7〜9月', te['rid'].nunique(), '）')
fm = minimize(nll, [1.0], args=(tr, ['lq']), method='Nelder-Mead')
fc = minimize(nll, [0.3, 1.0], args=(tr, ['lp', 'lq']), method='Nelder-Mead')
fp = minimize(nll, [1.0], args=(tr, ['lp']), method='Nelder-Mead')
print(f"市場だけ：b={fm.x[0]:.3f}  7〜9月の対数損失 {nll(fm.x, te, ['lq']):.4f}（そのまま {nll([1.0], te, ['lq']):.4f}）")
print(f"モデルだけ：a={fp.x[0]:.3f}  7〜9月の対数損失 {nll(fp.x, te, ['lp']):.4f}")
print(f"組み合わせ：a={fc.x[0]:.3f} b={fc.x[1]:.3f}  7〜9月の対数損失 {nll(fc.x, te, ['lp', 'lq']):.4f}")
fa = minimize(nll, [0.3, 1.0], args=(D, ['lp', 'lq']), method='Nelder-Mead')
print(f"（全部の月で決めた場合 a={fa.x[0]:.3f} b={fa.x[1]:.3f}）")

# 組み合わせの見込み × オッズ（確定）での単勝の回収（7〜9月、見方だけ。確定オッズなので甘い）
s = fc.x[0] * te['lp'].values + fc.x[1] * te['lq'].values
te = te.assign(pc=np.exp(s)); te['pc'] = te['pc'] / te.groupby(KEY)['pc'].transform('sum')
te['期待'] = te['pc'] * te['オッズ']
print('\n7〜9月：組み合わせの見込み×確定オッズの帯ごとの単勝（確定オッズで決めているので甘い）')
print(te.groupby(pd.cut(te['期待'], [0, 0.6, 0.8, 1.0, 1.2, 1.5, 99]), observed=True).agg(
    頭=('勝', 'size'), 一着率=('勝', lambda x: round(x.mean() * 100, 1)), 回収=('単払', lambda x: round(x.mean() * 100, 1)), 人気平均=('人気', 'mean')).round(1).to_string())
