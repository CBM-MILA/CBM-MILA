/**
 * السجل الرسمي لبطاقات مناصري نادي شباب بلدية ميلة (CBM Mila 1936) — Google Apps Script (v5)
 * ===========================================================================================
 * الميزات الأمنية والوظيفية:
 *   1) توليد معرّفات عشوائية غير قابلة للتخمين بصيغة CBM-XXXXXX (6 أرقام) عبر Utilities.getUuid()
 *      مع ضمان عدم التكرار في الشيت، مع بقاء جميع المعرّفات التسلسلية القديمة صالحة تماماً.
 *   2) حماية الخصوصية في التحقق العام (verify): إرجاع الاسم مقنّعاً فقط (مثال: «م*** ب***»)
 *      مع الحالة وتاريخ الإصدار، وعدم إرجاع الاسم الكامل أبداً عبر التحقق العام.
 *   3) حماية استعادة البطاقة (restore) بحد محاولات (Rate Limit) عبر CacheService:
 *      بحد أقصى 5 محاولات فاشلة كل 15 دقيقة لكل جهاز (deviceId).
 *   4) فصل الصلاحيات:
 *      - doGet: مخصص للتحقق العام فقط (يرفض أي إجراء إداري مثل list أو ack أو register).
 *      - doPost: يستقبل طلبات التسجيل، الاستعادة، التحقق، والإجراءات الإدارية المحمية بـ ADMIN_KEY.
 */

const SHEET_NAME = 'Supporters';
const PUSH_SHEET_NAME = 'PushSubs';
const VERSION = 6;
const RATE_LIMIT_MAX_FAILS = 5;
const RATE_LIMIT_WINDOW_SEC = 900; // 15 دقيقة

// ضع قيمة ADMIN_KEY هنا أو في Project Settings > Script Properties باسم ADMIN_KEY
const DEFAULT_ADMIN_KEY = '';

function getAdminKey_() {
  try {
    const propKey = PropertiesService.getScriptProperties().getProperty('ADMIN_KEY');
    if (propKey) return String(propKey).trim();
  } catch (e) {}
  return String(DEFAULT_ADMIN_KEY || '').trim();
}

// --- Web App Endpoints ---
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.q) return run_(p.q, 'GET');
  let sheetName = '';
  try { sheetName = ss_().getName(); } catch (err) { sheetName = 'ERROR'; }
  return out_({ ok: true, v: VERSION, service: 'CBM Mila Official Supporters Registry', sheet: sheetName });
}

function doPost(e) {
  const raw = (e && e.postData && e.postData.contents) || '{}';
  return run_(raw, 'POST');
}

