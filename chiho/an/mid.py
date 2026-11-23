"""地方の昼の見直し（検証計画 EM1）：朝の一覧に、当日の馬体重（E1）と、その日の前のレースの結果から出す内の有利さ（E2）を足して、まだ走っていないレースの見込みを直す。
使い方：python chiho/an/mid.py STORE 日付 [出力の置き場（既定 data/picks）]
材料：STORE/data/picks/日付.json（朝の一覧）、STORE/data/daily/日付/race_horselist.csv.gz（30分ごとに取り直している当日の出馬表。馬体重・着順）。
出力：日付_mid.json（朝の一覧と同じ形。直したレースには「昼の見直し」の印と、直す前の数字を残す）。
前の有利さ（E2 の前）は、朝の一覧に先行率5 が入るまで使わない（θ を 0 にする）。"""
import json, os, sys, datetime as dt
from itertools import combinations
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'jra'))
import jk_wide
JST = dt.timezone(dt.timedelta(hours=9))
store, day = sys.argv[1], sys.argv[2]; outdir = sys.argv[3] if len(sys.argv) > 3 else 'data/picks'
FX = json.load(open(f'{HERE}/nar_fix.json', encoding='utf-8')); TH = FX['昼の見直し']['θ']
RC = json.load(open(f'{HERE}/rentai_calib.json', encoding='utf-8')); PC = json.load(open(f'{HERE}/pair_calib.json', encoding='utf-8'))
WC = json.load(open(f'{HERE}/wide_calib.json', encoding='utf-8')) if os.path.exists(f'{HERE}/wide_calib.json') else None
O = json.load(open(f'{store}/data/picks/{day}.json', encoding='utf-8'))
HL = pd.read_csv(f'{store}/data/daily/{day}/race_horselist.csv.gz', dtype=str)
HL['R'] = pd.to_numeric(HL['レース番号'], errors='coerce'); HL['u'] = pd.to_numeric(HL['馬番'], errors='coerce')
HL['着'] = pd.to_numeric(HL['着順'], errors='coerce'); HL['体重'] = pd.to_numeric(HL['馬体重'], errors='coerce')
HL['増減'] = pd.to_numeric(HL['馬体重増減'].astype(str).str.replace('+', '', regex=False), errors='coerce')
now = dt.datetime.now(JST)
def band(w, z):
    if pd.isna(w): return None                     # 馬体重がまだ出ていない
    if pd.isna(z): return 'e_none'
    return 'e_m10' if z <= -10 else ('e_m4' if z <= -4 else ('e_p4' if 4 <= z <= 9 else ('e_p10' if z >= 10 else None)))
# その日の場ごとに、終わったレースの「実際の3着内−朝の3着内の見込み」から内の有利さを作る（11/17 の決め方）
done, inadv = {}, {}
for pl in sorted({r['場'] for r in O['レース']}):
    rs = sorted([r for r in O['レース'] if r['場'] == pl], key=lambda r: r['R']); acc = []; m = 0
    for r in rs:
        inadv[(pl, r['R'])] = (np.mean(acc) * m / (m + 3)) if acc else 0.0
        X = HL[(HL['競馬場'] == pl) & (HL['R'] == r['R'])]
        fin = X.dropna(subset=['着'])
        if len(fin) >= 3 and (fin['着'] <= 3).sum() >= 3:      # 結果が出たレース
            done[(pl, r['R'])] = True; n = len(r['馬']); top = set(fin.loc[fin['着'] <= 3, 'u'].astype(int))
            res = {h['馬番']: (1.0 if h['馬番'] in top else 0.0) - h['三着内'] / 100 for h in r['馬']}
            inn = [v for u, v in res.items() if u <= n / 3]; out = [v for u, v in res.items() if u > n * 2 / 3]
            if inn and out: acc.append(np.mean(inn) - np.mean(out)); m += 1
