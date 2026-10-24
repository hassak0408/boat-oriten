// 公式サイトの直前情報（beforeinfo）のページの形を見るための見本取り（q12 の通知を早める・BoatraceOpenAPI が遅れたときの代わりにするため）
//   node q12/before_probe.js YYYYMMDD [件数]  … その日の v1 の出走表から場ごとに1R・12Rなどを選び、公式の beforeinfo のページをそのまま q12/before/samples に保存する
//   あわせて同じレースの v1 の直前情報（preview）を samples/YYYYMMDD_v1.json に保存する（読み取りが v1 と同じになるかの確かめ用）。読み始めは2秒に1回まで
const fs = require('fs'); const path = require('path');
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const ymd = process.argv[2], N = Number(process.argv[3] || 8);
const OUT = path.join(__dirname, 'before', 'samples'); fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(s => setTimeout(s, ms)); const pad = n => String(n).padStart(2, '0');
async function get(url, json) {
  for (let i = 0; i < 3; i++) {
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(30e3) }); if (r.ok) return json ? await r.json() : await r.text(); if (r.status === 404) return null; } catch (e) {}
    await sleep(3000);
  }
  return null;
}
(async () => {
  const J = await get(`https://boatraceopenapi.github.io/api/v1/${ymd.slice(0, 4)}/${ymd}.json?t=${Date.now()}`, true);
  if (!J) { console.log('v1 が読めない'); process.exit(1); }
  const S = (J.programs || {}).stadiums || {}, pick = [], keep = {};
  for (const v of Object.keys(S)) { const R = S[v].races || {}; for (const k of ['1', '6', '12']) if (R[k] && pick.length < N) pick.push(R[k]); }
  for (const r of pick) {
    const url = `https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=${r.race_number}&jcd=${pad(r.stadium_number)}&hd=${ymd}`;
    const html = await get(url, false);
    const f = path.join(OUT, `${ymd}_${pad(r.stadium_number)}_${pad(r.race_number)}.html`);
    if (html) { fs.writeFileSync(f, html); console.log('保存', f, html.length); } else console.log('読めない', url);
    keep[`${r.stadium_number}-${r.race_number}`] = { closed_at: r.closed_at, preview: r.preview || null, racers: Object.fromEntries(Object.entries(r.racers || {}).map(([b, x]) => [b, { racer_number: x.racer_number, name: x.name }])) };
    await sleep(2000);
  }
  fs.writeFileSync(path.join(OUT, `${ymd}_v1.json`), JSON.stringify(keep, null, 1));
  console.log('おわり', pick.length);
})().catch(e => { console.error(e); process.exit(1); });
