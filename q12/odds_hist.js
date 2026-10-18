// 過去のレースの確定オッズ（2連単・2連複）を公式サイトのオッズのページから読んで q12/odds_hist.csv に足す（オッズの見送りの確かめ用）
//   読むレース：q12/odds_targets.csv（日付,場,R）。もう読んだレースは飛ばす（途中で止まっても続きから）
//   node q12/odds_hist.js 分        … 決めた分（既定90分）だけ読んで止まる。1秒に1回まで
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const T = path.join(DIR, 'odds_targets.csv'), OUT = path.join(DIR, 'odds_hist.csv');
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const LIMIT = Number(process.argv[2] || 90) * 60e3, t0 = Date.now();
const HEAD = 'date,v,rno,q12,quinella,exacta';
function cells(html) {
  const re = /<td class="oddsPoint[^"]*"[^>]*>([\s\S]*?)<\/td>/g, out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    const t = m[1].replace(/<[^>]*>/g, '').trim(), v = parseFloat(t);
    out.push(/^[0-9.]+$/.test(t) && isFinite(v) ? v : null);
  }
  return out;
}
(async () => {
  const targets = fs.readFileSync(T, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => s.split(','));
  if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, HEAD + '\n');
  const done = new Set(fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => s.split(',').slice(0, 3).join(',')));
  let got = 0, miss = 0, buf = [];
  const flush = () => { if (buf.length) { fs.appendFileSync(OUT, buf.join('\n') + '\n'); buf = []; } };
  for (const [d, v, r] of targets) {
    const key = [d, v, r].join(',');
    if (done.has(key)) continue;
    if (Date.now() - t0 > LIMIT) break;
    const url = `https://www.boatrace.jp/owpc/pc/race/odds2tf?rno=${r}&jcd=${String(v).padStart(2, '0')}&hd=${d.replace(/-/g, '')}`;
    let c = null;
    for (let i = 0; i < 3 && c === null; i++) {
      try {
        const res = await fetch(url, { headers: { 'User-Agent': UA } });
        if (res.ok) c = cells(await res.text());
      } catch (e) { /* もう一度 */ }
      if (c === null) await new Promise(s => setTimeout(s, 3000));
    }
    if (c && c.length === 45) {
      const ex = c.slice(0, 30), qu = c.slice(30);
      buf.push([d, v, r, qu[0] === null ? '' : qu[0], qu.map(x => x === null ? '' : x).join('/'), ex.map(x => x === null ? '' : x).join('/')].join(','));
      got++;
    } else { buf.push([d, v, r, 'なし', '', ''].join(',')); miss++; }
    if (buf.length >= 50) flush();
    await new Promise(s => setTimeout(s, 1000));
  }
  flush();
  const left = targets.length - fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).length;
  console.log('読んだ', got, '読めなかった', miss, '残り', left, `${Math.round((Date.now() - t0) / 1000)}秒`);
})().catch(e => { console.error(e); process.exit(1); });
