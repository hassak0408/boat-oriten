// 公式の直前情報の preview（展示を見つけたとき）と v1 の確定した preview で、モデルごとのお得度（線との比、上位2%）を出す → q12/before/cmp3.csv（2026-10-30）
//   単勝1（model_2026A_w1.json）が締切16分前ごろの気象でどれだけずれるかを測るため。node q12/before_cmp3.js
const fs = require('fs'), path = require('path'), Q12 = require('./q12core.js');
const D = path.join(__dirname, 'before'), V1 = 'https://boatraceopenapi.github.io/api/v1/';
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const MS = { w1: 'model_2026A_w1.json', A: 'model_2026A.json', B: 'model_2026A_c10.json', C: 'model_2026A_c6.json' };
const M = {}; for (const [k, f] of Object.entries(MS)) M[k] = JSON.parse(fs.readFileSync(path.join(__dirname, f), 'utf8'));
async function getJSON(url) {
  for (let i = 0; i < 3; i++) {
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(60e3) }); if (r.status === 404) return null; if (r.ok) return await r.json(); } catch (e) { /* もう一度 */ }
    await new Promise(s => setTimeout(s, 3000));
  }
  return null;
}
(async () => {
  const out = ['date,v,rno,closed,' + Object.keys(MS).map(k => `${k}_fin,${k}_off`).join(',')];
  for (const f of fs.readdirSync(D).filter(x => /^pv_\d{8}\.jsonl$/.test(x)).sort()) {
    const ymd = f.slice(3, 11), J = await getJSON(`${V1}${ymd.slice(0, 4)}/${ymd}.json`);
    const S = ((J || {}).programs || {}).stadiums || {};
    for (const line of fs.readFileSync(path.join(D, f), 'utf8').split('\n').filter(s => s)) {
      let o; try { o = JSON.parse(line); } catch (e) { continue; }
      const r = ((S[String(o.v)] || {}).races || {})[String(o.rno)]; if (!r || !r.preview) continue;
      const ro = Object.assign({}, r, { preview: o.preview }), cells = [];
      let okk = true;
      for (const k of Object.keys(MS)) { const a = Q12.score(M[k], r, null), b = Q12.score(M[k], ro, null); if (!a || !b) { okk = false; break; } cells.push(a.ratio[1].toFixed(5), b.ratio[1].toFixed(5)); }
      if (okk) out.push([ymd, o.v, o.rno, String(r.closed_at || '').slice(11, 16), ...cells].join(','));
    }
    await new Promise(s => setTimeout(s, 1000));
  }
  fs.writeFileSync(path.join(D, 'cmp3.csv'), out.join('\n') + '\n'); console.log('行', out.length - 1);
})().catch(e => { console.error(e); process.exit(1); });
