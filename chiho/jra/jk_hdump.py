"""中央の過去の表を、分析のために書き出す（2026-11-23 に手元の H_jra.pkl が消えたので作り直す）。jpipe.py の頭（過去の表を作るまで）を動かして、H の一部の列を年ごとに保存する。
使い方：python chiho/jra/jk_hdump.py STORE 日付（その日の出馬表が jra/card にある日）。出力：STORE/jra/exp/hdump_年.csv.gz"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
store, day = sys.argv[1], sys.argv[2]
src = open(f'{HERE}/jpipe.py', encoding='utf-8').read(); head = src[:src.index("FE = [c for c in FEATS")]
g = {'__name__': 'jpipe_head', '__file__': f'{HERE}/jpipe.py'}; sys.argv = ['jpipe.py', store, day]
exec(compile(head, f'{HERE}/jpipe.py', 'exec'), g)
H = g['H']; H = H[~H['予測'] & (H['年'] >= 2021)]
COLS = ['年月日', '場', 'R', '馬番', '枠', '馬名', '馬', '年', 'n', '人気', '単勝オッズ', '着', '勝', '3着内', '馬場', '天候', '芝ダ', '距離', '格', '新馬', '先頭', '初角', '初角率', '先頭率5', '先行率5', 'ペース比', '不利発走', '発走不利5', '前走数']
C = [c for c in COLS if c in H.columns]; print('書き出す列', C, '／無い列', [c for c in COLS if c not in H.columns], flush=True)
os.makedirs(f'{store}/jra/exp', exist_ok=True)
for y, X in H[C].groupby('年'):
    X.to_csv(f'{store}/jra/exp/hdump_{int(y)}.csv.gz', index=False); print(y, len(X), flush=True)
