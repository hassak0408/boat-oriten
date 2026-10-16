// =========================================
// 出走表 直前情報
// =========================================

//グローバル関数
var xmlRaceTableOriginal = null;

// ファイルロード時に関数を読み込む
$(document).ready( function(){
  // テーブルの値の変更はクリック時に行う ファイルロード時に呼び出しても動作しない
  // 出走表 直前情報を表示する為の関数
  $(document).on("click",  "#act02-03, #act02", function(){
    getXmlRaceTableOriginal();
  });

});

//運用ファイル取得
function getXmlRaceTableOriginal() {
    //システム用XML取得
    download('./xml/kaisai/' + DATE + '/race_table_original_' + zero2(RACE_NO) + '.xml', 'xml', function(xml) {
      //$("#race_table_original_message").css('z-index','-1');
      $("#main_open_pc #disp02-03 .data_table").show();
      $("#main_open_pc #disp02-03 #original_message").hide();
      $("#main_open_sp #disp02-03 .data_table").show();
      $("#main_open_sp #disp02-03 #original_message").hide();
      //ドキュメントを格納
      xmlRaceTableOriginal = xml;
      setRaceTableOriginal();
    }, function() {
      showRaceTableOriginalMMessage();
      $("#race_table_original_message").css('z-index','2');
      $("#main_open_pc #disp02-03 #original_message").show();
      $("#main_open_pc #disp02-03 .data_table").hide();
      $("#main_open_sp #disp02-03 #original_message").show();
      $("#main_open_sp #disp02-03 .data_table").hide();
      $("*[name=original_message]").html("表示するデータがありません。<br>更新までしばらくお待ちください。");
    });
}

function showRaceTableOriginalMMessage() {
  // データなしメッセージ表示要素の基準となる横幅
  var sumLeft = 0;
  var sumWidth = 0;

  $("#disp02-03").find(".data_table").find("thead").find("th").each(function(i, val) {
    // 現在の成績～早見までの幅を取得
    if (i >= 0 && i <= 3) {
      sumLeft += $(val).width();
    }
    if (i >= 4 && i <= 12) {
      sumWidth += $(val).width();
    }
  });
  $("#race_table_original_message").width(sumWidth - 30);
  $("#race_table_original_message").css("left", sumLeft + 30);
}
  
//直前情報の展示情報の表示
function setRaceTableOriginal() {
  var RaceTableOriginal = $(xmlRaceTableOriginal).find("table").find("record");
  $(RaceTableOriginal).each(function(i, RaceTableOriginalInfo) {
    $("*[name=ttime" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("ttime").text());
    $("*[name=tiltc" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("tiltc").text());
    $("*[name=taiju" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("taiju").text());
    $("*[name=ctaiju" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("ctaiju").text());
    $("*[name=ttm" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("ttime").text());
	$("*[name=rnd" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("rnd").text());
	$("*[name=cnr" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("cnr").text());
	$("*[name=str" + (i + 1) + "]").html($(RaceTableOriginalInfo).find("str").text());
	var ttm_rank = $(RaceTableOriginalInfo).find("ttm_rank").text();
    var rnd_rank = $(RaceTableOriginalInfo).find("rnd_rank").text();
    var cnr_rank = $(RaceTableOriginalInfo).find("cnr_rank").text();
    var str_rank = $(RaceTableOriginalInfo).find("str_rank").text();
/*    if (ttm_rank == 1) {
		$("*[name=ttm" + (i + 1) + "]").addClass("bg_oriten_r");
		$("*[name=ttm" + (i + 1) + "]").removeClass("bg_oriten_y");
	} else if (ttm_rank == 2) {
		$("*[name=ttm" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=ttm" + (i + 1) + "]").addClass("bg_oriten_y");
	} else {
		$("*[name=ttm" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=ttm" + (i + 1) + "]").removeClass("bg_oriten_y");
	}*/
    if (rnd_rank == 1) {
		$("*[name=rnd" + (i + 1) + "]").addClass("bg_oriten_r");
		$("*[name=rnd" + (i + 1) + "]").removeClass("bg_oriten_y");
	} else if (rnd_rank == 2) {
		$("*[name=rnd" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=rnd" + (i + 1) + "]").addClass("bg_oriten_y");
	} else {
		$("*[name=rnd" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=rnd" + (i + 1) + "]").removeClass("bg_oriten_y");
	}
    if (cnr_rank == 1) {
		$("*[name=cnr" + (i + 1) + "]").addClass("bg_oriten_r");
		$("*[name=cnr" + (i + 1) + "]").removeClass("bg_oriten_y");
	} else if (cnr_rank == 2) {
		$("*[name=cnr" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=cnr" + (i + 1) + "]").addClass("bg_oriten_y");
	} else {
		$("*[name=cnr" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=cnr" + (i + 1) + "]").removeClass("bg_oriten_y");
	}
    if (str_rank == 1) {
		$("*[name=str" + (i + 1) + "]").addClass("bg_oriten_r");
		$("*[name=str" + (i + 1) + "]").removeClass("bg_oriten_y");
	} else if (str_rank == 2) {
		$("*[name=str" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=str" + (i + 1) + "]").addClass("bg_oriten_y");
	} else {
		$("*[name=str" + (i + 1) + "]").removeClass("bg_oriten_r");
		$("*[name=str" + (i + 1) + "]").removeClass("bg_oriten_y");
	}
	
  })
}

