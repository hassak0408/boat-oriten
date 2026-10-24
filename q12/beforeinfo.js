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
  return { parse: parse, count: count };
})();
if (typeof module !== 'undefined') module.exports = BeforeInfo;
