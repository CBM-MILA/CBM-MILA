"""
مراقب بيانات شباب ميلة (CBM Mila) — النسخة المطوّرة
=====================================================
ماذا يفعل هذا الملف؟  (يشغّله GitHub Actions تلقائياً كل فترة)
  1) يقرأ ملف data/data.json الحالي بأمان.
  2) يزور موقع الرابطة (lirf.dz) مع إعادة المحاولة التلقائية عند ضعف الاتصال:
       - صفحة كل مباراة قادمة  ← يحدّث الموعد والملعب، ويسجّل النتيجة بعد نهاية المباراة.
       - صفحة الترتيب          ← يحدّث النقاط والمراكز وفارق الأهداف (مع الحفاظ على العقوبات).
  3) إن تغيّر شيء يحفظ data/data.json بطريقة ذرّية آمنة (Atomic Write) لمنع تلف الملف.
  4) يرسل إشعارات تليغرام منسّقة (نتائج مباريات شباب ميلة، تغيير المواعيد، وملخص التشغيل).
  5) يجلب قائمة المناصرين الجدد الذين استخرجوا بطاقات من سجل Google بمفتاح ADMIN_KEY،
     ويرسلها على تليغرام ثم يؤكد الاستلام (ack) فقط بعد نجاح إرسال كل الرسائل.

الإعدادات التي قد تغيّرها تجدها في القسم الأول فقط.
لتجربة السكربت دون حفظ تغييرات أو تأكيد السجل: شغّله بـ `python scraper.py --dry-run`
"""
import argparse
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ════════════════════════ 1) الإعدادات ════════════════════════
DATA_PATH = "data/data.json"          # ملف البيانات الذي يقرؤه الموقع
CBM_ID = "733"                        # رقم نادي شباب ميلة في موقع الرابطة

# True  = رسالة تليغرام في كل تشغيل، حتى لو لم يتغير شيء (للاطمئنان أن المراقب يعمل).
# False = رسائل فقط عند وجود تغيير أو مشكلة.
NOTIFY_EVERY_RUN = True

TZ = timezone(timedelta(hours=1))     # توقيت الجزائر (UTC+1 طوال السنة)
MATCH_LENGTH = timedelta(minutes=110)  # بعد هذه المدة من الانطلاق نعتبر المباراة منتهية
MAX_MATCHES_PER_RUN = 3               # نفحص أقرب 3 مباريات غير منتهية فقط (لتقليل الطلبات)
MAX_VALID_GOALS = 25                  # حد منطقي للأهداف لمنع قراءة أرقام الدقائق (مثل 90) كنتيجة

# ملعب شباب ميلة: يُستعمل تلقائياً للمباريات التي تُلعب في ميلة إن لم نجد اسم الملعب في صفحة المباراة.
HOME_STADIUM = "Stade Belkacem Belaid, Mila"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ar,fr;q=0.9,en;q=0.8",
}

