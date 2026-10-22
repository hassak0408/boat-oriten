// 締切前のオッズの記録（公式サイトの2連単・2連複のページ odds2tf）。q12 の「オッズで見送る」を締切前のオッズで確かめるため
//   node q12/snap.js 分   … 今日（日本時間）の全レースを、締切の約12分前（通知のころ）・5分前（黒石で買うころ）・2分前に1回ずつ読む。
//                           決めた分だけ動いて止まる（その日のレースが全部締め切られたら早く止まる）。読み始めは1秒に1回まで
//   出力：q12/snap/YYYYMMDD.csv  日付,場,R,締切,読んだ時刻,締切の何分前,印,2連複1=2,2連複15,2連単30（/区切り、2連複は1=2,1=3,…,5=6、2連単は公式の並び）
//   その日のレースと締切は BoatraceOpenAPI（通知と同じ v1、前の日の0時すぎに出る）から読み、5分ごとに読み直す（締切の変更に追いつく）
const fs = require('fs');
const path = require('path');
const DIR = path.join(__dirname, 'snap');
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const V1 = 'https://boatraceopenapi.github.io/api/v1/';
const BR = 'https://www.boatrace.jp/owpc/pc/race/odds2tf';
const LIMIT = Number(process.argv[2] || 340) * 60e3, t0 = Date.now();
const HEAD = 'date,v,rno,closed_at,read_at,mins,tag,q12,quinella,exacta';
const TAGS = [['T12', 12, 8], ['T5', 5, 3], ['T2', 2, 0.5]];   // 印・締切の何分前に読むか・締切の何分前までなら読むか
const sleep = ms => new Promise(s => setTimeout(s, ms));
const now = () => Date.now() + Number(process.env.SNAP_SHIFT_MS || 0);   // 試すときだけずらす
const pad = n => String(n).padStart(2, '0');
function jst(ms) { const d = new Date(ms + 9 * 3600e3); return { ymd: `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`, hms: `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}` }; }
function cells(html) {
  const re = /<td class="oddsPoint[^"]*"[^>]*>([\s\S]*?)<\/td>/g, out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    const t = m[1].replace(/<[^>]*>/g, '').trim(), v = parseFloat(t);
    out.push(/^[0-9.]+$/.test(t) && isFinite(v) ? v : null);
  }
  return out;
}
let next = 0;
async function slot() { for (;;) { const t = Date.now(); if (t >= next) { next = t + 1000; return; } await sleep(next - t); } }
async function get(url, asJson) {
  for (let i = 0; i < 3; i++) {
    await slot();
    try {
      const res = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(30e3) });
      if (res.ok) return asJson ? await res.json() : await res.text();
      if (res.status === 404) return null;
    } catch (e) { /* もう一度 */ }
    await sleep(3000);
  }
  return null;
}
async function schedule(ymd) {   // [{v, rno, close(ms)}]
  const J = await get(`${V1}${ymd.slice(0, 4)}/${ymd}.json?t=${Date.now()}`, true);
  const out = [], S = ((J || {}).programs || {}).stadiums || {};
  for (const v of Object.keys(S)) {
    const R = (S[v] || {}).races || {};
    for (const k of Object.keys(R)) {
      const r = R[k], c = String(r.closed_at || '');
      if (!/^\d{4}-\d\d-\d\d \d\d:\d\d/.test(c)) continue;
      out.push({ v: Number(r.stadium_number || v), rno: Number(r.race_number || k), closed: c, close: Date.parse(c.replace(' ', 'T') + '+09:00') });
    }
  }
  return out;
}
(async () => {
  const ymd = jst(now()).ymd, OUT = path.join(DIR, `${ymd}.csv`);
  fs.mkdirSync(DIR, { recursive: true });
  if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, HEAD + '\n');
  const done = new Set(fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => { const a = s.split(','); return `${a[1]}-${a[2]}-${a[6]}`; }));
  let races = [], lastSched = 0, got = 0, miss = 0;
  for (;;) {
    const t = now();
    if (t - t0 - Number(process.env.SNAP_SHIFT_MS || 0) > LIMIT) { console.log('時間になったので止める'); break; }
    if (t - lastSched > 5 * 60e3 || !races.length) {
      const s = await schedule(ymd);
      if (s.length) races = s; else if (!races.length) { console.log('今日のレースが読めない', ymd); await sleep(120e3); if (Date.now() - t0 > 180 * 60e3) break; continue; }
      lastSched = t;
    }
    if (races.every(r => r.close < t)) { console.log('今日のレースはすべて締め切られた'); break; }
    const due = [];
    for (const r of races) for (const [tag, at, until] of TAGS) {
      const key = `${r.v}-${r.rno}-${tag}`;
      if (done.has(key)) continue;
      if (t >= r.close - at * 60e3 && t <= r.close - until * 60e3) due.push({ r, tag, key });
    }
    due.sort((a, b) => a.r.close - b.r.close);
    due.forEach(d => done.add(d.key));
    let i = 0;
    const one = async () => {
      while (i < due.length) {
        const { r, tag } = due[i++];
        const html = await get(`${BR}?rno=${r.rno}&jcd=${pad(r.v)}&hd=${ymd}`, false);
        const tr = now(), c = html ? cells(html) : null, j = jst(tr);
        const mins = ((r.close - tr) / 60e3).toFixed(2);
        if (c && c.length === 45) {
          const ex = c.slice(0, 30), qu = c.slice(30), s = x => x === null ? '' : x;
          fs.appendFileSync(OUT, [ymd, r.v, r.rno, r.closed, j.hms, mins, tag, s(qu[0]), qu.map(s).join('/'), ex.map(s).join('/')].join(',') + '\n');
          got++;
        } else { fs.appendFileSync(OUT, [ymd, r.v, r.rno, r.closed, j.hms, mins, tag, 'なし', '', ''].join(',') + '\n'); miss++; }
      }
    };
    await Promise.all([one(), one(), one(), one()]);   // 同時に待つのは4本まで（読み始めは全体で1秒に1回まで）
    await sleep(due.length ? 1000 : 10e3);
  }
  const left = races.filter(r => r.close > now()).length;
  console.log('読んだ', got, '読めなかった', miss, 'まだ締め切られていないレース', left, `${Math.round((Date.now() - t0) / 60e3)}分`);
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `left=${left}\nymd=${ymd}\n`);
})().catch(e => { console.error(e); process.exit(1); });
