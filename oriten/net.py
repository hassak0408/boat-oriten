"""間を空けて1ページずつ読む（同じサイトには interval 秒以上あける。robots.txt で止められたページは読まない）"""
import time, requests
from urllib.parse import urlparse
from urllib import robotparser
from .venues import UA

class Fetcher:
    def __init__(self, interval=1.5, timeout=30):
        self.interval = interval; self.timeout = timeout; self.last = {}; self.robots = {}
        self.s = requests.Session(); self.s.headers.update({'User-Agent': UA, 'Accept-Language': 'ja'})

    def allowed(self, url):
        u = urlparse(url); base = f'{u.scheme}://{u.netloc}'
        if base not in self.robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.s.get(base + '/robots.txt', timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self.robots[base] = rp
        return self.robots[base].can_fetch(UA, url)

    def get(self, url, tries=3):
        if not self.allowed(url):
            return None, 'robots.txt で止められている'
        host = urlparse(url).netloc; err = ''
        for k in range(tries):
            wait = self.last.get(host, 0) + self.interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.time()
            try:
                r = self.s.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                err = f'通信エラー {type(e).__name__}'; time.sleep(10 * (k + 1)); continue
            if r.status_code in (429, 500, 502, 503, 504):
                err = f'HTTP {r.status_code}'; time.sleep(30 * (k + 1)); continue
            if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'ascii'):
                r.encoding = r.apparent_encoding or 'utf-8'
            return r.status_code, r.text
        return None, err
