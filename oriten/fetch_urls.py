"""指定したページをそのまま読んで probe/fetched/ に置く（ページの場所探しの下調べ用）。URL は環境変数 URLS（空白区切り）"""
import os, re, json, hashlib
from .net import Fetcher

def main():
    urls = [u for u in os.environ.get('URLS', '').split() if u.startswith('http')]
    os.makedirs('probe/fetched', exist_ok=True)
    F = Fetcher(1.0); idx = {}
    for u in urls:
        code, text = F.get(u, tries=2)
        name = re.sub(r'[^A-Za-z0-9._-]+', '_', u.split('://', 1)[-1])[:120] + '_' + hashlib.md5(u.encode()).hexdigest()[:6] + '.txt'
        if code == 200 and text:
            with open(f'probe/fetched/{name}', 'w', encoding='utf-8') as f:
                f.write(text)
        idx[u] = dict(code=code, file=name if code == 200 else None, bytes=len(text or ''), mawari=('まわり' in (text or '')))
        print(u, code, len(text or ''), flush=True)
    old = {}
    if os.path.exists('probe/fetched/index.json'):
        old = json.load(open('probe/fetched/index.json', encoding='utf-8'))
    old.update(idx)
    json.dump(old, open('probe/fetched/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
