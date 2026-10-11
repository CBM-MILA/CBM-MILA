"""
مراقب بيانات شباب ميلة (CBM Mila)
====================================
ماذا يفعل هذا الملف؟  (يشغّله GitHub Actions تلقائياً كل فترة)
  1) يقرأ ملف data/data.json الحالي.
  2) يزور موقع الرابطة (lirf.dz):
       - صفحة كل مباراة قادمة  ← يحدّث الموعد، ويسجّل النتيجة بعد نهاية المباراة.
       - صفحة الترتيب          ← يحدّث النقاط والمراكز.
  3) إن تغيّر شيء يحفظ data/data.json (وسيظهر التغيير في الموقع).
  4) يرسل لك إشعار تليغرام في كل تشغيل (إن كان NOTIFY_EVERY_RUN = True).

الإعدادات التي قد تغيّرها تجدها في القسم الأول فقط.
"""
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ════════════════════════ 1) الإعدادات ════════════════════════
DATA_PATH = "data/data.json"          # ملف البيانات الذي يقرؤه الموقع
CBM_ID = "733"                        # رقم نادي شباب ميلة في موقع الرابطة

# True  = رسالة تليغرام في كل تشغيل، حتى لو لم يتغير شيء (للاطمئنان أن المراقب يعمل).
# False = رسائل فقط عند وجود تغيير أو مشكلة.
NOTIFY_EVERY_RUN = True

TZ = timezone(timedelta(hours=1))     # توقيت الجزائر (UTC+1 طوال السنة)
MATCH_LENGTH = timedelta(minutes=110)  # بعد هذه المدة من الانطلاق نعتبر المباراة منتهية
MAX_MATCHES_PER_RUN = 3               # نفحص أقرب 3 مباريات غير منتهية فقط (لتقليل الطلبات)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# أسماء الأشهر في موقع الرابطة (بالعربية الجزائرية)
MONTHS = {"جانفي": 1, "فيفري": 2, "مارس": 3, "أفريل": 4, "افريل": 4, "ماي": 5, "جوان": 6,
          "جويلية": 7, "أوت": 8, "اوت": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10,
          "نوفمبر": 11, "ديسمبر": 12}

# المفتاحان السريان (يُضافان في GitHub: Settings > Secrets and variables > Actions)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ════════════════════════ 2) أدوات مساعدة ════════════════════════
def send_telegram_alert(message):
    """يرسل رسالة إلى تليغرام. إن غابت المفاتيح أو فشل الإرسال لا يتوقف السكربت."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")


def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    data["lastUpdated"] = datetime.now(TZ).isoformat(timespec="seconds")  # الموقع يعتمد عليه ليعرف أن البيانات أحدث
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(url, problems):
    """يجلب صفحة ويعيدها جاهزة للقراءة. عند الفشل يسجّل السبب في قائمة problems (تظهر في إشعار تليغرام)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            problems.append(f"{url} ← رد الخادم {r.status_code}")
            return None
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        problems.append(f"{url} ← تعذر الاتصال ({type(e).__name__})")
        return None


def to_int(text):
    """يحوّل '+5' إلى 5 و '-3' إلى -3 (ويقبل علامة الناقص العربية). وإلا يعيد None."""
    t = str(text).strip().replace("−", "-").replace("–", "-").replace("+", "")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


