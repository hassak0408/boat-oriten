"""勝ちきる馬とその相手（馬連）（検証計画の同じ名前の節）。組の見込みを A（ハービル式）と B（2着は3着内の見込みで割り振る）でくらべる。
材料は一覧と同じ（cand3.py 朝3 の p1・p3）。2021〜2023年で選び、2024〜2025年・2026年1〜9月で確かめる。"""
import numpy as np, pandas as pd
from itertools import combinations
from load import _read
KEY = ['競馬場', '競走年月日', 'レース番号']


def num(x):
    try: return float(str(x).replace(',', ''))
    except ValueError: return np.nan


H = pd.read_pickle('/tmp/chiho_feat3.pkl')[KEY + ['馬番', '着', '人気', 'n', '年', '日']]
H['馬番'] = H['馬番'].astype(float)
C = pd.read_pickle('/tmp/chiho_cand3_朝3.pkl'); C['馬番'] = C['馬番'].astype(float)
D = H[H['年'] >= 2021].merge(C, on=KEY + ['馬番'])
D = D[D.groupby(KEY)['人気'].transform('count') == D.groupby(KEY)['馬番'].transform('size')]
D = D[(D['n'] >= 5)]
PB = _read('race', 'payback')
x = PB[KEY + ['馬複組番1', '馬複組番2', '馬複払戻金（円）']].copy()
x['a'] = pd.to_numeric(x['馬複組番1'], errors='coerce'); x['b'] = pd.to_numeric(x['馬複組番2'], errors='coerce'); x['払'] = x['馬複払戻金（円）'].map(num)
x = x.dropna(subset=['a', 'b', '払'])
PAY = {}
for r in x.itertuples(index=False):
    PAY.setdefault((r[0], r[1], r[2]), {})[tuple(sorted((int(r.a), int(r.b))))] = r.払 / 100

rows, cal = [], []
for k, g in D.groupby(KEY, sort=False):
    if k not in PAY: continue
    nums = g['馬番'].astype(int).values; p1 = g['p1'].values / g['p1'].sum(); p3 = g['p3'].values / g['p3'].sum()
    pop = g['人気'].values; fin = g['着'].values
    top2 = set(nums[(fin <= 2)]) if (fin <= 2).sum() >= 2 else None
    if top2 is None: continue
    n = len(nums); idx = range(n)
    pairs = list(combinations(idx, 2))
    def harv(i, j, s1, s2):   # i が1着・j が2着、または逆
        return s1[i] * s2[j] / (1 - s2[i]) + s1[j] * s2[i] / (1 - s2[j])
    PA = {(i, j): harv(i, j, p1, p1) for i, j in pairs}
    PBv = {(i, j): harv(i, j, p1, p3) for i, j in pairs}
    zb = sum(PBv.values()); PBv = {kk: v / zb for kk, v in PBv.items()}      # 合計1にそろえる
    hit = {(i, j): {nums[i], nums[j]} == top2 for i, j in pairs}
    pay = {(i, j): PAY[k].get(tuple(sorted((nums[i], nums[j]))), 0.0) for i, j in pairs}
    rec = dict(zip(KEY, k)); rec.update(年=int(g['年'].iloc[0]), 日=g['日'].iloc[0])
    for lab, P in (('A', PA), ('B', PBv)):
        order = sorted(P, key=P.get, reverse=True)
        for m in (1, 3, 5):
            rec[f'{lab}上位{m}組の的中'] = any(hit[o] for o in order[:m]); rec[f'{lab}上位{m}組の払戻'] = sum(pay[o] for o in order[:m])
        rec[f'{lab}1組目の見込み'] = P[order[0]]
        # 軸：連対の見込み（その馬を含む組の見込みの合計）が一番の馬から、相手3頭（その馬との組の見込みの上位3つ）
        ren = np.zeros(n)
        for (i, j), v in P.items(): ren[i] += v; ren[j] += v
        ax = int(np.argmax(ren)); partners = sorted([o for o in P if ax in o], key=P.get, reverse=True)[:3]
        rec[f'{lab}軸流し3点の的中'] = any(hit[o] for o in partners); rec[f'{lab}軸流し3点の払戻'] = sum(pay[o] for o in partners)
        rec[f'{lab}軸が連対'] = nums[ax] in top2
        if lab == 'B':
            for o in order[:10]: cal.append((rec['年'], P[o], hit[o]))
    # 人気
    r_ = np.argsort(pop)
    f1, f2, f3, f4 = r_[0], r_[1], r_[2], r_[3] if n > 3 else r_[2]
    pp = lambda i, j: tuple(sorted((i, j)))
    rec['人気1点の的中'] = hit[pp(f1, f2)]; rec['人気1点の払戻'] = pay[pp(f1, f2)]
    box = [pp(f1, f2), pp(f1, f3), pp(f2, f3)]; rec['人気BOX3点の的中'] = any(hit[o] for o in box); rec['人気BOX3点の払戻'] = sum(pay[o] for o in box)
    fl = [pp(f1, f2), pp(f1, f3), pp(f1, f4)]; rec['人気流し3点の的中'] = any(hit[o] for o in fl); rec['人気流し3点の払戻'] = sum(pay[o] for o in fl)
    rec['人気軸が連対'] = nums[f1] in top2
    rows.append(rec)
R = pd.DataFrame(rows); R.to_pickle('/tmp/chiho_pair2.pkl')
CA = pd.DataFrame(cal, columns=['年', '見込み', '的中'])
pd.set_option('display.width', 250)
for per, m in (('2021〜2023年（選ぶ期間）', R['年'] <= 2023), ('2024〜2025年（確かめ）', R['年'].between(2024, 2025)), ('2026年1〜9月（確かめ）', R['年'] == 2026)):
    X = R[m]; out = []
    for lab, pts in (('A上位1組', 1), ('B上位1組', 1), ('人気1点', 1), ('A上位3組', 3), ('B上位3組', 3), ('人気BOX3点', 3), ('A軸流し3点', 3), ('B軸流し3点', 3), ('人気流し3点', 3), ('A上位5組', 5), ('B上位5組', 5)):
        key = lab.replace('組', '組') ; hk = f'{lab}の的中'; pk = f'{lab}の払戻'
        out.append(dict(買い方=lab, 点=pts, 的中=f"{X[hk].mean()*100:.1f}%", 回収=f"{X[pk].sum()/(pts*len(X))*100:.1f}%"))
    print(f'\n■ {per}　{len(X)}レース'); print(pd.DataFrame(out).to_string(index=False))
    print(f"  軸が1・2着に来た率：A {X['A軸が連対'].mean()*100:.1f}%  B {X['B軸が連対'].mean()*100:.1f}%  人気（1番人気） {X['人気軸が連対'].mean()*100:.1f}%")
print('\n■ 組の見込みと実際（B、各レースの上位10組、2021〜2025年）')
A = CA[CA['年'] <= 2025]
print(A.groupby(pd.cut(A['見込み'], [0, .02, .05, .1, .15, .2, .3, .4, 1]), observed=True).agg(組=('的中', 'size'), 見込み=('見込み', lambda s: round(s.mean() * 100, 1)), 実際=('的中', lambda s: round(s.mean() * 100, 1))).to_string())
