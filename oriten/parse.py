"""各場の公式サイトの「オリジナル展示データ」の表を読む（場によって列の並びが違うので、見出しの文字で列を決める）"""
import re
import lxml.html

KEYS = {
    'lap': ('一周', '半周'),
    'turn': ('まわり足', 'まわりあし', '回り足'),
    'straight': ('直線',),
}
NUM = re.compile(r'^-?\d+(?:\.\d+)?$')


def _clean(s):
    return re.sub(r'\s+', '', s or '')


def _num(s):
    s = _clean(s).replace('秒', '')
    if s.startswith('.'):
        s = '0' + s
    return float(s) if NUM.match(s) else None


def table_grid(tbl):
    """rowspan/colspan を広げた表。grid[(行, 列)] = (文字, 見出しか, 元のセルか)。
    rowspan は thead・tbody の中だけで広げる（ブラウザと同じ。見出しの rowspan が本文にはみ出す場があるため）"""
    sections, cur = [], []
    for ch in tbl:
        tag = ch.tag if isinstance(ch.tag, str) else ''
        if tag in ('thead', 'tbody', 'tfoot'):
            if cur:
                sections.append(cur); cur = []
            sections.append(ch.xpath('./tr'))
        elif tag == 'tr':
            cur.append(ch)
    if cur:
        sections.append(cur)
    grid = {}; base = 0
    for rows in sections:
        n = len(rows)
        for i, tr in enumerate(rows):
            r = base + i; c = 0
            for cell in tr.xpath('./th|./td'):
                while (r, c) in grid:
                    c += 1
                try:
                    rs = max(1, int(cell.get('rowspan', '1') or 1))
                    cs = max(1, int(cell.get('colspan', '1') or 1))
                except ValueError:
                    rs, cs = 1, 1
                rs = min(rs, n - i)
                text = cell.text_content()
                for dr in range(rs):
                    for dc in range(cs):
                        grid[(r + dr, c + dc)] = (text, cell.tag == 'th', dr == 0 and dc == 0)
                c += cs
        base += n
    return grid, base


def parse_toda_xml(text):
    """戸田の XML（record ごとに teiban・ttime・rnd（一周）・cnr（まわり足）・str（直線））"""
    out = []
    for rec in re.findall(r'<record>(.*?)</record>', text, re.S):
        g = lambda t: (re.search(rf'<{t}>(.*?)</{t}>', rec, re.S) or [None, None])[1]
        lane = g('teiban')
        if not lane or not lane.strip().isdigit():
            continue
        out.append(dict(lane=int(lane), reg=None, ex=_num(g('ttime') or ''), lap=_num(g('rnd') or ''), lap_kind='一周',
                        turn=_num(g('cnr') or ''), straight=_num(g('str') or '')))
    return out


def parse_page(html):
    """返り値：(艇ごとの行のリスト, メモ)。行は dict(lane, reg, name, ex, lap, lap_kind, turn, straight)"""
    if isinstance(html, bytes):
        html = html.decode('utf-8', errors='replace')
    if '<record>' in html and '<rnd>' in html:
        rows = parse_toda_xml(html)
        return rows, ('戸田のXML' if rows else 'XMLが読めない')
    if 'まわり' not in html and '回り足' not in html:
        return [], 'まわり足の表なし'
    doc = lxml.html.fromstring(html)
    for tbl in doc.xpath('//table'):
        heads = ''.join(_clean(th.text_content()) for th in tbl.xpath('.//th'))
        if not any(k in heads for k in KEYS['turn']):
            continue
        grid, nrow = table_grid(tbl)
        ncol = max(c for _, c in grid) + 1
        # 列の見出し（見出しセルの文字をつなぐ）
        label = {}
        for c in range(ncol):
            parts = []
            for r in range(nrow):
                v = grid.get((r, c))
                if v and v[1]:
                    t = _clean(v[0])
                    if t and (not parts or parts[-1] != t):
                        parts.append(t)
            label[c] = ''.join(parts)
        def find(pred):
            for c in range(ncol):
                if pred(label[c]):
                    return c
            return None
        col = {
            'lane': find(lambda s: s in ('枠', '艇番', '枠番', '艇') or s.endswith('枠') or '艇番' in s),
            'player': find(lambda s: '選手' in s or 'レーサー' in s or '登録番号' in s or '登番' in s),
            'ex': find(lambda s: ('展示' in s) and not any(k in s for k in ('一周', '半周', 'まわり', '回り', '直線', '評価', 'スタート', 'ST', '順位'))
                       and ('タイム' in s or s.endswith('展示') or s == '展示')),
            'lap': find(lambda s: any(k in s for k in KEYS['lap'])),
            'turn': find(lambda s: any(k in s for k in KEYS['turn'])),
            'straight': find(lambda s: any(k in s for k in KEYS['straight'])),
        }
        if col['turn'] is None:
            continue
        lap_kind = '半周' if (col['lap'] is not None and '半周' in label[col['lap']]) else '一周'
        out = {}
        for r in range(nrow):
            # 艇の行：枠の列が td で、その行で始まるセル、中身が1〜6
            if col['lane'] is not None:
                v = grid.get((r, col['lane']))
                if not v or v[1] or not v[2]:
                    continue
                m = re.match(r'^([1-6])$', _clean(v[0]))
                if not m:
                    continue
                lane = int(m.group(1))
            else:
                # 枠の列が見つからないときは、まわり足の列の値が始まる行を上から1〜6
                v = grid.get((r, col['turn']))
                if not v or v[1] or not v[2]:
                    continue
                lane = len(out) + 1
                if lane > 6:
                    break
            if lane in out:
                continue
            def val(k):
                if col[k] is None:
                    return None
                x = grid.get((r, col[k]))
                return _num(x[0]) if x else None
            reg, name = None, None
            if col['player'] is not None:
                x = grid.get((r, col['player']))
                if x:
                    t = x[0]
                    m = re.search(r'(?<!\d)(\d{4})(?!\d)', t)
                    reg = int(m.group(1)) if m else None
            out[lane] = dict(lane=lane, reg=reg, ex=val('ex'), lap=val('lap'), lap_kind=lap_kind, turn=val('turn'), straight=val('straight'))
        if out:
            got = [k for k in ('ex', 'lap', 'turn', 'straight') if col[k] is not None]
            return [out[k] for k in sorted(out)], '列:' + ','.join(f'{k}={label[col[k]]}' for k in got)
    return [], '表はあるが読めない'
