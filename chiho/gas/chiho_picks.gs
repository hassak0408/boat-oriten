/**
 * 地方競馬の来そうな馬：毎朝の一覧を、自分の Gmail に送る（Google Apps Script）。
 * 一覧は GitHub の非公開のリポジトリ hassak0408/chiho-keiba の data/picks/日付.txt（毎朝 GitHub Actions の chiho-pick が作る）。
 *
 * 使い方
 * 1. スクリプトのプロパティに GITHUB_TOKEN を入れる（chiho-keiba を読むだけのトークン。ここには書かない）。
 * 2. setup() を一度だけ実行する（10分ごとに check() が動くようになる）。
 * 3. 9:30〜13:00 のあいだ、今日の一覧ができていれば1回だけ送る。5場の開催が無い日は送らない。
 */
const REPO = 'hassak0408/chiho-keiba';
const FROM_HOUR = 9, TO_HOUR = 13;

function setup() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'check').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('check').timeBased().everyMinutes(10).create();
}

function check() {
  const now = new Date();
  const hour = Number(Utilities.formatDate(now, 'Asia/Tokyo', 'H'));
  if (hour < FROM_HOUR || hour >= TO_HOUR) return;
  const day = Utilities.formatDate(now, 'Asia/Tokyo', 'yyyyMMdd');
  const props = PropertiesService.getScriptProperties();
  if (props.getProperty('SENT') === day) return;
  const text = readFile_('data/picks/' + day + '.txt');
  if (!text) return;                      // まだできていない（または開催が無い日）
  GmailApp.sendEmail(Session.getEffectiveUser().getEmail(), text.split('\n')[0], text);
  props.setProperty('SENT', day);
}

function readFile_(path) {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトのプロパティに GITHUB_TOKEN がありません');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/contents/' + path, {
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github.raw' },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) return null;
  return res.getContentText('UTF-8');
}

/** 試し：今日（なければ指定した日）の一覧をすぐ送る。例：sendNow('20261025') */
function sendNow(day) {
  day = day || Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd');
  const text = readFile_('data/picks/' + day + '.txt');
  if (!text) { Logger.log('一覧がまだ無い：' + day); return; }
  GmailApp.sendEmail(Session.getEffectiveUser().getEmail(), text.split('\n')[0], text);
}