function run_(raw, method) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    const payload = typeof raw === 'string' ? JSON.parse(raw) : raw;
    return out_(handle_(payload || {}, method));
  } catch (err) {
    return out_({ ok: false, code: 'error', msg: 'Invalid request payload' });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

// --- أدوات مساعدة ---
function num_(v) {
  return parseInt(String(v == null ? '' : v).replace(/\D/g, ''), 10) || 0;
}

function sid_(n) {
  return 'CBM-' + String(n).padStart(6, '0');
}

function normName_(s) {
  return String(s == null ? '' : s)
    .replace(/[\u064B-\u065F\u0670]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .replace(/[أإآ]/g, 'ا')
    .replace(/ة/g, 'ه')
    .replace(/ى/g, 'ي');
}

function cleanName_(s) {
  return String(s == null ? '' : s).replace(/\s+/g, ' ').trim().slice(0, 80);
}

/**
 * تقنيع الاسم لحماية الخصوصية عند مسح QR: يظهر أول حرف من كل كلمة متبوعاً بـ ***
 * مثال: "محمد أمين بلعريبي" -> "م*** أ*** ب***"
 */
function maskName_(fullName) {
  const cleaned = cleanName_(fullName);
  if (!cleaned) return '***';
  return cleaned
    .split(' ')
    .filter(Boolean)
    .map(function(word) { return Array.from(word)[0] + '***'; })
    .join(' ');
}

/**
 * توليد رقم عشوائي غير قابل للتخمين من 6 خانات (100000 - 999999) باستخدام Utilities.getUuid()
 * مع التأكد من عدم وجوده مسبقاً في الشيت.
 */
function generateUniqueRandomNo_(usedSet) {
  for (let attempt = 0; attempt < 50; attempt++) {
    const uuid = Utilities.getUuid().replace(/-/g, '');
    const chunk = parseInt(uuid.slice(0, 8), 16);
    const rand = Math.floor(Math.random() * 900000);
    const candidate = 100000 + ((chunk ^ rand) % 900000 + 900000) % 900000;
    if (!usedSet[candidate]) {
      return candidate;
    }
  }
  // احتياطي نادر جداً
  let fallback = 100000 + Math.floor(Math.random() * 899999);
  while (usedSet[fallback]) fallback = ((fallback - 99999) % 900000) + 100000;
  return fallback;
}

function rowStatus_(r) {
  const raw = String(r[5] || '').trim().toLowerCase();
  if (raw === 'revoked' || raw === 'ملغاة' || raw === 'ملغى') return 'revoked';
  if (raw === 'inactive' || raw === 'غير نشط') return 'inactive';
  return 'active';
}

function rowIso_(r) {
  try {
    const d = r[0] ? new Date(r[0]) : new Date();
    return isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
  } catch (e) {
    return new Date().toISOString();
  }
}

function fullCardObj_(r) {
  const no = num_(r[1]);
  const iso = rowIso_(r);
  const status = rowStatus_(r);
  return {
    ok: true,
    no: no,
    supporterId: sid_(no),
    serialNumber: sid_(no),
    name: String(r[2] || '').trim(),
    status: status,
    createdAt: iso
  };
}

function publicVerifyObj_(r) {
  const no = num_(r[1]);
  const iso = rowIso_(r);
  const status = rowStatus_(r);
  const masked = maskName_(r[2]);
  if (status !== 'active') {
    return {
      ok: false,
      code: status,
      supporterId: sid_(no),
      maskedName: masked,
      status: status,
      createdAt: iso
    };
  }
  return {
    ok: true,
    supporterId: sid_(no),
    serialNumber: sid_(no),
    maskedName: masked,
    status: 'active',
    createdAt: iso
  };
}

// --- المعالج الرئيسي للطلبات ---
function handle_(q, method) {
  const ver = q.v || 2;
  if (ver !== 1 && ver !== 2) return { ok: false, code: 'bad' };

  const action = String(q.a || 'verify').trim().toLowerCase();

  // رفض قاطع لأي إجراء إداري أو تعديلي عبر GET
  if (method === 'GET' && (action !== 'verify' || q.key)) {
    return { ok: false, code: 'method_not_allowed' };
  }

  const sheet = sheet_();
  const lastRow = sheet.getLastRow();
  const n = Math.max(0, lastRow - 1);
  const rows = n ? sheet.getRange(2, 1, n, 7).getValues() : [];

  // 1) التحقق العام من صلاحية البطاقة (يرجع الاسم مقنّعاً فقط)
  if (action === 'verify') {
    const targetNo = num_(q.supporterId || q.no || q.n || q.q);
    if (!targetNo) return { ok: false, code: 'not_found' };
    const r = rows.find(function(x) { return num_(x[1]) === targetNo; });
    if (!r) return { ok: false, code: 'not_found' };
    return publicVerifyObj_(r);
  }

  // جميع الإجراءات التالية تتطلب POST حصراً
  if (method !== 'POST') {
    return { ok: false, code: 'method_not_allowed' };
  }

  // 2) تسجيل بطاقة مناصر جديدة بمعرّف عشوائي CBM-XXXXXX
  if (action === 'register') {
    const name = cleanName_(q.name);
    if (name.length < 2 || name.length > 80) {
      return { ok: false, code: 'invalid_name' };
    }
    const targetNorm = normName_(name);
    const reqId = String(q.requestId || '').trim();
    const devId = String(q.dev || '').trim();

    const usedNumbers = {};
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i];
      const rNo = num_(r[1]);
      if (rNo > 0) usedNumbers[rNo] = true;
      if (normName_(r[2]) === targetNorm) {
        if ((reqId && String(r[3]) === reqId) || (devId && String(r[4]) === devId)) {
          return fullCardObj_(r);
        }
        return { ok: false, code: 'exists' };
      }
    }

    const randomNo = generateUniqueRandomNo_(usedNumbers);
    const nowIso = new Date().toISOString();
    const newRow = [nowIso, sid_(randomNo), name, reqId, devId, 'active', String(q.lang || 'ar')];
    sheet.appendRow(newRow);
    return fullCardObj_(newRow);
  }

  // 3) استعادة بطاقة مناصر مع حماية Rate Limit عبر CacheService
  if (action === 'restore') {
    const devKey = String(q.dev || 'anon').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 48) || 'anon';
    const cache = CacheService.getScriptCache();
    const rateKey = 'RL_RESTORE_' + devKey;
    const fails = parseInt(cache.get(rateKey) || '0', 10) || 0;

    if (fails >= RATE_LIMIT_MAX_FAILS) {
      return { ok: false, code: 'rate_limit', retryAfterMinutes: 15 };
    }

    const targetNo = num_(q.supporterId || q.no);
    const targetNorm = normName_(q.name);
    if (!targetNo || !targetNorm) {
      cache.put(rateKey, String(fails + 1), RATE_LIMIT_WINDOW_SEC);
      return { ok: false, code: 'not_found' };
    }

    const r = rows.find(function(x) { return num_(x[1]) === targetNo && normName_(x[2]) === targetNorm; });
    if (!r) {
      cache.put(rateKey, String(fails + 1), RATE_LIMIT_WINDOW_SEC);
      if (fails + 1 >= RATE_LIMIT_MAX_FAILS) {
        return { ok: false, code: 'rate_limit', retryAfterMinutes: 15 };
      }
      return { ok: false, code: 'not_found' };
    }

    cache.remove(rateKey);
    const status = rowStatus_(r);
    if (status === 'revoked') return { ok: false, code: 'revoked' };
    return fullCardObj_(r);
  }

  // 4) إجراء إداري: جلب المناصرين الجدد (POST + ADMIN_KEY)
  // نعتمد على رقم الصف الفعلي (rowIndex) لمتابعة المناصرين الجدد لأن أرقام البطاقات أصبحت عشوائية
  if (action === 'list') {
    const adminKey = getAdminKey_();
    if (!adminKey || String(q.key || '').trim() !== adminKey) {
      return { ok: false, code: 'denied' };
    }
    const props = PropertiesService.getScriptProperties();
    const lastAckRow = num_(props.getProperty('LAST_ACK_ROW') || 0);
    const items = [];
    for (let i = 0; i < rows.length; i++) {
      const rowNumber = i + 2; // الصف الفعلي في الشيت (يبدأ من 2)
      const r = rows[i];
      const rNo = num_(r[1]);
      if (rowNumber > lastAckRow && rNo > 0 && rowStatus_(r) !== 'revoked') {
        items.push({
          row: rowNumber,
          no: rNo,
          supporterId: sid_(rNo),
          name: String(r[2] || '').trim(),
          createdAt: rowIso_(r)
        });
      }
    }
    return { ok: true, total: rows.length, lastAck: lastAckRow, items: items };
  }

  // 5) إجراء إداري: تأكيد استلام قائمة المناصرين الجدد (POST + ADMIN_KEY)
  if (action === 'ack') {
    const adminKey = getAdminKey_();
    if (!adminKey || String(q.key || '').trim() !== adminKey) {
      return { ok: false, code: 'denied' };
    }
    const upTo = num_(q.upTo);
    const props = PropertiesService.getScriptProperties();
    const currentAck = num_(props.getProperty('LAST_ACK_ROW') || 0);
    const nextAck = Math.max(currentAck, upTo);
    props.setProperty('LAST_ACK_ROW', String(nextAck));
    return { ok: true, upTo: nextAck };
  }

  // 6) اشتراك إشعارات الهاتف الفورية (Web Push Subscribe - من الموقع)
  if (action === 'push_sub') {
    const sub = q.sub || {};
    const endpoint = String(sub.endpoint || '').trim();
    const keys = sub.keys || {};
    const p256dh = String(keys.p256dh || '').trim();
    const auth = String(keys.auth || '').trim();
    const devId = String(q.dev || '').trim().slice(0, 64);
    const lang = ['ar', 'fr', 'en'].indexOf(q.lang) >= 0 ? q.lang : 'ar';

    if (!/^https:\/\//i.test(endpoint) || !p256dh || !auth) {
      return { ok: false, code: 'invalid_subscription' };
    }

    const ps = pushSheet_();
    const pLast = ps.getLastRow();
    const pCount = Math.max(0, pLast - 1);
    const pRows = pCount ? ps.getRange(2, 1, pCount, 7).getValues() : [];
    const nowIso = new Date().toISOString();

    for (let i = 0; i < pRows.length; i++) {
      if (String(pRows[i][2]) === endpoint || (devId && String(pRows[i][1]) === devId)) {
        ps.getRange(i + 2, 1, 1, 7).setValues([[nowIso, devId, endpoint, p256dh, auth, lang, 'active']]);
        return { ok: true, subscribed: true };
      }
    }
    ps.appendRow([nowIso, devId, endpoint, p256dh, auth, lang, 'active']);
    return { ok: true, subscribed: true };
  }

  // 7) إلغاء اشتراك إشعارات الهاتف الفورية (Web Push Unsubscribe - من الموقع)
  if (action === 'push_unsub') {
    const endpoint = String((q.sub && q.sub.endpoint) || q.endpoint || '').trim();
    const devId = String(q.dev || '').trim();
    const ps = pushSheet_();
    const pLast = ps.getLastRow();
    const pCount = Math.max(0, pLast - 1);
    const pRows = pCount ? ps.getRange(2, 1, pCount, 7).getValues() : [];
    for (let i = 0; i < pRows.length; i++) {
      if ((endpoint && String(pRows[i][2]) === endpoint) || (devId && String(pRows[i][1]) === devId)) {
        ps.getRange(i + 2, 7).setValue('unsubscribed');
      }
    }
    return { ok: true, subscribed: false };
  }

  // 8) إجراء إداري: جلب اشتراكات الإشعارات النشطة لإرسال تنبيهات المباريات (POST + ADMIN_KEY)
  if (action === 'push_list') {
    const adminKey = getAdminKey_();
    if (!adminKey || String(q.key || '').trim() !== adminKey) {
      return { ok: false, code: 'denied' };
    }
    const ps = pushSheet_();
    const pLast = ps.getLastRow();
    const pCount = Math.max(0, pLast - 1);
    const pRows = pCount ? ps.getRange(2, 1, pCount, 7).getValues() : [];
    const subs = [];
    for (let i = 0; i < pRows.length; i++) {
      const r = pRows[i];
      if (String(r[6] || 'active').trim().toLowerCase() === 'active' && /^https:\/\//i.test(String(r[2]))) {
        subs.push({
          endpoint: String(r[2]).trim(),
          keys: { p256dh: String(r[3]).trim(), auth: String(r[4]).trim() },
          lang: String(r[5] || 'ar').trim()
        });
      }
    }
    return { ok: true, total: subs.length, items: subs };
  }

  // 9) إجراء إداري: تعطيل الاشتراكات المنتهية الصلاحية 404/410 (POST + ADMIN_KEY)
  if (action === 'push_prune') {
    const adminKey = getAdminKey_();
    if (!adminKey || String(q.key || '').trim() !== adminKey) {
      return { ok: false, code: 'denied' };
    }
    const dead = q.endpoints || [];
    const deadMap = {};
    for (let i = 0; i < dead.length; i++) deadMap[String(dead[i])] = true;
    const ps = pushSheet_();
    const pLast = ps.getLastRow();
    const pCount = Math.max(0, pLast - 1);
    const pRows = pCount ? ps.getRange(2, 1, pCount, 7).getValues() : [];
    let pruned = 0;
    for (let i = 0; i < pRows.length; i++) {
      if (deadMap[String(pRows[i][2])]) {
        ps.getRange(i + 2, 7).setValue('expired');
        pruned++;
      }
    }
    return { ok: true, pruned: pruned };
  }

  return { ok: false, code: 'bad' };
}

function sheet_() {
  const ss = ss_();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(['Timestamp', 'Number', 'Name', 'RequestId/NIN', 'DeviceId/Phone', 'Status/Paid', 'Lang']);
  }
  return sheet;
}

function pushSheet_() {
  const ss = ss_();
  let sheet = ss.getSheetByName(PUSH_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(PUSH_SHEET_NAME);
    sheet.appendRow(['Timestamp', 'DeviceId', 'Endpoint', 'P256dh', 'Auth', 'Lang', 'Status']);
  }
  return sheet;
}

function ss_() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function out_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
