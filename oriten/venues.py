"""場ごとの「オリジナル展示データ」のページ（{d}=YYYYMMDD、{r}=レース番号）。2026-10-16 に実際の値を読めたものだけ ok=True（14場）"""
VENUES = {
    1:  dict(name='桐生',   ok=True,  url='http://www.kiryu-kyotei.com/modules/yosou/cyokuzen.php?day={d}&race={r}'),
    5:  dict(name='多摩川', ok=True,  url='https://boatrace-tamagawa.com/modules/yosou/oriten.php?day={d}&race={r}'),
    6:  dict(name='浜名湖', ok=True,  url='https://www.boatrace-hamanako.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    10: dict(name='三国',   ok=True,  url='https://www.boatrace-mikuni.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    11: dict(name='びわこ', ok=True,  url='https://www.boatrace-biwako.jp/modules/yosou/cyokuzen.php?day={d}&race={r}&kind=2'),
    13: dict(name='尼崎',   ok=True,  url='https://boatrace-amagasaki.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    18: dict(name='徳山',   ok=True,  url='https://www.boatrace-tokuyama.jp/modules/yosou/tenji.php?day={d}&race={r}'),
    22: dict(name='福岡',   ok=True,  url='https://www.boatrace-fukuoka.com/modules/yosou/tenji_info.php?day={d}&race={r}'),
    # 2026-10-16 の probe で見つけた場
    2:  dict(name='戸田',   ok=True,  url='https://www.boatrace-toda.jp/xml/kaisai/{d}/race_table_original_{r2}.xml'),
    8:  dict(name='常滑',   ok=True,  url='https://www.boatrace-tokoname.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    14: dict(name='鳴門',   ok=True,  url='https://www.n14.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    19: dict(name='下関',   ok=True,  url='https://www.boatrace-shimonoseki.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    20: dict(name='若松',   ok=True,  url='https://www.wmb.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    21: dict(name='芦屋',   ok=True,  url='https://www.boatrace-ashiya.com/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
    23: dict(name='唐津',   ok=True,  url='https://www.boatrace-karatsu.jp/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2'),
}
# まだページの場所が分かっていない場（probe.py で探す）。江戸川（3）と津（9）はオリジナル展示を出していない
CANDIDATES = {
    4:  dict(name='平和島', sites=['https://www.heiwajima.gr.jp']),
    7:  dict(name='蒲郡',   sites=['https://www.gamagori-kyotei.com']),
    12: dict(name='住之江', sites=['https://www.boatrace-suminoe.jp']),
    15: dict(name='丸亀',   sites=['https://www.marugameboat.jp']),
    16: dict(name='児島',   sites=['https://www.kojimaboat.jp'], extra=['https://hj.kojima-yosou.com/hjpc/index/{d}/{r2}']),
    17: dict(name='宮島',   sites=['https://www.boatrace-miyajima.com']),
    24: dict(name='大村',   sites=['https://www.omurakyotei.jp', 'https://omurakyotei.jp']),
}
PATHS = [
    '/modules/yosou/cyokuzen.php?day={d}&race={r}',
    '/modules/yosou/cyokuzen.php?day={d}&race={r}&kind=2',
    '/modules/yosou/group-cyokuzen.php?day={d}&race={r}&kind=2',
    '/modules/yosou/oriten.php?day={d}&race={r}',
    '/modules/yosou/group-oriten.php?day={d}&race={r}',
    '/modules/yosou/tenji.php?day={d}&race={r}',
    '/modules/yosou/tenji_info.php?day={d}&race={r}',
    '/modules/yosou/group-tenji.php?day={d}&race={r}',
    '/modules/yosou/original.php?day={d}&race={r}',
]
UA = 'Mozilla/5.0 (compatible; boat-oriten/1.0; +https://github.com/hassak0408/boat-oriten)'
