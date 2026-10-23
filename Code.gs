/**
 * ============================================================================
 * نادِي شَبَاب بَلَدِيَّة مِيلَة · CBM MILA 1936
 * السجل الرسمي لبطاقات المناصرين وإشعارات الهواتف (Google Apps Script — v3.2)
 * ============================================================================
 *
 * الضمانات الأمنية والمعمارية (v3.2):
 *  1) حماية تامة من حقن الصيغ (Spreadsheet Formula Injection):
 *     تُمرَّر جميع القيم النصية عبر `safeCell_()` التي تضيف بادئة `'` لأي قيمة تبدأ بـ
 *     `=`, `+`, `-`, `@`, `\t`, `\r`, `\n` (حتى بعد المسافات البادئة) قبل `appendRow` أو `setValue`.
 *  2) فصل القراءة عن الكتابة (Read/Write Lock Separation):
 *     عملية التحقق العامة `verify` للقراءة فقط وتعمل بدون `LockService` مع تحديد معدل خفيف
 *     (`VERIFY_MAX_PER_DEV = 30` / 15 دقيقة لكل جهاز و `VERIFY_MAX_GLOBAL = 300` / 15 دقيقة)
 *     لمنع تعداد الأرقام التسلسلية دون تعطيل مسح رموز QR يوم المباراة.
 *  3) حماية `restore` من التخمين ومن هجمات الحرمان من الخدمة (DoS):
 *     - حد صارم لكل بطاقة (`RESTORE_MAX_FAILS_PER_SID = 5` / 15 دقيقة) ولكل جهاز (`RESTORE_MAX_FAILS_PER_DEV = 5`).
 *     - إذا طابق معرّف الجهاز `dev` المعرّف المسجّل عند إصدار البطاقة (`DeviceId`)، يُسمح لصاحبها
 *       باستعادتها فوراً دون أن يتأثر بأي ضغط عام.
 *     - بدلاً من الحظر الشامل القاسي الذي قد يستغله مهاجم لإغلاق الخدمة عن الجميع، يُطبَّق عند
 *       تجاوز العتبة العامة (`RESTORE_SOFT_GLOBAL_THRESHOLD = 30`) تبطيء تدريجي (`Utilities.sleep(1500)`)
 *       وسجل تنبيه أمني (`console.warn`) مع الإبقاء على الحظر الصارم لكل بطاقة ولكل جهاز.
 *     - ملاحظة معمارية: تطبيقات الويب في Google Apps Script لا تكشف عنوان IP الحقيقي للعميل داخل `doPost(e)`,
 *       لذلك نجمع بين حدود البطاقة (`sid`) والجهاز (`dev`) والتبطيء العام الناعم.
 *  4) دعم العائلات على نفس الهاتف في `register`:
 *     - إذا أعاد نفس الجهاز إرسال نفس الاسم (`normName_(r[2]) === targetNorm`)، تُعاد بطاقته الحالية (Idempotent).
 *     - إذا كان الاسم مختلفاً على نفس الجهاز (أفراد عائلة يتشاركون هاتفاً واحداً)، يُسمح بإصدار بطاقة
 *       مستقلة لكل فرد ضمن سقف التسجيل (`REGISTER_MAX_PER_DEV = 3` بطاقات / 15 دقيقة لكل جهاز).
 *  5) التحقق الصارم من نطاقات Web Push (`isAllowedPushEndpoint_`):
 *     لا تُقبل إلا روابط HTTPS التابعة لخدمات الدفع القياسية (`fcm.googleapis.com`,
 *     `updates.push.services.mozilla.com`, `*.push.apple.com`, `*.notify.windows.com`) وبحد أقصى 5000 مشترك.
 *  6) مقارنة زمنية ثابتة (`timingSafeEqual_`) لمفتاح الإدارة `ADMIN_KEY` المخزّن في Script Properties.
 */

