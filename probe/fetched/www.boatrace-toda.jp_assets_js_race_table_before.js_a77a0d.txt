// =========================================
// 出走表 直前情報
// =========================================

//グローバル関数
var xmlRaceTableBefore = null;

// ファイルロード時に関数を読み込む
$(document).ready( function(){
  // テーブルの値の変更はクリック時に行う ファイルロード時に呼び出しても動作しない
  // 出走表 直前情報を表示する為の関数
  $(document).on("click",  "#act02-01, #act02", function(){
    getXmlRaceTableBefore();
  });

});

//運用ファイル取得
function getXmlRaceTableBefore() {
    //システム用XML取得
    download('./xml/kaisai/' + DATE + '/race_table_before_' + zero2(RACE_NO) + '.xml', 'xml', function(xml) {
      //$("#race_table_before_message").css('z-index','-1');
      $("#main_open_pc #disp02-01 .data_table").show();
      $("#main_open_pc #disp02-01 #before_message").hide();
      $("#main_open_sp #disp02-01 .data_table").show();
      $("#main_open_sp #disp02-01 #before_message").hide();
      //ドキュメントを格納
      xmlRaceTableBefore = xml;
      setRaceTableBefore();
    }, function() {
      showRaceTableBeforeMMessage();
      $("#race_table_before_message").css('z-index','2');
      $("#main_open_pc #disp02-01 #before_message").show();
      $("#main_open_pc #disp02-01 .data_table").hide();
      $("#main_open_sp #disp02-01 #before_message").show();
      $("#main_open_sp #disp02-01 .data_table").hide();
      $("*[name=before_message]").html("表示するデータがありません。<br>更新までしばらくお待ちください。");
    });
}

function showRaceTableBeforeMMessage() {
  // データなしメッセージ表示要素の基準となる横幅
  var sumLeft = 0;
  var sumWidth = 0;

  $("#disp02-01").find(".data_table").find("thead").find("th").each(function(i, val) {
    // 現在の成績～早見までの幅を取得
    if (i >= 0 && i <= 3) {
      sumLeft += $(val).width();
    }
    if (i >= 4 && i <= 12) {
      sumWidth += $(val).width();
    }
  });
  $("#race_table_before_message").width(sumWidth - 30);
  $("#race_table_before_message").css("left", sumLeft + 30);
}
  
//直前情報の展示情報の表示
function setRaceTableBefore() {
  var RaceTableBefore = $(xmlRaceTableBefore).find("table").find("record");
  $(RaceTableBefore).each(function(i, RaceTableBeforeInfo) {
    $("*[name=ttime" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("ttime").text());
    $("*[name=tiltc" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("tiltc").text());
    $("*[name=taiju" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("taiju").text());
    $("*[name=ctaiju" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("ctaiju").text());
    var bcd1 = $(RaceTableBeforeInfo).find("bcd1").text();
    var bcd2 = $(RaceTableBeforeInfo).find("bcd2").text();
    var bcd3 = $(RaceTableBeforeInfo).find("bcd3").text();
    var bcd4 = $(RaceTableBeforeInfo).find("bcd4").text();
    var bcd5 = $(RaceTableBeforeInfo).find("bcd5").text();
    var bcd6 = $(RaceTableBeforeInfo).find("bcd6").text();
    var bcd7 = $(RaceTableBeforeInfo).find("bcd7").text();
    var bcd8 = $(RaceTableBeforeInfo).find("bcd8").text();
    var bsu1 = $(RaceTableBeforeInfo).find("bsu1").text();
    var bsu2 = $(RaceTableBeforeInfo).find("bsu2").text();
    var bsu3 = $(RaceTableBeforeInfo).find("bsu3").text();
    var bsu4 = $(RaceTableBeforeInfo).find("bsu4").text();
    var bsu5 = $(RaceTableBeforeInfo).find("bsu5").text();
    var bsu6 = $(RaceTableBeforeInfo).find("bsu6").text();
    var bsu7 = $(RaceTableBeforeInfo).find("bsu7").text();
    var bsu8 = $(RaceTableBeforeInfo).find("bsu8").text();
    $("*[name=buhin" + (i + 1) + "]").text("");
    if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00 && bsu4 != 00 && bsu5 != 00 && bsu6 != 00 && bsu7 != 00 && bsu8 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3 + "、" + bcd4 + "×" + bsu4 + "、" + bcd5 + "×" + bsu5 + "、" + bcd6 + "×" + bsu6 + "、" + bcd7 + "×" + bsu7  + "、" + bcd8 + "×" + bsu8);
    } else if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00 && bsu4 != 00 && bsu5 != 00 && bsu6 != 00 && bsu7 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3 + "、" + bcd4 + "×" + bsu4 + "、" + bcd5 + "×" + bsu5 + "、" + bcd6 + "×" + bsu6 + "、" + bcd7 + "×" + bsu7);
    } else if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00 && bsu4 != 00 && bsu5 != 00 && bsu6 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3 + "、" + bcd4 + "×" + bsu4 + "、" + bcd5 + "×" + bsu5 + "、" + bcd6 + "×" + bsu6);
    } else if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00 && bsu4 != 00 && bsu5 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3 + "、" + bcd4 + "×" + bsu4 + "、" + bcd5 + "×" + bsu5);
    } else if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00 && bsu4 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3 + "、" + bcd4 + "×" + bsu4);
    } else if(bsu1 != 00 && bsu2 != 00 && bsu3 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2 + "、" + bcd3 + "×" + bsu3);
    } else if(bsu1 != 00 && bsu2 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1 + "、" + bcd2 + "×" + bsu2);
    } else if(bsu1 != 00) {
      $("*[name=buhin" + (i + 1) + "]").html(bcd1 + "×" + bsu1);
    }
    $("*[name=sst" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("sjiko").text() + $(RaceTableBeforeInfo).find("sst").text());
    var scsWk = $(RaceTableBeforeInfo).find("scs").text();
    if(!isNaN(scsWk)) {
        $("*[name=scs" + (i + 1) + "]").html($(RaceTableBeforeInfo).find("scs").text());
    } else {
        $("*[name=scs" + (i + 1) + "]").html("");
    }
  })
}