# أسماء الأشهر في موقع الرابطة (بالعربية الجزائرية والفرنسية الاحتياطية)
MONTHS = {
    "جانفي": 1, "يناير": 1,
    "فيفري": 2, "فبراير": 2,
    "مارس": 3,
    "أفريل": 4, "افريل": 4, "أبريل": 4,
    "ماي": 5, "مايو": 5,
    "جوان": 6, "يونيو": 6,
    "جويلية": 7, "يوليو": 7,
    "أوت": 8, "اوت": 8, "أغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}

MAX_NAMES_PER_MESSAGE = 40            # عدد الأسماء في الرسالة الواحدة
TELEGRAM_MAX_LEN = 4000               # الحد الآمن لطول رسالة تليغرام الواحدة

# المفاتيح السرية (تُضاف في GitHub: Settings > Secrets and variables > Actions)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_KEY = os.getenv("ADMIN_KEY")    # نفس القيمة الموجودة في ADMIN_KEY داخل سكربت Google (Code.gs)

# إعداد سجل المتابعة (Logging) ليظهر بوضوح في GitHub Actions
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cbm-scraper")


# ════════════════════════ 2) جلسة الاتصال وأدوات مساعدة ════════════════════════
def create_session():
    """ينشئ جلسة HTTP تعيد المحاولة تلقائياً عند انقطاع الاتصال المؤقت أو أخطاء الخادم."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = create_session()


def registry_url():
    """رابط سجل المناصرين: من متغير REGISTRY_URL إن وُجد، وإلا من ملف config.js الموجود في المستودع."""
    url = os.getenv("REGISTRY_URL")
    if url:
        return url.strip()
    try:
        with open("config.js", encoding="utf-8") as f:
            m = re.search(r"https://script\.google\.com/[^'\"\s]+/exec", f.read())
            return m.group(0) if m else None
    except OSError:
        return None


def send_telegram_alert(message, dry_run=False):
    """يرسل رسالة إلى تليغرام (مع تقسيمها إن كانت طويلة) ويعيد True عند نجاح الإرسال."""
    if dry_run:
        log.info("[وضع التجربة Dry-Run] رسالة تليغرام:\n%s", message)
        return True
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("مفاتيح تليغرام غير مضبوطة؛ تم تخطي إرسال الإشعار.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # تقسيم الرسالة إن تجاوزت الحد المسموح في تليغرام
    chunks = [message[i:i + TELEGRAM_MAX_LEN] for i in range(0, max(len(message), 1), TELEGRAM_MAX_LEN)]
    all_ok = True
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            time.sleep(0.5)  # تجنب حظر السرعة (Rate Limit) من تليغرام
        try:
            r = SESSION.post(
                url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            if r.status_code != 200:
                log.error("فشل إرسال تليغرام (كود %s): %s", r.status_code, r.text)
                all_ok = False
        except Exception as e:
            log.error("استثناء أثناء إرسال تليغرام: %s", e)
            all_ok = False
    return all_ok


def load_data():
    """يقرأ ملف data/data.json بأمان ويعيد محتواه كقاموس."""
    if not os.path.exists(DATA_PATH):
        log.error("الملف %s غير موجود!", DATA_PATH)
        return None
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("تعذر قراءة ملف البيانات %s: %s", DATA_PATH, e)
        return None


def save_data(data, dry_run=False):
    """يحفظ البيانات بطريقة ذرّية (Atomic Write) عبر ملف مؤقت لضمان عدم تلف الملف الأصلي."""
    data["lastUpdated"] = datetime.now(TZ).isoformat(timespec="seconds")
    if dry_run:
        log.info("[وضع التجربة Dry-Run] تم تخطي حفظ التغييرات في %s", DATA_PATH)
        return

    parent_dir = os.path.dirname(DATA_PATH)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    tmp_path = f"{DATA_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, DATA_PATH)
    log.info("تم حفظ التحديثات بنجاح في %s", DATA_PATH)


def fetch(url, problems):
    """يجلب صفحة ويعيدها كـ BeautifulSoup. عند الفشل يسجّل السبب في قائمة problems."""
    try:
        r = SESSION.get(url, timeout=20)
        if r.status_code != 200:
            problems.append(f"{url} ← رد الخادم {r.status_code}")
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        problems.append(f"{url} ← تعذر الاتصال ({type(e).__name__})")
        return None


def to_int(text):
    """يحوّل '+5' إلى 5 و '-3' إلى -3 و '1.' إلى 1 (ويقبل علامة الناقص العربية). وإلا يعيد None."""
    t = str(text).strip().replace("−", "-").replace("–", "-").replace("+", "").rstrip(".")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def parse_iso_kickoff(iso_str):
    """يحوّل نص تاريخ المباراة إلى كائن datetime مزوّد بمنطقة زمنية (TZ) بأمان تام."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).strip())
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=TZ)
    except ValueError:
        return None


def get_club_name(data, club_id):
    """يبحث عن اسم النادي في بيانات الترتيب أو الأندية لعرضه في الإشعارات."""
    cid = str(club_id)
    for s in data.get("standings", []):
        if str(s.get("clubId")) == cid:
            return s.get("name") or s.get("clubName") or s.get("shortName") or f"نادي #{cid}"
    for c in data.get("clubs", []):
        if str(c.get("id")) == cid:
            return c.get("name") or c.get("shortName") or f"نادي #{cid}"
    return "شباب ميلة" if cid == CBM_ID else f"نادي #{cid}"