var SHEET_NAME = 'Supporters';
var PUSH_SHEET_NAME = 'PushSubs';
var PROP_ACK_CURSOR = 'LAST_ACK_ROW';
var PROP_ADMIN_KEY = 'ADMIN_KEY';

var RATE_WINDOW_SEC = 900;               // 15 minutes
var RESTORE_MAX_FAILS_PER_DEV = 5;       // Max 5 failed restore attempts per device / 15m
var RESTORE_MAX_FAILS_PER_SID = 5;       // Max 5 failed restore attempts per supporterId / 15m
var RESTORE_SOFT_GLOBAL_THRESHOLD = 30;  // Soft tarpit threshold (1500ms sleep + anomaly log, never global DoS)
var RESTORE_TARPIT_MS = 1500;
var REGISTER_MAX_PER_DEV = 3;            // Max 3 registrations per device / 15m (allows family members on shared phone)
var REGISTER_MAX_GLOBAL = 60;            // Max 60 registrations globally / 15m
var VERIFY_MAX_PER_DEV = 30;             // Max 30 verify lookups per device / 15m (prevents 6-digit ID enumeration)
var VERIFY_MAX_GLOBAL = 300;             // Max 300 verify lookups globally / 15m
var MAX_PUSH_SUBSCRIBERS = 5000;

var ALLOWED_PUSH_HOSTS_EXACT = [
  'fcm.googleapis.com',
  'updates.push.services.mozilla.com'
];
var ALLOWED_PUSH_HOST_SUFFIXES = [
  '.push.apple.com',
  '.notify.windows.com'
];

function doGet() {
  return json_({
    ok: false,
    code: 'method_not_allowed',
    message: 'Use HTTP POST with a JSON body.'
  });
}

function doPost(e) {
  var body = {};
  try {
    var raw = (e && e.postData && e.postData.contents) ? e.postData.contents : '{}';
    body = JSON.parse(raw);
  } catch (parseErr) {
    return json_({ ok: false, code: 'bad_json' });
  }

  var action = String(body.a || body.action || '').trim();

  // Read-only public verification runs WITHOUT LockService so public QR scans never contend with writes
  if (action === 'verify') {
    try {
      return verifySupporter_(body);
    } catch (verErr) {
      return json_({ ok: false, code: 'server_error' });
    }
  }

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    return json_({ ok: false, code: 'lock_timeout' });
  }

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ensureSupportersSheet_(ss);

    if (action === 'register')   return registerSupporter_(sh, body);
    if (action === 'restore')    return restoreSupporter_(sh, body);
    if (action === 'list')       return listNewSupporters_(sh, body);
    if (action === 'ack')        return ackSupporters_(sh, body);
    if (action === 'push_sub')   return savePushSub_(ss, body);
    if (action === 'push_unsub') return removePushSub_(ss, body);
    if (action === 'push_list')  return listPushSubs_(ss, body);
    if (action === 'push_prune') return prunePushSubs_(ss, body);

    return json_({ ok: false, code: 'unknown_action' });
  } catch (err) {
    return json_({ ok: false, code: 'server_error' });
  } finally {
    lock.releaseLock();
  }
}

/* ─────────────────── 1) إصدار واستعادة والتحقق من البطاقات ─────────────────── */

