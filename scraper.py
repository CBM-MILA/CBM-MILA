import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

DATA_PATH = "data/data.json"
CBM_ID = "733"
TZ = timezone(timedelta(hours=1))  # Africa/Algiers (UTC+1، بدون توقيت صيفي)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
MONTHS = {"جانفي": 1, "فيفري": 2, "مارس": 3, "أفريل": 4, "افريل": 4, "ماي": 5, "جوان": 6,
          "جويلية": 7, "أوت": 8, "اوت": 8, "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10,
          "نوفمبر": 11, "ديسمبر": 12}
MATCH_LENGTH = timedelta(minutes=110)  # بعد هذه المدة نعتبر المباراة منتهية

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_alert(message):
    """إرسال إشعار فوري إلى حسابك على تليغرام"""
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
    data["lastUpdated"] = datetime.now(TZ).isoformat(timespec="seconds")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return BeautifulSoup(r.text, "html.parser") if r.status_code == 200 else None
    except Exception as e:
        print(f"fetch failed {url}: {e}")
        return None


def to_int(text):
    """'+5' -> 5, '-3' -> -3, '−2' -> -2 ؛ وإلا None"""
    t = str(text).strip().replace("−", "-").replace("–", "-").replace("+", "")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


# ─────────────────────────── الترتيب ───────────────────────────
# أعمدة جدول الرابطة: # | النادي | النقاط | لعب | فوز | تعادل | خسارة | له | عليه | الفارق | ...
def update_standings(data):
    url = data.get("sourceUrls", {}).get("ranking", "https://www.lirf.dz/ar/ranking")
    soup = fetch(url)
    table = soup.find("table") if soup else None
    if not table:
        return False

    by_club = {str(s.get("clubId")): s for s in data.get("standings", [])}
    updated = False
    for row in table.find_all("tr"):
        html = str(row)
        m = re.search(r"clubs-logos/(\d+)-|/club/(\d+)", html)  # صف النادي فقط (وليس صف «المباراة السابقة/التالية»)
        if not m:
            continue
        item = by_club.get(m.group(1) or m.group(2))
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not item or len(cells) < 10:
            continue
        pos = to_int(cells[0].split()[0]) if cells[0].split() else None
        nums = [to_int(c) for c in cells[2:10]]  # pts, played, w, d, l, gf, ga, gd
        if pos is None or any(n is None for n in nums):
            continue
        pts, played, w, d, l, gf, ga, gd = nums
        penalty = (item.get("adjustedPoints", item.get("points", 0)) or 0) - (item.get("points", 0) or 0)  # خصم نقاط يدوي
        new = {"position": pos, "played": played, "wins": w, "draws": d, "losses": l,
               "goalsFor": gf, "goalsAgainst": ga, "goalDifference": gd, "points": pts,
               "adjustedPoints": pts + penalty}
        if any(item.get(k) != v for k, v in new.items()):
            item.update(new)
            updated = True
    if updated:
        data["standings"].sort(key=lambda s: s.get("position", 99))
    return updated


# ─────────────────────────── المباريات ───────────────────────────
def parse_score(soup, home_id, away_id):
    """النتيجة تظهر بين رابط نادي المضيف ورابط نادي الضيف، كرقمين منفصلين (مثل «1 0»)."""
    collecting, nums = False, []
    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a":
            m = re.search(r"/club/(\d+)", node.get("href", ""))
            if not m:
                continue
            if not collecting and m.group(1) == str(home_id):
                collecting = True
            elif collecting and m.group(1) == str(away_id):
                break
        elif collecting and isinstance(node, NavigableString):
            s = str(node).strip()
            two = re.fullmatch(r"(\d{1,2})\s*[-–:]?\s*(\d{1,2})", s)
            if two:
                nums += [int(two.group(1)), int(two.group(2))]
            elif re.fullmatch(r"\d{1,2}", s):
                nums.append(int(s))
            if len(nums) >= 2:
                return nums[0], nums[1]
    return None


def parse_kickoff(soup, home_id):
    """الموعد في رأس الصفحة، قبل رابط نادي المضيف (حتى لا نلتقط تواريخ من مكان آخر)."""
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
        return None
    return datetime(int(d.group(3)), MONTHS[d.group(2)], int(d.group(1)), int(t.group(1)), int(t.group(2)), tzinfo=TZ)


def update_matches(data):
    base = data.get("sourceUrls", {}).get("match", "https://www.lirf.dz/ar/match/{id}")
    now = datetime.now(TZ)
    updated = False
    pending = [m for m in data.get("matches", []) if m.get("status") != "finished"]
    pending.sort(key=lambda m: m.get("round", 99))
    for m in pending[:3]:  # المباراة الحالية والقادمتان فقط (لتقليل الطلبات)
        soup = fetch(base.replace("{id}", str(m["id"])))
        if not soup:
            continue

        # 1) الموعد (يتغير عند التأجيل أو بعد تحديد الموعد)
        ko = parse_kickoff(soup, m.get("home"))
        if ko and m.get("kickoff") != ko.isoformat():
            m["kickoff"] = ko.isoformat()
            updated = True

        # 2) النتيجة: فقط بعد انتهاء المباراة فعلاً
        kick = datetime.fromisoformat(m["kickoff"]) if m.get("kickoff") else None
        if not kick or now < kick + MATCH_LENGTH:
            continue
        sc = parse_score(soup, m.get("home"), m.get("away"))
        if sc:
            m["score"] = {"home": sc[0], "away": sc[1]}
            m["status"] = "finished"
            updated = True
            mine = CBM_ID in (str(m.get("home")), str(m.get("away")))
            if mine:
                send_telegram_alert(f"⚽ <b>نتيجة جديدة لشباب ميلة!</b>\nالجولة {m.get('round')}: {sc[0]} - {sc[1]}")
    return updated


def main():
    print("بدء عملية فحص وتحديث البيانات...")
    data = load_data()
    if not data:
        print("ملف data.json غير موجود!")
        return

    m_updated = update_matches(data)
    s_updated = update_standings(data)

    if s_updated or m_updated:
        save_data(data)
        print("تم تحديث وحفظ البيانات بنجاح.")
        send_telegram_alert("✅ <b>تم تحديث منصة CBM Mila بنجاح!</b>\nتمت مزامنة النتائج وجدول الترتيب مع موقع الرابطة.")
    else:
        print("لا توجد بيانات جديدة.")


if __name__ == "__main__":
    main()
