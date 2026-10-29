// 4号艇のきまり（4号艇が4コースを得意なら1=2を買わない、2026-10-25 確かめ・版12から）の材料：選手×コースの前の365日の成績
//   日ごとの記録：q12/course/YYYYMMDD.csv（reg,course,place。実際の進入1〜6・着1〜6だけ。F・L・転覆・欠場などは数えない）
//     2025-10-01〜2026-10-16 は手元の全レース表から作った（course_backfill.py）。そのあとは毎朝ここで BoatraceOpenAPI v1 の結果から足す
//   今日の表：q12/course4.json（その日より前の365日に4コースから走った数と2着以内の数。通知 boat_q12_alert.gs が朝に読む）
//   ふつう・得意の線：q12/course4_curve.json（全国勝率ごとの4コース2連対率のふつう。2017〜2025年で引いた。2027年1月の作り直しで引き直す）
//   node q12/course4.js fill        … 足りない日を v1 から足して、今日の表を作る（毎朝 Actions）
//   node q12/course4.js table 20261016 … その日の表を作って中身の数だけ出す（確かめ用）
const fs = require('fs');
const path = require('path');
const DIR = __dirname, CD = path.join(DIR, 'course');
const V1 = 'https://boatraceopenapi.github.io/api/v1/';
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const DAYS = 365;
function addDays8(ymd, n) { const t = new Date(Date.UTC(+ymd.slice(0, 4), +ymd.slice(4, 6) - 1, +ymd.slice(6, 8))); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10).replace(/-/g, ''); }
function today8() { return new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10).replace(/-/g, ''); }
// v1 の1日分から、実際に走って着がついた艇（進入1〜6・着1〜6）を [reg, course, place] で
function extract(J) {
  const rows = []; let races = 0;
  for (const S of Object.values(((J || {}).programs || {}).stadiums || {})) for (const r of Object.values(S.races || {})) {
    const res = r.result || {}; let any = false;
    for (const x of Object.values(res.racers || {})) {
      const c = Number(x.course_number), p = Number(x.place_number), reg = Number(x.number);
      if (p >= 1 && p <= 16) any = true;
      if (Number.isInteger(c) && c >= 1 && c <= 6 && Number.isInteger(p) && p >= 1 && p <= 6 && reg > 0) rows.push([reg, c, p]);
    }
    if (any) races++;
  }
  rows.sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  return { rows, races };
}
function readDay(ymd) {
  const f = path.join(CD, ymd + '.csv');
  if (!fs.existsSync(f)) return null;
  return fs.readFileSync(f, 'utf8').split('\n').slice(1).filter(s => s).map(s => s.split(',').map(Number));
}
// その日（ymd）より前の365日（ymd−365 〜 ymd−1）に、そのコースから走った数と2着以内の数（選手ごと）
function windowStats(ymd, course) {
  const R = {}; let days = 0;
  for (let i = DAYS; i >= 1; i--) {
    const rows = readDay(addDays8(ymd, -i)); if (!rows) continue; days++;
    for (const [reg, c, p] of rows) { if (c !== course) continue; const m = R[reg] || (R[reg] = [0, 0]); m[0]++; if (p <= 2) m[1]++; }
  }
  return { R, days };
}
// 4号艇のきまり：4号艇が展示で4コース・前の365日に4コースから10走以上で、4コース2連対率−ふつう が線以上なら「得意」（skip）
function judge(race, R, curve) {
  const b = (race.racers || {})['4'] || {}, p = ((race.preview || {}).racers || {})['4'] || {};
  if (Number(p.course_number) !== 4) return null;
  const reg = Number(b.number), w = Number(b.national_win_rate), s = R[reg] || R[String(reg)];
  if (!s || s[0] < curve.min_n || !isFinite(w) || w <= 0) return null;
  let k = 0; for (let i = 0; i < curve.n_edges; i++) if (curve.edges_from + i * curve.edges_step <= w) k++;
  const normal = curve.normal[k], w2 = s[1] / s[0], d = w2 - normal;
  return { reg, natw: w, n: s[0], top2: s[1], w2, normal, d, skip: d >= curve.th };
}
async function getJSON(url) {
  for (let i = 0; i < 3; i++) {
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(60e3) }); if (r.status === 404) return null; if (r.ok) return await r.json(); } catch (e) { /* もう一度 */ }
    await new Promise(s => setTimeout(s, 3000));
  }
  return null;
}
function writeTable(ymd) {
  const curve = JSON.parse(fs.readFileSync(path.join(DIR, 'course4_curve.json'), 'utf8'));
  const { R, days } = windowStats(ymd, 4);
  const T = {}; let n = 0;
  for (const [reg, s] of Object.entries(R)) if (s[0] >= curve.min_n) { T[reg] = s; n++; }
  const out = { made: `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}`, from: addDays8(ymd, -DAYS), to: addDays8(ymd, -1), days, racers: n, curve, R: T };
  fs.writeFileSync(path.join(DIR, 'course4.json'), JSON.stringify(out));
  console.log('今日の表', out.made, '日数', days, '選手', n);
  return out;
}
module.exports = { extract, windowStats, judge, addDays8, readDay };
if (require.main === module) {
  (async () => {
    const cmd = process.argv[2] || 'fill';
    if (cmd === 'table') { writeTable(process.argv[3] || today8()); return; }
    if (cmd === 'extract') { const J = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')); const { rows, races } = extract(J); console.log('レース', races, '行', rows.length); if (process.argv[4]) fs.writeFileSync(process.argv[4], 'reg,course,place\n' + rows.map(x => x.join(',') + '\n').join('')); return; }
    const today = today8();
    if (!fs.existsSync(CD)) fs.mkdirSync(CD, { recursive: true });
    let fetched = 0;
    for (let i = DAYS + 1; i >= 1 && fetched < 40; i--) {   // 足りない日（古い方から。1回40日まで）
      const d = addDays8(today, -i);
      if (fs.existsSync(path.join(CD, d + '.csv'))) continue;
      const J = await getJSON(`${V1}${d.slice(0, 4)}/${d}.json`); fetched++;
      if (!J) { console.log(d, 'v1 に無い'); continue; }
      const { rows, races } = extract(J);
      if (!races) { console.log(d, '結果がまだ無い'); continue; }
      fs.writeFileSync(path.join(CD, d + '.csv'), 'reg,course,place\n' + rows.map(x => x.join(',') + '\n').join(''));
      console.log(d, 'レース', races, '行', rows.length);
      await new Promise(s => setTimeout(s, 1000));
    }
    writeTable(today);
  })().catch(e => { console.error(e); process.exit(1); });
}