function registerSupporter_(sh, b) {
  var name = cleanName_(b.name);
  if (name.length < 2 || name.length > 80) {
    return json_({ ok: false, code: 'invalid_name' });
  }

  var devId = cleanToken_(b.dev || 'anon', 64);
  var requestId = cleanToken_(b.requestId || '', 80);
  var lang = ['ar', 'fr', 'en'].indexOf(String(b.lang || '')) !== -1 ? String(b.lang) : 'ar';

  var targetNorm = normName_(name);
  var rows = sh.getDataRange().getValues();

  // 1) Check idempotent retries and duplicate names first
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (requestId && String(r[8] || '') === requestId) {
      return cardRes_(r, true);
    }
    if (normName_(r[2]) === targetNorm) {
      // Same person on the same device retrying -> return their existing card
      if (devId !== 'anon' && String(r[9] || '') === devId) {
        return cardRes_(r, true);
      }
      return json_({ ok: false, code: 'exists' });
    }
  }

  // 2) Enforce registration rate limits (allows up to 3 family members on the same phone / 15m)
  var cache = CacheService.getScriptCache();
  var devRegKey = 'rl_reg_dev_' + devId;
  var globalRegKey = 'rl_reg_global';
  var devCount = Number(cache.get(devRegKey) || 0);
  var globalCount = Number(cache.get(globalRegKey) || 0);
  if ((devId !== 'anon' && devCount >= REGISTER_MAX_PER_DEV) || globalCount >= REGISTER_MAX_GLOBAL) {
    return json_({ ok: false, code: 'rate_limit' });
  }
  cache.put(devRegKey, String(devCount + 1), RATE_WINDOW_SEC);
  cache.put(globalRegKey, String(globalCount + 1), RATE_WINDOW_SEC);

  var usedIds = {};
  for (var j = 1; j < rows.length; j++) {
    usedIds[String(rows[j][1] || '').toUpperCase()] = true;
  }

  var no = Math.max(1, rows.length);
  var supporterId = generateUniqueSupporterId_(usedIds);
  var nowIso = new Date().toISOString();

  sh.appendRow([
    no,
    safeCell_(supporterId),
    safeCell_(name),
    safeCell_(supporterId),
    'active',
    nowIso,
    safeCell_(lang),
    'Mila',
    safeCell_(requestId),
    safeCell_(devId)
  ]);

  return json_({
    ok: true,
    no: no,
    supporterId: supporterId,
    serialNumber: supporterId,
    name: name,
    status: 'active',
    createdAt: nowIso
  });
}

function restoreSupporter_(sh, b) {
  var devId = cleanToken_(b.dev || 'anon', 64);
  var sid = String(b.supporterId || '').trim().toUpperCase();
  var name = cleanName_(b.name);
  if (!/^CBM-\d{6}$/.test(sid) || name.length < 2) {
    return json_({ ok: false, code: 'not_found' });
  }

  var cache = CacheService.getScriptCache();
  var kDev = 'rl_rest_dev_' + devId;
  var kSid = 'rl_rest_sid_' + sid;
  var kGlobal = 'rl_rest_global';

  var dFails = Number(cache.get(kDev) || 0);
  var sFails = Number(cache.get(kSid) || 0);
  var gFails = Number(cache.get(kGlobal) || 0);

  // Strict per-card and per-device brute-force lockouts
  if (dFails >= RESTORE_MAX_FAILS_PER_DEV || sFails >= RESTORE_MAX_FAILS_PER_SID) {
    return json_({ ok: false, code: 'rate_limit' });
  }

  var targetNorm = normName_(name);
  var rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (String(r[1] || '').toUpperCase() === sid) {
      var isRegisteredDevice = (devId !== 'anon' && String(r[9] || '') === devId);

      // Soft global protection: if global failures are elevated and caller is NOT on the registered device,
      // apply a progressive tarpit delay + log anomaly rather than locking out all legitimate users globally.
      if (!isRegisteredDevice && gFails >= RESTORE_SOFT_GLOBAL_THRESHOLD) {
        console.warn('[CBM Security] High global restore failure rate (' + gFails + '); applying tarpit delay for sid=' + sid);
        Utilities.sleep(RESTORE_TARPIT_MS);
      }

      if (normName_(r[2]) !== targetNorm) {
        break;
      }

      cache.remove(kDev);
      cache.remove(kSid);
      var st = String(r[4] || 'active').toLowerCase();
      if (st === 'revoked') return json_({ ok: false, code: 'revoked' });
      return cardRes_(r, false);
    }
  }

  cache.put(kDev, String(dFails + 1), RATE_WINDOW_SEC);
  cache.put(kSid, String(sFails + 1), RATE_WINDOW_SEC);
  cache.put(kGlobal, String(gFails + 1), RATE_WINDOW_SEC);
  return json_({ ok: false, code: 'not_found' });
}

