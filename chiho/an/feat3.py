"""B3の材料の表：B2の材料（/tmp/chiho_feat2.pkl）の、前の成績の列を、全部の場で作り直したもの（/tmp/chiho_hist_all.pkl）に入れ替える。
レースの中の順位（過去3差・タイムの指数）も作り直す。前走の場・前走が5場の外・5走前までの5場の外の数を足す。→ /tmp/chiho_feat3.pkl"""
import numpy as np, pandas as pd
KEY = ['競馬場', '競走年月日', 'レース番号']
EXTRA3 = ['前場c', '前走外', '外走5']

def apply3(H, A):
    """H（B2の材料の表）の前の成績の列を、A（hist_all.build_hist の表）に入れ替え、レースの中の順位を作り直す。"""
    H = H.copy(); A = A.drop(columns=[c for c in ('予測',) if c in A])
    H['馬番'] = H['馬番'].astype(float); A = A.copy(); A['馬番'] = A['馬番'].astype(float)
    cols = [c for c in A.columns if c not in KEY + ['馬番']]
    H = H.drop(columns=[c for c in cols if c in H]).merge(A, on=KEY + ['馬番'], how='left')
    H['過去3差順率'] = H.groupby(KEY)['過去3差'].rank(ascending=True, method='min') / H['n']
    H['指数最高3順率'] = H.groupby(KEY)['指数最高3'].rank(ascending=False, method='min') / H['n']
    H['指数最高3差'] = H.groupby(KEY)['指数最高3'].transform('max') - H['指数最高3']
    H['指数1順率'] = H.groupby(KEY)['指数1'].rank(ascending=False, method='min') / H['n']
    return H


if __name__ == '__main__':
    H = pd.read_pickle('/tmp/chiho_feat2.pkl'); A = pd.read_pickle('/tmp/chiho_hist_all.pkl')
    H['馬番'] = H['馬番'].astype(float); A['馬番'] = A['馬番'].astype(float)
    old = H[KEY + ['馬番', '着x1', '差1', '指数1', '走数', '過去3差']].copy(); old['馬番'] = old['馬番'].astype(float)
    H = apply3(H, A)
    H.to_pickle('/tmp/chiho_feat3.pkl')
    # 確かめ：5場の外を走っていない馬は、B2と同じ値になるはず
    M = old.merge(H[KEY + ['馬番', '着x1', '差1', '指数1', '走数', '過去3差', '外走5', '前走外', '外の走数', '初データ']], on=KEY + ['馬番'], suffixes=('_B2', ''))
    same = M[(M['外走5'] == 0) & (M['走数'] == M['走数_B2'])]
    for c in ['着x1', '差1', '指数1', '過去3差']:
        print(c, '同じ割合', round(np.isclose(same[c].astype(float), same[c + '_B2'].astype(float), equal_nan=True).mean(), 4), '（', len(same), '行）')
    A21 = H[H['年'] >= 2021]; O21 = old[old['競走年月日'] >= '20210101']
    print('2021年以降：5場で初めて（B2）', round((O21['走数'] == 0).mean(), 3), '／全部の場でも初めて', round((A21['初データ'] == 1).mean(), 3),
          '／前走が5場の外', round(A21['前走外'].mean(), 3))
