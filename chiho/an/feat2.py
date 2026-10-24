"""市場より劣る所を直す材料（検証計画「市場より劣る所の洗い出しと改善」）。/tmp/chiho_feat.pkl に足して /tmp/chiho_feat2.pkl に置く。
1) クラス：レース名からA1〜C6と組を読む。前走とのクラスの差（昇級・降級）。新馬・交流・重賞など。
2) 全成績の中身：連対率、ダートの走数、芝の走数（中央から来た馬の目印）。
3) 初めての馬の目印：このデータで初めて、5場の外での走数、前走（このデータ）とのあいだに外で走ったか。
4) タイムの指数：場・距離・馬場ごとの基準タイムと、その日の馬場の速さで直した速さ（1000mあたりの秒）。前走・過去3走の最高と平均・過去5走の最高。
5) 父・母父・馬主・生産牧場の成績、調教師の「このデータで初めての馬」の成績（どれも前の日まで）。"""
import re, unicodedata, numpy as np, pandas as pd
from load import _read
from feat import FEATS, rec4
KEY = ['競馬場', '競走年月日', 'レース番号']
KAN = {c: i + 1 for i, c in enumerate('一二三四五六七八九十')}


def cls(name):
    s = unicodedata.normalize('NFKC', str(name))
    ks = re.findall(r'([ABC])\s*(\d?)\s*級?\s*([一二三四五六七八九十]?)', s)
    ks = [k for k in ks if k[1] or k[2]]
    if ks:
        v = [{'A': 0, 'B': 10, 'C': 20}[a] + int(b or 1) + (KAN.get(c, 0) / 10) for a, b, c in ks]
        return float(np.mean(v))
    m = re.search(r'歳\s*(\d+)\s*(組|特選|特別)', s)
    if m: return 30 + int(m.group(1))            # 2歳・3歳の組分け（別の物差し）
    if 'オープン' in s: return -1.0
    return np.nan


