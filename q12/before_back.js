// 公式の直前情報（beforeinfo）の過去のページから、市場の値段にまだ入っていないかもしれない材料を集める（2026-11-09〜）
//   集めるもの（B.extras）：艇ごとのプロペラ（新）・部品交換、レースの見出しの札（進入固定・安定板使用など）・距離・「安定板」の有無、展示がそろった艇の数（n）
//   node q12/before_back.js FROM TO [分] [間隔ms] [1日の上限]
//     FROM・TO：YYYYMMDD。新しい日から古い日へ読む。FROM に「,」でつないだ日を並べると、その日だけ読む
//     出走表は BoatraceOpenAPI（api v1、なければ programs v3）から。公式のページは1本ずつ、間隔をあけて読む（既定1.5秒）
//     出力：q12/before/back/ex_YYYYMM.jsonl（1行1レース。札のある艇だけを書く：p プロペラ、x 部品交換、lab 見出しの札、m 1800m以外の距離、a 安定板）
//           済んだ日は q12/before/back/done.txt（次の回はとばす）
//       1日の上限を入れたとき（ページがあるかの確かめ）は q12/before/back/probe.jsonl に B.extras をそのまま書き、done には書かない
//     1日の途中で時間が来たら、その日の分は捨てて次の回で読み直す（同じレースが2回入らないように）
//     公式が20回続けて読めなかったら止めて、次の回も動かさない（相手に負担をかけない）
const fs = require('fs'); const path = require('path');
const B = require('./beforeinfo.js');
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const BR = 'https://www.boatrace.jp/owpc/pc/race/beforeinfo';
const FROM = process.argv[2] || '', TO = process.argv[3] || '';
const LIMIT = Number(process.argv[4] || 330) * 60e3, GAP = Math.max(1000, Number(process.argv[5] || 1500)), PER = Number(process.argv[6] || 0), t0 = Date.now();
const DIR = process.env.Q12_BACK_DIR || path.join(__dirname, 'before', 'back'); fs.mkdirSync(DIR, { recursive: true });   // Q12_BACK_DIR は確かめ用
const DONE = path.join(DIR, 'done.txt');
const sleep = ms => new Promise(s => setTimeout(s, ms)); const pad = n => String(n).padStart(2, '0');
function out(k, v) { if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `${k}=${v}\n`); }
let lastGet = 0;
async function get(url, json, official) {   // 読めたら中身、404 なら null、3回とも読めなければ undefined
  for (let i = 0; i < 3; i++) {
    if (official) { const w = lastGet + GAP - Date.now(); if (w > 0) await sleep(w); lastGet = Date.now(); }
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(30e3) });
      if (r.ok) return json ? await r.json() : await r.text();
      if (r.status === 404) return null;
      console.log('読めない', r.status, url);
    } catch (e) { console.log('読めない', String(e).slice(0, 80), url); }
    await sleep(5000 * (i + 1));
  }
  return undefined;
}
function days() {
  if (FROM.includes(',')) return FROM.split(',').filter(x => /^\d{8}$/.test(x)).sort().reverse();
  if (!/^\d{8}$/.test(FROM) || !/^\d{8}$/.test(TO)) { console.log('日付は YYYYMMDD で'); process.exit(1); }
  const u = s => Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8)), a = [];
  for (let x = u(TO); x >= u(FROM); x -= 864e5) { const d = new Date(x); a.push(`${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`); }
  return a;
}
async function races(ymd) {   // [[場, R], …]。開催がない日は []、読めないときは null（次の回に残す）
  const y = ymd.slice(0, 4);
  const J1 = await get(`https://boatraceopenapi.github.io/api/v1/${y}/${ymd}.json`, true, false);
  const S = J1 && J1.programs && J1.programs.stadiums, a = [];
  if (S) for (const v of Object.keys(S)) for (const k of Object.keys(S[v].races || {})) a.push([Number(v), Number(k)]);
  if (!a.length) {
    const J3 = await get(`https://boatraceopenapi.github.io/programs/v3/${y}/${ymd}.json`, true, false);
    if (J3 && Array.isArray(J3.programs)) for (const p of J3.programs) a.push([Number(p.stadium_number), Number(p.number)]);
    else if (!(J1 === null && J3 === null)) return null;
  }
  return a.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
}
function row(d, v, r, n, ex) {   // ふつうの日の1行：札のある艇だけ
  const o = { d, v, r, n }, p = {}, x = {};
  for (const k of Object.keys(ex.b).sort()) { const z = ex.b[k]; if (z.pr) p[k] = z.pr; if (z.pt && z.pt.length) x[k] = z.pt; }
  if (Object.keys(p).length) o.p = p;
  if (Object.keys(x).length) o.x = x;
  if (ex.lab && ex.lab.length) o.lab = ex.lab;
  if (ex.m && ex.m !== 1800) o.m = ex.m;
  if (ex.antei) o.a = 1;
  return o;
}
(async () => {
  const done = new Set(fs.existsSync(DONE) ? fs.readFileSync(DONE, 'utf8').split('\n').filter(x => x) : []);
  const todo = days().filter(d => PER > 0 || !done.has(d));
  let left = todo.length, stop = '', first = '', last = '', nPage = 0, fails = 0;   // fails は日をまたいで数える（続けて読めない回数）
  console.log('読む日', todo.length, '（済み', done.size, '）間隔', GAP, 'ms');
  for (const ymd of todo) {
    if (Date.now() - t0 > LIMIT) { stop = '時間'; break; }
    const R = await races(ymd);
    if (R === null) { console.log(ymd, '出走表が読めない（次の回に残す）'); continue; }
    const rows = []; let cut = false;
    for (const [v, rno] of (PER > 0 ? R.filter(x => x[1] === 1 || x[1] === 12).slice(0, PER) : R)) {
      if (Date.now() - t0 > LIMIT) { cut = true; break; }
      const html = await get(`${BR}?rno=${rno}&jcd=${pad(v)}&hd=${ymd}`, false, true); nPage++;
      if (html === undefined) { rows.push({ d: ymd, v, r: rno, e: 1 }); if (++fails >= 20) { stop = '公式が続けて読めない'; break; } continue; }
      fails = 0;
      if (html === null) { rows.push({ d: ymd, v, r: rno, e: 404 }); continue; }
      try {
        const pv = B.parse(html), ex = B.extras(html), n = B.count(pv);
        rows.push(PER > 0 ? { d: ymd, v, r: rno, n, len: html.length, ex } : row(ymd, v, rno, n, ex));
      } catch (e) { rows.push({ d: ymd, v, r: rno, e: 'parse' }); }
    }
    if (cut || stop) { if (!stop) stop = '時間'; console.log(ymd, '途中で止めたので、この日の分は捨てる'); break; }
    const e1 = rows.filter(x => x.e === 1).length;
    if (e1 && e1 >= rows.length / 2) { console.log(ymd, '読めないページが多いので、この日は次の回に読み直す', e1, '/', rows.length); continue; }
    const txt = rows.map(x => JSON.stringify(x)).join('\n') + (rows.length ? '\n' : '');
    if (PER > 0) fs.appendFileSync(path.join(DIR, 'probe.jsonl'), txt);
    else { if (rows.length) fs.appendFileSync(path.join(DIR, `ex_${ymd.slice(0, 6)}.jsonl`), txt); fs.appendFileSync(DONE, ymd + '\n'); }
    left--; if (!first) first = ymd; last = ymd;
    const ok = rows.filter(x => x.n >= 5).length, bad = rows.filter(x => x.e).length, part = rows.filter(x => x.x || (x.ex && Object.values(x.ex.b).some(z => z.pt.length))).length;
    console.log(ymd, 'レース', R.length, '読んだ', rows.length, '展示あり', ok, '読めない', bad, '部品交換あり', part);
  }
  if (PER > 0) left = 0;
  if (!first && stop !== '時間') left = 0;   // 1日も進まなかった（出走表が読めない日ばかり）ときは、くり返さない
  if (stop === '公式が続けて読めない') { console.log('公式が続けて読めないので止める（次の回は動かさない）'); left = 0; }
  console.log('おわり', stop || '全部', '残りの日', left, '読んだページ', nPage, '分', ((Date.now() - t0) / 60e3).toFixed(1));
  out('left', left); out('span', first ? `${first}〜${last}` : 'なし');
})().catch(e => { console.error(e); process.exit(1); });
