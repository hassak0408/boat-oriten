"""中央競馬：不利明けの馬の前向きの記録（検証計画「F3：不利明けの馬の評価の直し・前向きの確かめ」）。
不利明け＝前走で発走の不利（出遅れ・立上るなど）か、競走中の疾病があった馬。2026年11月7日からの中央の平地のレースで、
その馬の単勝と、1番人気との馬連1点（不利明けが1番人気なら2番人気と）を、買ったとして確定の払戻で数える。外れも全部書く。買い方の決まりではない。
見る時：前向きで300頭たまったら。採用の条件：前向き300頭以上・回収100%以上、かつ過去（2016年〜2026年10月）と前向きを合わせた日を単位の95%幅の下が100%以上。
成績表の払戻や頭数が読み取りと合わないレース（3着の同着など）は、過去の数え方と同じく数えない。
STORE/data/fwd/jra_furiake.txt（読む用）と jra_furiake.csv（馬ごと）に置く。
使い方：python chiho/jra/jfwd.py STORE [nosave]"""
import os, sys, glob, json, time, subprocess, datetime as dt, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jfeat

KEY = ['年月日', '場', 'R']
START, PAST_END, LOOK = os.environ.get('JFWD_START', '20261107'), '20261031', 300      # JFWD_START は試しのときだけ
store = sys.argv[1]
JST = dt.timezone(dt.timedelta(hours=9))
GIT_ID = ['-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com']

H = pd.read_pickle(os.environ['JFWD_PKL']) if os.environ.get('JFWD_PKL') else jfeat.build(f'{store}/jra/data', verbose=False)      # JFWD_PKL は試しのときだけ
H = H[~H['予測'] & (H['合わない'] == 0)].copy()
H = H[(H['n'] >= 5) & H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())].copy()
H = H.sort_values(KEY + ['単勝オッズ', '馬番']); H['人気順'] = H.groupby(KEY).cumcount() + 1
H['不利明け'] = (H['前不利発走'] == 1) | (H['前不利疾病'] == 1)

pay = {}
for f in glob.glob(f'{store}/jra/data/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '払戻'])
    for a, b, c, p in r.itertuples(index=False):
        try: d = json.loads(p) if p else {}
        except ValueError: d = {}
        pay[(a, b, int(c))] = d

rows = []
for k, g in H[H.groupby(KEY)['不利明け'].transform('any')].groupby(KEY, sort=False):
    d = pay.get((k[0], k[1], int(k[2])), {})
    pop = dict(zip(g['人気順'], g['馬番'].astype(int)))
    win = sorted(g.loc[g['着'] == 1, '馬番'].astype(int))
    top2 = tuple(sorted(g.loc[g['着'] <= 2, '馬番'].astype(int)))
    tan = d.get('単勝') if isinstance(d.get('単勝'), list) else []
    uren = d.get('馬連') if isinstance(d.get('馬連'), list) else []
    for _, h in g[g['不利明け']].iterrows():
        me = int(h['馬番'])
        if me in win:      # 同着は馬番の順に払戻が並ぶとする。払戻が読めないときは単勝オッズ
            t = tan[win.index(me)] if len(tan) == len(win) else round(float(h['単勝オッズ']) * 100)
        else: t = 0
        partner = pop[2] if h['人気順'] == 1 else pop[1]
        if len(uren) == 1 and len(top2) == 2: u = uren[0] if tuple(sorted((me, partner))) == top2 else 0
        else: u = np.nan       # 2着の同着などで馬連の払戻が1つでないときは数えない
        mark = '・'.join(x for x in (('前走で出遅れなど' if h['前不利発走'] == 1 else ''), ('前走で疾病' if h['前不利疾病'] == 1 else '')) if x)
        rows.append(dict(年月日=k[0], 場=k[1], R=int(k[2]), 馬番=me, 馬名=h['馬名'], 印=mark, 人気=int(h['人気順']), 単勝オッズ=float(h['単勝オッズ']),
                         着=int(h['着']) if pd.notna(h['着']) else 99, 単勝払戻=int(t), 相手=partner, 馬連払戻=u))
R = pd.DataFrame(rows).sort_values(['年月日', '場', 'R', '馬番'])
FW = R[R['年月日'] >= START]; PA = R[R['年月日'] <= PAST_END]


def stat(X, col, B=2000):
    X = X[X[col].notna()]
    if not len(X): return 0, 0, float('nan'), (float('nan'), float('nan'))
    x = X.groupby('年月日')[col].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1)
    return len(X), int((X[col] > 0).sum()), X[col].sum() / len(X), tuple(np.percentile(s, [2.5, 97.5]))


