/**
 * 来そうな馬：毎朝の一覧を、自分の Gmail に送る（Google Apps Script）。地方競馬と中央競馬は別のメール。
 * 一覧は GitHub の非公開のリポジトリ hassak0408/chiho-keiba の
 *   data/picks/日付.txt（地方。毎朝 GitHub Actions の chiho-pick が作る）
 *   data/picks/日付_jra.txt（中央。開催日の朝に jra-pick が作る）
 *
 * 使い方
 * 1. スクリプトのプロパティに GITHUB_TOKEN を入れる（chiho-keiba を読むだけのトークン。ここには書かない）。
 * 2. setup() を一度だけ実行する（10分ごとに check() が動くようになる）。試しに送るときは sendLatest() を実行する。
 * 3. 9:00〜13:00 のあいだ、今日の一覧ができていれば、それぞれ1回だけ送る。開催が無い日は送らない。
 */
const REPO = 'hassak0408/chiho-keiba';
const FROM_HOUR = 9, TO_HOUR = 13;
const KINDS = [
  { suffix: '', sent: 'SENT' },          // 地方
  { suffix: '_jra', sent: 'SENT_JRA' },  // 中央
];

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
  KINDS.forEach(k => {
    if (props.getProperty(k.sent) === day) return;
    const text = readFile_('data/picks/' + day + k.suffix + '.txt');
    if (!text) return;                    // まだできていない（または開催が無い日）
    GmailApp.sendEmail(Session.getEffectiveUser().getEmail(), text.split('\n')[0], text);
    props.setProperty(k.sent, day);
  });
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

/** 試し：いちばん新しい一覧（地方と中央のそれぞれ）をすぐ送る（設定を確かめるとき、これを選んで「実行」） */
function sendLatest() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトのプロパティに GITHUB_TOKEN がありません');
  const res = UrlFetchApp.fetch('https://api.github.com/repos/' + REPO + '/contents/data/picks', {
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) { Logger.log('読めない：' + res.getResponseCode() + '（トークンの権限を確かめる）'); return; }
  const all = JSON.parse(res.getContentText()).map(f => f.name);
  KINDS.forEach(k => {
    const re = new RegExp('^\\d{8}' + k.suffix + '\\.txt$');
    const names = all.filter(n => re.test(n)).sort();
    if (!names.length) { Logger.log('一覧がまだ無い：' + (k.suffix || '地方')); return; }
    const text = readFile_('data/picks/' + names[names.length - 1]);
    GmailApp.sendEmail(Session.getEffectiveUser().getEmail(), text.split('\n')[0], text);
    Logger.log('送った：' + names[names.length - 1]);
  });
}