function verifySupporter_(b) {
  var sid = String(b.supporterId || '').trim().toUpperCase();
  if (!/^CBM-\d{6}$/.test(sid)) {
    return json_({ ok: false, code: 'not_found' });
  }

  // Light rate limit on public verify to make 6-digit ID enumeration impractical
  var devId = cleanToken_(b.dev || 'anon', 64);
  var cache = CacheService.getScriptCache();
  var kVerDev = 'rl_ver_dev_' + devId;
  var kVerGlobal = 'rl_ver_global';
  var vDev = Number(cache.get(kVerDev) || 0);
  var vGlobal = Number(cache.get(kVerGlobal) || 0);
  if (vDev >= VERIFY_MAX_PER_DEV || vGlobal >= VERIFY_MAX_GLOBAL) {
    return json_({ ok: false, code: 'rate_limit' });
  }
  cache.put(kVerDev, String(vDev + 1), RATE_WINDOW_SEC);
  cache.put(kVerGlobal, String(vGlobal + 1), RATE_WINDOW_SEC);

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) return json_({ ok: false, code: 'not_found' });

  var rows = sh.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    var r = rows[i];
    if (String(r[1] || '').toUpperCase() === sid) {
      var st = String(r[4] || 'active').toLowerCase();
      if (st === 'revoked')  return json_({ ok: false, code: 'revoked' });
      if (st === 'inactive') return json_({ ok: false, code: 'inactive' });
      return json_({
        ok: true,
        supporterId: String(r[1]),
        serialNumber: String(r[3] || r[1]),
        maskedName: maskName_(String(r[2] || '')),
        status: st,
        createdAt: r[5]
      });
    }
  }
  return json_({ ok: false, code: 'not_found' });
}

/* ─────────────────── 2) إدارة سجل المناصرين (للمراقب الآلي) ─────────────────── */