# ════════════════════════ 3) جدول الترتيب ════════════════════════
# أعمدة جدول الرابطة بالترتيب:
#   # | النادي | النقاط | لعب | فوز | تعادل | خسارة | له | عليه | الفارق
def update_standings(data, problems):
    url = data.get("sourceUrls", {}).get("ranking", "https://www.lirf.dz/ar/ranking")
    soup = fetch(url, problems)
    table = soup.find("table") if soup else None
    if not table:
        if soup:
            problems.append("صفحة الترتيب: لم أجد الجدول (ربما تغيّر تصميم الموقع)")
        return False

    by_club = {str(s.get("clubId")): s for s in data.get("standings", [])}
    updated = False
    rows_read = 0
    for row in table.find_all("tr"):
        # صف النادي يحتوي شعاره أو رابطه، أما صفوف «المباراة السابقة/التالية» فنتجاهلها
        m = re.search(r"clubs-logos/(\d+)-|/club/(\d+)", str(row))
        if not m:
            continue
        item = by_club.get(m.group(1) or m.group(2))
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not item or len(cells) < 10:
            continue
        pos = to_int(cells[0].split()[0]) if cells[0].split() else None
        nums = [to_int(c) for c in cells[2:10]]          # النقاط، لعب، فوز، تعادل، خسارة، له، عليه، الفارق
        if pos is None or any(n is None for n in nums):
            continue
        rows_read += 1
        pts, played, w, d, l, gf, ga, gd = nums

        # خصم النقاط اليدوي (مثل أمل عين مليلة -3) نحافظ عليه: adjustedPoints = النقاط الرسمية + الفرق القديم
        penalty = (item.get("adjustedPoints", item.get("points", 0)) or 0) - (item.get("points", 0) or 0)
        new = {"position": pos, "played": played, "wins": w, "draws": d, "losses": l,
               "goalsFor": gf, "goalsAgainst": ga, "goalDifference": gd,
               "points": pts, "adjustedPoints": pts + penalty}
        if any(item.get(k) != v for k, v in new.items()):
            item.update(new)
            updated = True

    if rows_read == 0:
        problems.append("صفحة الترتيب: لم أستطع قراءة أي صف (تغيّر ترتيب الأعمدة؟)")
    if updated:
        data["standings"].sort(key=lambda s: s.get("position", 99))
    return updated


# ════════════════════════ 4) المباريات ════════════════════════
def parse_score(soup, home_id, away_id):
    """
    النتيجة في صفحة المباراة تقع بين رابط نادي المضيف ورابط نادي الضيف،
    وتظهر كرقمين منفصلين (مثل «1» و«0»). نجمع أول رقمين بينهما.
    """
    collecting, nums = False, []
    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a":
            m = re.search(r"/club/(\d+)", node.get("href", ""))
            if not m:
                continue
            if not collecting and m.group(1) == str(home_id):
                collecting = True                      # بدأنا بعد رابط المضيف
            elif collecting and m.group(1) == str(away_id):
                break                                  # وصلنا لرابط الضيف: انتهى البحث
        elif collecting and isinstance(node, NavigableString):
            s = str(node).strip()
            two = re.fullmatch(r"(\d{1,2})\s*[-–:]?\s*(\d{1,2})", s)   # شكل «1 - 0» أو «1 0»
            if two:
                nums += [int(two.group(1)), int(two.group(2))]
            elif re.fullmatch(r"\d{1,2}", s):                          # رقم وحده
                nums.append(int(s))
            if len(nums) >= 2:
                return nums[0], nums[1]
    return None


def parse_kickoff(soup, home_id):
    """
    موعد المباراة (التاريخ والساعة) في رأس الصفحة، قبل رابط نادي المضيف.
    نقرأ هذا الجزء فقط حتى لا نلتقط تواريخ من أماكن أخرى في الصفحة.
    """
    head, found = [], False
    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a" and re.search(rf"/club/{home_id}\b", node.get("href", "")):
            found = True
            break
        if isinstance(node, NavigableString):
            head.append(str(node).strip())
    if not found:
        return None
    text = "\n".join(x for x in head if x)
    d = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", text)
    t = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not d or not t:
        return None                                    # الموعد لم يُحدَّد بعد
    return datetime(int(d.group(3)), MONTHS[d.group(2)], int(d.group(1)),
                    int(t.group(1)), int(t.group(2)), tzinfo=TZ)