# ════════════════════════ 3) جدول الترتيب ════════════════════════
# أعمدة جدول الرابطة بالترتيب:
#   # | النادي | النقاط | لعب | فوز | تعادل | خسارة | له | عليه | الفارق
def update_standings(data, problems):
    url = data.get("sourceUrls", {}).get("ranking", "https://www.lirf.dz/ar/ranking")
    soup = fetch(url, problems)
    if not soup:
        return False

    # البحث عن جدول الترتيب الذي يحتوي على صفوف الأندية
    tables = soup.find_all("table")
    table = next((t for t in tables if re.search(r"clubs-logos/\d+-|/club/\d+", str(t))), None)
    if not table:
        problems.append("صفحة الترتيب: لم أجد الجدول (ربما تغيّر تصميم الموقع)")
        return False

    by_club = {str(s.get("clubId")): s for s in data.get("standings", []) if s.get("clubId") is not None}
    updated = False
    rows_read = 0

    for row in table.find_all("tr"):
        # صف النادي يحتوي شعاره أو رابطه، أما صفوف «المباراة السابقة/التالية» فنتجاهلها
        m = re.search(r"clubs-logos/(\d+)-|/club/(\d+)", str(row))
        if not m:
            continue
        club_id = m.group(1) or m.group(2)
        item = by_club.get(club_id)
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not item or len(cells) < 10:
            continue

        pos = to_int(cells[0].split()[0]) if cells[0].split() else None
        nums = [to_int(c) for c in cells[2:10]]  # النقاط، لعب، فوز، تعادل، خسارة، له، عليه، الفارق
        if pos is None or any(n is None for n in nums):
            continue

        rows_read += 1
        pts, played, w, d, l, gf, ga, gd = nums

        # الحفاظ على خصم النقاط اليدوي إن وُجد (مثل -3): adjustedPoints = النقاط الرسمية + الفرق القديم
        old_pts = item.get("points")
        old_adj = item.get("adjustedPoints")
        penalty = (old_adj - old_pts) if (isinstance(old_adj, int) and isinstance(old_pts, int)) else 0

        new = {
            "position": pos,
            "played": played,
            "wins": w,
            "draws": d,
            "losses": l,
            "goalsFor": gf,
            "goalsAgainst": ga,
            "goalDifference": gd,
            "points": pts,
            "adjustedPoints": pts + penalty,
        }
        if any(item.get(k) != v for k, v in new.items()):
            item.update(new)
            updated = True

    if rows_read == 0:
        problems.append("صفحة الترتيب: لم أستطع قراءة أي صف (تغيّر ترتيب الأعمدة؟)")
    if updated:
        data["standings"].sort(key=lambda s: (s.get("position") or 99, -(s.get("adjustedPoints") or 0)))
    return updated


