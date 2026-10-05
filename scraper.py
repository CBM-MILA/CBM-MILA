import json
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

DATA_PATH = "data/data.json"
CBM_ID = "733"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def load_data():
    if not os.path.exists(DATA_PATH):
        return None
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    data["lastUpdated"] = datetime.now().astimezone().isoformat()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_standings(data):
    """جلب وتحديث جدول الترتيب من صفحة الترتيب الرسمية"""
    url = data.get("sourceUrls", {}).get("ranking", "https://www.lirf.dz/ar/ranking")
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return False
        
        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return False

        updated = False
        rows = table.find_all("tr")[1:]  # تخطي صف الرأس
        
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 8:
                continue

            # البحث عن معرف النادي من روابط الصف إن وُجدت
            link = row.find("a", href=re.compile(r"/club/(\d+)"))
            if not link:
                continue
            club_id = re.search(r"/club/(\d+)", link["href"]).group(1)

            for item in data.get("standings", []):
                if str(item.get("clubId")) == club_id:
                    try:
                        item["position"] = int(cols[0])
                        item["played"] = int(cols[2])
                        item["wins"] = int(cols[3])
                        item["draws"] = int(cols[4])
                        item["losses"] = int(cols[5])
                        item["goalsFor"] = int(cols[6])
                        item["goalsAgainst"] = int(cols[7])
                        item["goalDifference"] = item["goalsFor"] - item["goalsAgainst"]
                        item["points"] = int(cols[-1])
                        item["adjustedPoints"] = item["points"]
                        updated = True
                    except (ValueError, IndexError):
                        continue
        return updated
    except Exception as e:
        print(f"Error updating standings: {e}")
        return False

def update_matches(data):
    """فحص رزنامة مباريات شباب ميلة لتحديث النتائج المنتهية"""
    club_url = data.get("sourceUrls", {}).get("club", f"https://www.lirf.dz/ar/club/{CBM_ID}")
    try:
        res = requests.get(club_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return False
        
        soup = BeautifulSoup(res.text, "html.parser")
        match_links = soup.find_all("a", href=re.compile(r"/match/(\d+)"))
        
        updated = False
        for link in match_links:
            match_id = re.search(r"/match/(\d+)", link["href"]).group(1)
            
            for m in data.get("matches", []):
                if str(m.get("id")) == match_id and m.get("status") != "finished":
                    # جلب تفاصيل المباراة عند انتهاء موعدها
                    m_res = requests.get(f"https://www.lirf.dz/ar/match/{match_id}", headers=HEADERS, timeout=10)
                    if m_res.status_code == 200:
                        m_soup = BeautifulSoup(m_res.text, "html.parser")
                        score_text = m_soup.find(text=re.compile(r"^\s*\d+\s*-\s*\d+\s*$"))
                        if score_text:
                            scores = re.findall(r"\d+", score_text)
                            if len(scores) >= 2:
                                m["score"] = {"home": int(scores[0]), "away": int(scores[1])}
                                m["status"] = "finished"
                                updated = True
        return updated
    except Exception as e:
        print(f"Error updating matches: {e}")
        return False

def main():
    print("بدء عملية فحص وتحديث البيانات...")
    data = load_data()
    if not data:
        print("ملف data.json غير موجود!")
        return

    s_updated = update_standings(data)
    m_updated = update_matches(data)

    if s_updated or m_updated:
        save_data(data)
        print("تم تحديث وحفظ البيانات بنجاح في data/data.json.")
    else:
        print("لا توجد نتائج جديدة منشورة حالياً على موقع الرابطة.")

if __name__ == "__main__":
    main()
