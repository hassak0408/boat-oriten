// ===== 2連複1=2 戻りモデル（オッズなし）の計算部分 =====
// BoatraceOpenAPI v1 の1レース（出走表＋直前情報）から学習と同じ143項目を作り、木のモデル3本で「100円あたりの戻りの見込み」を出す。
// Node（確かめ用）でも Google Apps Script でもそのまま動くように、標準の JavaScript だけで書く。
var Q12 = (function () {
  var PREF = {1:10,2:11,3:13,4:13,5:13,6:22,7:23,8:23,9:24,10:18,11:25,12:27,13:28,14:36,15:37,16:33,17:34,18:35,19:35,20:40,21:40,22:40,23:41,24:42};
  var WOMEN = ['レディース','ヴィーナス','女子','クイーンズ','オールレディ','レディス','女王'];
  var NOTW = ['ルーキー','男女','VS','ＶＳ','対抗','ダブル','ミックス','混合'];
  var RT = ['予選','一般戦','特選・選抜','ドリーム戦','準優勝戦','優勝戦','進入固定戦','その他'];
  var DL = {'初日':1,'2日目':2,'3日目':3,'4日目':4,'5日目':5,'6日目':6,'最終日':9};
  var PER = ['cls','natw','nat2','locw','loc2','mot2','boat2','age','wt','F','L','avgst','exst','ext','tilt','pcrs','地元','展示T順','展示ST順','勝率順','展示T差'];
  function has(s, k) { return String(s).indexOf(k) >= 0; }
  function rtype(s) {
    s = s || '';
    if (has(s,'準優')) return '準優勝戦';
    if (has(s,'優勝戦')) return '優勝戦';
    if (has(s,'ドリーム')) return 'ドリーム戦';
    if (has(s,'進入固定')) return '進入固定戦';
    var k = ['選抜','特選','特賞','シード','選抜戦'];
    for (var i = 0; i < k.length; i++) if (has(s,k[i])) return '特選・選抜';
    if (has(s,'予選')) return '予選';
    if (has(s,'一般')) return '一般戦';
    return 'その他';
  }
  function z2h(s) { return String(s || '').replace(/[０-９]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); }); }
  function num(x) { if (x === null || x === undefined || x === '') return NaN; var v = Number(x); return isFinite(v) ? v : NaN; }
  function f32(x) { return isNaN(x) ? NaN : Math.fround(x); }   // 学習の表は艇ごとの値を float32 で持っていた（差を取る前にそろえる）
  function rankRow(a, asc) {               // 小さいほど1位（asc=false は大きいほど1位）。空は最下位でそろう。同じ値は良い方の順位
    var x = a.map(function (v) { var w = isNaN(v) ? (asc ? Infinity : -Infinity) : v; return asc ? w : -w; });
    return x.map(function (xi) { var c = 0; for (var j = 0; j < 6; j++) if (xi > x[j]) c++; return c + 1; });
  }
  function nanmin(a) { var m = Infinity, f = false; a.forEach(function (v) { if (!isNaN(v)) { f = true; if (v < m) m = v; } }); return f ? m : NaN; }
  function nanmax(a) { var m = -Infinity, f = false; a.forEach(function (v) { if (!isNaN(v)) { f = true; if (v > m) m = v; } }); return f ? m : NaN; }
  // v1 の1レース → { 項目名: 値 }
  function features(race) {
    var F = {};
    var v = num(race.stadium_number);
    F['場'] = v;
    var g = num(race.grade_number); if (g === 6) g = 2;   // v1 の G1a（6）は v3 では 2
    F['グレード'] = g;
    F['種類'] = RT.indexOf(rtype(race.subtitle));
    F['R'] = num(race.race_number);
    var dl = z2h(race.day_number_source);
    F['日目'] = DL.hasOwnProperty(dl) ? DL[dl] : NaN;
    var ca = String(race.closed_at || '');
    F['時'] = ca.length >= 13 ? num(ca.substr(11, 2)) : NaN;
    var pv = race.preview || {};
    F['wind'] = num(pv.wind_speed); F['wdir'] = num(pv.wind_direction_number); F['wave'] = num(pv.wave_height);
    var w = num(pv.weather_number); if (w === 6) w = NaN;  // v1 の台風（6）は v3 では空
    F['weather'] = w; F['air'] = num(pv.air_temperature); F['water'] = num(pv.water_temperature);
    F['月'] = num(String(race.date || '').substr(5, 2));
    var t = race.title || '', wo = false, nt = false;
    WOMEN.forEach(function (k) { if (has(t,k)) wo = true; }); NOTW.forEach(function (k) { if (has(t,k)) nt = true; });
    F['女子戦'] = (wo && !nt) ? 1 : 0;
    var R = race.racers || {}, P = (pv.racers) || {};
    var per = {}; PER.forEach(function (c) { per[c] = [NaN,NaN,NaN,NaN,NaN,NaN]; });
    for (var L = 0; L < 6; L++) {
      var b = R[String(L + 1)] || {}, c = P[String(L + 1)] || {};
      per.cls[L] = f32(num(b.rank_number)); per.natw[L] = f32(num(b.national_win_rate)); per.nat2[L] = f32(num(b.national_top_2_percent));
      per.locw[L] = f32(num(b.local_win_rate)); per.loc2[L] = f32(num(b.local_top_2_percent)); per.mot2[L] = f32(num(b.motor_top_2_percent));
      per.boat2[L] = f32(num(b.boat_top_2_percent)); per.age[L] = f32(num(b.age)); per.wt[L] = f32(num(b.weight));
      per.F[L] = f32(num(b.flying_count)); per.L[L] = f32(num(b.late_count));
      var av = f32(num(b.average_start_timing)); per.avgst[L] = (av <= 0) ? NaN : av;
      per.exst[L] = f32(num(c.start_timing));
      var ex = f32(num(c.exhibition_time)); per.ext[L] = (ex <= 0) ? NaN : ex;
      per.tilt[L] = f32(num(c.tilt_adjustment)); per.pcrs[L] = f32(num(c.course_number));
      per['地元'][L] = (num(b.branch_number) === PREF[v]) ? 1 : 0;
    }
    per['展示T順'] = rankRow(per.ext, true); per['展示ST順'] = rankRow(per.exst, true); per['勝率順'] = rankRow(per.natw, false);
    var mn = nanmin(per.ext); per['展示T差'] = per.ext.map(function (x) { return x - mn; });
    PER.forEach(function (c) { for (var L = 0; L < 6; L++) F[c + (L + 1)] = per[c][L]; });
    F['1勝率-他最高'] = per.natw[0] - nanmax(per.natw.slice(1));
    F['A級人数'] = per.cls.filter(function (x) { return x <= 2; }).length;
    var wk = true; for (var i = 0; i < 6; i++) if (per.pcrs[i] !== i + 1) wk = false;
    F['枠なり'] = wk ? 1 : 0;
    return { F: F, ext: per.ext };
  }
  function inBits(bits, val) { val = val >>> 0; return ((bits[val >>> 5] >>> (val & 31)) & 1) === 1; }
  function predictOne(M, xs) {               // xs：学習の列の順の値（float32 にそろえたもの）
    var n = M.order.length, ncat = M.cats.length, z = new Array(n);
    for (var k = 0; k < n; k++) {
      var val = xs[M.order[k]];
      if (k < ncat) {                          // カテゴリ列：値 → 学習で見た値の番号（無ければ空）
        var code = NaN, cs = M.cats[k];
        if (!isNaN(val)) for (var j = 0; j < cs.length; j++) if (cs[j] === val) { code = j; break; }
        z[k] = code;
      } else z[k] = val;
    }
    var raw = M.baseline;
    for (var ti = 0; ti < M.trees.length; ti++) {
      var T = M.trees[ti], nd = 0;
      while (!T.leaf[nd]) {
        var f = T.f[nd], d = z[f];
        if (isNaN(d)) nd = T.m[nd] ? T.l[nd] : T.r[nd];
        else if (T.c[nd]) {
          if (d < 0) nd = T.m[nd] ? T.l[nd] : T.r[nd];
          else if (inBits(T.bits[T.b[nd]], d)) nd = T.l[nd];
          else if (inBits(M.known[M.fmap[f]], d)) nd = T.r[nd];
          else nd = T.m[nd] ? T.l[nd] : T.r[nd];
        } else nd = (d <= T.t[nd]) ? T.l[nd] : T.r[nd];
      }
      raw += T.v[nd];
    }
    return Math.exp(raw);
  }
  // 1レースの判定。戻り値 null＝まだ展示が出ていない（MODEL.lanes で目の艇を指定。無ければ1=2）
  function score(MODEL, race) {
    var o = features(race), F = o.F;
    var nEx = o.ext.filter(function (x) { return !isNaN(x); }).length;
    if (nEx < 5) return null;                                   // 展示がまだ（欠場1艇までは待たない）
    var lanes = MODEL.lanes || [0, 1];                           // この目の艇（0始まり。1=2なら[0,1]、1=3なら[0,2]）
    var absent12 = lanes.some(function (i) { return isNaN(o.ext[i]); });   // 目の艇が展示に出ていない＝欠場とみなして買わない
    var xs = MODEL.cols.map(function (c) { var v = F[c]; return (v === undefined) ? NaN : Math.fround(v); });
    var preds = MODEL.models.map(function (M) { return predictOne(M, xs); });
    var r = MODEL.qs.map(function (q, qi) {                       // 線との比の3本の平均
      var s = 0; MODEL.models.forEach(function (M, i) { s += preds[i] / M.thr[qi]; }); return s / MODEL.models.length;
    });
    var tier = absent12 ? 0 : (r[1] >= 1 ? 2 : (r[0] >= 1 ? 1 : 0));   // 2＝★★（上位2%の線）、1＝★（上位5%の線）
    return { preds: preds, ratio: r, tier: tier, absent12: absent12, mean: preds.reduce(function (a, b) { return a + b; }, 0) / preds.length };
  }
  return { features: features, predictOne: predictOne, score: score, rtype: rtype };
})();
if (typeof module !== 'undefined') module.exports = Q12;
