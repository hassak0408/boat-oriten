// 1=2お得レース通知（オッズを使わない）：毎日の記録（名前は2026-10-23に付け直し：お得度＝線との比、来る確率＝的中見込み、安定型＝B、配当型＝A、的中型＝C、勝負レース＝強い通知）
// q12/models.json に並べた目ごとに、まだ記録していない日（START〜前の日）について、BoatraceOpenAPI v1 の1日ファイルを読み、
// 展示の出た全レースの見込みと印（★★・★）、その目の結果を q12/<csv>_年.csv に足し、q12/summary.md を作り直す。
// models.json に hit（確率モデル）がある目は「的中見込み」（その目が来る確率＝来る確率。列の名前は前のまま）の列も足す。
// 最後の列は「確定オッズ」（その目の確定オッズ。turnmark のデータが出た日から埋める。出ていない日は次の回にもう一度読む）。
//   node q12/record.js            … 前の日まで
//   Q12_LOCAL_DIR=フォルダ node q12/record.js  … ネットに出ずに、フォルダの YYYYMMDD.json を読む（確かめ用）
//   Q12_TM_DIR=フォルダ … 確定オッズも、フォルダの YYYYMMDD.json（turnmark と同じ形）から読む（確かめ用）
const fs = require('fs');
const path = require('path');
const Q12 = require('./q12core.js');
const C4 = require('./course4.js');   // 4号艇のきまり（版12）
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
  const out = [`## ${c.label}`, '', `モデル：${M.name}（${M.made}）。★★＝お得度（払戻の見込み÷お得なレースの上位2%の線、3本の平均）が1.00以上、★＝上位5%の線で1以上（★★を除く）。1点100円として数える。${c.note ? c.note : ''}` +
    (PM ? `来る確率のモデル：${PM.name}（${PM.made}）。` : ''), ''];
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
    out.push(line(`★★・来る確率${Math.round(pm * 100)}%以上`, sel.filter(r => r['印'] === '★★' && pok(r))));
    out.push(line(`★以上・来る確率${Math.round(pm * 100)}%以上`, sel.filter(r => star(r) && pok(r))));
    out.push(line(`★以上・来る確率${Math.round(pm * 100)}%未満`, sel.filter(r => star(r) && !pok(r))));
    const b2 = sel.filter(r => r['印'] === '★★' && pok(r));
    out.push(line(`★★・来る確率${Math.round(pm * 100)}%以上・確定オッズで期待値${em}以上（参考：確定オッズでの見送り。通知では使わない）`, b2.filter(r => odd(r) && ev(r) >= em)));
    out.push(line(`★★・来る確率${Math.round(pm * 100)}%以上・確定オッズで期待値${em}未満（参考：その見送った分）`, b2.filter(r => odd(r) && ev(r) < em)));
    out.push(line(`★★・確定オッズで期待値${em}以上`, sel.filter(r => r['印'] === '★★' && odd(r) && ev(r) >= em)));
    const wait = b2.filter(r => !odd(r) && r[ODDS_COL] !== 'なし').length;
    if (wait) out.push(`| （確定オッズ待ち：★★・来る確率${Math.round(pm * 100)}%以上 ${wait}点） | | | | |`);
  }
  out.push(line(`参考：全部のレースで${c.combo}（欠場がらみを除く）`, sel.filter(r => r['印'] !== '欠場')));
  out.push('', '月ごと（★以上）', '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
  const months = [...new Set(sel.map(r => r['日付'].slice(0, 7)))].sort();
  months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && star(r)))));
  out.push('', '月ごと（★★）', '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
  months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && r['印'] === '★★'))));
  if (c.hit) {
    out.push('', `月ごと（★★・来る確率${Math.round(pm * 100)}%以上）`, '', '| 月 | 点 | 的中 | 回収 | 損益 |', '| --- | --- | --- | --- | --- |');
    months.forEach(m => out.push(line(m, sel.filter(r => r['日付'].startsWith(m) && r['印'] === '★★' && pok(r)))));
  }
  out.push('');
  return out;
}
function topU(R, end, CADO, PV) {   // summary.md のいちばん上：いまの買い方（全部＝安定型B＋配当型A＋的中型C）の通算・月ごと・直近7日のレース。R＝{A,B,C}：各モデルの行。CADO＝4号艇のきまりの判定、PV＝公式の preview での印（どちらも 日付|場|R → 行）
  // 版12を貼った日（はっさくさんに聞いて入れる）。この日から ①4号艇がカド得意の分を買った分から外す ②印を、通知と同じ公式の preview（展示を見つけたとき）で出したものに替える（その記録が無いレースは v1 の確定した preview のまま）
  const CADO_FROM = process.env.Q12_CADO_FROM || '';
  const win = r => { const hm = (r['締切'] || '').slice(0, 5); return hm >= '10:00' && hm <= '20:50'; };
  const ok = r => r['結果'] !== '中止' && r['結果'] !== '' && win(r);
  const pick = { B: r => r['印'] === '★★' && Number(r['的中見込み']) >= 0.25, A: r => r['印'] === '★★', C: r => r['印'] === '★★' };
  const TAG = { B: '安定', A: '配当', C: '的中' };
  const U = new Map();
  ['B', 'A', 'C'].forEach(k => (R[k] || []).forEach(r => {
    if (!ok(r) || !pick[k](r)) return;
    const key = r['日付'] + '|' + r['場'] + '|' + r['R'];
    const u = U.get(key) || Object.assign({}, r, { 選ばれ方: '', 強さ: 0 });
    u['選ばれ方'] += (u['選ばれ方'] ? '・' : '') + TAG[k]; u['強さ'] = Math.max(u['強さ'], Number(r['線比2']) || 0); U.set(key, u);   // 強さ＝お得度（選ばれた形の線との比の一番高いもの）
  }));
  // 公式の preview の印があるレースは、その印で選び直した形（Upv、版12の通知と同じ判断）。CADO_FROM（版12を貼った日）から、買った分はこちらで数える
  const Upv = new Map(U);
  if (PV) {
    for (const key of [...Upv.keys()]) if (PV.has(key)) Upv.delete(key);
    for (const [key, p] of PV) {
      if (!ok(p)) continue;
      const tags = [], st = [];
      if (p['安定'] === '★★' && Number(p['来る確率']) >= 0.25) { tags.push('安定'); st.push(Number(p['安定比'])); }
      if (p['配当'] === '★★') { tags.push('配当'); st.push(Number(p['配当比'])); }
      if (p['的中'] === '★★') { tags.push('的中'); st.push(Number(p['的中比'])); }
      if (tags.length) Upv.set(key, { '日付': p['日付'], '場': p['場'], '場名': p['場名'], 'R': p['R'], '締切': p['締切'], '結果': p['結果'], '戻り': p['戻り'], '的中見込み': p['来る確率'], '選ばれ方': tags.join('・'), '強さ': Math.max(...st), '公式': 1 });
    }
  }
  const Ufin = new Map(U);   // 確定の preview で選んだ形（確かめと同じ）
  if (CADO_FROM && PV) { for (const key of [...U.keys()]) if (U.get(key)['日付'] >= CADO_FROM) U.delete(key); for (const [key, u] of Upv) if (u['日付'] >= CADO_FROM) U.set(key, u); }
  // 4号艇のきまり（版12）：4号艇がカド得意なら買わない。CADO_FROM（版12を貼った日）から、その分を「買った分」から外す。それまでは参考に数えるだけ
  const isCado = r => { const c = (CADO || new Map()).get(r['日付'] + '|' + r['場'] + '|' + r['R']); return !!(c && c['得意'] === '1'); };
  const S0 = [...U.values()].sort((a, b) => (a['日付'] + a['締切']).localeCompare(b['日付'] + b['締切']));
  const S = S0.filter(r => !(CADO_FROM && r['日付'] >= CADO_FROM && isCado(r)));
  const SC = S0.filter(isCado);   // 4号艇がカド得意の分（10月1日から。版12で買わない分）
  const sum = X => ({ n: X.length, hit: X.filter(r => r['結果'] === '的中').length, ret: X.reduce((a, r) => a + Number(r['戻り']), 0) });
  const yen = x => (x >= 0 ? '+' : '−') + Math.round(Math.abs(x) * 100).toLocaleString('ja-JP') + '円';
  const roi = t => t.n ? (t.ret / t.n * 100).toFixed(1) + '%' : '-';
  const FROM = '2026-10-23';   // 全部（安定＋配当＋的中）にした日（その前は安定型だけで買っていた）
  const STRONG = 1.1, SWEET = [0.25, 0.32], STRONG_UNITS = 2, SUMMER_ONE = true;   // 勝負レース（お得度1.10以上・または来る確率25〜32%）は2点・7〜9月は1点（通知の STRONG・SWEET・STRONG_UNITS・SUMMER_ONE と同じ）
  const pOf = r => Number(r['的中見込み']);
  const strong = r => r['強さ'] >= STRONG || (pOf(r) >= SWEET[0] && pOf(r) < SWEET[1]);
  const summer = r => SUMMER_ONE && ['07', '08', '09'].includes(String(r['日付']).slice(5, 7));   // 7〜9月は勝負レースも1点（5年とも7〜9月の勝負レースは100%未満。前の年までで決める確かめで損益が増えた、2026-10-23 夜）
  const units = r => (strong(r) && !summer(r)) ? STRONG_UNITS : 1;
  const sumU = X => ({ n: X.reduce((a, r) => a + units(r), 0), ret: X.reduce((a, r) => a + units(r) * Number(r['戻り']), 0) });
  const t = sum(S.filter(r => r['日付'] >= FROM)), t0 = sum(S.filter(r => r['日付'] < FROM)), tb = sum(S.filter(r => r['選ばれ方'].includes('安定')));
  const tu = sumU(S.filter(r => r['日付'] >= FROM)), ts = sum(S.filter(r => strong(r))), tsu = sumU(S);
  // 撤退ライン（stop_line.json）：買い始め（FROM）からの通算の損益（勝負レースは2点・7〜9月は1点）が、効いているなら2,000点までに一度でも割る見込みが約6%（撤退）・約11%（注意）の線
  let lineTxt = '';
  try {
    const J = JSON.parse(fs.readFileSync(path.join(DIR, 'stop_line.json'), 'utf8'));
    const at = (arr, n) => { const g = J.grid; if (n <= g[0]) return arr[0]; if (n >= g[g.length - 1]) return arr[arr.length - 1];
      const i = g.findIndex(x => x >= n); const f = (n - g[i - 1]) / (g[i] - g[i - 1]); return arr[i - 1] + f * (arr[i] - arr[i - 1]); };
    const pl = (tu.ret - tu.n) * 100, st = at(J.stop, tu.n), wa = at(J.warn, tu.n);
    const state = !tu.n ? 'まだ買っていない' : pl < st ? '撤退ラインを割った → 買うのを止めて、モデルを確かめ直す' : pl < wa ? '注意ラインを割った → 勝負レースも1点に戻す（STRONG_UNITS＝1）か、安定型だけ（RULE＝安定）にして様子を見る' : 'ふつうのぶれの中';
    const keys = [100, 200, 500, 1000].map(n => `${n}点で${yen(at(J.stop, n) / 100)}`).join('・');
    lineTxt = (tu.n ? `撤退ライン：${FROM}から ${tu.n}点で ${yen(st / 100)}（注意ライン ${yen(wa / 100)}）。いまの損益 ${yen(pl / 100)} → ${state}。` : `撤退ライン：${FROM}からの通算の損益で見る（${keys}。まだ買っていない）。`) +
      '（効いていても、2,000点までに一度でも撤退ラインを割る見込みは約6%・注意ラインは約11%。75点で−2,000円ほどの負けは確かめの5年でも年に3〜4回あった）';
  } catch (e) { lineTxt = ''; }
  // 勝ち幅がある見込み（edge_prior.json）：確かめから置いた「本当の回収」の見込み（平均・ばらつき）を、10月1日からの実際の成績で更新し、100%より上である見込みを出す
  let edgeTxt = '';
  try {
    const E = JSON.parse(fs.readFileSync(path.join(DIR, 'edge_prior.json'), 'utf8'));
    const X = S.filter(r => r['日付'] >= (E.from || '2026-10-01'));
    const su = X.reduce((a, r) => a + units(r), 0), su2 = X.reduce((a, r) => a + units(r) * units(r), 0), sr = X.reduce((a, r) => a + units(r) * Number(r['戻り']), 0);
    const phi = z => { const t = 1 / (1 + 0.2316419 * Math.abs(z)), d = 0.3989423 * Math.exp(-z * z / 2);
      const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return z > 0 ? 1 - p : p; };
    const p0 = phi((E.mean - 1) / E.sd);
    let pm = E.mean, ps = E.sd;
    if (su > 0) { const w0 = 1 / (E.sd * E.sd), w1 = su * su / (E.sigma * E.sigma * su2); pm = (E.mean * w0 + (sr / su) * w1) / (w0 + w1); ps = Math.sqrt(1 / (w0 + w1)); }
    edgeTxt = `勝ち幅がある見込み（この買い方の本当の回収が100%より上である見込み）：${(phi((pm - 1) / ps) * 100).toFixed(0)}%（確かめだけなら${(p0 * 100).toFixed(0)}%。` +
      (su > 0 ? `${E.from}からの実際の${su}点・回収${(sr / su * 100).toFixed(1)}%で更新。本当の回収の見立ては${(pm * 100).toFixed(1)}%前後` : 'まだ実際の成績がない') +
      '。1点の払戻のばらつきが大きいので、はっきりするまで数千点かかる。50%を切ったら、撤退ラインの前でも買い方を見直す）';
  } catch (e) { edgeTxt = ''; }
  const out = ['## いまの買い方（1=2お得レース通知：全部＝安定型・配当型・的中型、締切10:00〜20:50）', '',
    (t.n ? `この形で買った分（${FROM}〜${end}）：${t.n}レース・${tu.n}点（うち勝負レース${sum(S.filter(r => r['日付'] >= FROM && strong(r))).n}）・的中${t.hit}・回収${(tu.ret / tu.n * 100).toFixed(1)}%・損益${yen(tu.ret - tu.n)}（1点100円、勝負レースは2点・7〜9月は1点）` : `この形で買った分（${FROM}〜）：まだありません（毎朝7:20に前の日の分が入ります）`) +
      '。見込み：決まりを毎年、前の年までのデータだけで選び直す厳しい数え方（2023〜2026年9月）で回収109.5%・1か月+1,400円前後（いまの決まりの決め打ちなら111.1%・+1,800円）。ただし2026年は100〜105%。月ごとのぶれは大きい',
    `参考：その前（〜${addDays(FROM, -1)}）も同じ形で数えると ${t0.n}点・的中${t0.hit}・回収${roi(t0)}・${yen(t0.ret - t0.n)}。10月1日からの全部のうち安定型は ${tb.n}点・的中${tb.hit}・回収${roi(tb)}`,
    ...(CADO ? [`4号艇のきまり（版12：4号艇が展示で4コースに入り、4コースを得意なら買わない）：このきまりに当てはまる分は、10月1日からの全部で ${SC.length}レース・${sumU(SC).n}点・的中${sum(SC).hit}・回収${sumU(SC).n ? (sumU(SC).ret / sumU(SC).n * 100).toFixed(1) + '%' : '-'}（勝負2点で数える。確かめでは99%前後で、外してももうけはほぼ同じ・点数が15%減る）` +
      (CADO_FROM ? `。${CADO_FROM}から、この分は買った分に入れていない` : '。版12を貼るまでは、この分も買った分に入れている')] : []),
    ...(PV ? (() => { const PF = '2026-10-25', a = [...Upv.values()].filter(r => r['日付'] >= PF && PV.has(r['日付'] + '|' + r['場'] + '|' + r['R'])), b = [...Ufin.values()].filter(r => r['日付'] >= PF && PV.has(r['日付'] + '|' + r['場'] + '|' + r['R']));
      const both = a.filter(r => Ufin.has(r['日付'] + '|' + r['場'] + '|' + r['R'])).length, ua = sumU(a), ub = sumU(b);
      return [`気象のずれの見張り（${PF}から、公式の preview の記録があるレース）：公式の preview（締切16分前ごろの気象＝版12の通知と同じ）で選ぶと ${a.length}レース・${ua.n}点・的中${sum(a).hit}・回収${ua.n ? (ua.ret / ua.n * 100).toFixed(1) + '%' : '-'}、確定の preview（確かめと同じ）で選ぶと ${b.length}レース・${ub.n}点・的中${sum(b).hit}・回収${ub.n ? (ub.ret / ub.n * 100).toFixed(1) + '%' : '-'}（同じレース ${both}）。確かめにずれを足すと回収は2ポイントほど下がる見込み（第16章「版12」）`]; })() : []),
    ...(CADO_FROM && PV ? [`版12（${CADO_FROM}から）は、通知と同じく公式の直前情報の preview（展示を見つけたとき・締切16分前ごろの気象）で印を出して数えている（その記録が無いレースは v1 の確定した preview）。${CADO_FROM}からの買った分のうち公式の preview で選んだもの ${S.filter(r => r['日付'] >= CADO_FROM && r['公式']).length}レース`] : []),
    `勝負レース（お得度${STRONG.toFixed(2)}以上・または来る確率${Math.round(SWEET[0] * 100)}〜${Math.round(SWEET[1] * 100)}%、${STRONG_UNITS}点で買う・7〜9月は1点）：10月1日からの全部で ${ts.n}点・的中${ts.hit}・回収${roi(ts)}（確かめでは1日1.3R・回収118%前後。外れが続くこともある）。` +
      `勝負レースを${STRONG_UNITS}点にした損益は、` + (t.n ? `${FROM}からで ${yen(tu.ret - tu.n)}（全部1点なら ${yen(t.ret - t.n)}）・` : '') + `10月1日からの全部で ${yen(tsu.ret - tsu.n)}（全部1点なら ${yen(sum(S).ret - S.length)}）`, ...(lineTxt ? [lineTxt] : []), ...(edgeTxt ? [edgeTxt] : []), '',
    '| 月 | 点 | 的中 | 回収 | 損益（1点100円） | 勝負レース | 勝負レースを2点（7〜9月は1点）にした損益 |', '| --- | --- | --- | --- | --- | --- | --- |'];
  [...new Set(S.map(r => r['日付'].slice(0, 7)))].sort().forEach(m => { const X = S.filter(r => r['日付'].startsWith(m)), u = sum(X), w = sum(X.filter(strong)), uu = sumU(X);
    out.push(`| ${m} | ${u.n} | ${u.hit} | ${roi(u)} | ${yen(u.ret - u.n)} | ${w.n}点・的中${w.hit} | ${yen(uu.ret - uu.n)} |`); });
  const from = addDays(end, -6), last = S.filter(r => r['日付'] >= from);
  out.push('', `直近7日（${from}〜${end}）のレース（選ばれ方：安定型・配当型・的中型のどれで選ばれたか。お得度1.10以上・または来る確率25〜32%は勝負レースで2点、7〜9月は1点）`, '');
  if (!last.length) out.push('（この7日はありませんでした）');
  else {
    out.push('| 日付 | 場 | R | 締切 | 選ばれ方 | お得度 | 点 | 来る確率 | 結果 | 払戻（100円） |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |');
    last.forEach(r => out.push(`| ${r['日付'].slice(5)} | ${r['場名']} | ${r['R']} | ${r['締切']} | ${r['選ばれ方']}${isCado(r) ? '（4号艇カド得意）' : ''} | ${r['強さ'].toFixed(3)} | ${units(r)} | ${r['的中見込み'] !== undefined && r['的中見込み'] !== '' ? Math.round(Number(r['的中見込み']) * 100) + '%' : '-'} | ${r['結果']} | ${Math.round(Number(r['戻り']) * 100)}円 |`));
  }
  const lastC = SC.filter(r => r['日付'] >= from && CADO_FROM && r['日付'] >= CADO_FROM);
  if (lastC.length) out.push('', '4号艇がカド得意で買わなかったレース（この7日）：' + lastC.map(r => `${r['日付'].slice(5)} ${r['場名']}${r['R']}R ${r['結果']}${r['結果'] === '的中' ? Math.round(Number(r['戻り']) * 100) + '円×' + units(r) : ''}`).join('、'));
  out.push('');
  return out;
}
(async () => {
  const end = addDays(jstToday(), -1);
  const parts = ['# 1=2お得レース通知の記録', '', '通知の買い方は、2026-10-23から「全部」（安定型・配当型・的中型のどれかが★★、締切10:00〜20:50）を全部買う形（オッズで見送らない。10-22までは安定型だけ）。お得度1.10以上・または来る確率25〜32%は勝負レースで2点（7〜9月は1点）。名前は2026-10-23に付け直した（お得度＝線との比、来る確率＝的中見込み、安定型＝B・頭打ち10倍、配当型＝A・いまの戻りモデル、的中型＝C・頭打ち6倍）。「確定オッズで期待値…」の行は、買うときには分からない確定オッズで見た参考。', ''];
  const ROWS = {};   // いちばん上の「いまの買い方」に使う各モデルの行
  for (const c of CFG) {
    const M = JSON.parse(fs.readFileSync(path.join(DIR, c.file), 'utf8'));
    const PM = c.hit ? JSON.parse(fs.readFileSync(path.join(DIR, c.hit), 'utf8')) : null;   // 来る確率のモデル
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
    const all = readAll(c.csv);
    if (c.key === '12') ROWS.A = all; if (c.key === '12c10') ROWS.B = all; if (c.key === '12c6') ROWS.C = all;
    parts.push(...section(c, M, all, PM));
    console.log(c.label, '足した行', added);
  }
  // 版12の通知と同じ判断：公式の直前情報の preview（q12/before/pv_日付.jsonl、展示を見つけたとき）で3つの型の印を出す → q12/record_pv_年.csv（2026-10-25から）
  let PV = null;
  try {
    const rd = f => JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8'));
    const MA = rd('model_2026A.json'), MB = rd('model_2026A_c10.json'), MC = rd('model_2026A_c6.json'), PMh = rd('model_2026A_hit.json');
    const c12 = CFG.find(c => c.key === '12');
    const PH = ['日付', '場', '場名', 'R', '締切', '配当', '配当比', '安定', '安定比', '的中', '的中比', '来る確率', '結果', '戻り'];
    const done = new Set(readAll('record_pv').map(r => r['日付']));
    const mk = s => s.tier === 2 ? '★★' : s.tier === 1 ? '★' : (s.absent12 ? '欠場' : '');
    for (let d = process.env.Q12_PV_START || '2026-10-25'; d <= end; d = addDays(d, 1)) {   // Q12_PV_START は確かめ用
      if (done.has(d)) continue;
      const f = path.join(DIR, 'before', `pv_${d.replace(/-/g, '')}.jsonl`); if (!fs.existsSync(f)) continue;
      const J = await loadDay(d); if (!J) continue;
      const S = (J.programs || {}).stadiums || {}, rows = [];
      for (const line of fs.readFileSync(f, 'utf8').split('\n').filter(x => x)) {
        let o; try { o = JSON.parse(line); } catch (e) { continue; }
        const r = ((S[String(o.v)] || {}).races || {})[String(o.rno)]; if (!r) continue;
        const ro = Object.assign({}, r, { preview: o.preview });
        const a = Q12.score(MA, ro, null), b = Q12.score(MB, ro, PMh), c = Q12.score(MC, ro, null); if (!a || !b || !c) continue;
        const oc = outcome(r, c12) || ['中止', 0];
        rows.push([d, r.stadium_number, VN[r.stadium_number] || '', r.race_number, String(r.closed_at || '').slice(11, 16), mk(a), a.ratio[1].toFixed(4), mk(b), b.ratio[1].toFixed(4), mk(c), c.ratio[1].toFixed(4), b.hitp.toFixed(4), oc[0], oc[1]].join(','));
      }
      if (!rows.length) continue;
      const g = path.join(DIR, `record_pv_${d.slice(0, 4)}.csv`);
      if (!fs.existsSync(g)) fs.writeFileSync(g, PH.join(',') + '\n');
      fs.appendFileSync(g, rows.map(x => x + '\n').join(''));
      console.log('公式の preview の印', d, 'レース', rows.length, '★★（どれか）', rows.filter(x => x.includes(',★★,')).length);
    }
    PV = new Map(readAll('record_pv').map(r => [r['日付'] + '|' + r['場'] + '|' + r['R'], r]));
  } catch (e) { console.log('公式の preview の印：' + e); }
  // 4号艇のきまり（版12）：4号艇が展示で4コース・前の365日に4コースから10走以上のレースの判定を q12/cado_年.csv に足す（2026-10-01から。コースの記録は course4.js）
  let CADO = null;
  try {
    const curve = JSON.parse(fs.readFileSync(path.join(DIR, 'course4_curve.json'), 'utf8'));
    const CH = ['日付', '場', 'R', '4号艇', '全国勝率', '出走', '2着以内', '2連対率', 'ふつう', 'ずれ', '得意'];
    const done = new Set(readAll('cado').map(r => r['日付']));
    for (let d = '2026-10-01'; d <= end; d = addDays(d, 1)) {
      if (done.has(d)) continue;
      const y8 = d.replace(/-/g, '');
      if (!fs.existsSync(path.join(DIR, 'course', C4.addDays8(y8, -1) + '.csv'))) { console.log('4号艇のきまり', d, 'コースの記録がまだ無い'); continue; }
      const J = await loadDay(d); if (!J) continue;
      const { R } = C4.windowStats(y8, 4), rows = [];
      for (const S of Object.values((J.programs || {}).stadiums || {})) for (const r of Object.values(S.races || {})) {
        const j = C4.judge(r, R, curve); if (!j) continue;
        rows.push([d, r.stadium_number, r.race_number, j.reg, j.natw, j.n, j.top2, j.w2.toFixed(4), j.normal.toFixed(4), j.d.toFixed(4), j.skip ? 1 : 0].join(','));
      }
      if (!rows.length) continue;
      rows.sort((a, b) => { const x = a.split(','), z = b.split(','); return (+x[1] - +z[1]) || (+x[2] - +z[2]); });
      const f = path.join(DIR, `cado_${d.slice(0, 4)}.csv`);
      if (!fs.existsSync(f)) fs.writeFileSync(f, CH.join(',') + '\n');
      fs.appendFileSync(f, rows.map(x => x + '\n').join(''));
      console.log('4号艇のきまり', d, '判定', rows.length, '得意', rows.filter(x => x.endsWith(',1')).length);
    }
    CADO = new Map(readAll('cado').map(r => [r['日付'] + '|' + r['場'] + '|' + r['R'], r]));
  } catch (e) { console.log('4号艇のきまり：' + e); }
  if (ROWS.B) parts.splice(4, 0, ...topU(ROWS, end, CADO, PV));
  parts.push(`最終更新：${new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 16).replace('T', ' ')}（日本時間）`);
  fs.writeFileSync(path.join(DIR, 'summary.md'), parts.join('\n') + '\n');
})().catch(e => { console.error(e); process.exit(1); });
