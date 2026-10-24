// 公式サイトの直前情報（beforeinfo）に展示が出る時刻と、BoatraceOpenAPI v1 に出る時刻をくらべる記録（q12 の通知を早められるかの確かめ）
//   node q12/before_log.js 分 … 今日（日本時間）の全レースについて、締切の25分前〜5分前のあいだ、公式のページを1分ごとに読み、展示タイムが5艇以上そろった時刻を書く。
//   v1 は5分ごとに読み直し、展示がそろったのを見つけた時刻を書く。読み始めは全体で2秒に1回まで。決めた分だけ動いて止まる（全部締め切られたら早く止まる）
//   出力：q12/before/log_YYYYMMDD.csv（日付,場,R,締切,公式で見つけた時刻,締切の何分前,v1で見つけた時刻,締切の何分前,その回の最初の読みか）
//         q12/before/pv_YYYYMMDD.jsonl（公式のページから作った preview。あとで v1 の最後の形とくらべる）
const fs = require('fs'); const path = require('path'); const { execSync } = require('child_process');
const B = require('./beforeinfo.js');
const DIR = path.join(__dirname, 'before'); const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const V1 = 'https://boatraceopenapi.github.io/api/v1/', BR = 'https://www.boatrace.jp/owpc/pc/race/beforeinfo';
const LIMIT = Number(process.argv[2] || 340) * 60e3, t0 = Date.now();
const sleep = ms => new Promise(s => setTimeout(s, ms)); const pad = n => String(n).padStart(2, '0');
function jst(ms) { const d = new Date(ms + 9 * 3600e3); return { ymd: `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`, hms: `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}` }; }
let next = 0; async function slot() { for (;;) { const t = Date.now(); if (t >= next) { next = t + 2000; return; } await sleep(next - t); } }
async function get(url, json) {
  for (let i = 0; i < 2; i++) {
    await slot();
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(30e3) }); if (r.ok) return json ? await r.json() : await r.text(); if (r.status === 404) return null; } catch (e) {}
    await sleep(3000);
  }
  return null;
}
function nEx(r) { const P = ((r || {}).preview || {}).racers || {}; let n = 0; for (let i = 1; i <= 6; i++) if (Number((P[String(i)] || {}).exhibition_time) > 0) n++; return n; }
function save(msg) {
  if (!process.env.GITHUB_ACTIONS) return;
  const sh = c => execSync(c, { stdio: 'inherit', shell: '/bin/bash', cwd: path.join(__dirname, '..') });
  try {
    sh(`git config user.name 'github-actions[bot]' && git config user.email '41898282+github-actions[bot]@users.noreply.github.com'`);
    sh(`git add q12/before && (git diff --cached --quiet || git commit -q -m "${msg}")`);
    for (let i = 0; i < 5; i++) { try { sh('git push -q origin HEAD:main'); return; } catch (e) { try { sh('git fetch -q origin main && (git rebase -q origin/main || git rebase --abort)'); } catch (e2) {} } }
  } catch (e) { console.log('途中の保存に失敗', String(e).slice(0, 200)); }
}
(async () => {
  const ymd = jst(Date.now()).ymd; fs.mkdirSync(DIR, { recursive: true });
  const LOG = path.join(DIR, `log_${ymd}.csv`), PV = path.join(DIR, `pv_${ymd}.jsonl`);
  if (!fs.existsSync(LOG)) fs.writeFileSync(LOG, 'date,v,rno,closed_at,official_seen,official_mins,v1_seen,v1_mins,first_read\n');
  const rec = {};   // key → {official, offMins, v1, v1Mins, first}
  let races = [], lastSched = 0, firstSched = true, lastSave = Date.now();
  const lastPoll = {};
  const flush = () => {   // 両方そろった（または締切を過ぎた）レースを書き出す
    const lines = [];
    for (const r of races) {
      const k = `${r.v}-${r.rno}`, o = rec[k]; if (!o || o.done) continue;
      if ((o.official && o.v1) || Date.now() > r.close + 60e3) {
        lines.push([ymd, r.v, r.rno, r.closed, o.official || '', o.offMins ?? '', o.v1 || '', o.v1Mins ?? '', o.first ? 1 : 0].join(',')); o.done = true;
      }
    }
    if (lines.length) fs.appendFileSync(LOG, lines.join('\n') + '\n');
  };
  for (;;) {
    const t = Date.now();
    if (t - t0 > LIMIT) { console.log('時間になったので止める'); break; }
    if (t - lastSched > 5 * 60e3 || !races.length) {
      const J = await get(`${V1}${ymd.slice(0, 4)}/${ymd}.json?t=${Date.now()}`, true), out = [];
      const S = ((J || {}).programs || {}).stadiums || {};
      for (const v of Object.keys(S)) for (const r of Object.values((S[v] || {}).races || {})) {
        const c = String(r.closed_at || ''); if (!/^\d{4}-\d\d-\d\d \d\d:\d\d/.test(c)) continue;
        const o = { v: Number(r.stadium_number), rno: Number(r.race_number), closed: c, close: Date.parse(c.replace(' ', 'T') + '+09:00'), nex: nEx(r) };
        out.push(o); const k = `${o.v}-${o.rno}`; rec[k] = rec[k] || {};
        if (o.nex >= 5 && !rec[k].v1) { const now = Date.now(); rec[k].v1 = jst(now).hms; rec[k].v1Mins = ((o.close - now) / 60e3).toFixed(2); if (firstSched) rec[k].first = true; }
      }
      if (out.length) { races = out; firstSched = false; } else if (!races.length) { console.log('今日のレースが読めない'); await sleep(120e3); if (Date.now() - t0 > 180 * 60e3) break; continue; }
      lastSched = t;
    }
    if (races.every(r => r.close < t)) { console.log('今日のレースはすべて締め切られた'); flush(); break; }
    // 締切25〜5分前で、公式でまだ見つけていないレースを、1分ごとに読む（締切の早い順）
    const due = races.filter(r => { const k = `${r.v}-${r.rno}`; return !(rec[k] || {}).official && t >= r.close - 25 * 60e3 && t <= r.close - 5 * 60e3 && (!lastPoll[k] || t - lastPoll[k] >= 60e3); }).sort((a, b) => a.close - b.close);
    for (const r of due) {
      const k = `${r.v}-${r.rno}`; lastPoll[k] = Date.now();
      const html = await get(`${BR}?rno=${r.rno}&jcd=${pad(r.v)}&hd=${ymd}`, false); if (!html) continue;
      let pv; try { pv = B.parse(html); } catch (e) { continue; }
      if (B.count(pv) >= 5) {
        const now = Date.now(); rec[k].official = jst(now).hms; rec[k].offMins = ((r.close - now) / 60e3).toFixed(2);
        fs.appendFileSync(PV, JSON.stringify({ v: r.v, rno: r.rno, at: jst(now).hms, mins: rec[k].offMins, preview: pv }) + '\n');
      }
    }
    flush();
    if (Date.now() - lastSave > 30 * 60e3) { save(`q12：直前情報の時刻 ${ymd}（途中・${jst(Date.now()).hms.slice(0, 5)}）`); lastSave = Date.now(); }
    await sleep(due.length ? 1000 : 10e3);
  }
  flush();
  const left = races.filter(r => r.close > Date.now()).length;
  console.log('まだ締め切られていないレース', left, `${Math.round((Date.now() - t0) / 60e3)}分`);
  if (process.env.GITHUB_OUTPUT) fs.appendFileSync(process.env.GITHUB_OUTPUT, `left=${left}\nymd=${ymd}\n`);
})().catch(e => { console.error(e); process.exit(1); });
