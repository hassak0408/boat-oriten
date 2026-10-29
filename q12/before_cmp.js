// 公式の直前情報から作った preview（q12/before/pv_日付.jsonl、展示を見つけたときのもの）を、その日の v1 の preview（あとで確定したもの）とくらべる
//   選手の数字（展示タイム・チルト・体重・調整重量・進入・展示ST）は同じになるはず。気象（風・波・天候・気温・水温）は時刻がずれると変わることがある
//   node q12/before_cmp.js → q12/before/cmp.txt
const fs = require('fs'), path = require('path');
const D = path.join(__dirname, 'before'), V1 = 'https://boatraceopenapi.github.io/api/v1/';
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
async function getJSON(url) {
  for (let i = 0; i < 3; i++) {
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(60e3) }); if (r.status === 404) return null; if (r.ok) return await r.json(); } catch (e) { /* もう一度 */ }
    await new Promise(s => setTimeout(s, 3000));
  }
  return null;
}
(async () => {
  const RK = ['exhibition_time', 'tilt_adjustment', 'weight', 'weight_adjustment', 'course_number', 'start_timing'];
  const WK = ['wind_speed', 'wind_direction_number', 'wave_height', 'weather_number', 'air_temperature', 'water_temperature'];
  const tot = { races: 0, racerSame: 0, wxSame: 0, noV1: 0 }, byKey = {}, ex = [];
  for (const f of fs.readdirSync(D).filter(x => /^pv_\d{8}\.jsonl$/.test(x)).sort()) {
    const ymd = f.slice(3, 11), J = await getJSON(`${V1}${ymd.slice(0, 4)}/${ymd}.json`);
    const S = ((J || {}).programs || {}).stadiums || {};
    for (const line of fs.readFileSync(path.join(D, f), 'utf8').split('\n').filter(s => s)) {
      const o = JSON.parse(line), r = ((S[String(o.v)] || {}).races || {})[String(o.rno)];
      if (!r || !r.preview) { tot.noV1++; continue; }
      tot.races++;
      const p = o.preview, q = r.preview; let rs = true, ws = true;
      for (let i = 1; i <= 6; i++) { const a = (p.racers || {})[String(i)] || {}, b = (q.racers || {})[String(i)] || {};
        for (const k of RK) if ((a[k] ?? null) !== (b[k] ?? null)) { rs = false; byKey[k] = (byKey[k] || 0) + 1; if (ex.length < 30) ex.push(`${ymd} ${o.v}-${o.rno} ${i}号艇 ${k} 公式${a[k]}・v1 ${b[k]}`); } }
      for (const k of WK) if ((p[k] ?? null) !== (q[k] ?? null)) { ws = false; byKey[k] = (byKey[k] || 0) + 1; }
      if (rs) tot.racerSame++; if (ws) tot.wxSame++;
    }
    await new Promise(s => setTimeout(s, 1000));
  }
  const out = [`くらべたレース ${tot.races}（v1 に無い ${tot.noV1}）`, `選手の数字が全部同じ ${tot.racerSame}（${(tot.racerSame / tot.races * 100).toFixed(1)}%）`,
    `気象が全部同じ ${tot.wxSame}（${(tot.wxSame / tot.races * 100).toFixed(1)}%）`, '違った項目（のべ）：' + JSON.stringify(byKey), '選手の数字が違った例：', ...ex];
  fs.writeFileSync(path.join(D, 'cmp.txt'), out.join('\n') + '\n'); console.log(out.join('\n'));
})().catch(e => { console.error(e); process.exit(1); });
