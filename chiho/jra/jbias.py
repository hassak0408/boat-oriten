"""中央競馬：J1 印ごとの単勝（検証計画「中央：値段がずれる所を探す」）。モデルは使わず、レース前に分かる印で馬を選ぶ。
選ぶ期間 2016〜2021年、確かめる期間 2022〜2026年。回収は確定の単勝オッズ（払戻）で数える。
使い方：python jbias.py 材料.pkl STORE/jra/data"""
import sys, glob, numpy as np, pandas as pd
KEY = ['年月日', '場', 'R']
H = pd.read_pickle(sys.argv[1])
H = H[~H['予測'] & (H['合わない'] == 0)].copy()
root = sys.argv[2]
# 減量の印（材料の表では0/1にしてあるので、元の表から読む）
M = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '馬番', '減量']) for f in glob.glob(f'{root}/*/*_horses.csv.gz')])
M['R'] = pd.to_numeric(M['R']).astype('Int64'); M['馬番'] = pd.to_numeric(M['馬番'], errors='coerce')
M = M.dropna(subset=['馬番']).drop_duplicates(KEY + ['馬番']); M['馬番'] = M['馬番'].astype(int)
H = H.merge(M.rename(columns={'減量': '印減量'}), on=KEY + ['馬番'], how='left')
ok = H.groupby(KEY)['単勝オッズ'].transform(lambda s: s.notna().all())
H = H[ok & (H['n'] >= 5)].copy()
H['q'] = 1 / H['単勝オッズ']; H['q'] = H['q'] / H.groupby(KEY)['q'].transform('sum')
H['払'] = np.where(H['勝'] == 1, H['単勝オッズ'], 0.0)
# 前走で逃げた
H = H.sort_values(['馬', '日', 'R']).reset_index(drop=True)
H['前先頭'] = H.groupby('馬', sort=False)['先頭'].shift(1)
# 上位騎手：前の年の勝ち数の上位10人
wins = H.groupby(['年', '騎手'])['勝'].sum().reset_index()
top = {y + 1: set(g.nlargest(10, '勝')['騎手']) for y, g in wins.groupby('年')}
H['騎上'] = [(j in top.get(y, set())) if y in top else np.nan for y, j in zip(H['年'], H['騎手'])]
H['前騎上'] = [(j in top.get(y, set())) if (y in top and isinstance(j, str)) else np.nan for y, j in zip(H['年'], H['前騎'])]
seg = {
    '①上位騎手へ乗り替わり': (H['乗替'] == 1) & (H['騎上'] == True) & (H['前騎上'] == False),
    '②上位騎手から乗り替わり': (H['乗替'] == 1) & (H['騎上'] == False) & (H['前騎上'] == True),
    '③減量騎手（▲△☆）': H['印減量'].isin(['▲', '△', '☆']),
    '④女性騎手（◇★）': H['印減量'].isin(['◇', '★']),
    '⑤前走大敗でも2〜5走前に3着内': (H['着率1'] > 0.6) & (H['最良着2_5'] <= 3),
    '⑥昇級初戦（前走1着）': (H['着x1'] == 1) & (H['クラス差'] > 0),
    '⑦前走1番人気で4着以下': (H['前人気'] == 1) & (H['着x1'] >= 4),
    '⑧90日以上の休み明け': H['間隔'] >= 90,
    '⑨180日以上の休み明け': H['間隔'] >= 180,
    '⑩初めてのブリンカー': (H['ブリンカー'] == 1) & (H['前ブリンカー'] == 0),
    '⑪馬体重10kg以上増': H['増減'] >= 10,
    '⑫馬体重10kg以上減': H['増減'] <= -10,
    '⑬距離200m以上短縮': H['距離差'] <= -200,
    '⑭距離200m以上延長': H['距離差'] >= 200,
    '⑮芝からダートへ': (H['芝ダ変更'] == 1) & (H['芝ダ'] == 'ダート'),
    '⑯ダートから芝へ': (H['芝ダ変更'] == 1) & (H['芝ダ'] == '芝'),
    '⑰牡馬と一緒の牝馬': (H['性'] == '牝') & (H['牝限'] == 0),
    '⑱外枠（7・8枠）': H['枠'] >= 7,
    '⑲前走で4角から5頭以上抜いた': H['上げ1'] >= 5,
    '⑳前走で逃げた': H['前先頭'] == 1,
    '（参考）新潟芝1000mの7・8枠': (H['場'] == '新潟') & (H['芝ダ'] == '芝') & (H['距離'] == 1000) & (H['枠'] >= 7),
    '（参考）全部': pd.Series(True, index=H.index),
}