nchg = 0; log = []
for r in O['レース']:
    k = (r['場'], r['R'])
    if done.get(k): r['昼の見直し'] = '済（終わったレース）'; continue
    X = HL[(HL['競馬場'] == r['場']) & (HL['R'] == r['R'])].set_index('u')
    hs = r['馬']; n = len(hs); ia = inadv.get(k, 0.0)
    x = []
    for h in hs:
        b = band(X['体重'].get(h['馬番'], np.nan), X['増減'].get(h['馬番'], np.nan)) if h['馬番'] in X.index else None
        h['体重増減'] = (None if h['馬番'] not in X.index or pd.isna(X['増減'].get(h['馬番'])) else int(X['増減'].get(h['馬番'])))
        s = (TH.get(b, 0.0) if b else 0.0) + TH['x_in'] * ia * (1.0 if h['馬番'] <= n / 3 else 0.0)
        x.append(s)
    x = np.array(x)
    if not np.any(x != 0): r['昼の見直し'] = '変わらず（馬体重がまだで、内の有利さも0）'; continue
    p1 = np.array([h['p1'] for h in hs]); p1n = p1 * np.exp(x); p1n = p1n / p1n.sum()
    p3 = np.clip(np.array([h['三着内'] for h in hs]) / 100, 1e-4, 0.97); lo = np.log(p3 / (1 - p3)) + x; q = 1 / (1 + np.exp(-lo)); q = np.clip(q * min(3, n) / q.sum(), 1e-4, 0.97)
    rr = p1n / np.clip(1 - p1n, 1e-9, None); p2 = np.clip(p1n + p1n * (rr.sum() - rr), 1e-4, 0.999); p2 = np.interp(p2, RC['見込み'], RC['直した見込み'])
    for i, h in enumerate(hs):
        h['朝の一着'], h['朝の三着内'] = h['一着'], h['三着内']
        h['p1'] = round(float(p1n[i]), 5); h['一着'] = round(float(p1n[i]) * 100); h['三着内'] = round(float(q[i]) * 100); h['連対'] = round(float(p2[i]) * 100)
        h['指数'] = int(round(min(100.0, max(0.0, 50 + 10 / np.log(2) * np.log(max(float(p1n[i]), 1e-4) * n)))))
    order = np.argsort(-q, kind='stable')
    for rk, i in enumerate(order, start=1): hs[i]['順位'] = rk
    r['馬'] = [hs[i] for i in order]
    nums = np.array([h['馬番'] for h in r['馬']]); a1 = np.array([h['p1'] for h in r['馬']]); a1 = a1 / a1.sum(); a3 = np.array([h['三着内'] for h in r['馬']], float); a3 = a3 / a3.sum()
    P = {(i, j): a1[i] * a3[j] / (1 - a3[i]) + a1[j] * a3[i] / (1 - a3[j]) for i, j in combinations(range(n), 2)}; z = sum(P.values())
    r['馬連'] = [dict(組='-'.join(str(v) for v in sorted((nums[i], nums[j]))), 見込み=round(float(np.interp(P[(i, j)] / z, PC['見込み'], PC['直した見込み'])) * 100)) for i, j in sorted(P, key=P.get, reverse=True)[:3]]
    if WC: r['ワイド'] = [dict(組=a, 見込み=round(b * 100)) for a, b in jk_wide.top_wide(nums.astype(int), a1, WC)]
    nb = sum(1 for h in r['馬'] if h.get('体重増減') is not None)
    r['昼の見直し'] = f"直した（馬体重 {nb}/{n}頭・内の有利さ {ia:+.3f}）"; nchg += 1
    log.append(f"{r['場']}{r['R']}R 馬体重 {nb}/{n}頭 内の有利さ {ia:+.3f}")
O['昼の見直し'] = {'時刻': now.strftime('%Y-%m-%d %H:%M'), '直したレース': nchg, '終わったレース': sum(1 for v in done.values() if v), 'θ': TH}
os.makedirs(f'{store}/{outdir}', exist_ok=True)
json.dump(O, open(f'{store}/{outdir}/{day}_mid.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('昼の見直し', now.strftime('%H:%M'), '直したレース', nchg, '終わったレース', sum(1 for v in done.values() if v)); print('\n'.join(log))
