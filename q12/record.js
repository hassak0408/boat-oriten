// 戻りモデル（オッズを使わない）：毎日の記録
// q12/models.json に並べた目ごとに、まだ記録していない日（START〜前の日）について、BoatraceOpenAPI v1 の1日ファイルを読み、
// 展示の出た全レースの見込みと印（★★・★）、その目の結果を q12/<csv>_年.csv に足し、q12/summary.md を作り直す。
// models.json に hit（確率モデル）がある目は「的中見込み」（その目が来る確率）の列も足す。
// 最後の列は「確定オッズ」（その目の確定オッズ。turnmark のデータが出た日から埋める。出ていない日は次の回にもう一度読む）。
//   node q12/record.js            … 前の日まで
//   Q12_LOCAL_DIR=フォルダ node q12/record.js  … ネットに出ずに、フォルダの YYYYMMDD.json を読む（確かめ用）
//   Q12_TM_DIR=フォルダ … 確定オッズも、フォルダの YYYYMMDD.json（turnmark と同じ形）から読む（確かめ用）
const fs = require('fs');
const path = require('path');
const Q12 = require('./q12core.js');
const DIR = __dirname;
const CFG = JSON.parse(fs.readFileSync(path.join(DIR, 'models.json'), 'utf8'));
const UA = 'boat-oriten (+https://github.com/hassak0408/boat-oriten)';
const VN = {1:'桐生',2:'戸田',3:'江戸川',4:'平和島',5:'多摩川',6:'浜名湖',7:'蒲郡',8:'常滑',9:'津',10:'三国',11:'びわこ',12:'住之江',13:'尼崎',14:'鳴門',15:'丸亀',16:'児島',17:'宮島',18:'徳山',19:'下関',20:'若松',21:'芦屋',22:'福岡',23:'唐津',24:'大村'};
const HEAD = ['日付','場','場名','R','締切','印','見込み','線比5','線比2','p0','p1','p2','結果','戻り'];
const ODDS_COL = '確定オッズ';
const TM_URL = 'https://raw.githubusercontent.com/turnmark/api/gh-pages/docs/v1/';
const ODDS_DAYS = 60;   // 確定オッズの空きを埋めにいく日数（さかのぼり）