def boot(pay, day, B=2000):
    x = pd.DataFrame({'d': day, 's': pay}).groupby('d')['s'].agg(['sum', 'size']); rng = np.random.default_rng(0)
    k = rng.integers(0, len(x), (B, len(x))); s = x['sum'].values[k].sum(1) / x['size'].values[k].sum(1) * 100
    return np.percentile(s, [2.5, 97.5])


def ratio_ci(w, q, day, B=2000):
    x = pd.DataFrame({'d': day, 'w': w, 'q': q}).groupby('d')[['w', 'q']].sum(); rng = np.random.default_rng(1)
    k = rng.integers(0, len(x), (B, len(x))); r = x['w'].values[k].sum(1) / x['q'].values[k].sum(1)
    return np.percentile(r, [2.5, 97.5])


rows = []
for name, m in seg.items():
    for lab, pm in (('2016〜2021', H['年'] <= 2021), ('2022〜2026', H['年'] >= 2022)):
        X = H[m.fillna(False).astype(bool) & pm]
        if not len(X): continue
        lo, hi = boot(X['払'].values, X['年月日'].values); rl, rh = ratio_ci(X['勝'].values, X['q'].values, X['年月日'].values)
        by = X.groupby('年')['払'].mean() * 100
        rows.append({'印': name, '期間': lab, '頭': len(X), '1着率': f"{X['勝'].mean()*100:.1f}%", '実際÷見込み': f"{X['勝'].sum()/X['q'].sum():.3f}（{rl:.2f}〜{rh:.2f}）",
                     '単勝の回収': f"{X['払'].mean()*100:.1f}%（{lo:.0f}〜{hi:.0f}）", '年ごと': '・'.join(f'{v:.0f}' for v in by.values)})
pd.set_option('display.width', 260); pd.set_option('display.max_colwidth', 80)
print(pd.DataFrame(rows).to_string(index=False))

# 障害のレース（人気ごと）
rs, hs = [], []
for f in glob.glob(f'{root}/*/*_races.csv.gz'):
    r = pd.read_csv(f, dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '芝ダ'])
    r = r[r['芝ダ'] == '障害']
    if len(r):
        rs.append(r); h = pd.read_csv(f.replace('_races', '_horses'), dtype=str, keep_default_na=False, usecols=['年月日', '場', 'R', '馬番', '単勝オッズ', '人気', '着順', '状態'])
        hs.append(h.merge(r[['年月日', '場', 'R']], on=['年月日', '場', 'R']))
J = pd.concat(hs); J = J[~J['状態'].isin(['出走取消', '取消', '競走除外', '除外'])].copy()
J['odds'] = pd.to_numeric(J['単勝オッズ'], errors='coerce'); J['pop'] = pd.to_numeric(J['人気'], errors='coerce'); J['勝'] = (J['着順'] == '1').astype(int)
J = J[J.groupby(['年月日', '場', 'R'])['odds'].transform(lambda s: s.notna().all())]
J['q'] = 1 / J['odds']; J['q'] = J['q'] / J.groupby(['年月日', '場', 'R'])['q'].transform('sum'); J['払'] = np.where(J['勝'] == 1, J['odds'], 0)
J['年'] = J['年月日'].str[:4].astype(int)
J['帯'] = pd.cut(J['pop'], [0, 1, 3, 6, 99], labels=['1番人気', '2〜3番人気', '4〜6番人気', '7番人気以下'])
print('\n■ 障害のレース（人気ごと）')
for lab, pm in (('2016〜2021', J['年'] <= 2021), ('2022〜2026', J['年'] >= 2022)):
    X = J[pm]
    t = X.groupby('帯', observed=True).agg(頭=('勝', 'size'), 一着率=('勝', 'mean'), 実際=('勝', 'sum'), 見込み=('q', 'sum'), 回収=('払', 'mean'))
    t['実際÷見込み'] = (t['実際'] / t['見込み']).round(3); t['一着率'] = (t['一着率'] * 100).round(1); t['回収'] = (t['回収'] * 100).round(1)
    print(lab, f"レース {X.groupby(['年月日', '場', 'R']).ngroups}"); print(t[['頭', '一着率', '実際÷見込み', '回収']].to_string())
