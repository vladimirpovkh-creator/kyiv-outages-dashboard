/**
 * Daniya / SvitloBot public Telegram checker.
 * Setup: run install() once, deploy as Web app with access "Anyone".
 * No Telegram admin credentials, no GitHub token.
 */
const CHANNEL = 'https://t.me/s/svitlobot_daniya';
const KEY = 'daniya_last_status';
function install() {
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'checkDaniya').forEach(ScriptApp.deleteTrigger);
  ScriptApp.newTrigger('checkDaniya').timeBased().everyMinutes(5).create();
  checkDaniya();
}
function checkDaniya() {
  const props = PropertiesService.getScriptProperties();
  let prev = {};
  try { prev = JSON.parse(props.getProperty(KEY) || '{}'); } catch (_) {}
  const now = new Date().toISOString();
  try {
    const response = UrlFetchApp.fetch(CHANNEL, {
      muteHttpExceptions: true, followRedirects: true,
      headers: {'User-Agent': 'Mozilla/5.0 (compatible; DaniyaStatus/1.0)'}
    });
    if (response.getResponseCode() !== 200) throw new Error('HTTP ' + response.getResponseCode());
    const html = response.getContentText();
    const posts = html.match(/<div class="tgme_widget_message_wrap[\s\S]*?(?=<div class="tgme_widget_message_wrap|<\/body>)/g) || [];
    const events = [];
    for (const post of posts) {
      const time = (post.match(/<time[^>]*datetime="([^"]+)"/) || [])[1];
      const id = (post.match(/data-post="([^"]+)"/) || [])[1] || '';
      const body = (post.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/) || [])[1] || '';
      const text = body.replace(/<br\s*\/?\s*>/gi, ' ').replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ').replace(/&#39;/g, "'").replace(/&quot;/g, '"')
        .replace(/&amp;/g, '&').toLowerCase().replace(/\s+/g, ' ').trim();
      if (!time || !text) continue;
      const isOn = /світло\s+(?:є|з['’]явилось|з['’]явилося|відновлено|увімкнули)(?=\s|$|[.,!?:;])|електропостачання\s+відновлено(?=\s|$|[.,!?:;])|(?:світло|електрику)\s+(?:дали|увімкнули)(?=\s|$|[.,!?:;])/u.test(text);
      const isOff = /(?:немає|нема|відсутнє)\s+світла(?=\s|$|[.,!?:;])|світло\s+(?:зникло|вимкнули|відключили|відсутнє)(?=\s|$|[.,!?:;])|відключення\s+електроенергії(?=\s|$|[.,!?:;])/u.test(text);
      const ts = Date.parse(time);
      if (isOn === isOff || !Number.isFinite(ts) || ts > Date.now() + 300000) continue;
      events.push({ts, state: isOn ? 'on' : 'off', id});
    }
    events.sort((a,b) => b.ts-a.ts);
    if (!events.length || Date.now()-events[0].ts > 86400000) {
      props.setProperty(KEY, JSON.stringify({...prev, checked_at:now, source_status:'no_recent_event', reason:'Немає однозначних подій за 24 години'}));
      return;
    }
    const top = events[0];
    props.setProperty(KEY, JSON.stringify({
      state:top.state, changed_at:new Date(top.ts).toISOString(), observed_at:new Date(top.ts).toISOString(),
      checked_at:now, source:CHANNEL, source_status:'ok', group:'5.2', place:'ЖК Данія',
      message_id:top.id, reason:'Публічне повідомлення Telegram'
    }));
  } catch (error) {
    // Do not make a failed network request look like a successful fresh check.
    props.setProperty(KEY, JSON.stringify({...prev, source_status:'error', reason:String(error), last_error_at:now}));
    throw error;
  }
}
function doGet(e) {
  let data = {};
  try { data = JSON.parse(PropertiesService.getScriptProperties().getProperty(KEY) || '{}'); } catch (_) {}
  const callback = (e && e.parameter && e.parameter.callback) || '';
  if (/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(callback)) {
    return ContentService.createTextOutput(callback+'('+JSON.stringify(data)+');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
