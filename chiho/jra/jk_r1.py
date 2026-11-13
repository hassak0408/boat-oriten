"""中央競馬：連対（2着内）の見込みの出し方をくらべ、直しの表を作る（検証計画「R1中央」）。地方の R1（nk_r1.py・nk_r1cal.py）と同じやり方。
R1a 馬連の組の見込み（B式、直す前）をその馬が入る組について足す／R1b 1着の見込みからハービル。
2021〜2023年で連対の当て分けが小さい方を選び、2024〜2026年で見込みの帯（10%ごと）と実際がそろうかを見る。
500頭以上ある帯で3ポイントより大きくずれていれば、2021〜2023年で単調な直しを作って2024〜2026年で確かめ、条件を満たせば jra_rentai_calib.json を書く。
使い方：python jk_r1.py 見込み.pkl（jra_refit.py の出力 jra_m7_final.pkl）"""
import os, sys, json, numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression

KEY = ['年月日', '場', 'R']
D = pd.read_pickle(sys.argv[1])
D = D[D['n'] >= 5].copy()
D['連対'] = (D['着'] <= 2).astype(int)                      # 着が無い（中止など）は0
ok = D.groupby(KEY)['連対'].transform('sum') >= 2
print('5頭以上', D.groupby(KEY).ngroups, 'レース → 2着内が2頭以上そろうもの', D[ok].groupby(KEY).ngroups, flush=True)
D = D[ok].reset_index(drop=True)
gk = [D[k] for k in KEY]
gs = lambda v: pd.Series(v).groupby(gk).transform('sum').values
p1 = D['p1'].values; p1 = p1 / gs(p1)
q = D['p3'].values * np.minimum(3, D['n'].values) / gs(D['p3'].values); q = np.clip(q, None, 0.97); q = q / gs(q)
# R1a：B式の組 P(i,j)=p1_i q_j/(1−q_i)+p1_j q_i/(1−q_j) を i の入る組で足す → u_i = p1_i + q_i (S − t_i)、t=p1/(1−q)、S=Σt。足して2に直す
t = p1 / (1 - q); u = p1 + q * (gs(t) - t)
D['R1a'] = np.clip(2 * u / gs(u), 1e-4, 0.999)
# R1b：ハービル p2_i = p1_i + p1_i Σ_{j≠i} p1_j/(1−p1_j)（足すとちょうど2）
r = p1 / np.clip(1 - p1, 1e-9, None)
D['R1b'] = np.clip(p1 + p1 * (gs(r) - r), 1e-4, 0.999)


def ll(y, p): return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def bands(X, col, lab):
    b = np.minimum((X[col].values * 10).astype(int), 9)
    T = pd.DataFrame({'帯': b, '見込み': X[col].values, '実際': X['連対'].values}).groupby('帯').agg(頭数=('実際', 'size'), 見込み=('見込み', 'mean'), 実際=('実際', 'mean'))
    T['ずれ'] = (T['実際'] - T['見込み']) * 100
    print(f'| {lab} | 帯 | 頭数 | 見込み | 実際 | ずれ（ポイント） |'); print('|---|---|---|---|---|---|')
    for k, x in T.iterrows():
        print(f"| | {k * 10}〜{k * 10 + 10}% | {int(x['頭数'])} | {x['見込み'] * 100:.1f}% | {x['実際'] * 100:.1f}% | {x['ずれ']:+.1f}{'' if x['頭数'] >= 500 else '（500頭未満）'} |")
    big = T[(T['頭数'] >= 500) & (T['ずれ'].abs() > 3)]
    return big


A = D[D['年'] <= 2023]; B = D[D['年'] >= 2024]
print('レース 2021〜23', A.groupby(KEY).ngroups, '・2024〜26', B.groupby(KEY).ngroups, '／頭数', len(A), len(B))
res = {c: (ll(A['連対'].values, A[c].values), ll(B['連対'].values, B[c].values)) for c in ('R1a', 'R1b')}
for c, (a, b) in res.items(): print(f'{c} 連対の当て分け 2021〜23 {a:.5f} ／ 2024〜26 {b:.5f}')
pick = 'R1a' if res['R1a'][0] < res['R1b'][0] else 'R1b'
print('2021〜2023年で小さい方 →', pick, flush=True)
big = bands(B, pick, f'{pick} 2024〜26（直す前）')
cal = None
if len(big):
    print('500頭以上の帯で3ポイントより大きいずれ：', ', '.join(f'{k * 10}〜{k * 10 + 10}% {v:+.1f}' for k, v in big['ずれ'].items()), '→ 2021〜2023年で単調な直しを作る')
    grid = np.round(np.arange(0, 1.001, 0.01), 2)
    ir = IsotonicRegression(out_of_bounds='clip', y_min=1e-3, y_max=0.999).fit(A[pick].values, A['連対'].values.astype(float))
    mapped = ir.predict(grid)
    B = B.copy(); B['直した'] = np.interp(B[pick].values, grid, mapped)
    print(f"直した後の連対の当て分け 2024〜26 {ll(B['連対'].values, B['直した'].values):.5f}（直す前 {res[pick][1]:.5f}）")
    big2 = bands(B, '直した', '直した後 2024〜26')
    # 参考：逆向き（2024〜2026年で作って2021〜2023年に当てる）
    ir2 = IsotonicRegression(out_of_bounds='clip', y_min=1e-3, y_max=0.999).fit(B[pick].values, B['連対'].values.astype(float))
    A = A.copy(); A['直した'] = np.interp(A[pick].values, grid, ir2.predict(grid))
    print(f"参考・逆向き：2021〜23 直す前 {res[pick][0]:.5f} → 直した後 {ll(A['連対'].values, A['直した'].values):.5f}")
    bands(A, '直した', '参考・逆向き 2021〜23')
    good = len(big2) == 0 and ll(B['連対'].values, B['直した'].values) < res[pick][1]
    cal = (grid, mapped)
else:
    good = True
print('条件：', '満たす' if good else '届かない')
if good:
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jra_rentai_calib.json')
    if cal is None: cal = (np.round(np.arange(0, 1.001, 0.01), 2), np.round(np.arange(0, 1.001, 0.01), 2))
    how = 'ハービル' if pick == 'R1b' else '馬連の組の見込み（B式、直す前）の和'
    json.dump({'出し方': pick, '見込み': cal[0].tolist(), '直した見込み': np.round(cal[1], 4).tolist(),
               '作り方': f'検証計画 R1中央。1着の見込み（M7、枠の付け直しのあと）から{how}で出した連対（2着内）の見込みに、2021〜2023年で単調な直しを作った（jk_r1.py）'},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('書いた', out)
