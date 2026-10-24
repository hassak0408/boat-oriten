// 見本の beforeinfo のページを読んで、v1 の preview と同じになるかを確かめる：node q12/before_test.js q12/before/samples
const fs = require('fs'); const path = require('path'); const B = require('./beforeinfo.js');
const D = process.argv[2] || path.join(__dirname, 'before', 'samples');
let ok = 0, bad = 0;
for (const f of fs.readdirSync(D).filter(x => x.endsWith('_v1.json'))) {
  const ymd = f.slice(0, 8), V = JSON.parse(fs.readFileSync(path.join(D, f), 'utf8'));
  for (const [key, r] of Object.entries(V)) {
    const [v, rno] = key.split('-'); const hf = path.join(D, `${ymd}_${String(v).padStart(2, '0')}_${String(rno).padStart(2, '0')}.html`);
    if (!fs.existsSync(hf) || !r.preview) continue;
    const p = B.parse(fs.readFileSync(hf, 'utf8')), q = r.preview, diffs = [];
    for (const k of ['wind_speed', 'wind_direction_number', 'wave_height', 'weather_number', 'air_temperature', 'water_temperature']) if (p[k] !== q[k]) diffs.push(`${k} ${p[k]}≠${q[k]}`);
    for (let i = 1; i <= 6; i++) { const a = p.racers[String(i)] || {}, b = (q.racers || {})[String(i)] || {};
      for (const k of ['exhibition_time', 'tilt_adjustment', 'course_number', 'start_timing', 'weight', 'weight_adjustment']) if ((a[k] ?? null) !== (b[k] ?? null)) diffs.push(`${i}号艇 ${k} ${a[k]}≠${b[k]}`); }
    if (diffs.length) { bad++; console.log(key, '違う：', diffs.join('、')); } else ok++;
  }
}
console.log('同じ', ok, '違う', bad);
