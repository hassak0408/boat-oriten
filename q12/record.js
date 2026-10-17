// 2連複1=2 の戻りモデル：毎日の記録
// まだ記録していない日（Q12_START〜前の日）について、BoatraceOpenAPI v1 の1日ファイルを読み、
// 展示の出た全レースの見込みと印（★★・★）、2連複1=2 の結果を q12/record_年.csv に足し、q12/summary.md を作り直す。
//   node q12/record.js            … 前の日まで
//   Q12_LOCAL_DIR=フォルダ node q12/record.js  … ネットに出ずに、フォルダの YYYYMMDD.json を読む（確かめ用）
const fs = require('fs');
const path = require('path');
const Q12 = require('./q12core.js');
const DIR = __dirname;
const MODEL = JSON.parse(fs.readFileSync(path.join(DIR, 'model_2026A.json'), 'utf8'));
const START = process.env.Q12_START || '2026-10-01';
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const VN = {1:'桐生',2:'戸田',3:'江戸川',4:'平和島',5:'多摩川',6:'浜名湖',7:'蒲郡',8:'常滑',9:'津',10:'三国',11:'びわこ',12:'住之江',13:'尼崎',14:'鳴門',15:'丸亀',16:'児島',17:'宮島',18:'徳山',19:'下関',20:'若松',21:'芦屋',22:'福岡',23:'唐津',24:'大村'};
const HEAD = ['日付','場','場名','R','締切','印','見込み','線比5','線比2','p0','p1','p2','結果','戻り'];

function jstToday() { return new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10); }
function addDays(d, n) { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
async function loadDay(d) {
  const ymd = d.replace(/-/g, '');
  if (process.env.Q12_LOCAL_DIR) {
    const f = path.join(process.env.Q12_LOCAL_DIR, ymd + '.json');
    return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
  }
  const url = `https://boatraceopenapi.github.io/api/v1/${ymd.slice(0, 4)}/${ymd}.json`;
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(url, { headers: { 'User-Agent': UA } });
      if (r.status === 404) return null;
      if (r.ok) return await r.json();
    } catch (e) { /* もう一度 */ }
    await new Promise(s => setTimeout(s, 3000));
  }
  throw new Error('読めなかった ' + url);
}
// 2連複1=2 の結果：中止は null、1号艇か2号艇の返還は1.0、的中は払戻÷100
function outcome(race) {
  const res = race.result || {};
  const pays = (res.payouts || {}).quinella || [];
  const rf = res.refunds || [];
  if (rf.indexOf(1) >= 0 || rf.indexOf(2) >= 0) return ['返還', 1];
  if (!pays.length) return null;
  let amt = 0; pays.forEach(p => { if (p.combination === '1=2') amt += Number(p.amount) || 0; });
  return amt > 0 ? ['的中', amt / 100] : ['外れ', 0];
}
function csvFile(y) { return path.join(DIR, `record_${y}.csv`); }
function readAll() {
  const rows = [];
  fs.readdirSync(DIR).filter(f => /^record_\d{4}\.csv$/.test(f)).sort().forEach(f => {
    const L = fs.readFileSync(path.join(DIR, f), 'utf8').split('\n').filter(s => s.trim());
    L.slice(1).forEach(s => { const a = s.split(','); const o = {}; HEAD.forEach((h, i) => o[h] = a[i]); rows.push(o); });
  });
  return rows;
}
function summary(rows) {
  const out = ['# 2連複1=2（戻りモデル）の記録', '', `モデル：${MODEL.name}（${MODEL.made}）。★★＝3本の「見込み÷上位2%の線」の平均が1以上、★＝「上位5%の線」で1以上（★★を除く）。1点100円として数える。`, ''];
  const sel = rows.filter(r => r['結果'] !== '中止' && r['結果'] !== '');
  function line(name, R) {
    const n = R.length, hit = R.filter(r => r['結果'] === '的中').length, ret = R.reduce((a, r) => a + Number(r['戻り']), 0);
    return `| ${name} | ${n} | ${hit} | ${n ? (ret / n * 100).toFixed(1) + '%' : '-'} | ${(ret - n).toFixed(1)} |`;
  }
  const bts = r => { const hm = (r['締切'] || '').slice(0, 5); return hm >= '10:00' && hm <= '20:50'; };
  out.push('| 形 | 点 | 的中 | 回収 | 損益（単位） |', '| --- | --- | --- | --- | --- |');
  out.push(line('★★', sel.filter(r => r['印'] === '★★')));
  out.push(line('★以上（★★と★）', sel.filter(r => r['印'] === '★★' || r['印'] === '★')));
  out.push(line('★以上・締切10:00〜20:50', sel.filter(r => (r['印'] === '★★' || r['印'] === '★') && bts(r))));
  out.push(line('参考：全部のレースで1=2（欠場がらみを除く）', sel.filter(r => r['印'] !== '欠場')));
  out.push('', '## 月ごと（★以上）', '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
  const months = [...new Set(sel.map(r => r['日付'].slice(0, 7)))].sort();
  months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && (r['印'] === '★★' || r['印'] === '★')))));
  out.push('', `最終更新：${new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 16).replace('T', ' ')}（日本時間）`);
  fs.writeFileSync(path.join(DIR, 'summary.md'), out.join('\n') + '\n');
}
(async () => {
  const done = new Set(readAll().map(r => r['日付']));
  const end = addDays(jstToday(), -1);
  let d = START, added = 0;
  while (d <= end) {
    if (!done.has(d)) {
      const J = await loadDay(d);
      if (J) {
        const rows = [];
        for (const S of Object.values((J.programs || {}).stadiums || {})) for (const r of Object.values(S.races || {})) {
          const s = Q12.score(MODEL, r);
          if (!s) continue;
          const oc = outcome(r) || ['中止', 0];
          const mark = s.tier === 2 ? '★★' : s.tier === 1 ? '★' : (s.absent12 ? '欠場' : '');
          rows.push([d, r.stadium_number, VN[r.stadium_number] || '', r.race_number, String(r.closed_at || '').slice(11, 16), mark,
            s.mean.toFixed(4), s.ratio[0].toFixed(4), s.ratio[1].toFixed(4), ...s.preds.map(x => x.toFixed(4)), oc[0], oc[1]].join(','));
        }
        rows.sort();
        const f = csvFile(d.slice(0, 4));
        if (!fs.existsSync(f)) fs.writeFileSync(f, HEAD.join(',') + '\n');
        fs.appendFileSync(f, rows.map(s => s + '\n').join(''));
        added += rows.length;
        console.log(d, 'レース', rows.length, '★★', rows.filter(s => s.includes(',★★,')).length, '★', rows.filter(s => s.includes(',★,')).length);
      } else console.log(d, 'ファイルなし');
    }
    d = addDays(d, 1);
  }
  summary(readAll());
  console.log('足した行', added);
})().catch(e => { console.error(e); process.exit(1); });
