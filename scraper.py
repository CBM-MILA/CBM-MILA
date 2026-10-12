
"""
مراقب بيانات شباب ميلة (CBM Mila)
====================================
ماذا يفعل هذا الملف؟
  1) يقرأ ملف data/data.json الحالي.
  2) يزور موقع الرابطة (lirf.dz):
       - يحدّث مواعيد المباريات القادمة.
       - يسجّل النتائج بعد انتهاء المباريات.
       - يحدّث النقاط والمراكز في جدول الترتيب.
  3) يحفظ البيانات عند حدوث تغييرات.
  4) يرسل إشعار تيليغرام في كل تشغيل إذا كان NOTIFY_EVERY_RUN = True.

الإعدادات التي يمكن تغييرها موجودة في القسم الأول.
"""

import html
import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


# ════════════════════════ 1) الإعدادات ════════════════════════

DATA_PATH = "data/data.json"
CBM_ID = "733"

# True = إشعار في كل تشغيل.
# False = إشعار عند وجود تغيير أو مشكلة فقط.
NOTIFY_EVERY_RUN = True

TZ = timezone(timedelta(hours=1))
MATCH_LENGTH = timedelta(minutes=110)
MAX_MATCHES_PER_RUN = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MONTHS = {
    "جانفي": 1,
    "فيفري": 2,
    "مارس": 3,
    "أفريل": 4,
    "افريل": 4,
    "ماي": 5,
    "جوان": 6,
    "جويلية": 7,
    "أوت": 8,
    "اوت": 8,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}

# تُضبط هذه القيم في:
# GitHub > Settings > Secrets and variables > Actions
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ════════════════════════ 2) أدوات مساعدة ════════════════════════

def send_telegram_alert(message):
    """إرسال إشعار تيليغرام مع تسجيل سبب الفشل."""

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "Telegram error: TELEGRAM_BOT_TOKEN "
            "or TELEGRAM_CHAT_ID is missing."
        )
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    try:
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            },
            timeout=15,
        )

        try:
            result = response.json()
        except ValueError:
            result = {}

        if response.ok and result.get("ok"):
            print("Telegram notification sent successfully.")
            return True

        description = (
            result.get("description") or response.text
        )

        print(
            f"Telegram error: HTTP {response.status_code} - "
            f"{description}"
        )
        return False

    except Exception as e:
        print(
            f"Telegram sending failed: "
            f"{type(e).__name__}: {e}"
        )
        return False


def load_data():
    if not os.path.exists(DATA_PATH):
        return None

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    data["lastUpdated"] = datetime.now(TZ).isoformat(
        timespec="seconds"
    )

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch(url, problems):
    """جلب صفحة وتسجيل أخطاء الاتصال أو الاستجابة."""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        if response.status_code != 200:
            problems.append(
                f"{url} ← رد الخادم {response.status_code}"
            )
            return None

        return BeautifulSoup(
            response.text,
            "html.parser",
        )

    except Exception as e:
        problems.append(
            f"{url} ← تعذر الاتصال ({type(e).__name__})"
        )
        return None


def to_int(text):
    """تحويل النص الرقمي إلى عدد صحيح."""

    value = (
        str(text)
        .strip()
        .replace("−", "-")
        .replace("–", "-")
        .replace("+", "")
    )

    if re.fullmatch(r"-?\d+", value):
        return int(value)

    return None


# ════════════════════════ 3) جدول الترتيب ════════════════════════

