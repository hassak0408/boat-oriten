// 公式の直前情報（展示を見つけたとき＝締切の約16分前）の preview で計算した通知と、v1 の確定した preview で計算した通知をくらべる
//   選手の数字は同じ（before_cmp.js）。違うのは気象（風・波・天候・気温・水温）で、それで ★★ や通知が変わるかを見る
//   node q12/before_cmp2.js → q12/before/cmp2.txt
const fs = require('fs'), path = require('path'), Q12 = require('./q12core.js');
const D = path.join(__dirname, 'before'), V1 = 'https://boatraceopenapi.github.io/api/v1/';
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const rd = f => JSON.parse(fs.readFileSync(path.join(__dirname, f), 'utf8'));
const MA = rd('model_2026A.json'), MB = rd('model_2026A_c10.json'), MC = rd('model_2026A_c6.json'), PM = rd('model_2026A_hit.json');
async function getJSON(url) {
  for (let i = 0; i < 3; i++) {
    try { const r = await fetch(url, { headers: { 'User-Agent': UA }, signal: AbortSignal.timeout(60e3) }); if (r.status === 404) return null; if (r.ok) return await r.json(); } catch (e) { /* もう一度 */ }
    await new Promise(s => setTimeout(s, 3000));
  }
  return null;
}
function decide(r) {
  const a = Q12.score(MA, r, null), b = Q12.score(MB, r, PM), c = Q12.score(MC, r, null);
  if (!a || !b || !c) return null;
  const hm = String(r.closed_at || '').slice(11, 16), win = hm >= '10:00' && hm <= '20:50';
  const parts = [];
  if (b.tier === 2 && b.hitp >= 0.25) parts.push('安定'); if (a.tier === 2) parts.push('配当'); if (c.tier === 2) parts.push('的中');
  return { win, parts, ra: a.ratio[1], rb: b.ratio[1], rc: c.ratio[1], hp: b.hitp };
}
(async () => {
  let n = 0, both = 0, onlyF = 0, onlyO = 0, none = 0; const dA = [], dB = [], dC = [], dP = [], ex = [];
  for (const f of fs.readdirSync(D).filter(x => /^pv_\d{8}\.jsonl$/.test(x)).sort()) {
    const ymd = f.slice(3, 11), J = await getJSON(`${V1}${ymd.slice(0, 4)}/${ymd}.json`);
    const S = ((J || {}).programs || {}).stadiums || {};
    for (const line of fs.readFileSync(path.join(D, f), 'utf8').split('\n').filter(s => s)) {
      const o = JSON.parse(line), r = ((S[String(o.v)] || {}).races || {})[String(o.rno)];
      if (!r || !r.preview) continue;
      const rf = r, ro = Object.assign({}, r, { preview: o.preview });
      const F = decide(rf), O = decide(ro); if (!F || !O || !F.win) continue;
      n++; dA.push(O.ra - F.ra); dB.push(O.rb - F.rb); dC.push(O.rc - F.rc); dP.push(O.hp - F.hp);
      const nf = F.parts.length > 0, no = O.parts.length > 0;
      if (nf && no) both++; else if (nf) onlyF++; else if (no) onlyO++; else none++;
      if (nf !== no && ex.length < 20) ex.push(`${ymd} ${o.v}-${o.rno} 確定の気象：${F.parts.join('・') || 'なし'}（お得度 A${F.ra.toFixed(3)} B${F.rb.toFixed(3)} C${F.rc.toFixed(3)}）／公式の気象：${O.parts.join('・') || 'なし'}（A${O.ra.toFixed(3)} B${O.rb.toFixed(3)} C${O.rc.toFixed(3)}）`);
    }
    await new Promise(s => setTimeout(s, 1000));
  }
  const mad = x => (x.reduce((a, v) => a + Math.abs(v), 0) / x.length).toFixed(4), q = (x, p) => { const s = [...x].sort((a, b) => a - b); return s[Math.floor(p * (s.length - 1))].toFixed(4); };
  const out = [`レース（締切10:00〜20:50）${n}`, `通知：両方 ${both}・確定の気象だけ ${onlyF}・公式の気象だけ ${onlyO}・どちらも無し ${none}`,
    `お得度の差（公式−確定）の絶対値の平均：配当型 ${mad(dA)}・安定型 ${mad(dB)}・的中型 ${mad(dC)}／来る確率 ${mad(dP)}`,
    `お得度の差の5%点・95%点：配当型 ${q(dA, 0.05)}〜${q(dA, 0.95)}・安定型 ${q(dB, 0.05)}〜${q(dB, 0.95)}・的中型 ${q(dC, 0.05)}〜${q(dC, 0.95)}`, '通知が変わった例：', ...ex];
  fs.writeFileSync(path.join(D, 'cmp2.txt'), out.join('\n') + '\n'); console.log(out.join('\n'));
})().catch(e => { console.error(e); process.exit(1); });
