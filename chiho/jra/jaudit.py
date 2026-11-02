"""中央競馬：馬の評価は正当か（検証計画の同じ名前の節）。② 何で評価しているか（材料の組ごとの入れ替え）、③ かたよりが無いか（印ごとの実際÷見込み）、
あわせて朝の条件（馬場・天候が分からない）での当て分け。
使い方：python jaudit.py 材料.pkl 見込み.pkl（jeval.py の出力）"""
import sys, time, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from jfeat import FEATS, CATF, KEY, EXTRA, PACE

t0 = time.time()
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
FE = [c for c in FEATS + EXTRA + PACE if c in H and H[c].notna().any()]
GROUPS = {
    '前の走り（着順・着差・タイムの指数・ペース）': ['着x1', '着率1', '差1', '指数1', '着x2', '差2', '指数2', '着x3', '差3', '指数3', '着x4', '着x5', '過去3差', '過去3着率',
                                       '最小差5', '最良着2_5', '指数最高3', '指数平均3', '指数最高5', '指数最高3差', '過去3差順率', '指数最高3順率', '指数1順率',
                                       '同指数1', '同指数最高3', '同着率3', '前ペース比', '前上り差'],
    '馬の成績・経験（走数・勝率・賞金・年齢）': ['走数', '全走', '全勝率', '全3率', '芝ダ走', '芝ダ3率', '当場走', '当場3率', '当距走', '当距3率', '獲得計', '獲得計順率',
                                      '全3率順率', '叩き戦目', '齢', '性c', '前馬体重', '前ブリンカー'],
    '前走からの変化（間隔・距離・クラス・乗り替わり）': ['間隔', '距離差', '賞金比', '場変更', '芝ダ変更', '乗替', '斤量差', 'クラス差', '前クラス', '前格'],
    '前走の人気（前のレースの市場の評価）': ['前人気', '前人気率', '前人気着差'],
    '騎手': ['騎数', '騎勝率', '騎3率', '騎単回', '騎場3率', '騎勝率順率', '減量', '騎初数', '騎初勝率', '騎初3率', '騎30勝率', '騎303率'],
    '厩舎（調教師）': ['調数', '調勝率', '調3率', '調単回', '調勝率順率', '調初数', '調初勝率', '調初3率', '調30勝率', '調303率'],
    '馬主・生産者': ['主数', '主勝率', '主3率', '牧数', '牧勝率', '牧3率', '主勝率順率', '牧勝率順率', '主初数', '主初勝率', '主初3率', '牧初数', '牧初勝率', '牧初3率'],
    '脚質（前に行くか）': ['先頭率5', '先行率5', '終角率1', '上げ1', '上げ3', '他の逃げ型', '先頭率5順', '過去3角順', '過去3角', '初角率1'],
    'レースの条件（場・距離・枠・斤量・頭数など）': ['場c', '芝ダc', '馬場c', '天候c', '月', '時', '距離', 'n', '賞金', 'クラス', '新馬', '牝限', 'ハンデ', '年齢c',
                                         '枠', '馬番', '馬番率', '斤量', '斤量差レース'],
}
left = [c for c in FE if not any(c in g for g in GROUPS.values())]
print('組に入っていない材料：', left)
cat = [FE.index(c) for c in CATF if c in FE]
BIG = dict(max_leaf_nodes=63, min_samples_leaf=200, learning_rate=0.05, max_iter=2000, l2_regularization=1.0, n_iter_no_change=30)
tr = H[(H['年'] >= 2017) & (H['年'] <= 2023)]; te = H[(H['年'] >= 2024) & (H['n'] >= 5)].copy()
te = te[te.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())]
m = HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, random_state=0, categorical_features=cat, **BIG).fit(tr[FE], tr['勝'])
print('学習', len(tr), '回数', m.n_iter_, round(time.time() - t0), '秒', flush=True)
gk = [te[k].values for k in KEY]


def race_loss(p):
    s = pd.Series(p, index=te.index); s = s / s.groupby(gk).transform('sum')
    return float(-np.log(s[te['勝'] == 1].clip(1e-6)).mean())


X0 = te[FE].copy(); base = race_loss(m.predict_proba(X0)[:, 1])
q = 1 / te['単勝オッズ']; mk = race_loss(q.values)
print(f'2024〜2026年 1着の当て分け：モデル {base:.4f}／市場 {mk:.4f}／何も分からない（頭数で割るだけ）{race_loss(np.ones(len(te))):.4f}')
rng = np.random.default_rng(0); rows = []
for name, cols in GROUPS.items():
    cols = [c for c in cols if c in FE]; inc = []
    for rep in range(3):
        X = X0.copy(); idx = rng.permutation(len(X)); X[cols] = X0[cols].values[idx]
        inc.append(race_loss(m.predict_proba(X)[:, 1]) - base)
    rows.append({'材料の組': name, '列': len(cols), '入れ替えたときの悪くなり方': round(float(np.mean(inc)), 4)})
    print(name, round(float(np.mean(inc)), 4), round(time.time() - t0), '秒', flush=True)