def update_standings(data, problems):
    url = data.get(
        "sourceUrls", {}
    ).get(
        "ranking",
        "https://www.lirf.dz/ar/ranking",
    )

    soup = fetch(url, problems)
    table = soup.find("table") if soup else None

    if not table:
        if soup:
            problems.append(
                "صفحة الترتيب: لم أجد الجدول "
                "(ربما تغيّر تصميم الموقع)"
            )
        return False

    by_club = {
        str(item.get("clubId")): item
        for item in data.get("standings", [])
    }

    updated = False
    rows_read = 0

    for row in table.find_all("tr"):
        match = re.search(
            r"clubs-logos/(\d+)-|/club/(\d+)",
            str(row),
        )

        if not match:
            continue

        club_id = match.group(1) or match.group(2)
        item = by_club.get(club_id)

        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["td", "th"])
        ]

        if not item or len(cells) < 10:
            continue

        first_cell = cells[0].split()
        position = to_int(first_cell[0]) if first_cell else None

        numbers = [
            to_int(cell)
            for cell in cells[2:10]
        ]

        if position is None or any(
            number is None for number in numbers
        ):
            continue

        rows_read += 1

        (
            points,
            played,
            wins,
            draws,
            losses,
            goals_for,
            goals_against,
            goal_difference,
        ) = numbers

        # الحفاظ على خصم النقاط اليدوي إن وجد.
        penalty = (
            item.get(
                "adjustedPoints",
                item.get("points", 0),
            ) or 0
        ) - (
            item.get("points", 0) or 0
        )

        new_values = {
            "position": position,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goalsFor": goals_for,
            "goalsAgainst": goals_against,
            "goalDifference": goal_difference,
            "points": points,
            "adjustedPoints": points + penalty,
        }

        if any(
            item.get(key) != value
            for key, value in new_values.items()
        ):
            item.update(new_values)
            updated = True

    if rows_read == 0:
        problems.append(
            "صفحة الترتيب: لم أستطع قراءة أي صف "
            "(ربما تغيّر ترتيب الأعمدة)"
        )

    if updated:
        data["standings"].sort(
            key=lambda item: item.get("position", 99)
        )

    return updated


# ════════════════════════ 4) المباريات ════════════════════════

def parse_score(soup, home_id, away_id):
    """
    استخراج النتيجة الواقعة بين رابط المضيف ورابط الضيف.
    """

    collecting = False
    numbers = []

    for node in soup.descendants:
        if isinstance(node, Tag) and node.name == "a":
            match = re.search(
                r"/club/(\d+)",
                node.get("href", ""),
            )

            if not match:
                continue

            if (
                not collecting
                and match.group(1) == str(home_id)
            ):
                collecting = True

            elif (
                collecting
                and match.group(1) == str(away_id)
            ):
                break

        elif (
            collecting
            and isinstance(node, NavigableString)
        ):
            value = str(node).strip()

            two_numbers = re.fullmatch(
                r"(\d{1,2})\s*[-–:]?\s*(\d{1,2})",
                value,
            )

            if two_numbers:
                numbers.extend([
                    int(two_numbers.group(1)),
                    int(two_numbers.group(2)),
                ])

            elif re.fullmatch(r"\d{1,2}", value):
                numbers.append(int(value))

            if len(numbers) >= 2:
                return numbers[0], numbers[1]

    return None


def parse_kickoff(soup, home_id):
    """استخراج تاريخ ووقت انطلاق المباراة."""

    head = []
    found = False

    for node in soup.descendants:
        if (
            isinstance(node, Tag)
            and node.name == "a"
            and re.search(
                rf"/club/{home_id}\b",
                node.get("href", ""),
            )
        ):
            found = True
            break

        if isinstance(node, NavigableString):
            head.append(str(node).strip())

    if not found:
        return None

    text = "\n".join(
        value for value in head if value
    )

    date_match = re.search(
        r"(\d{1,2})\s+("
        + "|".join(MONTHS)
        + r")\s+(\d{4})",
        text,
    )

    time_match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        text,
    )

    if not date_match or not time_match:
        return None

    return datetime(
        int(date_match.group(3)),
        MONTHS[date_match.group(2)],
        int(date_match.group(1)),
        int(time_match.group(1)),
        int(time_match.group(2)),
        tzinfo=TZ,
    )


def result_alert(match, score):
    """إنشاء إشعار نتيجة شباب ميلة."""

    at_home = str(match.get("home")) == CBM_ID

    if at_home:
        mine, theirs = score[0], score[1]
    else:
        mine, theirs = score[1], score[0]

    if mine > theirs:
        verdict = "🟢 فوز"
    elif mine == theirs:
        verdict = "🟡 تعادل"
    else:
        verdict = "🔴 خسارة"

    where = (
        "في الميدان"
        if at_home
        else "خارج الميدان"
    )

    return (
        f"⚽ <b>نتيجة شباب ميلة — الجولة "
        f"{match.get('round')}</b>\n"
        f"{verdict} {mine}-{theirs} ({where})"
    )


