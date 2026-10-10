/**
 * سجل مناصري شباب ميلة — Google Apps Script (النسخة 3)
 * يدعم البروتوكول القديم v1 والجديد v2 (التسجيل، الاستعادة، التحقق من البطاقة عبر QR).
 * الصقه كاملاً مكان الكود القديم، ثم: Deploy > Manage deployments > Edit (القلم) > Version: New version > Deploy
 * (يبقى الرابط /exec كما هو، لا حاجة لتغيير config.js)
 */
const SHEET_NAME = 'Supporters';
const VERSION = 3;

// افتح رابط /exec في المتصفح: يجب أن ترى "v":3 — إن لم تره فالنشر قديم (اصنع New version)
function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.q) return run_(p.q);               // مسار احتياطي للتطبيق (GET)
  let sheetName = '';
  try { sheetName = ss_().getName(); } catch (err) { sheetName = 'ERROR: ' + err.message; }
  return out_({ ok: true, v: VERSION, service: 'CBM Mila supporters registry', sheet: sheetName });
}

function doPost(e) {
  return run_((e && e.postData && e.postData.contents) || '{}');
}

function run_(raw) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    return out_(handle_(JSON.parse(raw)));
  } catch (err) {
    return out_({ ok: false, code: 'error', msg: String((err && err.message) || err) });
  } finally {
    try { lock.releaseLock(); } catch (x) {}
  }
}

// الرقم التسلسلي كعدد صحيح (الشيت قد يحوّل '0004' إلى 4 تلقائياً)
function num_(v) { return parseInt(String(v == null ? '' : v).replace(/\D/g, ''), 10) || 0; }
function no4_(n) { return String(n).padStart(4, '0'); }
function sid_(n) { return 'CBM-' + String(n).padStart(6, '0'); }

function handle_(q) {
  const ver = q.v;
  if (ver !== 1 && ver !== 2) return { ok: false, code: 'bad' };
  const sheet = sheet_();
  const n = Math.max(0, sheet.getLastRow() - 1);
  const rows = n ? sheet.getRange(2, 1, n, 6).getValues() : [];

  // شكل الرد حسب البروتوكول
  const card = function (r) {
    const iso = new Date(r[0]).toISOString(), no = num_(r[1]);
    if (ver === 2) return { ok: true, supporterId: sid_(no), serialNumber: sid_(no), name: String(r[2]), status: 'active', createdAt: iso };
    return { ok: true, no: no4_(no), name: String(r[2]), d: iso };
  };

  // التحقق من البطاقة (يُستخدم من رمز QR) — لا يحتاج الاسم
  if (q.a === 'verify') {
    const no = num_(q.supporterId || q.no);
    const r = no ? rows.find(function (x) { return num_(x[1]) === no; }) : null;
    return r ? card(r) : { ok: false, code: 'nf' };
  }

  const name = String(q.name || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  const key = key_(name);
  if (name.length < 2 || !key) return { ok: false, code: 'bad' };

  if (q.a === 'restore') {
    const no = num_(q.supporterId || q.no);
    const r = no ? rows.find(function (x) { return x[3] === key && num_(x[1]) === no; }) : null;
    return r ? card(r) : { ok: false, code: 'nf' };
  }

  if (q.a === 'register') {
    const ex = rows.find(function (x) { return x[3] === key; });
    if (ex) {
      // نفس الجهاز يعيد المحاولة (مثلاً انقطع الرد): نُرجع بطاقته بدل رفضه
      if (q.dev && String(ex[4]) === String(q.dev)) return card(ex);
      return { ok: false, code: 'exists' };
    }
    let max = 0;
    rows.forEach(function (x) { max = Math.max(max, num_(x[1])); });
    const no = max + 1;
    const now = new Date();
    sheet.appendRow([now, no4_(no), name, key, String(q.dev || '').slice(0, 40), String(q.lang || '').slice(0, 5)]);
    return card([now, no, name]);
  }
  return { ok: false, code: 'bad' };
}

// مفتاح الاسم: يتجاهل التشكيل والهمزات والتاء المربوطة والترتيب
function key_(s) {
  const t = String(s || '').normalize('NFKD')
    .replace(/[\u064B-\u065F\u0670\u0640\u0300-\u036F]/g, '')
    .replace(/[إأآٱ]/g, 'ا').replace(/ى/g, 'ي').replace(/ة/g, 'ه')
    .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي')
    .toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
  return t.split(' ').filter(Boolean).sort().join(' ');
}

// يعمل سواء أنشأت السكربت من داخل الشيت أو من script.google.com
function ss_() {
  let ss = SpreadsheetApp.getActiveSpreadsheet();
  if (ss) return ss;
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('SHEET_ID');
  if (id) return SpreadsheetApp.openById(id);
  ss = SpreadsheetApp.create('CBM Mila Supporters');   // يُنشأ تلقائياً في Google Drive الخاص بك
  props.setProperty('SHEET_ID', ss.getId());
  return ss;
}

function sheet_() {
  const ss = ss_();
  let s = ss.getSheetByName(SHEET_NAME);
  if (!s) {
    s = ss.insertSheet(SHEET_NAME);
    s.getRange('B:B').setNumberFormat('@');
    s.getRange('A:A').setNumberFormat('yyyy-mm-dd hh:mm');
    s.appendRow(['التاريخ والوقت', 'الرقم التسلسلي', 'الاسم واللقب', 'مفتاح (لا تعدّله)', 'الجهاز', 'اللغة']);
    s.setFrozenRows(1);
    s.getRange('H1').setValue('إجمالي المناصرين');
    s.getRange('I1').setFormula('=COUNTA(B2:B)');
  }
  return s;
}

// ملاحظة: ContentService يضيف ترويسة CORS تلقائياً بعد إعادة التوجيه، ولا يمكن ولا يلزم ضبطها يدوياً
function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
