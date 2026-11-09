// 公式サイトの直前情報（beforeinfo）のページから、BoatraceOpenAPI v1 の preview と同じ形を作る（q12 の通知を早める・v1 が遅れたときの代わり）
//   Node（確かめ用）でも Google Apps Script でもそのまま動くように、標準の JavaScript だけで書く
//   見本（q12/before/samples）で v1 と同じになるかを before_test.js で確かめる
var BeforeInfo = (function () {
  function num(s) { if (s === null || s === undefined) return null; var t = String(s).replace(/&nbsp;|\s/g, ''); if (t === '') return null; var v = parseFloat(t); return isFinite(v) ? v : null; }
  function st(s) {                       // スタート展示の ST：'.18'→0.18、'F.01'→−0.01（v1 と同じ）。読めなければ null
    var t = String(s || '').replace(/&nbsp;|\s/g, '');
    var m = /^(F|L)?(\d*\.\d+)$/.exec(t); if (!m) return null;
    var v = parseFloat(m[2]); return m[1] === 'F' ? -v : v;
  }
  function parse(html) {
    var pv = { racers: {} };
    // 艇ごと（tbody）：体重・展示タイム・チルト・調整重量
    var bodies = html.split('<tbody class="is-fs12');
    for (var i = 1; i < bodies.length; i++) {
      var b = bodies[i].split('</tbody>')[0];
      var mb = /is-boatColor(\d)/.exec(b); if (!mb) continue;
      var tds = []; var re = /<td[^>]*>([\s\S]*?)<\/td>/g, m;
      while ((m = re.exec(b)) !== null) tds.push(m[1].replace(/<[^>]*>/g, '').trim());
      // 並び：0枠 1写真 2名前 3体重 4展示タイム 5チルト 6プロペラ 7部品交換 8R 9（前走R） … 調整重量は「進入」の行のあと
      var kg = /([\d.]+)kg/.exec(tds[3] || '');
      var adj = null; for (var k = 0; k < tds.length; k++) if (tds[k] === 'ST' && k > 0) { adj = num(tds[k - 1]); break; }
      pv.racers[mb[1]] = { exhibition_time: num(tds[4]), tilt_adjustment: num(tds[5]), weight: kg ? parseFloat(kg[1]) : null, weight_adjustment: adj, course_number: null, start_timing: null };
    }
    // スタート展示：行の順がコース、番号が艇、ST
    var sec = html.split('スタート展示')[1] || '';
    var rows = sec.split('table1_boatImage1Number').slice(1), c = 0;
    for (var j = 0; j < rows.length && c < 6; j++) {
      var nb = /is-type(\d)">(\d)<\/span>/.exec(rows[j]); if (!nb) continue;
      c++;
      var tm = /table1_boatImage1Time[^>]*>([^<]*)</.exec(rows[j]);
      var r = pv.racers[nb[2]] || (pv.racers[nb[2]] = {});
      r.course_number = c; r.start_timing = tm ? st(tm[1]) : null;
    }
    // 気象：天候・風速・風向・気温・水温・波高
    function data(title) { var m2 = new RegExp('weather1_bodyUnitLabelTitle">' + title + '</span>\\s*<span class="weather1_bodyUnitLabelData">([^<]*)<').exec(html); return m2 ? m2[1].trim() : null; }
    var w = /weather1_bodyUnitImage is-weather(\d+)/.exec(html), wd = /weather1_bodyUnitImage is-wind(\d+)/.exec(html);
    pv.weather_number = w ? Number(w[1]) : null;
    pv.wind_direction_number = wd ? Number(wd[1]) : null;
    pv.wind_speed = num((data('風速') || '').replace('m', ''));
    pv.wave_height = num((data('波高') || '').replace('cm', ''));
    pv.air_temperature = num((data('気温') || '').replace('℃', ''));
    pv.water_temperature = num((data('水温') || '').replace('℃', ''));
    return pv;
  }
  function count(pv) { var n = 0; for (var k in pv.racers) if (pv.racers[k].exhibition_time > 0) n++; return n; }   // 展示タイムがそろった艇の数
  // 市場の値段にまだ入っていないかもしれない材料（2026-11-09から記録。parse は変えない＝通知と同じ形のまま）
  //   艇ごと：t 登録番号、pr プロペラの欄（替えたときは「新」）、pt 部品交換の札（「ピストン×２」など）
  //   レース：lab 見出しの札（進入固定・安定板使用などが出るところ）、name レース名、m 距離、antei ページのどこかに「安定板」があれば1
  function txt(s) { return String(s === null || s === undefined ? '' : s).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, '').replace(/\s+/g, ' ').trim(); }
  function extras(html) {
    var ex = { b: {} };
    var bodies = html.split('<tbody class="is-fs12');
    for (var i = 1; i < bodies.length; i++) {
      var b = bodies[i].split('</tbody>')[0];
      var mb = /is-boatColor(\d)/.exec(b); if (!mb) continue;
      var tds = [], re = /<td[^>]*>([\s\S]*?)<\/td>/g, m, kp = -1;
      while ((m = re.exec(b)) !== null) { if (kp < 0 && m[1].indexOf('labelGroup1') >= 0) kp = tds.length; tds.push(m[1]); }
      var pt = [], g = /<ul class="labelGroup1">([\s\S]*?)<\/ul>/.exec(b);
      if (g) { var rl = /<span[^>]*>([^<]*)<\/span>/g, q; while ((q = rl.exec(g[1])) !== null) { var u = txt(q[1]); if (u) pt.push(u); } }
      var tb = /toban=(\d+)/.exec(b);
      ex.b[mb[1]] = { t: tb ? tb[1] : null, pr: kp > 0 ? txt(tds[kp - 1]) : null, pt: pt };   // プロペラの欄は部品交換の欄のすぐ前
    }
    var lab = [], lb = html.split('title16_titleLabels__add2020">')[1];
    if (lb) { lb = lb.split('</div>')[0]; var rs = />([^<]+)</g, z; while ((z = rs.exec(lb)) !== null) { var w = txt(z[1]); if (w) lab.push(w); } }
    ex.lab = lab;
    var td = /title16_titleDetail__add2020">([\s\S]*?)<\/h3>/.exec(html), dt = td ? txt(td[1]) : '', dm = /(\d{3,4})m/.exec(dt);
    ex.name = td ? dt.replace(/\s*\d{3,4}m\s*$/, '') : null;
    ex.m = dm ? Number(dm[1]) : null;
    ex.antei = html.indexOf('安定板') >= 0 ? 1 : 0;
    return ex;
  }
  return { parse: parse, count: count, extras: extras };
})();
if (typeof module !== 'undefined') module.exports = BeforeInfo;
