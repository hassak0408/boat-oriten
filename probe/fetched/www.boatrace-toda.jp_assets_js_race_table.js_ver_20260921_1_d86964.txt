
// =========================================
// 出走表
// =========================================

//var RACE_NO =2;　レース番号はrace_number_change.jsより取得する

var tmplRaceTableBlock = null;

var xmlRaceTable = [null, null, null, null, null, null, null, null, null, null, null, null];
var xmlRaceTableForecast = [null, null, null, null, null, null, null, null, null, null, null, null];

var SM_CHECK = false;

// ファイルロード時に関数を読み込む
$(document).ready( function(){

  //pcスマホ判定
  var ua = navigator.userAgent;
  if(ua.indexOf("iPhone") > 0 || ua.indexOf("Android") > 0 && ua.indexOf("Mobile") > 0){
    //スマホ
    SM_CHECK = true;
  }
  // テーブルの値の変更はクリック時に行う ファイルロード時に呼び出しても動作しない
  // 出走表 全国過去3節成績を表示する為の関数
  $(document).on("click",  "#act01-03", function(){
    getXmlRaceTableAll3();
  });

});

// 全国過去3節xml取得
function getXmlRaceTableAll3() {
  download('./xml/kaisai/' + DATE + "/race_table_all3_" + zero2(RACE_NO) + ".xml", 'xml', function(xml) {
  // download('./xml/kaisai/20210215/race_table_all3_01.xml', 'xml', function(xml) {
    tmplRaceTableBlock = xml;
    setDataRaceTableAll3();
  });
}

// 全国過去3節xmlのデータセット
function setDataRaceTableAll3() {
    $(tmplRaceTableBlock).find("table").each(function(){
      $(this).find("record").each(function(){
        var no = $(this).find("teiban").text();
        // 1節前
        $("*[name=\'above-texts" + no + "-1\']").html($(this).find("grade1").text() + "  " + $(this).find("jyo1").text() + "  " + $(this).find("term1").text());
        $("*[name=\"under-text" + no + "-1\"]").html($(this).find("chaku1").text());
        // 2節前
        $("[name=\"above-texts" + no + "-2\"]").html($(this).find("grade2").text() + "  " + $(this).find("jyo2").text() + "  " + $(this).find("term2").text());
        $("[name=\"under-text" + no + "-2\"]").html($(this).find("chaku2").text());
        // 3節前
        $("[name=\"above-texts" + no + "-3\"]").html($(this).find("grade3").text() + "  " + $(this).find("jyo3").text() + "  " + $(this).find("term3").text());
        $("[name=\"under-text" + no + "-3\"]").html($(this).find("chaku3").text());
      });
  });
}

//出走表xml取得
function getXmlRaceTable() {
  download('./xml/kaisai/' + DATE + "/race_table_" + zero2(RACE_NO) + ".xml", 'xml', function(xml) {
    xmlRaceTable[RACE_NO] = xml;
    setDataRaceTable();
  });
}

