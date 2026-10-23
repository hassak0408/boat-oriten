// 締切前のオッズの記録（公式サイトの2連単・2連複のページ odds2tf）。q12 の「オッズで見送る」を締切前のオッズで確かめるため
//   node q12/snap.js 分   … 今日（日本時間）の全レースを、締切の約12分前（通知のころ）・5分前（黒石で買うころ）・2分前に1回ずつ読む。
//                           決めた分だけ動いて止まる（その日のレースが全部締め切られたら早く止まる）。読み始めは1秒に1回まで
//   出力：q12/snap/YYYYMMDD.csv  日付,場,R,締切,読んだ時刻,締切の何分前,印,2連複1=2,2連複15,2連単30（/区切り、公式のページの並び）
//     2連複：1=2,1=3,2=3,1=4,2=4,3=4,1=5,2=5,3=5,4=5,1=6,2=6,3=6,4=6,5=6
//     2連単：1-2,2-1,3-1,4-1,5-1,6-1,1-3,2-3,3-2,4-2,5-2,6-2,1-4,2-4,3-4,4-3,5-3,6-3,1-5,2-5,3-5,4-5,5-4,6-4,1-6,2-6,3-6,4-6,5-6,6-5
//   その日のレースと締切は BoatraceOpenAPI（通知と同じ v1、前の日の0時すぎに出る）から読み、5分ごとに読み直す（締切の変更に追いつく）
//   Actions の中では30分ごとに、それまでの記録を main に足す（途中で止まっても残る・途中でも確かめられる）
//   展示が v1 に出た時刻も記録する（2026-10-23 から）：q12/pv/YYYYMMDD.csv  日付,場,R,締切,見つけた時刻,締切の何分前,展示タイムの数,その回の最初の読み（1＝それより前は見ていない）
//     5分ごとに v1 を読み直すたびに、展示タイムが5艇以上そろったレースを1回だけ書く。通知（5分おき）が締切の何分前に計算できるかの目安。失敗しても odds の記録は止めない
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const DIR = path.join(__dirname, 'snap');
const PVDIR = path.join(__dirname, 'pv');
const PVHEAD = 'date,v,rno,closed_at,seen_at,mins,n_ex,first_read';
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
function save(msg) {   // Actions の中だけ：q12/snap を main に足す（失敗しても読むのは続ける）
  if (!process.env.GITHUB_ACTIONS) return;
  const sh = c => execSync(c, { stdio: 'inherit', shell: '/bin/bash', cwd: path.join(__dirname, '..') });
  try {
    // 名前とメールを先に設定する（無いと、main が先に進んでいたときの rebase が「名前が無い」で失敗して、途中の保存が1回も通らなかった。2026-10-23 に直した）
    sh(`git config user.name 'github-actions[bot]' && git config user.email '41898282+github-actions[bot]@users.noreply.github.com'`);
    sh(`git add q12/snap${fs.existsSync(PVDIR) ? ' q12/pv' : ''} && (git diff --cached --quiet || git commit -q -m "${msg}")`);
    for (let i = 0; i < 5; i++) {
      try { sh('git push -q origin HEAD:main'); console.log('途中の保存', msg); return; } catch (e) { try { sh('git fetch -q origin main && (git rebase -q origin/main || git rebase --abort)'); } catch (e2) { console.log('rebase に失敗', String(e2).slice(0, 200)); } }
    }
    console.log('途中の保存：push が5回とも通らなかった（最後の「保存」で入る）');
  } catch (e) { console.log('途中の保存に失敗', String(e).slice(0, 200)); }
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
function nEx(r) {   // v1 の展示タイムがそろっている艇の数（通知の q12core と同じ：0より大きい数）
  const P = ((r || {}).preview || {}).racers || {};
  let n = 0;
  for (let i = 1; i <= 6; i++) { const e = Number((P[String(i)] || {}).exhibition_time); if (e > 0) n++; }
  return n;
}
async function schedule(ymd) {   // [{v, rno, close(ms), nex}]
  const J = await get(`${V1}${ymd.slice(0, 4)}/${ymd}.json?t=${Date.now()}`, true);
  const out = [], S = ((J || {}).programs || {}).stadiums || {};
  for (const v of Object.keys(S)) {
    const R = (S[v] || {}).races || {};
    for (const k of Object.keys(R)) {
      const r = R[k], c = String(r.closed_at || '');
      if (!/^\d{4}-\d\d-\d\d \d\d:\d\d/.test(c)) continue;
      out.push({ v: Number(r.stadium_number || v), rno: Number(r.race_number || k), closed: c, close: Date.parse(c.replace(' ', 'T') + '+09:00'), nex: nEx(r) });
    }
  }
  return out;
}
(async () => {
  const ymd = jst(now()).ymd, OUT = path.join(DIR, `${ymd}.csv`);
  fs.mkdirSync(DIR, { recursive: true });
  if (!fs.existsSync(OUT)) fs.writeFileSync(OUT, HEAD + '\n');
  const done = new Set(fs.readFileSync(OUT, 'utf8').split('\n').slice(1).filter(s => s.trim()).map(s => { const a = s.split(','); return `${a[1]}-${a[2]}-${a[6]}`; }));
  let races = [], lastSched = 0, got = 0, miss = 0, lastSave = Date.now();
  const PVOUT = path.join(PVDIR, `${ymd}.csv`), pvDone = new Set();
  let pvFirst = true;
  try { if (fs.existsSync(PVOUT)) fs.readFileSync(PVOUT, 'utf8').split('\n').slice(1).filter(x => x.trim()).forEach(x => { const a = x.split(','); pvDone.add(`${a[1]}-${a[2]}`); }); } catch (e) { console.log('展示の記録が読めない', String(e).slice(0, 200)); }
  const pvLog = (list, ts) => {   // 展示タイムが5艇以上そろったレースを、見つけた回に1回だけ書く（失敗しても odds の記録は続ける）
    try {
      const rows = [];
      for (const r of list) {
        const key = `${r.v}-${r.rno}`;
        if (r.nex < 5 || pvDone.has(key)) continue;
        pvDone.add(key);
        rows.push([ymd, r.v, r.rno, r.closed, jst(ts).hms, ((r.close - ts) / 60e3).toFixed(2), r.nex, pvFirst ? 1 : 0].join(','));
      }
      pvFirst = false;
      if (!rows.length) return;
      fs.mkdirSync(PVDIR, { recursive: true });
      if (!fs.existsSync(PVOUT)) fs.writeFileSync(PVOUT, PVHEAD + '\n');
      fs.appendFileSync(PVOUT, rows.map(x => x + '\n').join(''));
    } catch (e) { console.log('展示の記録に失敗', String(e).slice(0, 200)); }
  };
  for (;;) {
    const t = now();
    if (t - t0 - Number(process.env.SNAP_SHIFT_MS || 0) > LIMIT) { console.log('時間になったので止める'); break; }
    if (t - lastSched > 5 * 60e3 || !races.length) {
      const s = await schedule(ymd);
      if (s.length) { races = s; pvLog(s, now()); } else if (!races.length) { console.log('今日のレースが読めない', ymd); await sleep(120e3); if (Date.now() - t0 > 180 * 60e3) break; continue; }
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
    if (Date.now() - lastSave > Number(process.env.SNAP_SAVE_MIN || 30) * 60e3) { save(`q12：締切前のオッズ ${ymd}（途中・${jst(now()).hms.slice(0, 5)}）`); lastSave = Date.now(); }
    await sleep(due.length ? 1000 : 10e3);
  }
  const left = races.filter(r => r.close > now()).length;
  console.log('読んだ', got, '読めなかった', miss, 'まだ締め切られていないレース', left, `${Math.round((Date.now() - t0) / 60e3)}分`);
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `left=${left}\nymd=${ymd}\n`);
})().catch(e => { console.error(e); process.exit(1); });
