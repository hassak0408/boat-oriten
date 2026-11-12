"""中央競馬：Z1 のくらべ（検証計画 Z1）。1着 ∝ 市場^α × exp(γ×f) を、2021〜2023年で決めて2024〜2026年に当てる、と逆向き。市場だけ（α だけ）とくらべる。
f の上位1割（しきいは決める期間の値）の馬の実際÷市場（日を単位の95%幅、2000回）と単勝の回収も出す。
使い方：python jk_z1cmp.py "…/z1_pred_*.csv.gz" """
import sys, glob, numpy as np, pandas as pd
from scipy.optimize import minimize

KEY = ['年月日', '場', 'R']
D = pd.concat([pd.read_csv(f, dtype={k: str for k in KEY}) for f in sorted(glob.glob(sys.argv[1]))], ignore_index=True)
D = D.sort_values(KEY + ['馬番']).reset_index(drop=True); D['g'] = D.groupby(KEY, sort=False).ngroup()
D['lm'] = np.log(D['pm']); D['単'] = np.where(D['勝'] == 1, D['単勝オッズ'], 0.0)
rng = np.random.default_rng(0)
print('レース', D['g'].nunique(), 'f の標準偏差', round(float(D['f'].std()), 4), {int(y): round(float(v), 4) for y, v in D.groupby('年')['f'].std().items()})


def p(X, a, c):
    s = a * X['lm'].values + c * X['f'].values; g = X['g'].values; s = s - pd.Series(s).groupby(g).transform('max').values
    e = np.exp(s); return e / pd.Series(e).groupby(g).transform('sum').values


def l1(X, q): return float(-np.log(np.clip(q[X['勝'].values == 1], 1e-9, 1)).mean())


def ci(x):
    d = x.groupby('年月日')[['勝', 'pm', '単']].sum().assign(c=x.groupby('年月日').size()).values
    i = rng.integers(0, len(d), size=(2000, len(d)))
    r = d[i, 0].sum(1) / d[i, 1].sum(1); t = d[i, 2].sum(1) / d[i, 3].sum(1)
    return (f"{x['勝'].sum() / x['pm'].sum():.2f}（{np.percentile(r, 2.5):.2f}〜{np.percentile(r, 97.5):.2f}）",
            f"{x['単'].mean() * 100:.0f}%（{np.percentile(t, 2.5) * 100:.0f}〜{np.percentile(t, 97.5) * 100:.0f}%）")


A = D[D['年'] <= 2023].reset_index(drop=True); B = D[D['年'] >= 2024].reset_index(drop=True); ok = True
for fit, test, lab in ((A, B, '2021〜23で決めて2024〜26'), (B, A, '2024〜26で決めて2021〜23')):
    r0 = minimize(lambda w: l1(fit, p(fit, w[0], 0.0)), [1.0], method='Nelder-Mead')
    r1 = minimize(lambda w: l1(fit, p(fit, w[0], w[1])), [1.0, 1.0], method='Nelder-Mead')
    a0, a1 = l1(test, p(test, r0.x[0], 0)), l1(test, p(test, *r1.x)); ok &= a1 < a0
    print(f'{lab}：市場だけ {a0:.5f}（α={r0.x[0]:.3f}）／市場×exp(γf) {a1:.5f}（α={r1.x[0]:.3f} γ={r1.x[1]:.3f}）差 {a1 - a0:+.5f}')
    th = fit['f'].quantile(0.9); lo = fit['f'].quantile(0.1)
    for nm, x in (('f の上位1割', test[test['f'] >= th]), ('f の下位1割', test[test['f'] <= lo]),
                  ('上位1割・1〜3番人気', test[(test['f'] >= th) & (test['人気'] <= 3)]), ('上位1割・4番人気以下', test[(test['f'] >= th) & (test['人気'] >= 4)])):
        r, t = ci(x); print(f'   {nm}：{len(x)}頭 実際÷市場 {r} 単勝の回収 {t}')
print('決めごと：', '市場のずれを学べた（両方の向きで市場だけより下がった）' if ok else '朝の材料では、市場のずれは学べない（どちらかの向きで下がらない）')
