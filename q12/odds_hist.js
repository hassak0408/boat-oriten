// 過去のレースの確定オッズ（2連単・2連複）を公式サイトのオッズのページから読んで q12/odds_hist.csv に足す（オッズの見送りの確かめ用）
//   読むレース：q12/odds_targets.csv（日付,場,R）。上から順に読む（通知Bのレースが先）。もう読んだレースは飛ばす（途中で止まっても続きから）
//   node q12/odds_hist.js 分 [同時数]   … 決めた分（既定90分）だけ読んで止まる。同時に待つのは既定4本、読み始めは全体で1秒に1回まで
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const T = path.join(DIR, 'odds_targets.csv'), OUT = path.join(DIR, 'odds_hist.csv');
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const LIMIT = Number(process.argv[2] || 90) * 60e3, N = Math.max(1, Number(process.argv[3] || 4)), t0 = Date.now();
const HEAD = 'date,v,rno,q12,quinella,exacta';
const sleep = ms => new Promise(s => setTimeout(s, ms));
function cells(html) {
  const re = /<td class="oddsPoint[^"]*"[^>]*>([\s\S]*?)<\/td>/g, out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    const t = m[1].replace(/<[^>]*>/g, '').trim(), v = parseFloat(t);
    out.push(/^[0-9.]+$/.test(t) && isFinite(v) ? v : null);
  }
  return out;
}
let next = 0; // 次に読み始めてよい時刻（全体で1秒に1回まで）
async function slot() {
  for (;;) {
    const now = Date.now();
    if (now >= next) { next = now + 1000; return; }
    await sleep(next - now);
  }
}
async function read(d, v, r) {
  const url = `https://www.boatrace.jp/owpc/pc/race/odds2tf?rno=${r}&jcd=${String(v).padStart(2, '0')}&hd=${d.replace(/-/g, '')}`;
  for (let i = 0; i < 3; i++) {
    await slot();
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(60e3) });
      if (res.ok) return cells(await res.text());
    } catch (e) { /* もう一度 */ }
    await sleep(3000);
  }
  return null;
}
(async () => {
  const targets = fs.readFileSync(T, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => s.trim().split(','));
  if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, HEAD + '\n');
  const done = new Set(fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => s.split(',').slice(0, 3).join(',')));
  const todo = targets.filter(t => !done.has(t.join(',')));
  let i = 0, got = 0, miss = 0, buf = [];
  const flush = () => { if (buf.length) { fs.appendFileSync(OUT, buf.join('\n') + '\n'); buf = []; } };
  async function worker() {
    while (i < todo.length && Date.now() - t0 <= LIMIT) {
      const [d, v, r] = todo[i++];
      const c = await read(d, v, r);
      if (c && c.length === 45) {
        const ex = c.slice(0, 30), qu = c.slice(30), s = x => x === null ? '' : x;
        buf.push([d, v, r, s(qu[0]), qu.map(s).join('/'), ex.map(s).join('/')].join(','));
        got++;
      } else { buf.push([d, v, r, 'なし', '', ''].join(',')); miss++; }
      if (buf.length >= 50) flush();
      if ((got + miss) % 200 === 0) console.log('途中', got + miss, `${Math.round((Date.now() - t0) / 1000)}秒`);
    }
  }
  await Promise.all(Array.from({ length: N }, worker));
  flush();
  const left = targets.length - fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).length;
  console.log('読んだ', got, '読めなかった', miss, '残り', left, `${Math.round((Date.now() - t0) / 1000)}秒`);
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `n=${got + miss}\nleft=${left}\n`);
})().catch(e => { console.error(e); process.exit(1); });
