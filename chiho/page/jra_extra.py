"""中央のページの足し（検証計画 JP2）：レースの展開予想と短評を、一覧（jpipe）が出した「逃げ型・出遅れくせ・展開型」から作る。
2026-11-23 に作業場所が消えたので作り直した（前は手元の H_jra から作っていた。11/22 から一覧が本番の過去の表から出している）。"""
def _nige(r):
    nige = sorted(h['馬番'] for h in r['馬'] if h.get('逃げ型'))
    k = len(nige); ns = '・'.join(f'{v}番' for v in nige)
    if k == 0: return 'よく逃げる馬がいない。ゆったりした流れになりやすい（これまで遅い流れ34%・速い流れ14%）。前に行く馬に向きやすい。'
    if k == 1: return f'よく逃げる馬は{ns}の1頭。流れはふつうになりやすい（遅い23%・速い22%）。'
    if k == 2: return f'よく逃げる馬が2頭（{ns}）。やや速くなりやすい（速い26%・遅い17%）。'
    return f'よく逃げる馬が{k}頭（{ns}）。速い流れになりやすい（速い36%・遅い10%）。後ろから来る馬に向きやすい。'
def _comment(r):
    hs = sorted(r['馬'], key=lambda h: h['順位']); by1 = sorted(r['馬'], key=lambda h: -(h.get('p1') or h['一着'] / 100))
    out = []
    a, b = (by1[0], by1[1]) if len(by1) >= 2 else (by1[0], None)
    pa = a.get('p1') or a['一着'] / 100; pb = (b.get('p1') or b['一着'] / 100) if b else 0
    if pa >= 0.40 and pa >= 2 * pb: out.append(f"{a['馬番']}番{a['馬名']}が抜けて強い（1着{a['一着']}%・3着内{a['三着内']}%）。")
    elif pa < 0.20: out.append(f"混戦。1着の見込みがいちばん高い{a['馬番']}番{a['馬名']}でも{a['一着']}%。")
    else: out.append(f"中心は{hs[0]['馬番']}番{hs[0]['馬名']}（3着内{hs[0]['三着内']}%）。")
    cut = [k + 1 for k in range(min(5, len(hs) - 1)) if hs[k]['三着内'] - hs[k + 1]['三着内'] >= 20]
    if cut: out.append('1位と2位以下に差がある。' if cut[0] == 1 else f'上位{cut[0]}頭とその下に差がある。')
    else: out.append('上位5頭の3着内の見込みが近く、相手を絞りにくい。')
    for t in ('前走は速い流れを差した', '前走は遅い流れを前で粘った'):
        x = [f"{h['馬番']}番" for h in hs if h.get('展開型') == t]
        if x: out.append(f"{'・'.join(x)}は{t}{'（恵まれた分を割り引く）' if '差した' in t else '（力はある）'}。")
    x = [f"{h['馬番']}番" for h in hs if h.get('型') == '市場よりかなり来やすい型']
    if x: out.append(f"{'・'.join(x)}は市場よりかなり来やすい型。")
    x = [f"{h['馬番']}番" for h in hs[:4] if h.get('型') == '市場より来にくい型']
    if x: out.append(f"上位の{'・'.join(x)}は市場より来にくい型（ワイドの軸・相手にすると戻りが下がりやすい）。")
    if '新馬' in str(r.get('レース名', '')): out.append('新馬戦はAIが弱い。人気を重く。')
    return ''.join(out)
def add(o):
    o['足しの元'] = '一覧' if all('逃げ型' in h for r in o['レース'] for h in r['馬']) else '一部なし'
    for r in o['レース']:
        for h in r['馬']:
            h.setdefault('逃げ型', False); h.setdefault('出遅れくせ', False); h.setdefault('展開型', '')
        r['展開予想'] = _nige(r); r['短評'] = _comment(r)
    return o