function listNewSupporters_(sh, b) {
  if (!isValidAdminKey_(b.key)) {
    return json_({ ok: false, code: 'denied' });
  }
  var props = PropertiesService.getScriptProperties();
  var lastRow = Number(props.getProperty(PROP_ACK_CURSOR) || 1);
  var rows = sh.getDataRange().getValues();
  var items = [];
  for (var i = Math.max(1, lastRow); i < rows.length; i++) {
    var r = rows[i];
    items.push({
      row: i + 1,
      no: r[0],
      supporterId: String(r[1] || '').replace(/^'+/, ''),
      name: String(r[2] || '').replace(/^'+/, ''),
      status: String(r[4] || 'active'),
      createdAt: r[5]
    });
  }
  return json_({
    ok: true,
    total: Math.max(0, rows.length - 1),
    items: items
  });
}

function ackSupporters_(sh, b) {
  if (!isValidAdminKey_(b.key)) {
    return json_({ ok: false, code: 'denied' });
  }
  var upTo = Number(b.upTo || 0);
  if (upTo > 0) {
    PropertiesService.getScriptProperties().setProperty(PROP_ACK_CURSOR, String(upTo));
  }
  return json_({ ok: true, upTo: upTo });
}

/* ─────────────────── 3) اشتراكات Web Push ─────────────────── */

function isAllowedPushEndpoint_(endpoint) {
  var ep = String(endpoint || '').trim();
  if (ep.indexOf('https://') !== 0 || ep.length > 1200) return false;
  var m = ep.match(/^https:\/\/([^\/:?#]+)(?:\/|$)/i);
  if (!m) return false;
  var host = m[1].toLowerCase();
  for (var i = 0; i < ALLOWED_PUSH_HOSTS_EXACT.length; i++) {
    if (host === ALLOWED_PUSH_HOSTS_EXACT[i]) return true;
  }
  for (var j = 0; j < ALLOWED_PUSH_HOST_SUFFIXES.length; j++) {
    var sfx = ALLOWED_PUSH_HOST_SUFFIXES[j];
    if (host.length > sfx.length && host.slice(host.length - sfx.length) === sfx) {
      return true;
    }
  }
  return false;
}

function savePushSub_(ss, b) {
  var sub = b.sub || {};
  var ep = String(sub.endpoint || '').trim();
  var keys = sub.keys || {};
  var p256dh = String(keys.p256dh || '').trim();
  var auth = String(keys.auth || '').trim();

  if (!isAllowedPushEndpoint_(ep) || !p256dh || !auth || p256dh.length > 256 || auth.length > 128) {
    return json_({ ok: false, code: 'invalid_subscription' });
  }

  var lang = ['ar', 'fr', 'en'].indexOf(String(b.lang || '')) !== -1 ? String(b.lang) : 'ar';
  var dev = cleanToken_(b.dev || 'anon', 64);
  var nowIso = new Date().toISOString();

  var sh = ensurePushSheet_(ss);
  var rows = sh.getDataRange().getValues();

  for (var i = 1; i < rows.length; i++) {
    var existingEp = String(rows[i][0] || '').replace(/^'+/, '');
    var existingDev = String(rows[i][3] || '').replace(/^'+/, '');
    if (existingEp === ep || (dev !== 'anon' && existingDev === dev)) {
      sh.getRange(i + 1, 1, 1, 5).setValues([[
        safeCell_(ep),
        safeCell_(p256dh),
        safeCell_(auth),
        safeCell_(dev),
        safeCell_(lang)
      ]]);
      sh.getRange(i + 1, 6).setValue(nowIso);
      return json_({ ok: true, updated: true });
    }
  }

  if (rows.length - 1 >= MAX_PUSH_SUBSCRIBERS) {
    return json_({ ok: false, code: 'push_capacity_reached' });
  }

  sh.appendRow([
    safeCell_(ep),
    safeCell_(p256dh),
    safeCell_(auth),
    safeCell_(dev),
    safeCell_(lang),
    nowIso
  ]);
  return json_({ ok: true, created: true });
}

function removePushSub_(ss, b) {
  var ep = String(b.endpoint || '').trim();
  var dev = cleanToken_(b.dev || '', 64);
  var sh = ss.getSheetByName(PUSH_SHEET_NAME);
  if (!sh) return json_({ ok: true });

  var rows = sh.getDataRange().getValues();
  for (var i = rows.length - 1; i >= 1; i--) {
    var rEp = String(rows[i][0] || '').replace(/^'+/, '');
    var rDev = String(rows[i][3] || '').replace(/^'+/, '');
    if ((ep && rEp === ep) || (dev && dev !== 'anon' && rDev === dev)) {
      sh.deleteRow(i + 1);
    }
  }
  return json_({ ok: true });
}

function listPushSubs_(ss, b) {
  if (!isValidAdminKey_(b.key)) {
    return json_({ ok: false, code: 'denied' });
  }
  var sh = ss.getSheetByName(PUSH_SHEET_NAME);
  if (!sh) return json_({ ok: true, items: [] });

  var rows = sh.getDataRange().getValues();
  var items = [];
  for (var i = 1; i < rows.length; i++) {
    var ep = String(rows[i][0] || '').replace(/^'+/, '');
    var p256dh = String(rows[i][1] || '').replace(/^'+/, '');
    var auth = String(rows[i][2] || '').replace(/^'+/, '');
    var lang = String(rows[i][4] || 'ar').replace(/^'+/, '');
    if (isAllowedPushEndpoint_(ep) && p256dh && auth) {
      items.push({
        endpoint: ep,
        keys: { p256dh: p256dh, auth: auth },
        lang: lang
      });
    }
  }
  return json_({ ok: true, items: items });
}

function prunePushSubs_(ss, b) {
  if (!isValidAdminKey_(b.key)) {
    return json_({ ok: false, code: 'denied' });
  }
  var list = Array.isArray(b.endpoints) ? b.endpoints : [];
  if (!list.length) return json_({ ok: true, pruned: 0 });

  var deadMap = {};
  for (var k = 0; k < list.length; k++) {
    deadMap[String(list[k] || '').trim()] = true;
  }

  var sh = ss.getSheetByName(PUSH_SHEET_NAME);
  if (!sh) return json_({ ok: true, pruned: 0 });

  var rows = sh.getDataRange().getValues();
  var pruned = 0;
  for (var i = rows.length - 1; i >= 1; i--) {
    var rEp = String(rows[i][0] || '').replace(/^'+/, '');
    if (deadMap[rEp]) {
      sh.deleteRow(i + 1);
      pruned++;
    }
  }
  return json_({ ok: true, pruned: pruned });
}

/* ─────────────────── 4) دوال الحماية والمساعدة ─────────────────── */

function safeCell_(val) {
  var s = String(val == null ? '' : val);
  if (/^[\s]*[=+\-@\t\r\n]/.test(s)) {
    return "'" + s;
  }
  return s;
}

function cleanName_(raw) {
  return String(raw || '')
    .replace(/[\u0000-\u001F\u007F]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80);
}

function cleanToken_(raw, maxLen) {
  return String(raw || '')
    .replace(/[^A-Za-z0-9_\-:.]/g, '')
    .slice(0, maxLen || 64);
}

function normName_(s) {
  return String(s || '')
    .replace(/^'+/, '')
    .replace(/[\u064B-\u065F\u0670]/g, '')
    .replace(/[أإآ]/g, 'ا')
    .replace(/ة/g, 'ه')
    .replace(/ى/g, 'ي')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function maskName_(name) {
  var clean = String(name || '').replace(/^'+/, '').trim();
  if (!clean) return '***';
  var parts = clean.split(/\s+/);
  var out = [];
  for (var i = 0; i < parts.length; i++) {
    if (parts[i]) out.push(parts[i].charAt(0) + '***');
  }
  return out.join(' ') || '***';
}

function generateUniqueSupporterId_(usedIds) {
  for (var attempt = 0; attempt < 50; attempt++) {
    var num = Math.floor(100000 + Math.random() * 900000);
    var cand = 'CBM-' + String(num);
    if (!usedIds[cand]) return cand;
  }
  return 'CBM-' + String(Date.now()).slice(-6);
}

function isValidAdminKey_(providedKey) {
  var expected = PropertiesService.getScriptProperties().getProperty(PROP_ADMIN_KEY);
  if (!expected || !providedKey) return false;
  return timingSafeEqual_(String(providedKey), String(expected));
}

function timingSafeEqual_(a, b) {
  var strA = String(a);
  var strB = String(b);
  var len = Math.max(strA.length, strB.length);
  var diff = strA.length ^ strB.length;
  for (var i = 0; i < len; i++) {
    var codeA = i < strA.length ? strA.charCodeAt(i) : 0;
    var codeB = i < strB.length ? strB.charCodeAt(i) : 0;
    diff |= (codeA ^ codeB);
  }
  return diff === 0 && strA.length > 0;
}

function ensureSupportersSheet_(ss) {
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(['No', 'SupporterId', 'Name', 'SerialNumber', 'Status', 'CreatedAt', 'Lang', 'City', 'RequestId', 'DeviceId']);
  }
  return sh;
}

function ensurePushSheet_(ss) {
  var sh = ss.getSheetByName(PUSH_SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(PUSH_SHEET_NAME);
    sh.appendRow(['Endpoint', 'P256dh', 'Auth', 'DeviceId', 'Lang', 'UpdatedAt']);
  }
  return sh;
}

function cardRes_(r, deduped) {
  return json_({
    ok: true,
    deduped: Boolean(deduped),
    no: r[0],
    supporterId: String(r[1] || '').replace(/^'+/, ''),
    name: String(r[2] || '').replace(/^'+/, ''),
    serialNumber: String(r[3] || r[1] || '').replace(/^'+/, ''),
    status: String(r[4] || 'active').toLowerCase(),
    createdAt: r[5]
  });
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