//出走表データ反映
function setDataRaceTable() {
  
  var now = new Date();
  var sub_now = now.getDate();
  var now_Y = now.getFullYear();
  //月取得時のズレ補正
  now.setDate(1);
  var now_M = now.getMonth() + 1;
  now.setDate(sub_now);
  var now_D = now.getDate();
  var now_h = now.getHours();
  var now_m = now.getMinutes();

  var sdate = DATE.match(/.{2}/g);
  var sdateY = parseInt(sdate[0] + sdate[1]);
  var sdateM = parseInt(sdate[2]);
  var sdateD = parseInt(sdate[3]);
  
  var stime = $(xmlRaceTable[RACE_NO]).find("stime").text().split("\:");
  var stime_h = parseInt(stime[0]);
  var stime_m = parseInt(stime[1].replace("\:",""));
  if(sdateY == now_Y && sdateM == now_M && sdateD == now_D) {
    if((now_h > stime_h) || (now_h == stime_h && now_m > stime_m)) {
      $("*[name=dead_line_time]").html("<i class='far fa-clock'></i> 発売締切　締切");
    } else {
      $("*[name=dead_line_time]").html("<i class='far fa-clock'></i> 発売締切　" + $(xmlRaceTable[RACE_NO]).find("stime").text());
    }
  } else {
    $("*[name=dead_line_time]").html("<i class='far fa-clock'></i> 発売締切　" + $(xmlRaceTable[RACE_NO]).find("stime").text());
  }
  
  
  //表示中のレースNoとレース名を更新
  $("*[name=disp_race_no]").text(Number(RACE_NO) + "R " + $(xmlRaceTable[RACE_NO]).find("rmei").text());
  
  $(xmlRaceTable[RACE_NO]).find("table").each(function(){
    if($(this).find("jcd").text() == "02") {
      // 枠番毎に
      $(this).find("record").each(function(){
        var rno = $(this).find("rno").text();
        var no = $(this).find("teiban").text();
        var haya = $(this).find("haya").text();
        // 欠場している選手であった場合は、<tr name="waku-gray-X">要素に.ketsuを追加する
        if ($(this).find("kjo").text() != 0) {
          $("*[name=\"waku-gray-" + no + "\"]").addClass("ketsu");
          console.log('ketujo' + no);
        } else {
          $("*[name=\"waku-gray-" + no + "\"]").removeClass("ketsu");
        }
        
        $("*[name=\"kyu" + no + "\"]").html($(this).find("kyu").text());
        
        $("*[name=\"name" + no + "\"]").find("a").remove();
        if(SM_CHECK == true){
          //スマホリンク
          $("*[name=\"name" + no + "\"]").html("<a href='https://www.boatrace.jp/owsp/sp/data/racersearch/profile?toban=" + $(this).find("toban").text() + "' style='text-decoration: underline;' target='_blank'></a>");
        } else {
          //pcリンク
          $("*[name=\"name" + no + "\"]").html("<a href='https://www.boatrace.jp/owpc/pc/data/racersearch/profile?toban=" + $(this).find("toban").text() + "' style='text-decoration: underline;' target='_blank'></a>");
        }
        $("*[name=\"name" + no + "\"]").find("a").html($(this).find("name").text());
        $("*[name=\"toban" + no + "\"]").html($(this).find("toban").text());
        $("*[name=\"syusin" + no + "\"]").html($(this).find("syusin").text());
        $("*[name=\"nenrei" + no + "\"]").html($(this).find("nenrei").text());
        
        //フライングはL数が画面xmlにないため暫定
        var fl = "";
        if($(this).find("fsu").text() != "0") {
          fl = $(this).find("fsu").text();
        }
        fl = fl + "<br>" + "<br>";
        if($(this).find("lsu").text() != "0") {
          fl = fl + $(this).find("lsu").text();
        }
        $("*[name=\"fsu" + no + "\"]").html(fl);
       
        $("*[name=\"p_st" + no + "\"]").html($(this).find("p_st").text().replace("0.", "."));
        
        $("*[name=\"zsyo" + no + "\"]").html($(this).find("zsyo").text());
        $("*[name=\"z2ren" + no + "\"]").html($(this).find("z2ren").text());
        
        $("*[name=\"jsyo" + no + "\"]").html($(this).find("jsyo").text());
        $("*[name=\"j2ren" + no + "\"]").html($(this).find("j2ren").text());
        
        //モーター変更フラグ処理の追加が多分必要
        $("*[name=\"mno" + no + "\"]").html($(this).find("mno").text());
        $("*[name=\"m2ren" + no + "\"]").html($(this).find("m2ren").text());
        
        //ボート
        $("*[name=\"bno" + no + "\"]").html($(this).find("bno").text());
        $("*[name=\"b2ren" + no + "\"]").html($(this).find("b2ren").text());
        
        if(haya != "") {
          $("*[name=\"hayami" + no + "\"]").html("<a href=javascript:void(0) class='race_num underline_num' name=\"race" + $(this).find("haya").text() + "\")>" + parseInt($(this).find("haya").text()) + "</a>");
        } else {
          $("*[name=\"hayami" + no + "\"]").html("");
        }
      });
    }
  });
}

//出走表xml取得(直前情報)
function getXmlRaceTableBeforInfo() {
  download('./xml/kaisai/' + DATE + "/race_table_" + zero2(RACE_NO) + ".xml", 'xml', function(xml) {
    xmlRaceTable[RACE_NO] = xml;
    setDataRaceTableBeforInfo();
  });
}

//出走表(直前情報)データ反映
function setDataRaceTableBeforInfo() {
  
  $(xmlRaceTable[RACE_NO]).find("table").each(function(){
    if($(this).find("jcd").text() == "02") {
      $(this).find("record").each(function(){
        var race = $(this).find("race");
        
        var no = $(this).find("teiban").text();
        var haya = $(this).find("haya").text();
        
        $("*[name=\"kyu" + no + "\"]").html($(this).find("kyu").text());
        
        $("*[name=\"name" + no + "\"]").html($(this).find("name").text());
        $("*[name=\"toban" + no + "\"]").html($(this).find("toban").text());
        $("*[name=\"syusin" + no + "\"]").html($(this).find("syusin").text());
        $("*[name=\"nenrei" + no + "\"]").html($(this).find("nenrei").text());
        
//        $("*[name=\"ttime" + no + "\"]").html($(this).find("ttime").text());
        
//        $("*[name=\"tiltc" + no + "\"]").html($(this).find("tiltc").text());
        
//        $("*[name=\"syussou" + no + "\"]").html($(this).find("syussou_taiju").text());
        
//        $("*[name=\"ctaiju" + no + "\"]").html($(this).find("ctaiju").text());
        
//        $("*[name=\"bcd" + no + "\"]").html($(this).find("bcd").text());
        
//        $("*[name=\"sst" + no + "\"]").html($(this).find("sst").text());
        
      });
      
    }
  });
  
}

//予想印xml取得
function getXmlRaceTableForecast() {
  download('./xml/kaisai/' + DATE + "/race_table_forecast_" + zero2(RACE_NO) + ".xml", 'xml', function(xml) {
    xmlRaceTableForecast[RACE_NO] = xml;
    setDataRaceTableForecast();
  });
}

//予想印反映
function setDataRaceTableForecast() {  
  $(xmlRaceTableForecast[RACE_NO]).find("table").find("record").each(function(){
    var no = $(this).find("waku").text();
    
    $("*[name=\"yosou" + no + "\"]").html($(this).find("yosou").text());
    
  });
}
