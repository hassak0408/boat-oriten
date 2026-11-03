"""中央競馬：K2 前走に不利があった馬は舐められているか（検証計画「中央：正しい評価で舐められている馬を探す」）。
前走で ①被害 ②発走の不利 ③疾病 があった馬の、実際の1着÷市場の見込みと単勝の回収。前走6着以下にも分ける。選ぶ期間2016〜2021年、確かめる期間2022〜2026年。
使い方：python jtrouble.py 材料.pkl"""
import sys, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1]); H = H[~H['予測'] & (H['合わない'] == 0)].copy()
H = H[(H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H['q'] = 1 / H['単勝オッズ']; H['q'] = H['q'] / H.groupby(KEY)['q'].transform('sum')
H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)
print('K1 不利の印（そのレース）：', {c: int(H['不利' + c].sum()) for c in ('被害', '発走', '疾病', '加害')}, '／前走に不利あり', int((H['前不利あり'] == 1).sum()), '頭')
bad = H['着x1'] >= 6
seg = {
    '前走で被害（斜行などをされた）': H['前不利被害'] == 1,
    '前走で発走の不利（出遅れ・立上るなど）': H['前不利発走'] == 1,
    '前走で疾病（鼻出血など）': H['前不利疾病'] == 1,
    '前走で斜行した（加害）': H['前不利加害'] == 1,
    '前走で不利あり（①〜③のどれか）': H['前不利あり'] == 1,
    '前走で不利あり・6着以下': (H['前不利あり'] == 1) & bad,
    '前走で不利あり・5着以内': (H['前不利あり'] == 1) & ~bad & H['着x1'].notna(),
    '（くらべる）前走6着以下で不利なし': (H['前不利あり'] == 0) & bad,
    '（くらべる）全部': pd.Series(True, index=H.index),
}


def boot(v, day, B=2000, ratio=None):
    x = pd.DataFrame({'d': day, 's': v} | ({'q': ratio} if ratio is not None else {})).groupby('d').sum()
    rng = np.random.default_rng(0); k = rng.integers(0, len(x), (B, len(x)))
    if ratio is not None: s = x['s'].values[k].sum(1) / x['q'].values[k].sum(1)
    else:
        n = pd.DataFrame({'d': day}).groupby('d').size().reindex(x.index).values
        s = x['s'].values[k].sum(1) / n[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


rows = []
for name, m in seg.items():
    for lab, pm in (('2016〜2021', H['年'] <= 2021), ('2022〜2026', H['年'] >= 2022)):
        X = H[m.fillna(False).astype(bool) & pm]
        if len(X) < 50: continue
        lo, hi = boot(X['払'].values, X['年月日'].values); rl, rh = boot(X['勝'].values, X['年月日'].values, ratio=X['q'].values)
        by = X.groupby('年')['払'].mean() * 100
        rows.append({'印': name, '期間': lab, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '人気の平均': round(X['人気'].mean(), 1),
                     '実際÷市場': f"{X['勝'].sum()/X['q'].sum():.3f}（{rl:.2f}〜{rh:.2f}）", '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo:.0f}〜{hi:.0f}）",
                     '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(pd.DataFrame(rows).to_string(index=False))
