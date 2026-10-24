/**
 * 地方競馬の来そうな馬：毎朝の一覧を、自分の Gmail に送る（Google Apps Script）。
 * 一覧は GitHub の非公開のリポジトリ hassak0408/chiho-keiba の data/picks/日付.txt（毎朝 GitHub Actions の chiho-pick が作る）。
 *
 * 使い方
 * 1. スクリプトのプロパティに GITHUB_TOKEN を入れる（chiho-keiba を読むだけのトークン。ここには書かない）。
 * 2. setup() を一度だけ実行する（10分ごとに check() が動くようになる）。試しに送るときは sendLatest() を実行する。
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

/** 試し：いちばん新しい一覧をすぐ送る（設定を確かめるとき、これを選んで「実行」） */
function sendLatest() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトのプロパティに GITHUB_TOKEN がありません');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/contents/data/picks', {
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) { Logger.log('読めない：' + res.getResponseCode() + '（トークンの権限を確かめる）'); return; }
  const names = JSON.parse(res.getContentText()).map(f => f.name).filter(n => /^\d{8}\.txt$/.test(n)).sort();
  if (!names.length) { Logger.log('一覧がまだ1つも無い'); return; }
  const text = readFile_('data/picks/' + names[names.length - 1]);
  GmailApp.sendEmail(Session.getEffectiveUser().getEmail(), text.split('\n')[0], text);
  Logger.log('送った：' + names[names.length - 1]);
}