def line(lab, X, col, ci=True):
    n, hit, r, (lo, hi) = stat(X, col)
    if not n: return f'{lab}：まだ無し'
    return f'{lab}：{n}点・的中{hit}・回収{r:.1f}%' + (f'（95%幅 {lo:.0f}〜{hi:.0f}）' if ci else '')


now = dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M')
L = [f'中央競馬 不利明けの馬の前向きの記録（{now}）',
     '不利明け＝前走で発走の不利（出遅れ・立上るなど）か、競走中の疾病があった馬。買ったとして確定の払戻で数える（外れも全部）。買い方の決まりではない。',
     '成績表の払戻が読めないレース（3着の同着など）は、過去と同じく数えない。',
     f'見る時：前向きで{LOOK}頭たまったら。採用の条件：前向き{LOOK}頭以上・回収100%以上、かつ過去と前向きを合わせた日を単位の95%幅の下が100%以上。', '',
     f'■ 前向き（{int(START[:4])}年{int(START[4:6])}月{int(START[6:])}日から、{len(FW)}頭' + ('・見る時になった' if len(FW) >= LOOK else '') + '）',
     line('単勝', FW, '単勝払戻', ci=len(FW) >= 30), line('1番人気との馬連1点', FW, '馬連払戻', ci=len(FW) >= 30), '',
     f'■ 過去（2016年〜{int(PAST_END[:4])}年{int(PAST_END[4:6])}月、くらべる用）', line('単勝', PA, '単勝払戻'), line('1番人気との馬連1点', PA, '馬連払戻'), '',
     '■ 過去と前向きを合わせて', line('単勝', pd.concat([PA, FW]), '単勝払戻'), line('1番人気との馬連1点', pd.concat([PA, FW]), '馬連払戻'), '',
     '■ 馬ごと（前向き、新しい順）']
for _, r in FW.iloc[::-1].iterrows():
    a, b = sorted((r['馬番'], r['相手']))
    u = '数えない' if pd.isna(r['馬連払戻']) else (f"{int(r['馬連払戻'])}円" if r['馬連払戻'] > 0 else '外れ')
    L.append(f"{r['年月日'][4:6]}/{r['年月日'][6:]} {r['場']}{r['R']}R {r['馬番']}番 {r['馬名']} {r['印']} {r['人気']}番人気 {r['単勝オッズ']:.1f}倍 → {r['着']}着"
             f" 単勝{r['単勝払戻']}円／馬連{a}-{b} {u}")
if not len(FW): L.append('まだ無し')
os.makedirs(f'{store}/data/fwd', exist_ok=True)
open(f'{store}/data/fwd/jra_furiake.txt', 'w', encoding='utf-8').write('\n'.join(L) + '\n')
FW.to_csv(f'{store}/data/fwd/jra_furiake.csv', index=False, encoding='utf-8')
print('\n'.join(L[:16]), flush=True)
if len(sys.argv) > 2 and sys.argv[2] == 'nosave': sys.exit(0)


def run(*a): return subprocess.run(['git', '-C', store] + GIT_ID + list(a), capture_output=True, text=True)


run('add', 'data/fwd')
if run('diff', '--cached', '--quiet').returncode != 0:
    run('commit', '-q', '-m', f'中央競馬 不利明けの馬の前向きの記録 {now}')
    for _ in range(5):
        if run('push', '-q', 'origin', 'HEAD:main').returncode == 0: print('保存した', flush=True); break
        run('fetch', '-q', '--depth', '20', 'origin', 'main'); rb = run('rebase', '-q', 'origin/main')
        if rb.returncode != 0: run('rebase', '--abort')
        time.sleep(5)
    else: print('保存できなかった', flush=True)
