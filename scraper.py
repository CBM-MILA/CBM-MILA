"""
مراقب بيانات شباب ميلة (CBM Mila 1936)
========================================
المهام:
  1) قراءة وتحديث data/data.json (schemaVersion 3) مع توحيد اسم الملعب (Stade Belkacem Belaid)،
     وتحويل الأسماء العربية إلى لاتينية، وحساب approxAge و lastFetchedAt، وربط playerId في الأحداث.
  2) فحص موقع الرابطة (lirf.dz) لتحديث مواعيد ونتائج وأحداث المباريات وجدول الترتيب.
  3) الاتصال بسجل المناصرين (Google Apps Script) عبر POST فقط مع إرسال ADMIN_KEY داخل الجسم JSON.
  4) تنقية جميع السجلات (Logs) لضمان عدم تسريب TELEGRAM_BOT_TOKEN أو ADMIN_KEY في سجل الأخطاء.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import html
import json
import logging
import os
import re
import shutil
import time

from bs4 import BeautifulSoup, NavigableString, Tag
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ════════════════════════ 1) الإعدادات ════════════════════════
DATA_PATH = "data/data.json"
ROOT_DATA_PATH = "data.json"
CBM_ID = "733"
NOTIFY_EVERY_RUN = True

TZ = timezone(timedelta(hours=1))      # توقيت الجزائر (UTC+1)
MATCH_LENGTH = timedelta(minutes=110)
MAX_MATCHES_PER_RUN = 3
MAX_VALID_GOALS = 25

HOME_STADIUM = "Stade Belkacem Belaid, Mila"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ar,fr;q=0.9,en;q=0.8",
}

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

# قاموس التحويل الصوتى للأسماء الجزائرية إلى الحروف اللاتينية
KNOWN_LATIN_NAMES = {
    "بلعريبي سعيد": "Said Belaribi",
    "قياس محمد": "Mohammed Kias",
    "يحياوي الوليد": "El Oualid Yahiaoui",
    "مسعي أسامة": "Oussama Messai",
    "حميدي محمد بهاء الدين": "Mohamed Baha Eddine Hamidi",
    "شابونية حسام": "Houceme Chabounia",
    "مقيرد عمر": "Omar Mekired",
    "فقراوي بلقاسم": "Belgacem Fekraoui",
    "زكور اسامة": "Oussama Zekour",
    "قلبوزة بلقاسم": "Belgacem Kalbouza",
    "بولدياب بلال": "Bilal Bouldiab",
    "بن يحي سراج الدين": "Seradj Eddine Benyahia",
    "بن لعريبي سليمان": "Slimane Benlaribi",
    "بودابة برهان": "Borhane Boudaba",
    "عابد واسيم": "Ouassim Abed",
    "سياب يوسف إسلام": "Youcef Islam Siab",
    "عقبي بن حدوش حسن": "Hassen Ogbi Benhadouche",
    "عتامنة محمد عصام": "Mohamed Issam Atamna",
    "قيرة إسماعيل": "Ismail Guira",
    "قدور عبد المالك": "Abdelmalek Kaddour",
    "مبرك محمد تاج الدين": "Mohamed Tadj Eddine Mebrek",
    "بوقصبة وسيم": "Ouassim Boukacem",
    "شريبط ابراهيم": "Brahim Cheribet",
    "جزار عبد العالي": "Abdelali Djezzar",
    "بن الطيب رامي": "Rami Bentayeb",
    "بن صغير حمزة": "Hamza Benseghier",
    "BENSEGHIER HAMZA": "Hamza Benseghier",
    "خابية صلاح الدين": "Salah Eddine Khabia",
    "رملي ناجي": "Nadji Ramli",
    "ماضي رابح": "Rabah Madhi",
    "لعطيوي وسيم": "Ouassim Latioui",
    "دغموش رابح": "Rabah Dekhmouche",
}

AR_WORD_LATIN = {
    "محمد": "Mohamed", "احمد": "Ahmed", "أحمد": "Ahmed", "وسيم": "Ouassim", "واسيم": "Ouassim",
    "اسامة": "Oussama", "أسامة": "Oussama", "بلقاسم": "Belgacem", "بلال": "Bilal", "عمر": "Omar",
    "حسام": "Houceme", "سليمان": "Slimane", "ابراهيم": "Brahim", "إبراهيم": "Brahim",
    "اسماعيل": "Ismail", "إسماعيل": "Ismail", "رابح": "Rabah", "رامي": "Rami", "حمزة": "Hamza",
    "ناجي": "Nadji", "حسن": "Hassen", "سعيد": "Said", "وليد": "Oualid", "الوليد": "El Oualid",
    "يوسف": "Youcef", "اسلام": "Islam", "إسلام": "Islam", "عصام": "Issam", "برهان": "Borhane",
    "صلاح": "Salah", "سراج": "Seradj", "تاج": "Tadj", "بهاء": "Baha", "الدين": "Eddine",
    "عبد": "Abdel", "المالك": "Malek", "العالي": "Ali", "القادر": "Kader", "الرحمان": "Rahmane",
    "الرحمن": "Rahmane", "بوقصبة": "Boukacem", "شريبط": "Cheribet", "جزار": "Djezzar",
    "خابية": "Khabia", "رملي": "Ramli", "ماضي": "Madhi", "لعطيوي": "Latioui", "دغموش": "Dekhmouche",
    "فقراوي": "Fekraoui", "زكور": "Zekour", "قلبوزة": "Kalbouza", "بولدياب": "Bouldiab",
    "بودابة": "Boudaba", "عابد": "Abed", "سياب": "Siab", "عقبي": "Ogbi", "عتامنة": "Atamna",
    "قيرة": "Guira", "قدور": "Kaddour", "مبرك": "Mebrek", "حميدي": "Hamidi", "شابونية": "Chabounia",
    "مقيرد": "Mekired", "بلعريبي": "Belaribi", "قياس": "Kias", "يحياوي": "Yahiaoui", "مسعي": "Messai",
    "بن": "Ben", "يحي": "Yahia", "لعريبي": "Laribi", "حدوش": "Hadouche", "الطيب": "Tayeb", "صغير": "Seghier",
}

MAX_NAMES_PER_MESSAGE = 40
TELEGRAM_MAX_LEN = 4000

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_KEY = os.getenv("ADMIN_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_CLAIMS = {"sub": "mailto:contact@cbm-mila.dz"}


# ════════════════════════ 2) حماية السجلات (Redaction Filter) ════════════════════════
def sanitize_text(msg):
    """يزيل أي ظهور للمفاتيح السرية أو توكن تليغرام من رسائل السجل والأخطاء."""
    s = str(msg or "")
    if TELEGRAM_TOKEN:
        s = s.replace(TELEGRAM_TOKEN, "***REDACTED_TOKEN***")
    if ADMIN_KEY:
        s = s.replace(ADMIN_KEY, "***REDACTED_KEY***")
    if VAPID_PRIVATE_KEY:
        s = s.replace(VAPID_PRIVATE_KEY, "***REDACTED_VAPID***")
    if TELEGRAM_CHAT_ID:
        s = s.replace(str(TELEGRAM_CHAT_ID), "***REDACTED_CHAT***")
    s = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***REDACTED***", s)
    return s


class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = sanitize_text(record.msg)
        if record.args:
            record.args = tuple(sanitize_text(a) if isinstance(a, str) else a for a in record.args)
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cbm-scraper")
log.addFilter(RedactingFilter())


# ════════════════════════ 3) جلسة الاتصال وأدوات مساعدة ════════════════════════
def create_session():
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
    if dry_run:
        log.info("[Dry-Run] رسالة تليغرام:\n%s", message)
        return True
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("مفاتيح تليغرام غير مضبوطة؛ تم تخطي إرسال الإشعار.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [message[i:i + TELEGRAM_MAX_LEN] for i in range(0, max(len(message), 1), TELEGRAM_MAX_LEN)]
    all_ok = True
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            time.sleep(0.5)
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
                log.error("فشل إرسال تليغرام (كود %s)", r.status_code)
                all_ok = False
        except Exception as e:
            log.error("استثناء أثناء إرسال تليغرام: %s", type(e).__name__)
            all_ok = False
    return all_ok


def load_data():
    path = DATA_PATH if os.path.exists(DATA_PATH) else (ROOT_DATA_PATH if os.path.exists(ROOT_DATA_PATH) else None)
    if not path:
        log.error("ملف البيانات %s غير موجود!", DATA_PATH)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("تعذر قراءة ملف البيانات %s: %s", path, type(e).__name__)
        return None


def save_data(data, dry_run=False):
    data["lastUpdated"] = datetime.now(TZ).isoformat(timespec="seconds")
    if dry_run:
        log.info("[Dry-Run] تم تخطي حفظ التغييرات في %s", DATA_PATH)
        return

    parent_dir = os.path.dirname(DATA_PATH)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    tmp_path = f"{DATA_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, DATA_PATH)

    if os.path.exists(ROOT_DATA_PATH):
        try:
            shutil.copy2(DATA_PATH, ROOT_DATA_PATH)
        except OSError:
            pass
    log.info("تم حفظ التحديثات بنجاح في %s", DATA_PATH)


def fetch(url, problems):
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
    t = str(text).strip().replace("−", "-").replace("–", "-").replace("+", "").rstrip(".")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def parse_iso_kickoff(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).strip())
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=TZ)
    except ValueError:
        return None


def get_club_name(data, club_id):
    cid = str(club_id)
    if cid == CBM_ID:
        return data.get("club", {}).get("name", {}).get("ar", "شباب ميلة")
    for c in data.get("opponents", []):
        if str(c.get("id")) == cid:
            return c.get("name", {}).get("ar") or c.get("name", {}).get("latin") or f"نادي #{cid}"
    return f"نادي #{cid}"


def norm_ar(text):
    """تطبيع النص العربي: إزالة التشكيل والهمزات والمسافات الزائدة."""
    t = str(text or "")
    t = re.sub(r"[\u064B-\u065F\u0670]", "", t)
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", t).strip().lower()


def transliterate_ar_name(raw_name):
    """يحوّل الاسم العربي إلى حروف لاتينية، أو يعيد None إن لم يتيسر بدلاً من تكرار النص العربي."""
    s = re.sub(r"\s+", " ", str(raw_name or "")).strip()
    if not s:
        return None
    if s in KNOWN_LATIN_NAMES:
        return KNOWN_LATIN_NAMES[s]
    if re.search(r"[A-Za-z]", s) and not re.search(r"[\u0600-\u06FF]", s):
        return s.title()
    words = s.split()
    out = []
    for w in words:
        if w in AR_WORD_LATIN:
            out.append(AR_WORD_LATIN[w])
        else:
            return None
    return " ".join(out) if out else None


def match_cbm_player_id(data, raw_name):
    target = norm_ar(raw_name)
    if not target:
        return None
    for p in data.get("players", []):
        for k in ("ar", "latin", "en"):
            pname = norm_ar(p.get("name", {}).get(k) or "")
            if pname and (pname == target or target in pname or pname in target):
                return str(p["id"])
    return None


def enrich_metadata_and_players(data):
    """توحيد اسم الملعب، تحويل الأسماء للاتينية، حساب approxAge، وربط playerId في الأحداث."""
    changed = False
    now_iso = datetime.now(TZ).isoformat(timespec="seconds")
    today = datetime.now(TZ).date()

    # 1) توحيد اسم الملعب Stade Belkacem Belaid
    expected_stadium = {
        "name": "Stade Belkacem Belaid",
        "ar": "ملعب بلقاسم بلعيد",
        "source": HOME_STADIUM,
    }
    if data.get("club", {}).get("stadium") != expected_stadium:
        data.setdefault("club", {})["stadium"] = expected_stadium
        changed = True

    # 2) تحويل أسماء الطاقم الفني
    for s in data.get("staff", []):
        name_obj = s.get("name") or {}
        ar_n = name_obj.get("ar") or ""
        lat_n = name_obj.get("latin")
        if not lat_n or re.search(r"[\u0600-\u06FF]", str(lat_n)):
            new_lat = transliterate_ar_name(ar_n)
            if name_obj.get("latin") != new_lat or name_obj.get("en") != new_lat:
                s["name"] = {"ar": ar_n, "latin": new_lat, "en": new_lat}
                changed = True

    # 3) تحويل أسماء اللاعبين وحساب approxAge و lastFetchedAt
    for p in data.get("players", []):
        name_obj = p.get("name") or {}
        ar_n = name_obj.get("ar") or ""
        if ar_n == "BENSEGHIER HAMZA":
            ar_n = "بن صغير حمزة"
        lat_n = name_obj.get("latin")
        if not lat_n or re.search(r"[\u0600-\u06FF]", str(lat_n)):
            new_lat = transliterate_ar_name(ar_n)
            if name_obj.get("latin") != new_lat or name_obj.get("en") != new_lat or name_obj.get("ar") != ar_n:
                p["name"] = {"ar": ar_n, "latin": new_lat, "en": new_lat}
                changed = True

        if p.get("birthDate"):
            try:
                b = date.fromisoformat(str(p["birthDate"]).strip())
                age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
                if p.get("approxAge") != age:
                    p["approxAge"] = age
                    changed = True
            except ValueError:
                pass

        if not p.get("lastFetchedAt"):
            p["lastFetchedAt"] = now_iso
            changed = True

    # 4) ربط playerId في أحداث المباريات وتوحيد الملعب
    for m in data.get("matches", []):
        if str(m.get("home")) == CBM_ID and not m.get("venue"):
            m["venue"] = HOME_STADIUM
            changed = True
        for ev in m.get("events", []):
            if not ev.get("playerId") and ev.get("playerName"):
                pid = match_cbm_player_id(data, ev["playerName"])
                if pid:
                    ev["playerId"] = pid
                    changed = True
            if not ev.get("relatedPlayerId") and ev.get("relatedPlayerName"):
                rpid = match_cbm_player_id(data, ev["relatedPlayerName"])
                if rpid:
                    ev["relatedPlayerId"] = rpid
                    changed = True

    return changed


# ════════════════════════ 4) جدول الترتيب ════════════════════════
def update_standings(data, problems):
    url = data.get("sourceUrls", {}).get("ranking", "https://www.lirf.dz/ar/ranking")
    soup = fetch(url, problems)
    if not soup:
        return False

    tables = soup.find_all("table")
    table = next((t for t in tables if re.search(r"clubs-logos/\d+-|/club/\d+", str(t))), None)
    if not table:
        problems.append("صفحة الترتيب: لم أجد الجدول (ربما تغيّر تصميم الموقع)")
        return False

    by_club = {str(s.get("clubId")): s for s in data.get("standings", []) if s.get("clubId") is not None}
    updated = False
    rows_read = 0

    for row in table.find_all("tr"):
        m = re.search(r"clubs-logos/(\d+)-|/club/(\d+)", str(row))
        if not m:
            continue
        club_id = m.group(1) or m.group(2)
        item = by_club.get(club_id)
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not item or len(cells) < 10:
            continue

        pos = to_int(cells[0].split()[0]) if cells[0].split() else None
        nums = [to_int(c) for c in cells[2:10]]
        if pos is None or any(n is None for n in nums):
            continue

        rows_read += 1
        pts, played, w, d, l, gf, ga, gd = nums

        old_pts = item.get("points")
        old_adj = item.get("adjustedPoints")
        penalty = (old_adj - old_pts) if (isinstance(old_adj, int) and isinstance(old_pts, int) and pts >= 0) else 0
        adj_pts = pts if pts < 0 else (pts + penalty)

        new = {
            "position": pos,
            "played": played,
            "wins": w,
            "draws": d,
            "losses": l,
            "goalsFor": gf,
            "goalsAgainst": ga,
            "goalDifference": gd,
            "points": max(0, pts) if penalty < 0 else pts,
            "adjustedPoints": adj_pts,
        }
        if any(item.get(k) != v for k, v in new.items()):
            item.update(new)
            updated = True

    if rows_read == 0:
        problems.append("صفحة الترتيب: لم أستطع قراءة أي صف (تغيّر ترتيب الأعمدة؟)")
    if updated:
        data["standings"].sort(key=lambda s: (s.get("position") or 99, -(s.get("adjustedPoints") or 0)))
    return updated


# ════════════════════════ 5) المباريات وأحداثها ════════════════════════
def parse_score(soup, home_id, away_id):
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
                nums = []
            elif collecting and cid == away_str:
                break
        elif collecting and isinstance(node, NavigableString):
            s = str(node).strip()
            if not s or re.search(r"\b\d{1,2}:\d{2}\b", s) or "'" in s:
                continue

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

    d_ar = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", text)
    if d_ar:
        return datetime(int(d_ar.group(3)), MONTHS[d_ar.group(2)], int(d_ar.group(1)), hour, minute, tzinfo=TZ)

    d_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if d_iso:
        return datetime(int(d_iso.group(1)), int(d_iso.group(2)), int(d_iso.group(3)), hour, minute, tzinfo=TZ)

    d_num = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", text)
    if d_num:
        return datetime(int(d_num.group(3)), int(d_num.group(2)), int(d_num.group(1)), hour, minute, tzinfo=TZ)

    return None


def parse_venue(soup, home_id):
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


def parse_events(soup, data, m):
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    events = []
    opp_id = str(m.get("away")) if str(m.get("home")) == CBM_ID else str(m.get("home"))

    for i, ln in enumerate(lines):
        m_min = re.fullmatch(r"(\d{1,3})'", ln)
        if not m_min or i + 1 >= len(lines):
            continue
        minute = int(m_min.group(1))
        desc = lines[i + 1]

        g_match = re.match(r"^هدف من\s+([^\(]+?)(?:\s*\((.+?)\))?$", desc)
        if g_match:
            pname = g_match.group(1).strip()
            pid = match_cbm_player_id(data, pname)
            team = CBM_ID if pid else opp_id
            events.append({"minute": minute, "type": "goal", "team": team, "playerId": pid, "playerName": None if pid else pname})
            continue

        c_match = re.match(r"^بطاقة (صفراء|حمراء) لـ?(.+)$", desc)
        if c_match:
            ctype = "yellow" if c_match.group(1) == "صفراء" else "red"
            pname = c_match.group(2).strip()
            pid = match_cbm_player_id(data, pname)
            team = CBM_ID if pid else opp_id
            events.append({"minute": minute, "type": ctype, "team": team, "playerId": pid, "playerName": None if pid else pname})
            continue

        s_match = re.match(r"^(.+?)\s+يعوّض\s+(.+)$", desc)
        if s_match:
            in_name, out_name = s_match.group(1).strip(), s_match.group(2).strip()
            in_id = match_cbm_player_id(data, in_name)
            out_id = match_cbm_player_id(data, out_name)
            team = CBM_ID if (in_id or out_id) else opp_id
            events.append({
                "minute": minute, "type": "sub-in", "team": team,
                "playerId": in_id, "playerName": None if in_id else in_name,
                "relatedPlayerId": out_id, "relatedPlayerName": None if out_id else out_name
            })
            events.append({
                "minute": minute, "type": "sub-out", "team": team,
                "playerId": out_id, "playerName": None if out_id else out_name,
                "relatedPlayerId": in_id, "relatedPlayerName": None if in_id else in_name
            })

    return events


def result_alert(data, m, score):
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


def build_kickoff_push(data, m, ko):
    rnd = m.get("round", "؟")
    h_ar = get_club_name(data, m.get("home"))
    a_ar = get_club_name(data, m.get("away"))
    dt_str = f"{ko:%Y-%m-%d %H:%M}"
    return {
        "tag": f"cbm-ko-{m.get('id')}",
        "url": "./#/home",
        "ar": {"title": f"📅 موعد مباراة شباب ميلة — الجولة {rnd}", "body": f"{h_ar} ضد {a_ar} · الموعد: {dt_str}"},
        "fr": {"title": f"📅 Horaire du Match — Journée {rnd}", "body": f"CBM Mila · Coup d'envoi : {dt_str}"},
        "en": {"title": f"📅 Match Schedule — Round {rnd}", "body": f"CBM Mila · Kickoff: {dt_str}"},
    }


def build_result_push(data, m, score):
    rnd = m.get("round", "؟")
    at_home = str(m.get("home")) == CBM_ID
    mine, theirs = (score[0], score[1]) if at_home else (score[1], score[0])
    h_ar = get_club_name(data, m.get("home"))
    a_ar = get_club_name(data, m.get("away"))
    v_ar = "🟢 فوز" if mine > theirs else "🟡 تعادل" if mine == theirs else "🔴 خسارة"
    v_fr = "🟢 Victoire" if mine > theirs else "🟡 Match Nul" if mine == theirs else "🔴 Défaite"
    v_en = "🟢 Victory" if mine > theirs else "🟡 Draw" if mine == theirs else "🔴 Defeat"
    return {
        "tag": f"cbm-res-{m.get('id')}",
        "url": "./#/matches",
        "ar": {"title": f"⚽ نهاية المباراة — الجولة {rnd}", "body": f"{h_ar} {score[0]} - {score[1]} {a_ar} ({v_ar})"},
        "fr": {"title": f"⚽ Fin du Match — Journée {rnd}", "body": f"Score final : {score[0]} - {score[1]} ({v_fr})"},
        "en": {"title": f"⚽ Full Time — Round {rnd}", "body": f"Final Score: {score[0]} - {score[1]} ({v_en})"},
    }


def update_matches(data, problems, notes, push_events, dry_run=False):
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
            ko = parse_kickoff(soup, m.get("home"))
            if ko and m.get("kickoff") != ko.isoformat():
                m["kickoff"] = ko.isoformat()
                notes.append(f"الجولة {m.get('round')}: موعد جديد {ko:%Y-%m-%d %H:%M}")
                updated = True
                if CBM_ID in (str(m.get("home")), str(m.get("away"))):
                    push_events.append(build_kickoff_push(data, m, ko))

        if not m.get("venue"):
            venue = HOME_STADIUM if str(m.get("home")) == CBM_ID else (parse_venue(soup, m.get("home")) if soup else None)
            if venue:
                m["venue"] = venue
                notes.append(f"الجولة {m.get('round')}: الملعب {venue}")
                updated = True

        if not soup:
            continue

        kick = parse_iso_kickoff(m.get("kickoff"))
        if not kick or now < kick + MATCH_LENGTH:
            continue

        sc = parse_score(soup, m.get("home"), m.get("away"))
        if sc:
            m["score"] = {"home": sc[0], "away": sc[1]}
            m["status"] = "finished"
            if not m.get("events"):
                evs = parse_events(soup, data, m)
                if evs:
                    m["events"] = evs
            notes.append(f"الجولة {m.get('round')}: سُجّلت النتيجة {sc[0]}-{sc[1]}")
            updated = True
            if CBM_ID in (str(m.get("home")), str(m.get("away"))):
                send_telegram_alert(result_alert(data, m, sc), dry_run=dry_run)
                push_events.append(build_result_push(data, m, sc))
        else:
            problems.append(f"الجولة {m.get('round')}: انتهى وقتها ولم تُدرج النتيجة في الموقع بعد")

    return updated


# ════════════════════════ 6) سجل المناصرين (POST مع حماية ADMIN_KEY) ════════════════════════
def registry_call(url, payload):
    """يرسل طلب POST بجسم JSON (Content-Type: text/plain;charset=utf-8) مع ADMIN_KEY داخل الجسم وليس في الرابط."""
    try:
        r = SESSION.post(
            url,
            data=json.dumps(payload),
            headers={"Content-Type": "text/plain;charset=utf-8"},
            allow_redirects=True,
            timeout=30,
        )
        if r.status_code != 200:
            log.error("رد غير متوقع من سجل Google: كود %s", r.status_code)
            return None
        return r.json()
    except Exception as e:
        log.error("فشل الاتصال بسجل المناصرين: %s", type(e).__name__)
        return None


def report_new_supporters(problems, notes, dry_run=False):
    url = registry_url()
    if not ADMIN_KEY or not url:
        notes.append("قائمة المناصرين: غير مفعّلة (ADMIN_KEY أو الرابط غير مضبوط)")
        return

    res = registry_call(url, {"v": 2, "a": "list", "key": ADMIN_KEY})
    if not res:
        problems.append("سجل المناصرين: تعذر الاتصال بسكربت Google")
        return
    if not res.get("ok"):
        code = res.get("code")
        hint = " (تأكد من تطابق ADMIN_KEY ونشر النسخة الجديدة من Code.gs)" if code in ("denied", "bad", "method_not_allowed") else ""
        problems.append(f"سجل المناصرين: رفض الطلب [{code}]{hint}")
        return

    raw_items = res.get("items", [])
    items = [
        x for x in raw_items
        if isinstance(x, dict) and str(x.get("row", x.get("no", ""))).strip().isdigit()
    ]
    notes.append(f"مناصرون جدد: {len(items)} (الإجمالي {res.get('total', '؟')})")
    if not items:
        return

    all_sent = True
    for i in range(0, len(items), MAX_NAMES_PER_MESSAGE):
        part = items[i:i + MAX_NAMES_PER_MESSAGE]
        lines = [f"👥 <b>مناصرون استخرجوا بطاقاتهم</b> ({i + 1}–{i + len(part)} من {len(items)})"]
        for x in part:
            sid = x.get("supporterId") or f"CBM-{int(x.get('no', 0)):06d}"
            lines.append(f"• {html.escape(str(x.get('name', 'بدون اسم')).strip())} — <code>{html.escape(str(sid))}</code>")
        all_sent &= send_telegram_alert("\n".join(lines), dry_run=dry_run)

    if all_sent:
        if not dry_run:
            max_cursor = max(int(x.get("row", x.get("no", 0))) for x in items)
            ack_res = registry_call(url, {"v": 2, "a": "ack", "key": ADMIN_KEY, "upTo": max_cursor})
            if not ack_res or not ack_res.get("ok"):
                problems.append("سجل المناصرين: أُرسلت الأسماء لكن تعذر تأكيد الاستلام (ack)")
    else:
        problems.append("سجل المناصرين: تعذر إرسال القائمة إلى تليغرام (ستُعاد المحاولة في التشغيل التالي)")


def send_web_push_notifications(push_events, problems, notes, dry_run=False):
    """يرسل إشعارات Web Push الفورية لهواتف الأنصار المشتركين عند تحديد موعد أو انتهاء مباراة."""
    if not push_events:
        return
    url = registry_url()
    if not VAPID_PRIVATE_KEY or not ADMIN_KEY or not url:
        notes.append("إشعارات الهواتف (Web Push): غير مفعّلة (VAPID_PRIVATE_KEY أو ADMIN_KEY غير مضبوط)")
        return
    if dry_run:
        log.info("[Dry-Run] سيتم إرسال %d إشعار Web Push للأنصار", len(push_events))
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        problems.append("إشعارات الهواتف: مكتبة pywebpush غير مثبّتة")
        return

    res = registry_call(url, {"v": 2, "a": "push_list", "key": ADMIN_KEY})
    if not res or not res.get("ok"):
        problems.append("إشعارات الهواتف: تعذر جلب قائمة المشتركين من السجل")
        return

    subs = res.get("items", [])
    if not subs:
        notes.append("إشعارات الهواتف: لا يوجد مشتركون نشطون حالياً")
        return

    sent_count = 0
    dead_endpoints = []
    for ev in push_events:
        for sub in subs:
            ep = sub.get("endpoint")
            keys = sub.get("keys") or {}
            if not ep or not keys.get("p256dh") or not keys.get("auth"):
                continue
            lang = sub.get("lang") if sub.get("lang") in ("ar", "fr", "en") else "ar"
            msg = ev.get(lang) or ev["ar"]
            payload = json.dumps({
                "title": msg["title"],
                "body": msg["body"],
                "icon": "./icon-192.png",
                "badge": "./icon-192.png",
                "tag": ev.get("tag", "cbm-match"),
                "url": ev.get("url", "./#/home"),
            }, ensure_ascii=False)
            try:
                webpush(
                    subscription_info={"endpoint": ep, "keys": keys},
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims= dict(VAPID_CLAIMS),
                    timeout=10,
                )
                sent_count += 1
            except WebPushException as ex:
                status_code = getattr(getattr(ex, "response", None), "status_code", None)
                if status_code in (404, 410):
                    dead_endpoints.append(ep)
            except Exception:
                pass

    notes.append(f"إشعارات الهواتف الفورية: أُرسلت {sent_count} رسالة لـ {len(subs)} مشترك")
    if dead_endpoints:
        registry_call(url, {"v": 2, "a": "push_prune", "key": ADMIN_KEY, "endpoints": list(set(dead_endpoints))})


# ════════════════════════ 7) التشغيل الرئيسي ════════════════════════
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

    problems, notes, push_events = [], [], []
    e_updated = enrich_metadata_and_players(data)
    m_updated = update_matches(data, problems, notes, push_events, dry_run=dry_run)
    s_updated = update_standings(data, problems)
    notes.append("الترتيب: " + ("تم تحديثه" if s_updated else "بلا تغيير"))

    if e_updated or s_updated or m_updated:
        save_data(data, dry_run=dry_run)

    if push_events:
        try:
            send_web_push_notifications(push_events, problems, notes, dry_run=dry_run)
        except Exception as e:
            log.error("خطأ في إرسال إشعارات الهواتف: %s", type(e).__name__)

    try:
        report_new_supporters(problems, notes, dry_run=dry_run)
    except Exception as e:
        log.error("خطأ غير متوقع في report_new_supporters: %s", type(e).__name__)
        problems.append(f"سجل المناصرين: خطأ غير متوقع ({type(e).__name__})")

    if e_updated or s_updated or m_updated:
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