# ════════════════════════ 4) المباريات ════════════════════════
def parse_score(soup, home_id, away_id):
    """
    النتيجة في صفحة المباراة تقع بين رابط نادي المضيف ورابط نادي الضيف.
    - نعيد تصفير الأرقام إذا تكرر رابط المضيف (الشعار ثم الاسم) لنقرأ فقط ما بين المضيف والضيف.
    - نستبعد صيغ الوقت (مثل 15:00) وأرقام الدقائق الكبيرة (مثل 90) لمنع النتائج الوهمية.
    """
    collecting, nums = False, []
    home_str, away_str = str(home_id), str(away_id)

    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a":
            m = re.search(r"/club/(\d+)\b", node.get("href", ""))
            if not m:
                continue
            cid = m.group(1)
            if cid == home_str:
                collecting = True
                nums = []  # تصفير الأرقام إن تكرر رابط المضيف (شعار النادي ثم اسمه)
            elif collecting and cid == away_str:
                break      # وصلنا لرابط الضيف: انتهى البحث
        elif collecting and isinstance(node, NavigableString):
            s = str(node).strip()
            if not s or re.search(r"\b\d{1,2}:\d{2}\b", s) or "'" in s:
                continue   # تجاهل النصوص الفارغة أو الساعة (15:00) أو الدقائق ('90)

            two = re.fullmatch(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", s)
            if two:
                h_val, a_val = int(two.group(1)), int(two.group(2))
                if h_val <= MAX_VALID_GOALS and a_val <= MAX_VALID_GOALS:
                    nums += [h_val, a_val]
            elif re.fullmatch(r"\d{1,2}", s):
                val = int(s)
                if val <= MAX_VALID_GOALS:
                    nums.append(val)

            if len(nums) >= 2:
                return nums[0], nums[1]
    return None


def parse_kickoff(soup, home_id):
    """
    موعد المباراة (التاريخ والساعة) في رأس الصفحة، قبل رابط نادي المضيف.
    يدعم الأشهر العربية (مثل: 10 أكتوبر 2026) والتواريخ الرقمية (مثل: 2026-10-10 أو 10/10/2026).
    """
    head, found = [], False
    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a" and re.search(rf"/club/{home_id}\b", node.get("href", "")):
            found = True
            break
        if isinstance(node, NavigableString):
            s = str(node).strip()
            if s:
                head.append(s)
    if not found:
        return None

    text = "\n".join(head)
    t = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not t:
        return None
    hour, minute = int(t.group(1)), int(t.group(2))

    # 1) صيغة الشهر العربي: "10 أكتوبر 2026"
    d_ar = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", text)
    if d_ar:
        return datetime(int(d_ar.group(3)), MONTHS[d_ar.group(2)], int(d_ar.group(1)), hour, minute, tzinfo=TZ)

    # 2) صيغة رقمية قياسية: "2026-10-10"
    d_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if d_iso:
        return datetime(int(d_iso.group(1)), int(d_iso.group(2)), int(d_iso.group(3)), hour, minute, tzinfo=TZ)

    # 3) صيغة رقمية محلية: "10/10/2026" أو "10-10-2026"
    d_num = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", text)
    if d_num:
        return datetime(int(d_num.group(3)), int(d_num.group(2)), int(d_num.group(1)), hour, minute, tzinfo=TZ)

    return None


def parse_venue(soup, home_id):
    """
    اسم الملعب في رأس صفحة المباراة: أول نص صالح بعد الساعة (مثل 15:00) وقبل رابط نادي المضيف.
    """
    head, found = [], False
    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a" and re.search(rf"/club/{home_id}\b", node.get("href", "")):
            found = True
            break
        if isinstance(node, NavigableString):
            t = re.sub(r"\s+", " ", str(node)).strip()
            if t:
                head.append(t)
    if not found:
        return None

    ignore_pattern = re.compile(
        r"الجولة|جولة|\d{4}|^\d+$|رابطة|الدوري|الجهات|الجهوي|الشرق|\bشرق\b|\bغرب\b|\bوسط\b|VS|QVR|أكابر|قريباً"
    )
    for i, t in enumerate(head):
        if re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", t):
            for cand in head[i + 1:i + 4]:
                if ignore_pattern.search(cand) or any(mn in cand for mn in MONTHS):
                    continue
                if 2 <= len(cand.split()) <= 12 and len(cand) <= 65:
                    return cand
            return None
    return None


def result_alert(data, m, score):
    """رسالة تليغرام مفصّلة لنتيجة شباب ميلة (مع اسم المنافس ومكان اللقاء)."""
    at_home = str(m.get("home")) == CBM_ID
    mine, theirs = (score[0], score[1]) if at_home else (score[1], score[0])
    verdict = "🟢 فوز" if mine > theirs else "🟡 تعادل" if mine == theirs else "🔴 خسارة"
    where = "داخل الديار" if at_home else "خارج الديار"

    home_name = html.escape(get_club_name(data, m.get("home")))
    away_name = html.escape(get_club_name(data, m.get("away")))

    return (
        f"⚽ <b>نهاية المباراة — الجولة {html.escape(str(m.get('round', '؟')))}</b>\n"
        f"🏟 {home_name} <b>{score[0]} - {score[1]}</b> {away_name}\n"
        f"📊 النتيجة لشباب ميلة: {verdict} ({where})"
    )


def update_matches(data, problems, notes, dry_run=False):
    base = data.get("sourceUrls", {}).get("match", "https://www.lirf.dz/ar/match/{id}")
    now = datetime.now(TZ)
    updated = False

    pending = [m for m in data.get("matches", []) if m.get("status") != "finished" and m.get("id") is not None]
    pending.sort(key=lambda m: m.get("round") or 99)
    checked_count = min(len(pending), MAX_MATCHES_PER_RUN)
    notes.append(f"المباريات غير المنتهية التي فُحصت: {checked_count}")

    for m in pending[:MAX_MATCHES_PER_RUN]:
        match_url = base.replace("{id}", str(m["id"])) if "{id}" in base else f"{base.rstrip('/')}/{m['id']}"
        soup = fetch(match_url, problems)

        if soup:
            # (أ) الموعد: يتغير عند التأجيل أو عندما يُحدَّد لأول مرة
            ko = parse_kickoff(soup, m.get("home"))
            if ko and m.get("kickoff") != ko.isoformat():
                m["kickoff"] = ko.isoformat()
                notes.append(f"الجولة {m.get('round')}: موعد جديد {ko:%Y-%m-%d %H:%M}")
                updated = True

        # (ب) الملعب (لا نغيّر ملعباً مكتوباً يدوياً)
        if not m.get("venue"):
            venue = HOME_STADIUM if str(m.get("home")) == CBM_ID else (parse_venue(soup, m.get("home")) if soup else None)
            if venue:
                m["venue"] = venue
                notes.append(f"الجولة {m.get('round')}: الملعب {venue}")
                updated = True

        if not soup:
            continue

        # (ج) النتيجة: لا نسجّلها إلا بعد انتهاء الوقت القانوني للمباراة
        kick = parse_iso_kickoff(m.get("kickoff"))
        if not kick or now < kick + MATCH_LENGTH:
            continue

        sc = parse_score(soup, m.get("home"), m.get("away"))
        if sc:
            m["score"] = {"home": sc[0], "away": sc[1]}
            m["status"] = "finished"
            notes.append(f"الجولة {m.get('round')}: سُجّلت النتيجة {sc[0]}-{sc[1]}")
            updated = True
            if CBM_ID in (str(m.get("home")), str(m.get("away"))):
                send_telegram_alert(result_alert(data, m, sc), dry_run=dry_run)
        else:
            problems.append(f"الجولة {m.get('round')}: انتهى وقتها ولم تُدرج النتيجة في الموقع بعد")

    return updated


# ════════════════════════ 5) المناصرون الذين استخرجوا بطاقات ════════════════════════
def registry_call(url, payload):
    """يطلب من سكربت Google (عبر GET) ويعيد الرد كقاموس، أو None عند الفشل."""
    try:
        r = SESSION.get(url, params={"q": json.dumps(payload)}, timeout=30)
        if r.status_code != 200:
            log.error("رد غير متوقع من سجل Google: %s", r.status_code)
            return None
        return r.json()
    except Exception as e:
        log.error("فشل الاتصال بسجل المناصرين: %s", e)
        return None


def report_new_supporters(problems, notes, dry_run=False):
    """
    يرسل على تليغرام أسماء وأرقام البطاقات للمناصرين الجدد فقط.
    بعد وصول الإشعار يؤكد للسجل (ack) حتى لا تتكرر نفس الأسماء.
    """
    url = registry_url()
    if not ADMIN_KEY or not url:
        notes.append("قائمة المناصرين: غير مفعّلة (ADMIN_KEY أو الرابط غير مضبوط)")
        return

    res = registry_call(url, {"v": 2, "a": "list", "key": ADMIN_KEY})
    if not res:
        problems.append("سجل المناصرين: تعذر الاتصال بسكربت Google")
        return
    if not res.get("ok"):
        hint = " (المفتاح لا يطابق ADMIN_KEY في Code.gs أو لم يُضبط)" if res.get("code") == "denied" else ""
        problems.append(f"سجل المناصرين: رفض الطلب [{res.get('code')}]{hint}")
        return

    raw_items = res.get("items", [])
    # تصفية العناصر للتأكد من سلامة رقم البطاقة (no) وعدم توقف السكربت بسبب بيانات ناقصة
    items = [
        x for x in raw_items
        if isinstance(x, dict) and str(x.get("no", "")).strip().isdigit()
    ]
    notes.append(f"مناصرون جدد: {len(items)} (الإجمالي {res.get('total', '؟')})")
    if not items:
        return

    all_sent = True
    for i in range(0, len(items), MAX_NAMES_PER_MESSAGE):
        part = items[i:i + MAX_NAMES_PER_MESSAGE]
        lines = [f"👥 <b>مناصرون استخرجوا بطاقاتهم</b> ({i + 1}–{i + len(part)} من {len(items)})"]
        lines += [f"• {html.escape(str(x.get('name', 'بدون اسم')).strip())} — <code>CBM-{int(x['no']):06d}</code>" for x in part]
        all_sent &= send_telegram_alert("\n".join(lines), dry_run=dry_run)

    if all_sent:
        if not dry_run:
            max_no = max(int(x["no"]) for x in items)
            ack_res = registry_call(url, {"v": 2, "a": "ack", "key": ADMIN_KEY, "upTo": max_no})
            if not ack_res or not ack_res.get("ok"):
                problems.append("سجل المناصرين: أُرسلت الأسماء لكن تعذر تأكيد الاستلام (ack)")
    else:
        problems.append("سجل المناصرين: تعذر إرسال القائمة إلى تليغرام (ستُعاد المحاولة في التشغيل التالي)")


# ════════════════════════ 6) التشغيل الرئيسي ════════════════════════
def main():
    parser = argparse.ArgumentParser(description="مراقب بيانات شباب ميلة (CBM Mila)")
    parser.add_argument("--dry-run", action="store_true", help="تشغيل تجريبي دون حفظ ملفات أو إرسال تليغرام فعلي")
    args = parser.parse_args()
    dry_run = args.dry_run or os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    log.info("بدء عملية فحص وتحديث البيانات... (dry_run=%s)", dry_run)
    data = load_data()
    if not data:
        send_telegram_alert("❌ <b>المراقب:</b> ملف data/data.json غير موجود أو تالف!", dry_run=dry_run)
        return

    problems, notes = [], []

    # 1) تحديث المباريات والترتيب
    m_updated = update_matches(data, problems, notes, dry_run=dry_run)
    s_updated = update_standings(data, problems)
    notes.append("الترتيب: " + ("تم تحديثه" if s_updated else "بلا تغيير"))

    # 2) حفظ التغييرات فوراً قبل أي خطوة خارجية أخرى لضمان عدم ضياع تحديثات الموقع
    if s_updated or m_updated:
        save_data(data, dry_run=dry_run)

    # 3) فحص سجل المناصرين الجدد (محمي بـ try/except حتى لا يؤثر على سير السكربت)
    try:
        report_new_supporters(problems, notes, dry_run=dry_run)
    except Exception as e:
        log.exception("خطأ غير متوقع في report_new_supporters")
        problems.append(f"سجل المناصرين: خطأ غير متوقع ({type(e).__name__})")

    # 4) تحديد حالة التشغيل وإرسال التقرير النهائي
    if s_updated or m_updated:
        status = "✅ <b>تم تحديث بيانات الموقع</b>"
    elif problems:
        status = "⚠️ <b>لم أستطع فحص الرابطة بالكامل</b> (التفاصيل أدناه)"
    else:
        status = "😴 <b>لا جديد</b> (لم يتغير شيء في الموقع)"
    log.info("الحالة النهائية: %s", re.sub(r"<[^>]+>", "", status))

    if NOTIFY_EVERY_RUN or s_updated or m_updated or problems:
        lines = [f"🤖 <b>مراقب CBM Mila</b> — {datetime.now(TZ):%Y-%m-%d %H:%M} (الجزائر)", status]
        lines += ["• " + html.escape(n) for n in notes]
        if problems:
            lines.append("⚠️ <b>مشاكل:</b>")
            lines += ["• " + html.escape(p) for p in problems]
        send_telegram_alert("\n".join(lines), dry_run=dry_run)


if __name__ == "__main__":
    main()