function jstToday() { return new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10); }
function addDays(d, n) { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
const dayCache = {};
async function loadDay(d) {
  if (dayCache[d] !== undefined) return dayCache[d];
  const ymd = d.replace(/-/g, '');
  let J = null;
  if (process.env.Q12_LOCAL_DIR) {
    const f = path.join(process.env.Q12_LOCAL_DIR, ymd + '.json');
    J = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
  } else {
    const url = `https://boatraceopenapi.github.io/api/v1/${ymd.slice(0, 4)}/${ymd}.json`;
    for (let i = 0; i < 3 && J === null; i++) {
      try {
        const r = await fetch(url, { headers: { 'User-Agent': UA } });
        if (r.status === 404) break;
        if (r.ok) J = await r.json();
      } catch (e) { /* もう一度 */ }
      if (J === null) await new Promise(s => setTimeout(s, 3000));
    }
  }
  dayCache[d] = J;
  return J;
}
const tmCache = {};
async function loadTM(d) {           // その日の確定オッズ（turnmark）。まだ出ていなければ null
  if (tmCache[d] !== undefined) return tmCache[d];
  const ymd = d.replace(/-/g, '');
  let J = null;
  if (process.env.Q12_TM_DIR) {
    const f = path.join(process.env.Q12_TM_DIR, ymd + '.json');
    J = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : null;
  } else {
    for (let i = 0; i < 2 && J === null; i++) {
      try {
        const r = await fetch(`${TM_URL}${ymd.slice(0, 4)}/${ymd}.json`, { headers: { 'User-Agent': UA } });
        if (r.status === 404) break;
        if (r.ok) J = await r.json();
      } catch (e) { /* もう一度 */ }
      if (J === null) await new Promise(s => setTimeout(s, 2000));
    }
  }
  tmCache[d] = J;
  return J;
}
function finalOdds(TM, v, rno, c) {   // その目の確定オッズ（数）。レースが無い・オッズが無いときは 'なし'
  const race = ((((TM.programs || {}).stadiums || {})[String(v)] || {}).races || {})[String(rno)];
  const o = race && race.odds ? race.odds[c.payout] : null;
  if (!o) return 'なし';
  let a = c.boats[0], b = c.boats[1];
  if (c.payout === 'quinella' && a > b) { const t = a; a = b; b = t; }
  const x = (o[String(a)] || {})[String(b)];
  return (typeof x === 'number' && x > 0) ? String(x) : 'なし';
}
// ファイルの列をいまの形にそろえる（確定オッズの列が無ければ空で足す）
function migrate(f, head) {
  if (!fs.existsSync(f)) return;
  const L = fs.readFileSync(f, 'utf8').split('\n').filter(s => s.trim());
  if (L[0] === head.join(',')) return;
  if (L[0] + ',' + ODDS_COL === head.join(',')) {
    fs.writeFileSync(f, [L[0] + ',' + ODDS_COL].concat(L.slice(1).map(s => s + ',')).join('\n') + '\n');
    console.log(f, 'に確定オッズの列を足した');
  }
}
// 確定オッズの空きを埋める（turnmark が出た日だけ）
async function fillOdds(c, end) {
  const re = new RegExp('^' + c.csv + '_\\d{4}\\.csv$');
  const from = addDays(end, -ODDS_DAYS);
  for (const fn of fs.readdirSync(DIR).filter(x => re.test(x)).sort()) {
    const f = path.join(DIR, fn);
    const L = fs.readFileSync(f, 'utf8').split('\n').filter(s => s.trim());
    const hd = L[0].split(','), di = hd.indexOf('日付'), vi = hd.indexOf('場'), ri = hd.indexOf('R'), oi = hd.indexOf(ODDS_COL);
    if (oi < 0) continue;
    let filled = 0;
    for (let i = 1; i < L.length; i++) {
      const a = L[i].split(',');
      if (a[oi] !== undefined && a[oi] !== '') continue;
      if (a[di] < from || a[di] > end) continue;
      const TM = await loadTM(a[di]);
      if (!TM) continue;
      while (a.length < hd.length) a.push('');
      a[oi] = finalOdds(TM, a[vi], a[ri], c); L[i] = a.join(','); filled++;
    }
    if (filled) { fs.writeFileSync(f, L.join('\n') + '\n'); console.log(c.label, fn, '確定オッズを埋めた行', filled); }
  }
}
// 目の結果：中止は null、目の艇の返還は1.0、的中は払戻÷100
function outcome(race, c) {
  const res = race.result || {};
  const pays = (res.payouts || {})[c.payout] || [];
  const rf = res.refunds || [];
  if (c.boats.some(b => rf.indexOf(b) >= 0)) return ['返還', 1];
  if (!pays.length) return null;
  let amt = 0; pays.forEach(p => { if (p.combination === c.combo) amt += Number(p.amount) || 0; });
  return amt > 0 ? ['的中', amt / 100] : ['外れ', 0];
}
function readAll(prefix) {                // 列はファイルの1行目に合わせて読む（的中見込みの列の有り無しどちらでも）
  const rows = [];
  const re = new RegExp('^' + prefix + '_\\d{4}\\.csv$');
  fs.readdirSync(DIR).filter(f => re.test(f)).sort().forEach(f => {
    const L = fs.readFileSync(path.join(DIR, f), 'utf8').split('\n').filter(s => s.trim());
    const hd = L[0].split(',');
    L.slice(1).forEach(s => { const a = s.split(','); const o = {}; hd.forEach((h, i) => o[h] = a[i]); rows.push(o); });
  });
  return rows;
}
function section(c, M, rows, PM) {
  const out = [`## ${c.label}`, '', `モデル：${M.name}（${M.made}）。★★＝3本の「見込み÷上位2%の線」の平均が1以上、★＝「上位5%の線」で1以上（★★を除く）。1点100円として数える。${c.note ? c.note : ''}` +
    (PM ? `的中見込みのモデル：${PM.name}（${PM.made}）。` : ''), ''];
  const sel = rows.filter(r => r['結果'] !== '中止' && r['結果'] !== '');
  function line(name, R) {
    const n = R.length, hit = R.filter(r => r['結果'] === '的中').length, ret = R.reduce((a, r) => a + Number(r['戻り']), 0);
    return `| ${name} | ${n} | ${hit} | ${n ? (ret / n * 100).toFixed(1) + '%' : '-'} | ${(ret - n).toFixed(1)} |`;
  }
  const bts = r => { const hm = (r['締切'] || '').slice(0, 5); return hm >= '10:00' && hm <= '20:50'; };
  const star = r => r['印'] === '★★' || r['印'] === '★';
  out.push('| 形 | 点 | 的中 | 回収 | 損益（単位） |', '| --- | --- | --- | --- | --- |');
  out.push(line('★★', sel.filter(r => r['印'] === '★★')));
  out.push(line('★以上（★★と★）', sel.filter(star)));
  out.push(line('★以上・締切10:00〜20:50', sel.filter(r => star(r) && bts(r))));
  const pm = c.pmin || 0.25, pok = r => r['的中見込み'] !== undefined && r['的中見込み'] !== '' && Number(r['的中見込み']) >= pm;
  const em = c.evmin || 0.8, odd = r => Number(r[ODDS_COL]) > 0, ev = r => Number(r['的中見込み']) * Number(r[ODDS_COL]);
  if (c.hit) {
    out.push(line(`★★・的中見込み${Math.round(pm * 100)}%以上`, sel.filter(r => r['印'] === '★★' && pok(r))));
    out.push(line(`★以上・的中見込み${Math.round(pm * 100)}%以上`, sel.filter(r => star(r) && pok(r))));
    out.push(line(`★以上・的中見込み${Math.round(pm * 100)}%未満`, sel.filter(r => star(r) && !pok(r))));
    const b2 = sel.filter(r => r['印'] === '★★' && pok(r));
    out.push(line(`★★・的中見込み${Math.round(pm * 100)}%以上・確定オッズで期待値${em}以上（見送りを入れた形）`, b2.filter(r => odd(r) && ev(r) >= em)));
    out.push(line(`★★・的中見込み${Math.round(pm * 100)}%以上・確定オッズで期待値${em}未満（見送った分）`, b2.filter(r => odd(r) && ev(r) < em)));
    out.push(line(`★★・確定オッズで期待値${em}以上`, sel.filter(r => r['印'] === '★★' && odd(r) && ev(r) >= em)));
    const wait = b2.filter(r => !odd(r) && r[ODDS_COL] !== 'なし').length;
    if (wait) out.push(`| （確定オッズ待ち：★★・的中見込み${Math.round(pm * 100)}%以上 ${wait}点） | | | | |`);
  }
  out.push(line(`参考：全部のレースで${c.combo}（欠場がらみを除く）`, sel.filter(r => r['印'] !== '欠場')));
  out.push('', '月ごと（★以上）', '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
  const months = [...new Set(sel.map(r => r['日付'].slice(0, 7)))].sort();
  months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && star(r)))));
  out.push('', '月ごと（★★）', '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
  months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && r['印'] === '★★'))));
  if (c.hit) {
    out.push('', `月ごと（★★・的中見込み${Math.round(pm * 100)}%以上）`, '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
    months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && r['印'] === '★★' && pok(r)))));
  }
  out.push('');
  return out;
}
(async () => {
  const end = addDays(jstToday(), -1);
  const parts = ['# 戻りモデル（オッズを使わない）の記録', ''];
  for (const c of CFG) {
    const M = JSON.parse(fs.readFileSync(path.join(DIR, c.file), 'utf8'));
    const PM = c.hit ? JSON.parse(fs.readFileSync(path.join(DIR, c.hit), 'utf8')) : null;   // 的中見込みのモデル
    const head = (c.hit ? HEAD.concat(['的中見込み']) : HEAD).concat([ODDS_COL]);
    fs.readdirSync(DIR).filter(x => new RegExp('^' + c.csv + '_\\d{4}\\.csv$').test(x)).forEach(x => migrate(path.join(DIR, x), head));
    const done = new Set(readAll(c.csv).map(r => r['日付']));
    let d = c.start, added = 0;
    while (d <= end) {
      if (!done.has(d)) {
        const J = await loadDay(d);
        if (J) {
          const rows = [];
          for (const S of Object.values((J.programs || {}).stadiums || {})) for (const r of Object.values(S.races || {})) {
            const s = Q12.score(M, r, PM);
            if (!s) continue;
            const oc = outcome(r, c) || ['中止', 0];
            const mark = s.tier === 2 ? '★★' : s.tier === 1 ? '★' : (s.absent12 ? '欠場' : '');
            rows.push([d, r.stadium_number, VN[r.stadium_number] || '', r.race_number, String(r.closed_at || '').slice(11, 16), mark,
              s.mean.toFixed(4), s.ratio[0].toFixed(4), s.ratio[1].toFixed(4), ...s.preds.map(x => x.toFixed(4)), oc[0], oc[1],
              ...(PM ? [s.hitp.toFixed(4)] : []), ''].join(','));
          }
          rows.sort();
          const f = path.join(DIR, `${c.csv}_${d.slice(0, 4)}.csv`);
          if (!fs.existsSync(f)) fs.writeFileSync(f, head.join(',') + '\n');
          const hd0 = fs.readFileSync(f, 'utf8').split('\n')[0];
          if (hd0 !== head.join(',')) throw new Error(`${f} の列が違う（${hd0}）。ファイルを作り直してから動かす`);   // 列のずれた行を足さない
          fs.appendFileSync(f, rows.map(s => s + '\n').join(''));
          added += rows.length;
          console.log(c.label, d, 'レース', rows.length, '★★', rows.filter(s => s.includes(',★★,')).length, '★', rows.filter(s => s.includes(',★,')).length);
        } else console.log(c.label, d, 'ファイルなし');
      }
      d = addDays(d, 1);
    }
    await fillOdds(c, end);
    parts.push(...section(c, M, readAll(c.csv), PM));
    console.log(c.label, '足した行', added);
  }
  parts.push(`最終更新：${new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 16).replace('T', ' ')}（日本時間）`);
  fs.writeFileSync(path.join(DIR, 'summary.md'), parts.join('\n') + '\n');
})().catch(e => { console.error(e); process.exit(1); });