R = pd.DataFrame(rows); R['割合'] = (R['入れ替えたときの悪くなり方'] / R['入れ替えたときの悪くなり方'].clip(lower=0).sum() * 100).round(1)
pd.set_option('display.width', 220)
print('\n■ ② 何で評価しているか（2024〜2026年、組ごとに値を入れ替えたとき1着の当て分けが悪くなる大きさ）'); print(R.sort_values('入れ替えたときの悪くなり方', ascending=False).to_string(index=False))
# 朝の条件：馬場・天候が分からない（良・晴とする）
X = X0.copy()
if '馬場c' in X: X['馬場c'] = 0.0
if '天候c' in X: X['天候c'] = 0.0
print(f'\n■ 朝の条件（馬場を良・天候を晴にする）での1着の当て分け：{race_loss(m.predict_proba(X)[:, 1]):.4f}（本当の馬場・天候 {base:.4f}）')

# ③ かたより：印ごとの実際÷見込み（jeval の見込み、各年はその前の年まで）
D = pd.read_pickle(sys.argv[2]); D = D.loc[:, ~D.columns.duplicated()]
D = D.drop(columns=[c for c in D.columns if c not in KEY + ['馬番', 'p1', 'p3']]).merge(H, on=KEY + ['馬番'], how='inner')
D = D[(D['n'] >= 5) & D.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
D['p1'] = D['p1'] / D.groupby(KEY)['p1'].transform('sum')
D['p3'] = D['p3'] * np.minimum(3, D['n']) / D.groupby(KEY)['p3'].transform('sum')
D['q'] = 1 / D['単勝オッズ']; D['q'] = D['q'] / D.groupby(KEY)['q'].transform('sum')
wins = H.groupby(['年', '騎手'])['勝'].sum().reset_index(); topj = {y + 1: set(g.nlargest(10, '勝')['騎手']) for y, g in wins.groupby('年')}
wt = H.groupby(['年', '調教師'])['勝'].sum().reset_index(); topt = {y + 1: set(g.nlargest(20, '勝')['調教師']) for y, g in wt.groupby('年')}
D['上位騎手'] = [j in topj.get(y, set()) for y, j in zip(D['年'], D['騎手'])]
D['上位厩舎'] = [j in topt.get(y, set()) for y, j in zip(D['年'], D['調教師'])]
pop = pd.cut(D['人気'], [0, 1, 3, 6, 9, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7〜9番人気', '10番人気以下'])
seg = {}
for v in pop.cat.categories: seg[f'人気：{v}'] = pop == v
seg['新馬'] = D['新馬'] == 1
for lab, a, b in (('前の走数0（新馬以外）', 0, 0), ('前の走数1', 1, 1), ('前の走数2〜4', 2, 4), ('前の走数5以上', 5, 999)):
    seg[lab] = D['走数'].between(a, b) & ((D['新馬'] == 0) if a == 0 else True)
for c, lab in ((0, '新馬戦'), (1, '未勝利'), (2, '1勝'), (3, '2勝'), (4, '3勝')): seg[f'クラス：{lab}'] = D['クラス'] == c
seg['クラス：オープン・重賞'] = D['クラス'] >= 5
seg['芝'] = D['芝ダ'] == '芝'; seg['ダート'] = D['芝ダ'] == 'ダート'
seg['上位騎手'] = D['上位騎手']; seg['上位騎手でない'] = ~D['上位騎手']
seg['上位厩舎'] = D['上位厩舎']; seg['ノーザンファーム生産'] = D['生産'].astype(str).str.contains('ノーザンファーム')
seg['90日以上の休み明け'] = D['間隔'] >= 90; seg['距離200m以上の変更'] = D['距離差'].abs() >= 200
seg['外枠（7・8枠）'] = D['枠'] >= 7; seg['牝馬'] = D['性'] == '牝'
for a in (2, 3, 4): seg[f'{a}歳'] = D['齢'] == a
seg['5歳以上'] = D['齢'] >= 5
rows = []
for lab, per in (('2021〜2023', D['年'] <= 2023), ('2024〜2026', D['年'] >= 2024)):
    for name, mm in seg.items():
        X = D[mm.fillna(False).astype(bool) & per]
        if len(X) < 300: continue
        rows.append({'期間': lab, '印': name, '頭': len(X), '1着 実際÷モデル': round(X['勝'].sum() / X['p1'].sum(), 3), '1着 実際÷市場': round(X['勝'].sum() / X['q'].sum(), 3),
                     '3着内 実際÷モデル': round(X['3着内'].sum() / X['p3'].sum(), 3)})
S = pd.DataFrame(rows)
W = S.pivot_table(index='印', columns='期間', values=['1着 実際÷モデル', '3着内 実際÷モデル', '1着 実際÷市場'], aggfunc='first')
W = W.reindex([k for k in seg if k in W.index])
print('\n■ ③ 印ごとの「実際÷見込み」（1に近いほど、かたよりが無い）'); print(W.to_string())
print(round(time.time() - t0), '秒')
