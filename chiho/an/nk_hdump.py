"""地方の過去の表（5場）を、分析のために書き出す（2026-11-23 に手元の H_nar.pkl が消えたので作り直す）。pipe.py の頭（今日の出馬表まで）を動かして、H の一部の列を年ごとに保存する。
使い方：python chiho/an/nk_hdump.py STORE 日付（その日の出馬表が data/daily にある日）。出力：STORE/data/exp/nk_hdump_年.csv.gz"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
store, day = sys.argv[1], sys.argv[2]
os.environ['CHIHO_EV'] = '1'
src = open(f'{HERE}/pipe.py', encoding='utf-8').read(); head = src[:src.index("Y = int(today[:4])")]
g = {'__name__': 'pipe_head', '__file__': f'{HERE}/pipe.py'}; sys.argv = ['pipe.py', store, day]
exec(compile(head, f'{HERE}/pipe.py', 'exec'), g)
H = g['H']; H = H[~H['予測'] & (H['年'] >= 2021)]
COLS = ['競馬場', '競走年月日', 'レース番号', '馬番', '枠番', '馬名', '年', 'n', '人気', '着', '勝', '3着内', '馬場', '天候', '距離', '先頭', '先行', '先頭率5', '先行率5', '逃げ型', '他の逃げ型', '先頭率5順', '初角', '初角率']
C = [c for c in COLS if c in H.columns]; print('書き出す列', C, '／無い列', [c for c in COLS if c not in H.columns], flush=True)
os.makedirs(f'{store}/data/exp', exist_ok=True)
for y, X in H[C].groupby('年'):
    X.to_csv(f'{store}/data/exp/nk_hdump_{int(y)}.csv.gz', index=False); print(y, len(X), flush=True)