def result_alert(m, score):
    """رسالة تليغرام لنتيجة شباب ميلة: فوز / تعادل / خسارة، داخل الميدان أو خارجه."""
    at_home = str(m.get("home")) == CBM_ID
    mine, theirs = (score[0], score[1]) if at_home else (score[1], score[0])
    verdict = "🟢 فوز" if mine > theirs else "🟡 تعادل" if mine == theirs else "🔴 خسارة"
    where = "في الميدان" if at_home else "خارج الميدان"
    return f"⚽ <b>نتيجة شباب ميلة — الجولة {m.get('round')}</b>\n{verdict} {mine}-{theirs} ({where})"


def update_matches(data, problems, notes):
    base = data.get("sourceUrls", {}).get("match", "https://www.lirf.dz/ar/match/{id}")
    now = datetime.now(TZ)
    updated = False

    pending = [m for m in data.get("matches", []) if m.get("status") != "finished"]
    pending.sort(key=lambda m: m.get("round", 99))
    notes.append(f"المباريات غير المنتهية التي فُحصت: {min(len(pending), MAX_MATCHES_PER_RUN)}")

    for m in pending[:MAX_MATCHES_PER_RUN]:
        soup = fetch(base.replace("{id}", str(m["id"])), problems)
        if not soup:
            continue

        # (أ) الموعد: يتغير عند التأجيل أو عندما يُحدَّد لأول مرة
        ko = parse_kickoff(soup, m.get("home"))
        if ko and m.get("kickoff") != ko.isoformat():
            m["kickoff"] = ko.isoformat()
            notes.append(f"الجولة {m.get('round')}: موعد جديد {ko:%Y-%m-%d %H:%M}")
            updated = True

        # (ب) النتيجة: لا نسجّلها إلا بعد انتهاء المباراة فعلاً
        kick = datetime.fromisoformat(m["kickoff"]) if m.get("kickoff") else None
        if not kick or now < kick + MATCH_LENGTH:
            continue
        sc = parse_score(soup, m.get("home"), m.get("away"))
        if sc:
            m["score"] = {"home": sc[0], "away": sc[1]}
            m["status"] = "finished"
            notes.append(f"الجولة {m.get('round')}: سُجّلت النتيجة {sc[0]}-{sc[1]}")
            updated = True
            if CBM_ID in (str(m.get("home")), str(m.get("away"))):
                send_telegram_alert(result_alert(m, sc))   # رسالة النتيجة الخاصة بشباب ميلة
        else:
            problems.append(f"الجولة {m.get('round')}: انتهى وقتها ولم أجد النتيجة بعد")
    return updated


# ════════════════════════ 5) التشغيل الرئيسي ════════════════════════
def main():
    print("بدء عملية فحص وتحديث البيانات...")
    data = load_data()
    if not data:
        print("ملف data.json غير موجود!")
        send_telegram_alert("❌ <b>المراقب:</b> ملف data/data.json غير موجود!")
        return

    problems, notes = [], []                       # problems = مشاكل، notes = ما فعلناه
    m_updated = update_matches(data, problems, notes)
    s_updated = update_standings(data, problems)
    notes.append("الترتيب: " + ("تم تحديثه" if s_updated else "بلا تغيير"))

    if s_updated or m_updated:
        save_data(data)
        status = "✅ <b>تم تحديث بيانات الموقع</b>"
    elif problems:
        status = "⚠️ <b>لم أستطع فحص الرابطة بالكامل</b> (التفاصيل أدناه)"
    else:
        status = "😴 <b>لا جديد</b> (لم يتغير شيء في الموقع)"
    print(status)

    # ملخص التشغيل (يُرسل في كل مرة إن كان NOTIFY_EVERY_RUN = True، أو عند تحديث/مشكلة)
    if NOTIFY_EVERY_RUN or s_updated or m_updated or problems:
        lines = [f"🤖 <b>مراقب CBM Mila</b> — {datetime.now(TZ):%Y-%m-%d %H:%M} (الجزائر)", status]
        lines += ["• " + html.escape(n) for n in notes]
        if problems:
            lines.append("⚠️ <b>مشاكل:</b>")
            lines += ["• " + html.escape(p) for p in problems]
        send_telegram_alert("\n".join(lines))


if __name__ == "__main__":
    main()