def update_matches(data, problems, notes):
    base = data.get(
        "sourceUrls", {}
    ).get(
        "match",
        "https://www.lirf.dz/ar/match/{id}",
    )

    now = datetime.now(TZ)
    updated = False

    pending = [
        match
        for match in data.get("matches", [])
        if match.get("status") != "finished"
    ]

    pending.sort(
        key=lambda match: match.get("round", 99)
    )

    notes.append(
        "المباريات غير المنتهية التي فُحصت: "
        f"{min(len(pending), MAX_MATCHES_PER_RUN)}"
    )

    for match in pending[:MAX_MATCHES_PER_RUN]:
        soup = fetch(
            base.replace("{id}", str(match["id"])),
            problems,
        )

        if not soup:
            continue

        # تحديث موعد المباراة.
        kickoff = parse_kickoff(
            soup,
            match.get("home"),
        )

        if (
            kickoff
            and match.get("kickoff") != kickoff.isoformat()
        ):
            match["kickoff"] = kickoff.isoformat()

            notes.append(
                f"الجولة {match.get('round')}: "
                f"موعد جديد {kickoff:%Y-%m-%d %H:%M}"
            )

            updated = True

        # تسجيل النتيجة بعد انتهاء الوقت المحدد.
        kickoff_value = (
            datetime.fromisoformat(match["kickoff"])
            if match.get("kickoff")
            else None
        )

        if (
            not kickoff_value
            or now < kickoff_value + MATCH_LENGTH
        ):
            continue

        score = parse_score(
            soup,
            match.get("home"),
            match.get("away"),
        )

        if score:
            match["score"] = {
                "home": score[0],
                "away": score[1],
            }

            match["status"] = "finished"

            notes.append(
                f"الجولة {match.get('round')}: "
                f"سُجّلت النتيجة {score[0]}-{score[1]}"
            )

            updated = True

            if CBM_ID in (
                str(match.get("home")),
                str(match.get("away")),
            ):
                send_telegram_alert(
                    result_alert(match, score)
                )

        else:
            problems.append(
                f"الجولة {match.get('round')}: "
                "انتهى وقتها ولم أجد النتيجة بعد"
            )

    return updated


# ════════════════════════ 5) التشغيل الرئيسي ════════════════════════

def main():
    print("بدء عملية فحص وتحديث البيانات...")

    data = load_data()

    if not data:
        print("ملف data.json غير موجود!")

        send_telegram_alert(
            "❌ <b>المراقب:</b> "
            "ملف data/data.json غير موجود!"
        )

        return

    problems = []
    notes = []

    matches_updated = update_matches(
        data,
        problems,
        notes,
    )

    standings_updated = update_standings(
        data,
        problems,
    )

    notes.append(
        "الترتيب: "
        + (
            "تم تحديثه"
            if standings_updated
            else "بلا تغيير"
        )
    )

    if standings_updated or matches_updated:
        save_data(data)
        status = "✅ <b>تم تحديث بيانات الموقع</b>"

    elif problems:
        status = (
            "⚠️ <b>لم أستطع فحص الرابطة بالكامل</b> "
            "(التفاصيل أدناه)"
        )

    else:
        status = "😴 <b>لا جديد</b> (لم يتغير شيء في الموقع)"

    print(status)

    # إرسال ملخص التشغيل.
    if (
        NOTIFY_EVERY_RUN
        or standings_updated
        or matches_updated
        or problems
    ):
        lines = [
            (
                f"🤖 <b>مراقب CBM Mila</b> — "
                f"{datetime.now(TZ):%Y-%m-%d %H:%M} "
                "(الجزائر)"
            ),
            status,
        ]

        lines += [
            "• " + html.escape(note)
            for note in notes
        ]

        if problems:
            lines.append("⚠️ <b>مشاكل:</b>")

            lines += [
                "• " + html.escape(problem)
                for problem in problems
            ]

        send_telegram_alert("\n".join(lines))


if __name__ == "__main__":
    main()
