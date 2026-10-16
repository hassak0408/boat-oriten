"""集めた CSV（artifacts/**/csv/*.csv）を data/場番号/年.csv にまとめる（同じレース・枠は新しい方を残す）"""
import csv, glob, os, sys
from collections import defaultdict
FIELDS = ['date', 'venue', 'race', 'lane', 'reg', 'ex', 'lap', 'lap_kind', 'turn', 'straight']

def main(src='artifacts', dst='data'):
    rows = defaultdict(dict)
    for f in sorted(glob.glob(f'{dst}/*/*.csv')) + sorted(glob.glob(f'{src}/**/csv/*.csv', recursive=True)):
        with open(f, encoding='utf-8') as g:
            for r in csv.DictReader(g):
                if not r.get('date'):
                    continue
                key = (r['date'], int(r['venue']), int(r['race']), int(r['lane']))
                rows[(int(r['venue']), r['date'][:4])][key] = {k: r.get(k, '') for k in FIELDS}
    n = 0
    for (v, y), d in sorted(rows.items()):
        os.makedirs(f'{dst}/{v:02d}', exist_ok=True)
        with open(f'{dst}/{v:02d}/{y}.csv', 'w', newline='', encoding='utf-8') as g:
            w = csv.DictWriter(g, fieldnames=FIELDS); w.writeheader()
            for k in sorted(d):
                w.writerow(d[k]); n += 1
    # 場・月ごとの件数
    cnt = defaultdict(int)
    for (v, y), d in rows.items():
        for k in d:
            cnt[(v, k[0][:7])] += 1
    with open(f'{dst}/summary.csv', 'w', newline='', encoding='utf-8') as g:
        w = csv.writer(g); w.writerow(['venue', 'month', 'rows'])
        for (v, m), c in sorted(cnt.items()):
            w.writerow([v, m, c])
    print('まとめた行', n)

if __name__ == '__main__':
    main(*sys.argv[1:])