def add2(H, R):
    """H（feat.build の表）と R（レース一覧）から、足す材料を作って返す。"""
    R = R.drop_duplicates(KEY).copy()
    # 1) クラス
    R['クラス'] = R['レース名'].map(cls)
    nm = R['レース名'].map(lambda s: unicodedata.normalize('NFKC', str(s)))
    R['新馬'] = nm.str.contains('新馬').astype(float); R['交流'] = nm.str.contains('交流').astype(float)
    R['格'] = R['競走種類名称'].map({'普通': 0, '特別': 1, '準重賞': 2, '重賞': 3})
    H = H.drop(columns=[c for c in ('クラス', '新馬', '交流', '格') if c in H]).merge(R[KEY + ['クラス', '新馬', '交流', '格']], on=KEY, how='left')
    H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
    g = H.groupby('馬', sort=False)
    H['前クラス'] = g['クラス'].shift(1); H['クラス差'] = H['クラス'] - H['前クラス']      # プラス＝下のクラスへ（降級）
    H['前格'] = g['格'].shift(1)

    # 2) 全成績の中身
    a, b, c, d = rec4(H['全成績']); n = a + b + c + d
    H['全連対率'] = (a + b) / n.where(n > 0)
    la, lb, lc, ld = rec4(H['ダート左成績']); ra, rb, rc, rd = rec4(H['ダート右成績'])
    H['ダ走'] = la + lb + lc + ld + ra + rb + rc + rd
    H['芝走'] = (n - H['ダ走']).clip(lower=0); H['芝率'] = H['芝走'] / n.where(n > 0)
    H['ダ3率'] = (la + lb + lc + ra + rb + rc) / H['ダ走'].where(H['ダ走'] > 0)

    # 3) 初めての馬の目印
    H['初データ'] = (H['走数'] == 0).astype(float); H['初出走'] = (H['全走'] == 0).astype(float)
    H['外の走数'] = H['全走'] - H['走数']
    H['前の全走'] = g['全走'].shift(1)
    H['外を挟む'] = np.where(H['前の全走'].isna(), np.nan, (H['全走'] - H['前の全走'] - 1).clip(lower=0))

    # 4) タイムの指数（基準は2016〜2019年の勝ち馬のタイムの中央値。その日の速さは、その日のその場の勝ち馬のずれの中央値）
    W1 = H[(H['着'] == 1) & H['sec'].notna()]
    s1 = W1[W1['年'] <= 2019].groupby(['競馬場', '距離', '馬場'])['sec'].median()
    s2 = W1[W1['年'] <= 2019].groupby(['競馬場', '距離'])['sec'].median()
    H['基準'] = [s1.get((p, q, r), s2.get((p, q), np.nan)) for p, q, r in zip(H['競馬場'], H['距離'], H['馬場'])]
    W1 = H[(H['着'] == 1) & H['sec'].notna()].copy(); W1['ずれ'] = (W1['sec'] - W1['基準']) / W1['距離'] * 1000
    var = W1.groupby(['競馬場', '日'])['ずれ'].median().rename('当日の速さ').reset_index()
    H = H.drop(columns=[c for c in ('当日の速さ',) if c in H]).merge(var, on=['競馬場', '日'], how='left')
    H['指数'] = (H['基準'] - H['sec']) / H['距離'] * 1000 + H['当日の速さ']
    H.loc[H['中止'] == True, '指数'] = np.nan
    H = H.sort_values(['馬', '日', 'レース番号']).reset_index(drop=True)
    g = H.groupby('馬', sort=False)
    H['指数1'] = g['指数'].shift(1)
    H['指数最高3'] = g['指数'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).max())
    H['指数平均3'] = g['指数'].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    H['指数最高5'] = g['指数'].transform(lambda s: s.shift(1).rolling(5, min_periods=1).max())
    H['指数最高3順率'] = H.groupby(KEY)['指数最高3'].rank(ascending=False, method='min') / H['n']
    H['指数最高3差'] = H.groupby(KEY)['指数最高3'].transform('max') - H['指数最高3']
    H['指数1順率'] = H.groupby(KEY)['指数1'].rank(ascending=False, method='min') / H['n']


    # 5) 父・母父・馬主・生産牧場・調教師（初めての馬）の成績（前の日まで、全部の期間）
    def prior(ent, mask=None, pre=None):
        X = H[[ent, '日', '勝', '3着内']].copy()
        if mask is not None: X = X[mask]
        X['_n'] = 1
        day = X.groupby([ent, '日'])[['_n', '勝', '3着内']].sum().reset_index().sort_values([ent, '日'])
        day[['c_n', 'c_w', 'c_3']] = day.groupby(ent)[['_n', '勝', '3着内']].cumsum().values
        Q = H[[ent, '日']].reset_index().sort_values('日')
        M = pd.merge_asof(Q, day[[ent, '日', 'c_n', 'c_w', 'c_3']].sort_values('日'), on='日', by=ent,
                          allow_exact_matches=False).set_index('index').sort_index()     # 前の日まで
        cn, cw, c3 = M['c_n'].fillna(0), M['c_w'].fillna(0), M['c_3'].fillna(0)
        k = 20; m1 = H['勝'].mean(); m3 = H['3着内'].mean()
        H[pre + '数'] = cn.values
        H[pre + '勝率'] = ((cw + k * m1) / (cn + k)).values
        H[pre + '3率'] = ((c3 + k * m3) / (cn + k)).values


    H = H.sort_values(['日'] + KEY).reset_index(drop=True)
    for ent, pre in (('父馬名', '父'), ('母父馬名', '母父'), ('馬主氏名', '主'), ('生産牧場名', '牧')):
        prior(ent, pre=pre)
    prior('調教師', mask=H['走数'] == 0, pre='調初')
    # 調初の数・率は「その調教師が前の日までに、このデータで初めての馬を出した成績」。初めての馬でない行にも同じ値が入る。
    return H


from feat2cols import NEW
FEATS2 = FEATS + NEW

if __name__ == '__main__':
    H = add2(pd.read_pickle('/tmp/chiho_feat.pkl'), _read('race', 'racelist'))
    H.to_pickle('/tmp/chiho_feat2.pkl')
    A = H[H['年'] >= 2021]
    print(A[NEW].describe().T[['count', 'mean', 'min', 'max']].round(3).to_string())
