"""
CBM Mila 1936 — Official Fan Platform Scraper & Sync Engine
============================================================
Polite, resilient scraper for Ligue Inter-Régions (lirf.dz) that maintains
`data/data.json` (schemaVersion 3) and `data/status.json`.

Key guarantees:
  1. Competition pinning (`/ar/ranking` verified against `seasonName`/`seasonId` and `competitionAr` = `"شرق"`,
     plus strict 16-club set identity assertion so foreign clubs can never pollute standings) and
     header-driven table parsing (`النقاط`, `لعب`, `فوز`, `تعادل`, `خسارة`, `له`, `عليه`, `الفارق`).
  2. Explicit standings point-deduction model:
     - `points` = 3 * wins + draws (raw computed points)
     - `adjustedPoints` = displayed points on lirf.dz (includes disciplinary deductions)
     - `pointsPenalty` = points - adjustedPoints
     - `officialDeduction` = (adjustedPoints != points)
  3. Match status state machine (`scheduled`, `rescheduled`, `live`, `finished`, `postponed`, `forfeit`)
     built on real LIRF markup (two separate score elements, dedicated status badges without false-positive
     generic words like `"غياب"`, and `"قريباً"` vs `'90` event verification), `closedDoors` ("بدون جمهور")
     detection, kickoff/venue updates, new fixture discovery, and a 7-day detail re-check window.
  4. Deep-diff change detection (`lastUpdated` written ONLY on substantive data change; health state
     and notification dedupe state persisted in `data/status.json`).
  5. Strict sanity checks (16 clubs, W+D+L == played, non-decreasing played with `--accept-regression`
     manual override + loud logging/Telegram alert, goal consistency, JSON Schema) with atomic file replacement.
  6. GET-only HTTP retry policy, pre-persisted notification deduplication by stable event key
     (`matchId:kind:value`), and parallel Web Push delivery (`ThreadPoolExecutor(max_workers=10)`,
     10s timeout, 240s budget, single `push_prune` at end, logging counts only).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]

# ════════════════════════ 1. Paths & Constants ════════════════════════
DATA_PATH = "data/data.json"
SCHEMA_PATH = "data/schema.json"
STATUS_PATH = "data/status.json"
HTTP_CACHE_PATH = ".cache/http_cache.json"

DEFAULT_CLUB_ID = "733"
EXPECTED_CLUB_COUNT = 16
TZ = timezone(timedelta(hours=1))  # Africa/Algiers (UTC+1)
MATCH_LENGTH = timedelta(minutes=115)
DETAIL_RECHECK_WINDOW = timedelta(days=7)
MAX_VALID_GOALS = 25
POLITE_DELAY_SEC = 1.0
CONSECUTIVE_FAILURE_ALERT_THRESHOLD = 3

MAX_CACHE_BODY_CHARS = 250_000
MAX_CACHE_ENTRIES = 25

WEB_PUSH_MAX_WORKERS = 10
WEB_PUSH_TIMEOUT_SEC = 10
WEB_PUSH_TIME_BUDGET_SEC = 240.0

HOME_STADIUM = "Stade Belkacem Belaid, Mila"

VENUE_NORMALIZATION: dict[str, str] = {
    "بلقاسم بلعيد ميلة": HOME_STADIUM,
    "ملعب بلقاسم بلعيد ميلة": HOME_STADIUM,
    "ملعب بلقاسم بلعيد": HOME_STADIUM,
    "Stade Communal de Mila": HOME_STADIUM,
    "سويداني بوجمعة قالمة": "Souidani Boujemaa Stadium, Guelma",
    "فرجيوة": "Stade de Ferdjioua, Ferdjioua",
}

USER_AGENT = (
    "CBM-Mila-Fan-PWA/3.1 "
    "(+https://github.com/CBM-MILA/CBM-MILA; https://cbm-mila.github.io/CBM-MILA/)"
)

HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,fr;q=0.9,en;q=0.8",
}

MONTHS: dict[str, int] = {
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

ARABIC_DIGITS_MAP = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹−–—",
    "01234567890123456789---",
)

KNOWN_LATIN_NAMES: dict[str, str] = {
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
    "HAMZA BENSEGHIER": "Hamza Benseghier",
    "خابية صلاح الدين": "Salah Eddine Khabia",
    "رملي ناجي": "Nadji Ramli",
    "ماضي رابح": "Rabah Madhi",
    "لعطيوي وسيم": "Ouassim Latioui",
    "دغموش رابح": "Rabah Dekhmouche",
}

AR_WORD_LATIN: dict[str, str] = {
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
VAPID_CLAIMS: dict[str, str] = {"sub": "mailto:contact@cbm-mila.dz"}


# ════════════════════════ 2. Log Redaction & Setup ════════════════════════
def sanitize_text(msg: Any) -> str:
    """Redact any secret tokens or keys from log messages."""
    s = str(msg or "")
    for secret, label in (
        (TELEGRAM_TOKEN, "***REDACTED_TOKEN***"),
        (ADMIN_KEY, "***REDACTED_KEY***"),
        (VAPID_PRIVATE_KEY, "***REDACTED_VAPID***"),
        (TELEGRAM_CHAT_ID, "***REDACTED_CHAT***"),
    ):
        if secret:
            s = s.replace(str(secret), label)
    s = re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***REDACTED***", s)
    return s


class RedactingFilter(logging.Filter):
    """Logging filter that strips secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize_text(record.msg)
        if record.args:
            record.args = tuple(
                sanitize_text(a) if isinstance(a, str) else a for a in record.args
            )
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cbm-scraper")
log.addFilter(RedactingFilter())


# ════════════════════════ 3. Configuration & Data Structures ════════════════════════
@dataclass
class ScraperConfig:
    """Configuration derived dynamically from `data.json` (`sourceMeta` & `club`)."""

    club_id: str = DEFAULT_CLUB_ID
    season_id: str = "6"
    season_name: str = "2026/2027"
    competition_id: str = "4275"
    competition_ar: str = "شرق"
    ranking_url: str = "https://www.lirf.dz/ar/ranking"
    calendar_url: str = "https://www.lirf.dz/ar/calendar"
    club_url: str = "https://www.lirf.dz/ar/club/733"
    match_url_template: str = "https://www.lirf.dz/ar/match/{id}"
    player_url_template: str = "https://www.lirf.dz/ar/player/{id}"
    statistics_url: str = "https://www.lirf.dz/ar/statistics"
    home_url: str = "https://www.lirf.dz/"

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ScraperConfig":
        """Build a `ScraperConfig` from a loaded `data.json` dictionary."""
        meta = data.get("sourceMeta") or {}
        urls = data.get("sourceUrls") or {}
        club = data.get("club") or {}
        cid = str(club.get("id") or DEFAULT_CLUB_ID)
        return cls(
            club_id=cid,
            season_id=str(meta.get("seasonId") or "6"),
            season_name=str(meta.get("seasonName") or "2026/2027"),
            competition_id=str(meta.get("competitionId") or "4275"),
            competition_ar=str(meta.get("competitionAr") or "شرق"),
            ranking_url=str(urls.get("ranking") or "https://www.lirf.dz/ar/ranking"),
            calendar_url=str(urls.get("calendar") or "https://www.lirf.dz/ar/calendar"),
            club_url=str(urls.get("club") or f"https://www.lirf.dz/ar/club/{cid}"),
            match_url_template=str(urls.get("match") or "https://www.lirf.dz/ar/match/{id}"),
            player_url_template=str(urls.get("player") or "https://www.lirf.dz/ar/player/{id}"),
            statistics_url=str(urls.get("statistics") or "https://www.lirf.dz/ar/statistics"),
            home_url=str(urls.get("home") or "https://www.lirf.dz/"),
        )


@dataclass
class FixtureHint:
    """Extracted match metadata from ranking sub-rows or calendar/home cards."""

    match_id: Optional[str] = None
    round_num: Optional[int] = None
    home_id: Optional[str] = None
    away_id: Optional[str] = None
    home_name: Optional[str] = None
    away_name: Optional[str] = None
    kickoff: Optional[str] = None
    venue: Optional[str] = None
    score: Optional[tuple[int, int]] = None
    status: Optional[str] = None
    closed_doors: bool = False


# ════════════════════════ 4. Polite HTTP Client & Conditional Cache ════════════════════════
class PoliteFetcher:
    """
    HTTP client with GET-only retries, rate-limiting (~1 req/s), robots.txt check,
    and bounded ETag/Last-Modified conditional cache.
    """

    def __init__(self, polite_delay: float = POLITE_DELAY_SEC, cache_path: str = HTTP_CACHE_PATH) -> None:
        self.session = self._create_session()
        self.polite_delay = polite_delay
        self.cache_path = cache_path
        self._last_request_ts: float = 0.0
        self._cache: dict[str, dict[str, str]] = self._load_cache()
        self._cache_dirty: bool = False
        self._disallowed_paths: list[str] = []
        self._robots_checked_origins: set[str] = set()

    @staticmethod
    def _create_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(HEADERS)
        # Item 7: Retry GET only — never auto-retry non-idempotent POST requests
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=1.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _load_cache(self) -> dict[str, dict[str, str]]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        return loaded
            except Exception:
                return {}
        return {}

    def save_cache(self, dry_run: bool = False) -> None:
        """Persist HTTP conditional headers (`ETag`, `Last-Modified`, bounded body) to `.cache` only when changed."""
        if dry_run or not self._cache or not self._cache_dirty:
            return
        try:
            # Cap total entries to MAX_CACHE_ENTRIES
            if len(self._cache) > MAX_CACHE_ENTRIES:
                keys = list(self._cache.keys())[-MAX_CACHE_ENTRIES:]
                self._cache = {k: self._cache[k] for k in keys}
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            tmp = f"{self.cache_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
            self._cache_dirty = False
        except OSError:
            pass

    def _throttle(self) -> None:
        if self.polite_delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_ts
        if self._last_request_ts > 0 and elapsed < self.polite_delay:
            time.sleep(self.polite_delay - elapsed)
        self._last_request_ts = time.monotonic()

    def _check_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots_checked_origins:
            self._robots_checked_origins.add(origin)
            try:
                self._throttle()
                r = self.session.get(f"{origin}/robots.txt", timeout=10)
                if r.status_code == 200:
                    active_ua = False
                    for raw_line in r.text.splitlines():
                        line = raw_line.split("#", 1)[0].strip()
                        if not line:
                            continue
                        if line.lower().startswith("user-agent:"):
                            ua_val = line.split(":", 1)[1].strip()
                            active_ua = ua_val == "*" or "cbm" in ua_val.lower()
                        elif active_ua and line.lower().startswith("disallow:"):
                            path = line.split(":", 1)[1].strip()
                            if path:
                                self._disallowed_paths.append(path)
            except Exception:
                pass
        path = parsed.path or "/"
        for dis in self._disallowed_paths:
            if dis == "/" or path.startswith(dis):
                log.warning("robots.txt يمنع الوصول إلى المسار %s", path)
                return False
        return True

    def fetch_soup(self, url: str, problems: list[str]) -> Optional[BeautifulSoup]:
        """Fetch an HTML page politely with conditional ETag/If-Modified-Since headers."""
        if not self._check_robots(url):
            problems.append(f"{url} ← محظور بواسطة robots.txt")
            return None

        self._throttle()
        req_headers: dict[str, str] = {}
        cached = self._cache.get(url)
        if cached:
            if cached.get("etag"):
                req_headers["If-None-Match"] = cached["etag"]
            if cached.get("last_modified"):
                req_headers["If-Modified-Since"] = cached["last_modified"]

        try:
            r = self.session.get(url, headers=req_headers, timeout=20)
            if r.status_code == 304 and cached and cached.get("body"):
                log.debug("304 Not Modified: %s", url)
                return BeautifulSoup(cached["body"], "html.parser")
            if r.status_code != 200:
                problems.append(f"{url} ← رد الخادم {r.status_code}")
                return None
            etag = r.headers.get("ETag", "")
            last_mod = r.headers.get("Last-Modified", "")
            if (etag or last_mod) and len(r.text) <= MAX_CACHE_BODY_CHARS:
                new_entry = {
                    "etag": etag,
                    "last_modified": last_mod,
                    "body": r.text,
                }
                if self._cache.get(url) != new_entry:
                    self._cache[url] = new_entry
                    self._cache_dirty = True
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            problems.append(f"{url} ← تعذر الاتصال ({type(e).__name__})")
            return None


FETCHER = PoliteFetcher()


# ════════════════════════ 5. Normalization & Helper Functions ════════════════════════
def normalize_digits(text: Any) -> str:
    """Normalize Arabic-Indic digits, Unicode minus signs, and whitespace."""
    s = str(text if text is not None else "").translate(ARABIC_DIGITS_MAP)
    return re.sub(r"\s+", " ", s).strip()


def to_int(text: Any) -> Optional[int]:
    """Parse an integer from a string after normalizing Arabic digits and signs."""
    t = normalize_digits(text).replace("+", "").rstrip(".")
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def norm_ar(text: Any) -> str:
    """Normalize Arabic text: strip diacritics, unify hamzas/ta-marbuta/alef-maqsura, lowercase."""
    t = normalize_digits(text)
    t = re.sub(r"[\u064B-\u065F\u0670]", "", t)
    t = re.sub(r"[أإآ]", "ا", t)
    t = t.replace("ة", "ه").replace("ى", "ي")
    t = re.sub(r"^ال", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def transliterate_ar_name(raw_name: Any) -> Optional[str]:
    """Transliterate an Arabic player/staff name to Latin script, or return None if unknown."""
    s = re.sub(r"\s+", " ", str(raw_name or "")).strip()
    if not s:
        return None
    if s in KNOWN_LATIN_NAMES:
        return KNOWN_LATIN_NAMES[s]
    if s.upper() in KNOWN_LATIN_NAMES:
        return KNOWN_LATIN_NAMES[s.upper()]
    if re.search(r"[A-Za-z]", s) and not re.search(r"[\u0600-\u06FF]", s):
        return s.title()
    words = s.split()
    out: list[str] = []
    for w in words:
        if w in AR_WORD_LATIN:
            out.append(AR_WORD_LATIN[w])
        else:
            return None
    return " ".join(out) if out else None


def normalize_venue(raw_venue: Optional[str], is_cbm_home: bool = False) -> Optional[str]:
    """Normalize Arabic/French stadium names while preserving official venue strings."""
    if not raw_venue:
        return HOME_STADIUM if is_cbm_home else None
    cleaned = normalize_digits(raw_venue).strip(" -–—·|")
    if not cleaned or cleaned == "-":
        return HOME_STADIUM if is_cbm_home else None
    if cleaned in VENUE_NORMALIZATION:
        return VENUE_NORMALIZATION[cleaned]
    if "بلقاسم بلعيد" in cleaned or (is_cbm_home and "ميلة" in cleaned):
        return HOME_STADIUM
    return cleaned


def parse_iso_kickoff(iso_str: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 kickoff timestamp into a timezone-aware datetime (UTC+1)."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).strip())
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=TZ)
    except ValueError:
        return None


def parse_date_time_text(text: str, default_hour: int = 15, default_minute: int = 0) -> Optional[datetime]:
    """Extract a timezone-aware kickoff datetime (`+01:00`) from Arabic or ISO date/time text."""
    norm = normalize_digits(text)
    t_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", norm)
    hour = int(t_match.group(1)) if t_match else default_hour
    minute = int(t_match.group(2)) if t_match else default_minute

    # 1) Arabic month format: "23 أكتوبر 2026"
    d_ar = re.search(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", norm)
    if d_ar:
        return datetime(
            int(d_ar.group(3)),
            MONTHS[d_ar.group(2)],
            int(d_ar.group(1)),
            hour,
            minute,
            tzinfo=TZ,
        )

    # 2) ISO date format: "2026-10-23"
    d_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", norm)
    if d_iso:
        return datetime(
            int(d_iso.group(1)),
            int(d_iso.group(2)),
            int(d_iso.group(3)),
            hour,
            minute,
            tzinfo=TZ,
        )

    # 3) DD/MM/YYYY or DD-MM-YYYY
    d_num = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", norm)
    if d_num:
        return datetime(
            int(d_num.group(3)),
            int(d_num.group(2)),
            int(d_num.group(1)),
            hour,
            minute,
            tzinfo=TZ,
        )

    return None


def get_club_name(data: dict[str, Any], club_id: Any) -> str:
    """Return the Arabic display name of a club by its ID."""
    cid = str(club_id)
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    if cid == cbm_id:
        return data.get("club", {}).get("name", {}).get("ar", "شباب ميلة")
    for c in data.get("opponents", []):
        if str(c.get("id")) == cid:
            return c.get("name", {}).get("ar") or c.get("name", {}).get("latin") or f"نادي #{cid}"
    return f"نادي #{cid}"


def resolve_club_id_by_name(data: dict[str, Any], raw_name: str) -> Optional[str]:
    """Resolve a club ID from its Arabic/Latin name or common abbreviation on lirf.dz."""
    target = norm_ar(raw_name)
    if not target:
        return None
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    cbm_ar = norm_ar(data.get("club", {}).get("name", {}).get("ar") or "شباب ميلة")
    if target in (cbm_ar, norm_ar("ش. ميلة"), norm_ar("ش ميلة"), "cbm", "cb mila"):
        return cbm_id

    alias_map: dict[str, str] = {
        norm_ar("إ سدراتة"): "891",
        norm_ar("إ. سدراتة"): "891",
        norm_ar("اتحاد سدراتة"): "891",
        norm_ar("ش. عين كرشة"): "731",
        norm_ar("ش عين كرشة"): "731",
        norm_ar("إ. الفوبور"): "823",
        norm_ar("اتحاد الفوبور"): "823",
        norm_ar("ن. الفجوج"): "732",
        norm_ar("نصر الفجوج"): "732",
        norm_ar("ش. قايس"): "727",
        norm_ar("شباب قايس"): "727",
        norm_ar("إ.بوخضرة"): "884",
        norm_ar("إ. بوخضرة"): "884",
        norm_ar("اتحاد بوخضرة"): "884",
        norm_ar("ش الميلية"): "997",
        norm_ar("ش. الميلية"): "997",
        norm_ar("شباب الميلية"): "997",
        norm_ar("ش عين ياقوت"): "734",
        norm_ar("ش. عين ياقوت"): "734",
        norm_ar("شباب عين ياقوت"): "734",
        norm_ar("ت. قالمة"): "736",
        norm_ar("ترجي قالمة"): "736",
        norm_ar("ن. تازوقاغت"): "729",
        norm_ar("نجم تازوقاغت"): "729",
        norm_ar("ش عين فكرون"): "728",
        norm_ar("ش. عين فكرون"): "728",
        norm_ar("شباب عين فكرون"): "728",
        norm_ar("أ. عين مليلة"): "651",
        norm_ar("امل عين مليلة"): "651",
        norm_ar("crbf"): "1036",
        norm_ar("esfbea"): "849",
        norm_ar("essa"): "937",
    }
    if target in alias_map:
        return alias_map[target]

    for opp in data.get("opponents", []):
        oid = str(opp.get("id"))
        names = [
            opp.get("name", {}).get("ar"),
            opp.get("name", {}).get("latin"),
            opp.get("name", {}).get("en"),
            opp.get("short"),
        ]
        for candidate in names:
            cn = norm_ar(candidate)
            if cn and (cn == target or cn in target or target in cn):
                return oid
    return None


def match_cbm_player_id(data: dict[str, Any], raw_name: str) -> Optional[str]:
    """Match an Arabic or Latin player name from match events/lineups to a CBM `playerId`."""
    cleaned = re.sub(r"\s+", " ", str(raw_name or "")).strip()
    if not cleaned:
        return None
    if cleaned.upper() in ("BENSEGHIER HAMZA", "HAMZA BENSEGHIER"):
        cleaned = "بن صغير حمزة"
    target = norm_ar(cleaned)
    if not target:
        return None
    for p in data.get("players", []):
        for k in ("ar", "latin", "en"):
            pname = norm_ar(p.get("name", {}).get(k) or "")
            if pname and (pname == target or target in pname or pname in target):
                return str(p["id"])
    return None


# ════════════════════════ 6. Competition Pinning & Header-Driven Standings Parser ════════════════════════
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "position": ("#", "مركز", "الرتبة", "ترتيب"),
    "club": ("النادي", "الفريق"),
    "points": ("النقاط", "نقاط"),
    "played": ("لعب",),
    "wins": ("فوز", "فاز"),
    "draws": ("تعادل",),
    "losses": ("خسارة", "خسر"),
    "goalsFor": ("له",),
    "goalsAgainst": ("عليه",),
    "goalDifference": ("الفارق", "+/-"),
}

REQUIRED_STANDING_COLS = (
    "points",
    "played",
    "wins",
    "draws",
    "losses",
    "goalsFor",
    "goalsAgainst",
    "goalDifference",
)

WRONG_GROUP_NAMES = ("وسط شرق", "وسط غرب", "جنوب شرق", "جنوب غرب", "غرب")


def verify_ranking_competition(
    soup: BeautifulSoup,
    cfg: ScraperConfig,
    problems: list[str],
) -> bool:
    """
    Item 4: Pin the ranking page to the right competition (`seasonId`/`seasonName` and
    `competitionAr` = `"شرق"`). Checks selected `<option>` tags and active filter badges.
    """
    selected_options = [
        normalize_digits(opt.get_text(" ", strip=True))
        for opt in soup.find_all("option", selected=True)
        if normalize_digits(opt.get_text(" ", strip=True))
    ]
    selected_vals = [
        normalize_digits(opt.get("value", ""))
        for opt in soup.find_all("option", selected=True)
        if normalize_digits(opt.get("value", ""))
    ]

    if selected_options:
        # Check season if a season option (YYYY/YYYY) is present among selected options
        season_opts = [o for o in selected_options if re.search(r"\d{4}\s*/\s*\d{4}", o)]
        if season_opts and cfg.season_name not in season_opts and cfg.season_id not in selected_vals:
            problems.append(
                f"صفحة الترتيب: الموسم المحدد ({season_opts[0]}) لا يطابق {cfg.season_name}"
            )
            return False

        # Check group if any group option is selected
        for wrong in WRONG_GROUP_NAMES:
            if any(wrong in o for o in selected_options):
                problems.append(
                    f"صفحة الترتيب: المجموعة المحددة ({selected_options}) ليست '{cfg.competition_ar}'"
                )
                return False
        if not any(cfg.competition_ar == o or cfg.competition_ar in o for o in selected_options) and cfg.competition_id not in selected_vals:
            problems.append(
                f"صفحة الترتيب: لم يتم التأكد من اختيار مجموعة '{cfg.competition_ar}' في الفلتر ({selected_options})"
            )
            return False

    # Also check `.season-active` / `.group-active` filter badges if present
    season_badge = soup.find(class_=re.compile(r"season-active", re.I))
    if isinstance(season_badge, Tag):
        s_txt = normalize_digits(season_badge.get_text(" ", strip=True))
        s_id = normalize_digits(season_badge.get("data-season-id", ""))
        if s_txt and cfg.season_name not in s_txt and s_id != cfg.season_id:
            problems.append(f"صفحة الترتيب: الموسم النشط ({s_txt}) لا يطابق {cfg.season_name}")
            return False

    group_badge = soup.find(class_=re.compile(r"group-active", re.I))
    if isinstance(group_badge, Tag):
        g_txt = normalize_digits(group_badge.get_text(" ", strip=True))
        g_id = normalize_digits(group_badge.get("data-competition-id", ""))
        if any(w in g_txt for w in WRONG_GROUP_NAMES) or (
            g_txt and cfg.competition_ar not in g_txt and g_id != cfg.competition_id
        ):
            problems.append(f"صفحة الترتيب: المجموعة النشطة ({g_txt}) لا تطابق '{cfg.competition_ar}'")
            return False

    return True


def map_table_headers(table: Tag) -> Optional[dict[str, int]]:
    """Map column names to column indices using `<th>` header labels (not hard-coded positions)."""
    header_row: Optional[Tag] = None
    thead = table.find("thead")
    if isinstance(thead, Tag):
        header_row = thead.find("tr")
    if not header_row:
        header_row = table.find("tr")
    if not isinstance(header_row, Tag):
        return None

    cells = header_row.find_all(["th", "td"], recursive=False)
    if len(cells) < 8:
        return None

    col_map: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        text = normalize_digits(cell.get_text(" ", strip=True))
        for field_name, keywords in HEADER_ALIASES.items():
            if field_name in col_map:
                continue
            if any(kw in text for kw in keywords):
                col_map[field_name] = idx
                break

    if all(req in col_map for req in REQUIRED_STANDING_COLS):
        col_map.setdefault("position", 0)
        col_map.setdefault("club", 1)
        return col_map
    return None


def parse_standings_from_soup(
    soup: BeautifulSoup,
    data: dict[str, Any],
    problems: list[str],
) -> tuple[list[dict[str, Any]], list[FixtureHint]]:
    """
    Parse the full 16-club standings table by header labels and extract any embedded
    'المباراة السابقة' / 'المباراة التالية' fixture hints from expandable sub-rows.
    """
    cfg = ScraperConfig.from_data(data)
    if not verify_ranking_competition(soup, cfg, problems):
        return [], []

    target_table: Optional[Tag] = None
    col_map: Optional[dict[str, int]] = None

    for table in soup.find_all("table"):
        mapped = map_table_headers(table)
        if mapped:
            target_table = table
            col_map = mapped
            break

    if not target_table or not col_map:
        problems.append("صفحة الترتيب: لم يتم العثور على جدول الترتيب الكامل برؤوس الأعمدة المتوقعة")
        return [], []

    parsed_rows: list[dict[str, Any]] = []
    fixture_hints: list[FixtureHint] = []
    seen_clubs: set[str] = set()
    max_col_idx = max(col_map.values())

    for row in target_table.find_all("tr"):
        row_text = normalize_digits(row.get_text(" ", strip=True))
        if "المباراة السابقة" in row_text or "المباراة التالية" in row_text:
            fixture_hints.extend(extract_subrow_fixtures(row, data))
            continue

        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) <= max_col_idx:
            continue

        club_cell = cells[col_map["club"]]
        club_id: Optional[str] = None
        for a_tag in club_cell.find_all("a", href=True):
            m_href = re.search(r"/club/(\d+)\b", str(a_tag["href"]))
            if m_href:
                club_id = m_href.group(1)
                break
        if not club_id:
            m_row = re.search(r"/club/(\d+)\b|clubs-logos/(\d+)-", str(club_cell))
            if m_row:
                club_id = m_row.group(1) or m_row.group(2)
        if not club_id or club_id in seen_clubs:
            continue

        pos_raw = normalize_digits(cells[col_map["position"]].get_text(" ", strip=True))
        pos = to_int(pos_raw.split()[0]) if pos_raw.split() else None
        site_pts = to_int(cells[col_map["points"]].get_text(" ", strip=True))
        played = to_int(cells[col_map["played"]].get_text(" ", strip=True))
        wins = to_int(cells[col_map["wins"]].get_text(" ", strip=True))
        draws = to_int(cells[col_map["draws"]].get_text(" ", strip=True))
        losses = to_int(cells[col_map["losses"]].get_text(" ", strip=True))
        gf = to_int(cells[col_map["goalsFor"]].get_text(" ", strip=True))
        ga = to_int(cells[col_map["goalsAgainst"]].get_text(" ", strip=True))
        gd = to_int(cells[col_map["goalDifference"]].get_text(" ", strip=True))

        if None in (pos, site_pts, played, wins, draws, losses, gf, ga, gd):
            continue

        assert pos is not None and site_pts is not None and played is not None
        assert wins is not None and draws is not None and losses is not None
        assert gf is not None and ga is not None and gd is not None

        raw_points = 3 * wins + draws
        adjusted_points = site_pts
        points_penalty = max(0, raw_points - adjusted_points)
        official_deduction = adjusted_points != raw_points

        seen_clubs.add(club_id)
        entry: dict[str, Any] = {
            "position": pos,
            "clubId": club_id,
            "played": played,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "goalsFor": gf,
            "goalsAgainst": ga,
            "goalDifference": gd,
            "points": raw_points,
            "adjustedPoints": adjusted_points,
            "pointsPenalty": points_penalty,
            "official": True,
            "officialDeduction": official_deduction,
        }
        parsed_rows.append(entry)

        if len(cells) > max_col_idx + 1 or "المباراة" in row_text:
            fixture_hints.extend(extract_subrow_fixtures(row, data))

    parsed_rows.sort(key=lambda s: (s["position"], -s["adjustedPoints"], -s["goalDifference"]))
    return parsed_rows, fixture_hints


def extract_subrow_fixtures(container: Tag, data: dict[str, Any]) -> list[FixtureHint]:
    """Extract 'المباراة السابقة' and 'المباراة التالية' fixture hints from a ranking sub-row."""
    hints: list[FixtureHint] = []
    for a_tag in container.find_all("a", href=True):
        m_id = re.search(r"/match/(\d+)\b", str(a_tag["href"]))
        if not m_id:
            continue
        match_id = m_id.group(1)
        card_node = a_tag.parent if isinstance(a_tag.parent, Tag) else a_tag
        card_text = normalize_digits(card_node.get_text(" ", strip=True))
        is_prev = "المباراة السابقة" in card_text
        is_next = "المباراة التالية" in card_text
        closed_doors = "بدون جمهور" in card_text
        dt = parse_date_time_text(card_text)

        strings = [
            normalize_digits(s)
            for s in a_tag.stripped_strings
            if normalize_digits(s)
            and normalize_digits(s) not in ("المباراة السابقة", "المباراة التالية", "بدون جمهور")
        ]
        venue_cand: Optional[str] = None
        for idx, tok in enumerate(strings):
            if re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", tok) and idx + 1 < len(strings):
                cand = strings[idx + 1]
                if not any(m in cand for m in MONTHS) and not re.search(r"\d{4}", cand):
                    venue_cand = cand

        club_ids_found: list[str] = []
        for tok in strings:
            if re.fullmatch(r"\d{1,2}", tok) or re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", tok):
                continue
            if any(m in tok for m in MONTHS) or tok == venue_cand:
                continue
            cid = resolve_club_id_by_name(data, tok)
            if cid and (not club_ids_found or club_ids_found[-1] != cid):
                club_ids_found.append(cid)

        score_pair: Optional[tuple[int, int]] = None
        int_tokens = [int(tok) for tok in strings if re.fullmatch(r"\d{1,2}", tok) and int(tok) <= MAX_VALID_GOALS]
        if is_prev and len(int_tokens) >= 2:
            score_pair = (int_tokens[0], int_tokens[1])

        if len(club_ids_found) >= 2:
            hints.append(
                FixtureHint(
                    match_id=match_id,
                    home_id=club_ids_found[0],
                    away_id=club_ids_found[1],
                    kickoff=dt.isoformat() if dt else None,
                    venue=venue_cand,
                    score=score_pair,
                    status="finished" if score_pair else ("scheduled" if is_next else None),
                    closed_doors=closed_doors,
                )
            )
    return hints


def extract_calendar_fixtures(soup: BeautifulSoup, data: dict[str, Any]) -> list[FixtureHint]:
    """
    Extract fixture hints from `/ar/calendar` or `https://www.lirf.dz/` weekly match cards.
    Parses real LIRF structure where scores render as two separate numeric text nodes between
    the home and away club names, or `VS` for scheduled matches.
    """
    hints: list[FixtureHint] = []
    cards: list[Tag] = []

    # Locate parent containers of links to `/match/\d+`
    for a_tag in soup.find_all("a", href=re.compile(r"/match/\d+")):
        parent = a_tag.find_parent(["div", "li", "article"])
        if isinstance(parent, Tag) and parent not in cards:
            cards.append(parent)

    for card in cards:
        card_text = normalize_digits(card.get_text(" ", strip=True))
        m_round = re.search(r"الجولة\s*(\d{1,2})", card_text)
        round_num = int(m_round.group(1)) if m_round else None

        match_id: Optional[str] = None
        m_link = card.find("a", href=re.compile(r"/match/(\d+)\b"))
        if isinstance(m_link, Tag):
            m_id = re.search(r"/match/(\d+)\b", str(m_link.get("href", "")))
            if m_id:
                match_id = m_id.group(1)

        strings = [normalize_digits(s) for s in card.stripped_strings if normalize_digits(s)]

        club_ids: list[str] = []
        club_token_indices: list[int] = []
        for c_link in card.find_all("a", href=re.compile(r"/club/(\d+)\b")):
            m_cid = re.search(r"/club/(\d+)\b", str(c_link.get("href", "")))
            if m_cid:
                cid = m_cid.group(1)
                if not club_ids or club_ids[-1] != cid:
                    club_ids.append(cid)

        if len(club_ids) < 2:
            club_ids = []
            club_token_indices = []
            for idx, s in enumerate(strings):
                if re.fullmatch(r"\d{1,2}", s) or re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", s):
                    continue
                if s.startswith("الجولة") or re.search(r"\d{4}-\d{2}-\d{2}", s):
                    continue
                cid = resolve_club_id_by_name(data, s)
                if cid and (not club_ids or club_ids[-1] != cid):
                    club_ids.append(cid)
                    club_token_indices.append(idx)
                    if len(club_ids) >= 2:
                        break

        if len(club_ids) < 2:
            continue

        dt = parse_date_time_text(card_text)
        closed_doors = "بدون جمهور" in card_text
        postponed = any(s in ("مؤجلة", "مؤجل", "تأجلت") for s in strings)
        live = any(s in ("مباشر", "جارية الآن") for s in strings)

        venue_str: Optional[str] = None
        for idx, s in enumerate(strings):
            if re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", s) and idx + 1 < len(strings):
                cand = strings[idx + 1]
                if (
                    cand not in ("تفاصيل المباراة", "بدون جمهور", "VS", "-")
                    and not cand.startswith("الجولة")
                ):
                    venue_str = cand
                    break

        # Extract score from two separate numeric elements between the two club tokens (real LIRF structure)
        score_pair: Optional[tuple[int, int]] = None
        if len(club_token_indices) >= 2:
            between_tokens = strings[club_token_indices[0] + 1 : club_token_indices[1]]
            if not any(tok.upper() == "VS" for tok in between_tokens):
                nums = [
                    int(tok)
                    for tok in between_tokens
                    if re.fullmatch(r"\d{1,2}", tok) and int(tok) <= MAX_VALID_GOALS
                ]
                if len(nums) >= 2:
                    score_pair = (nums[0], nums[1])
                elif len(nums) == 0:
                    for tok in between_tokens:
                        m_two = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})", tok)
                        if m_two:
                            score_pair = (int(m_two.group(1)), int(m_two.group(2)))
                            break

        status: Optional[str] = None
        if postponed:
            status = "postponed"
        elif live:
            status = "live"
        elif score_pair is not None:
            status = "finished"
        elif "VS" in card_text or dt is not None:
            status = "scheduled"

        hints.append(
            FixtureHint(
                match_id=match_id,
                round_num=round_num,
                home_id=club_ids[0],
                away_id=club_ids[1],
                kickoff=dt.isoformat() if dt else None,
                venue=venue_str,
                score=score_pair,
                status=status,
                closed_doors=closed_doors,
            )
        )
    return hints


def update_standings(
    data: dict[str, Any],
    problems: list[str],
    fetch_fn: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None,
    accept_regression: bool = False,
) -> tuple[bool, list[FixtureHint]]:
    """
    Fetch `/ar/ranking`, verify competition filters and 16-club set identity,
    parse standings by header labels, and update `data['standings']`.
    """
    cfg = ScraperConfig.from_data(data)
    getter = fetch_fn or FETCHER.fetch_soup
    soup = getter(cfg.ranking_url, problems)
    if not soup:
        return False, []

    parsed_rows, hints = parse_standings_from_soup(soup, data, problems)
    if not parsed_rows:
        return False, hints

    if len(parsed_rows) != EXPECTED_CLUB_COUNT:
        problems.append(
            f"صفحة الترتيب: عدد الصفوف المقروءة ({len(parsed_rows)}) لا يطابق {EXPECTED_CLUB_COUNT} نادياً"
        )
        return False, hints

    # Item 4: Assert that the set of parsed clubIds equals the known standings clubIds
    known_club_ids = {
        str(s.get("clubId"))
        for s in data.get("standings", [])
        if s.get("clubId") is not None
    }
    parsed_club_ids = {str(r["clubId"]) for r in parsed_rows}
    if known_club_ids and parsed_club_ids != known_club_ids:
        foreign = sorted(parsed_club_ids - known_club_ids)
        missing = sorted(known_club_ids - parsed_club_ids)
        msg = (
            f"صفحة الترتيب: مجموعة الأندية المستخرجة لا تطابق أندية فوج الشرق المعروفة "
            f"(أندية غريبة={foreign}, أندية مفقودة={missing}) — تم إيقاف تحديث الترتيب"
        )
        log.error(msg)
        problems.append(msg)
        return False, []

    by_club = {str(s.get("clubId")): s for s in data.get("standings", []) if s.get("clubId") is not None}
    updated = False

    for new_row in parsed_rows:
        cid = str(new_row["clubId"])
        existing = by_club.get(cid)
        if not existing:
            # Should never happen when known_club_ids is populated, guarded above
            problems.append(f"صفحة الترتيب: نادٍ غير معروف ({cid}) — تم رفض الإضافة")
            return False, []

        old_played = existing.get("played", 0)
        if isinstance(old_played, int) and new_row["played"] < old_played:
            if not accept_regression:
                problems.append(
                    f"صفحة الترتيب: تراجع غير منطقي في عدد المباريات الملعوبة للنادي {cid} ({new_row['played']} < {old_played})"
                )
                return False, hints
            log.warning(
                "تم تفعيل --accept-regression: السماح بتراجع عدد المباريات الملعوبة للنادي %s (%s -> %s)",
                cid,
                old_played,
                new_row["played"],
            )

        if any(existing.get(k) != v for k, v in new_row.items()):
            existing.update(new_row)
            updated = True

    if updated:
        data["standings"].sort(
            key=lambda s: (
                s.get("position") or 99,
                -(s.get("adjustedPoints") if s.get("adjustedPoints") is not None else -999),
                -(s.get("goalDifference") or 0),
            )
        )
    return updated, hints


# ════════════════════════ 7. Match Page Parsing & Fixture Updates ════════════════════════
def _match_header_root(soup: BeautifulSoup) -> Tag:
    """Return the match header container (excluding embedded standings tables at page bottom)."""
    header = soup.find(class_=re.compile(r"match-header|match-hero|match-top", re.I))
    if isinstance(header, Tag):
        return header
    # On real LIRF match pages, the first <section> inside <main> is the match header
    main_el = soup.find("main")
    if isinstance(main_el, Tag):
        first_sec = main_el.find("section")
        if isinstance(first_sec, Tag):
            return first_sec
    clone = copy.copy(soup)
    for tbl in clone.find_all("table"):
        tbl.decompose()
    return clone


def verify_match_page_teams(soup: BeautifulSoup, home_id: Any, away_id: Any) -> bool:
    """Verify that the match page header links to `home_id` and `away_id` in order."""
    root = _match_header_root(soup)
    found_clubs: list[str] = []
    for a_tag in root.find_all("a", href=True):
        if a_tag.find_parent("table") is not None:
            continue
        m = re.search(r"/club/(\d+)\b", str(a_tag.get("href", "")))
        if m:
            cid = m.group(1)
            if not found_clubs or found_clubs[-1] != cid:
                found_clubs.append(cid)
            if len(found_clubs) >= 2:
                break
    if len(found_clubs) < 2:
        return False
    return found_clubs[0] == str(home_id) and found_clubs[1] == str(away_id)


def _tokens_between_clubs(soup: BeautifulSoup, home_id: Any, away_id: Any) -> list[str]:
    """Return normalized text tokens appearing between the home club link and away club link in the match header."""
    root = _match_header_root(soup)
    home_str, away_str = str(home_id), str(away_id)
    collecting = False
    tokens: list[str] = []

    for node in root.descendants:
        if isinstance(node, Tag) and node.find_parent("table") is not None:
            continue
        if isinstance(node, Tag) and node.name == "a":
            m = re.search(r"/club/(\d+)\b", str(node.get("href", "")))
            if not m:
                continue
            cid = m.group(1)
            if cid == home_str:
                collecting = True
                tokens = []
            elif collecting and cid == away_str:
                break
        elif collecting and isinstance(node, NavigableString):
            # Skip text inside the home club <a> tag itself
            if isinstance(node.parent, Tag) and node.parent.name == "a":
                m_parent = re.search(r"/club/(\d+)\b", str(node.parent.get("href", "")))
                if m_parent and m_parent.group(1) == home_str:
                    continue
            s = normalize_digits(str(node))
            if s:
                tokens.append(s)
    return tokens


def parse_score(soup: BeautifulSoup, home_id: Any, away_id: Any) -> Optional[tuple[int, int]]:
    """
    Extract `(home_score, away_score)` from a match page header after verifying clubs.
    On real LIRF match pages, scores render as two separate numeric elements (`3` and `0`)
    between `<a href=".../club/{home_id}">` and `<a href=".../club/{away_id}">`.
    """
    if not verify_match_page_teams(soup, home_id, away_id):
        return None

    between = _tokens_between_clubs(soup, home_id, away_id)
    nums: list[int] = []
    for s in between:
        if re.search(r"\b\d{1,2}:\d{2}\b", s) or "'" in s:
            continue
        if s.upper() == "VS":
            return None
        two = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})", s)
        if two:
            h_val, a_val = int(two.group(1)), int(two.group(2))
            if h_val <= MAX_VALID_GOALS and a_val <= MAX_VALID_GOALS:
                return (h_val, a_val)
        elif re.fullmatch(r"\d{1,2}", s):
            val = int(s)
            if val <= MAX_VALID_GOALS:
                nums.append(val)
        if len(nums) >= 2:
            return (nums[0], nums[1])
    return None


POSTPONED_BADGE_TERMS = frozenset({"مؤجلة", "مؤجل", "تأجلت", "لقاء مؤجل", "مباراة مؤجلة"})
FORFEIT_BADGE_TERMS = frozenset({"على البساط", "انسحاب رسمي", "خسارة على البساط", "فوز على البساط"})
LIVE_BADGE_TERMS = frozenset({"مباشر", "جارية الآن", "الشوط الأول", "الشوط الثاني"})


def detect_match_status(
    soup: BeautifulSoup,
    home_id: Any,
    away_id: Any,
    kickoff_dt: Optional[datetime],
    now: Optional[datetime] = None,
) -> tuple[str, Optional[tuple[int, int]], bool]:
    """
    Item 3 & Item 5:
    Determine `(status, score, closedDoors)` for a match page using dedicated status badges/tokens
    between the two clubs in the header and verified match event markers.
    Generic words like `"غياب"` in unrelated text NEVER mark a match as `forfeit`.
    """
    now = now or datetime.now(TZ)
    root = _match_header_root(soup)
    between_tokens = _tokens_between_clubs(soup, home_id, away_id)

    # Also collect explicit status badge elements if present in the header
    badge_tokens = set(between_tokens)
    for badge_el in root.find_all(class_=re.compile(r"status|badge", re.I)):
        if isinstance(badge_el, Tag):
            txt = normalize_digits(badge_el.get_text(" ", strip=True))
            if txt and len(txt) <= 30:
                badge_tokens.add(txt)

    closed_doors = "بدون جمهور" in badge_tokens or any(
        normalize_digits(s) == "بدون جمهور" for s in root.stripped_strings
    )

    if any(tok in POSTPONED_BADGE_TERMS for tok in badge_tokens):
        return ("postponed", None, closed_doors)

    if any(tok in FORFEIT_BADGE_TERMS for tok in badge_tokens):
        sc = parse_score(soup, home_id, away_id)
        return ("forfeit", sc, closed_doors)

    is_live_marker = any(tok in LIVE_BADGE_TERMS for tok in badge_tokens)
    sc = parse_score(soup, home_id, away_id)
    if is_live_marker:
        return ("live", sc, closed_doors)

    full_text = normalize_digits(soup.get_text(" ", strip=True))
    has_qareeban = "قريباً" in full_text
    has_90_marker = bool(
        re.search(r"(?:^|\s)('90|90')(?:\s|$)", full_text)
        and not has_qareeban
    )
    has_ft_text = bool(re.search(r"(نهاية المباراة|انتهت|Full Time)", full_text, re.I))
    has_events = bool(re.search(r"(هدف من|بطاقة صفراء|بطاقة حمراء|يعوّض)", full_text))

    if sc is not None:
        if has_ft_text or has_90_marker or has_events:
            if kickoff_dt and kickoff_dt <= now < kickoff_dt + MATCH_LENGTH and not has_ft_text and not has_90_marker:
                return ("live", sc, closed_doors)
            return ("finished", sc, closed_doors)
        if kickoff_dt and kickoff_dt <= now < kickoff_dt + MATCH_LENGTH:
            return ("live", sc, closed_doors)
        if kickoff_dt and now >= kickoff_dt + MATCH_LENGTH:
            return ("finished", sc, closed_doors)

    return ("scheduled", None, closed_doors)


def parse_kickoff(soup: BeautifulSoup, home_id: Any, away_id: Any = None) -> Optional[datetime]:
    """Parse kickoff datetime (`+01:00`) from the match header after verifying `home_id`."""
    if away_id is not None and not verify_match_page_teams(soup, home_id, away_id):
        return None

    head: list[str] = []
    found = False
    for node in soup.descendants:
        if isinstance(node, Tag) and node.find_parent("table") is not None:
            continue
        if (
            isinstance(node, Tag)
            and node.name == "a"
            and re.search(rf"/club/{home_id}\b", str(node.get("href", "")))
        ):
            found = True
            break
        if isinstance(node, NavigableString):
            s = normalize_digits(str(node))
            if s:
                head.append(s)
    if not found:
        return None
    return parse_date_time_text("\n".join(head))


def parse_venue(soup: BeautifulSoup, home_id: Any, away_id: Any = None) -> Optional[str]:
    """Parse stadium/venue name from a match header after verifying `home_id`."""
    if away_id is not None and not verify_match_page_teams(soup, home_id, away_id):
        return None

    v_el = _match_header_root(soup).find(class_=re.compile(r"venue|stadium", re.I))
    if isinstance(v_el, Tag):
        v_txt = normalize_digits(v_el.get_text(" ", strip=True))
        if v_txt and v_txt != "-":
            return v_txt

    head: list[str] = []
    found = False
    for node in soup.descendants:
        if isinstance(node, Tag) and node.find_parent("table") is not None:
            continue
        if (
            isinstance(node, Tag)
            and node.name == "a"
            and re.search(rf"/club/{home_id}\b", str(node.get("href", "")))
        ):
            found = True
            break
        if isinstance(node, NavigableString):
            t = normalize_digits(str(node))
            if t:
                head.append(t)
    if not found:
        return None

    ignore_pattern = re.compile(
        r"الجولة|جولة|\d{4}|^\d+$|رابطة|الدوري|الجهات|الجهوي|الشرق|\bشرق\b|\bغرب\b|\bوسط\b|VS|QVR|أكابر|قريباً|بدون جمهور|مؤجلة|مباشر"
    )
    for i, t in enumerate(head):
        if re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", t):
            for cand in head[i + 1 : i + 4]:
                if cand == "-" or ignore_pattern.search(cand) or any(mn in cand for mn in MONTHS):
                    continue
                if 1 <= len(cand.split()) <= 12 and len(cand) <= 65:
                    return cand
            return None
    return None


def parse_referees(soup: BeautifulSoup, home_id: Any, away_id: Any) -> list[str]:
    """Extract referee names from a match page (supports LIRF header strings between score and away club)."""
    if not verify_match_page_teams(soup, home_id, away_id):
        return []
    ref_container = soup.find(class_=re.compile(r"referee", re.I))
    if isinstance(ref_container, Tag):
        refs = [
            normalize_digits(s)
            for s in ref_container.stripped_strings
            if normalize_digits(s)
        ]
        if refs:
            return refs

    between = _tokens_between_clubs(soup, home_id, away_id)
    refs_out: list[str] = []
    score_nums = 0
    for s in between:
        if s.upper() == "VS" or re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}", s):
            continue
        if re.fullmatch(r"\d{1,2}", s):
            score_nums += 1
            continue
        if score_nums >= 2 and 1 <= len(s.split()) <= 5 and not re.search(r"\d", s):
            if (
                s not in refs_out
                and s not in ("بدون جمهور", "انتهت", "مباشر", "قريباً")
                and s not in POSTPONED_BADGE_TERMS
                and s not in FORFEIT_BADGE_TERMS
            ):
                refs_out.append(s)
    return refs_out[:4]


def parse_events(soup: BeautifulSoup, data: dict[str, Any], m: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract chronological match events (goals, yellow/red cards, substitutions) and link `playerId`.
    Supports LIRF narrative lines (`25'\nهدف من ...`).
    """
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    text = soup.get_text("\n", strip=True)
    lines = [normalize_digits(ln) for ln in text.splitlines() if normalize_digits(ln)]
    events: list[dict[str, Any]] = []
    opp_id = str(m.get("away")) if str(m.get("home")) == cbm_id else str(m.get("home"))

    for i, ln in enumerate(lines):
        m_min = re.fullmatch(r"(\d{1,3})'", ln)
        if not m_min or i + 1 >= len(lines):
            continue
        minute = int(m_min.group(1))
        desc = lines[i + 1]

        g_match = re.match(r"^هدف من\s+([^\(]+?)(?:\s*\((.+?)\))?$", desc)
        if g_match:
            pname = g_match.group(1).strip()
            team_hint = (g_match.group(2) or "").strip()
            hint_cid = resolve_club_id_by_name(data, team_hint) if team_hint else None
            pid = match_cbm_player_id(data, pname) if hint_cid in (None, cbm_id) else None
            team = hint_cid or (cbm_id if pid else opp_id)
            events.append(
                {
                    "minute": minute,
                    "type": "goal",
                    "team": team,
                    "playerId": pid if team == cbm_id else None,
                    "playerName": None if (pid and team == cbm_id) else pname,
                }
            )
            continue

        c_match = re.match(r"^بطاقة (صفراء|حمراء) لـ?(.+)$", desc)
        if c_match:
            ctype = "yellow" if c_match.group(1) == "صفراء" else "red"
            pname = c_match.group(2).strip()
            pid = match_cbm_player_id(data, pname)
            team = cbm_id if pid else opp_id
            events.append(
                {
                    "minute": minute,
                    "type": ctype,
                    "team": team,
                    "playerId": pid,
                    "playerName": None if pid else pname,
                }
            )
            continue

        s_match = re.match(r"^(.+?)\s+يعوّض\s+(.+)$", desc)
        if s_match:
            in_name, out_name = s_match.group(1).strip(), s_match.group(2).strip()
            in_id = match_cbm_player_id(data, in_name)
            out_id = match_cbm_player_id(data, out_name)
            team = cbm_id if (in_id or out_id) else opp_id
            events.append(
                {
                    "minute": minute,
                    "type": "sub-in",
                    "team": team,
                    "playerId": in_id,
                    "playerName": None if in_id else in_name,
                    "relatedPlayerId": out_id,
                    "relatedPlayerName": None if out_id else out_name,
                }
            )
            events.append(
                {
                    "minute": minute,
                    "type": "sub-out",
                    "team": team,
                    "playerId": out_id,
                    "playerName": None if out_id else out_name,
                    "relatedPlayerId": in_id,
                    "relatedPlayerName": None if in_id else in_name,
                }
            )

    return events


def parse_lineups(soup: BeautifulSoup, data: dict[str, Any], m: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Parse home and away lineups (`starters`, `bench`, `coach`) from a LIRF match page.
    On LIRF match pages, two sequential lineup blocks appear under `حراس المرمى`, `المدافعون`,
    `وسط الميدان`, `المهاجمون`, `البدلاء`, `المدرب` (first for `home`, second for `away`).
    """
    if not verify_match_page_teams(soup, m.get("home"), m.get("away")):
        return None

    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    text = soup.get_text("\n", strip=True)
    lines = [normalize_digits(ln) for ln in text.splitlines() if normalize_digits(ln)]

    section_headers = {"حراس المرمى", "المدافعون", "وسط الميدان", "المهاجمون", "البدلاء", "المدرب"}
    stop_markers = {"الترتيب", "عرض الكل", "الهبوط", "ألبوم الصور", "ألبوم الفيديوهات", "LIRF"}

    gk_indices = [idx for idx, ln in enumerate(lines) if ln == "حراس المرمى"]
    if not gk_indices:
        return None

    def _parse_team_block(start_idx: int, end_idx: int, is_cbm_team: bool) -> dict[str, Any]:
        starters: list[dict[str, Any]] = []
        bench: list[dict[str, Any]] = []
        coach: Optional[str] = None
        mode: Optional[str] = None
        i = start_idx

        while i < end_idx:
            ln = lines[i]
            if ln in stop_markers:
                break
            if ln in ("حراس المرمى", "المدافعون", "وسط الميدان", "المهاجمون"):
                mode = "starters"
                i += 1
                continue
            if ln == "البدلاء":
                mode = "bench"
                i += 1
                continue
            if ln == "المدرب":
                mode = "coach"
                i += 1
                continue

            if mode == "coach":
                if "الجزائر" not in ln and not re.fullmatch(r"\d+'?", ln) and ln not in section_headers:
                    coach = ln
                    break
                i += 1
                continue

            if mode in ("starters", "bench"):
                if "الجزائر" in ln or re.fullmatch(r"\d{1,3}'", ln) or re.fullmatch(r"\d{1,2}", ln):
                    i += 1
                    continue
                pname = ln
                shirt: Optional[int] = None
                if i + 1 < end_idx and re.fullmatch(r"\d{1,2}", lines[i + 1]):
                    shirt = int(lines[i + 1])
                    i += 2
                else:
                    i += 1
                while i < end_idx and (
                    lines[i] == pname
                    or re.fullmatch(r"\d{1,3}'", lines[i])
                    or "الجزائر" in lines[i]
                ):
                    i += 1

                target_list = starters if mode == "starters" else bench
                if is_cbm_team:
                    pid = match_cbm_player_id(data, pname)
                    if not pid and shirt is not None:
                        for p in data.get("players", []):
                            if p.get("shirt") == shirt:
                                pid = str(p["id"])
                                break
                    if pid:
                        if not any(x.get("playerId") == pid for x in target_list):
                            target_list.append({"playerId": pid})
                    else:
                        entry: dict[str, Any] = {"playerName": pname}
                        if shirt is not None:
                            entry["shirt"] = shirt
                        target_list.append(entry)
                else:
                    entry = {"playerName": pname}
                    if shirt is not None:
                        entry["shirt"] = shirt
                    if not any(x.get("playerName") == pname for x in target_list):
                        target_list.append(entry)
                continue

            i += 1

        return {"starters": starters, "bench": bench, "coach": coach}

    home_is_cbm = str(m.get("home")) == cbm_id
    away_is_cbm = str(m.get("away")) == cbm_id
    first_end = gk_indices[1] if len(gk_indices) > 1 else len(lines)
    home_lu = _parse_team_block(gk_indices[0], first_end, home_is_cbm)
    away_lu = (
        _parse_team_block(gk_indices[1], len(lines), away_is_cbm)
        if len(gk_indices) > 1
        else {"starters": [], "bench": [], "coach": None}
    )

    if not home_lu["starters"] and not away_lu["starters"]:
        return None
    return {"home": home_lu, "away": away_lu}


def apply_fixture_hints(
    data: dict[str, Any],
    hints: list[FixtureHint],
    notes: list[str],
    push_events: list[dict[str, Any]],
) -> bool:
    """
    Apply fixture updates (kickoff, venue, closedDoors, status, score, new fixtures)
    discovered from `/ar/ranking` sub-rows and `/ar/calendar` / homepage cards.
    """
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    matches: list[dict[str, Any]] = data.setdefault("matches", [])
    updated = False

    for hint in hints:
        if not hint.home_id or not hint.away_id:
            continue
        if cbm_id not in (str(hint.home_id), str(hint.away_id)):
            continue

        target: Optional[dict[str, Any]] = None
        for m in matches:
            if str(m.get("home")) == str(hint.home_id) and str(m.get("away")) == str(hint.away_id):
                if hint.round_num is None or m.get("round") == hint.round_num:
                    target = m
                    break

        if target is None and hint.round_num is not None and hint.match_id:
            new_match: dict[str, Any] = {
                "id": str(hint.match_id),
                "round": hint.round_num,
                "kickoff": hint.kickoff,
                "venue": normalize_venue(hint.venue, is_cbm_home=(str(hint.home_id) == cbm_id)),
                "home": str(hint.home_id),
                "away": str(hint.away_id),
                "status": hint.status or "scheduled",
                "closedDoors": bool(hint.closed_doors),
                "score": {"home": hint.score[0], "away": hint.score[1]} if hint.score else None,
                "referees": [],
                "events": [],
                "lineups": {
                    "home": {"starters": [], "bench": [], "coach": None},
                    "away": {"starters": [], "bench": [], "coach": None},
                },
                "detailFetchedAt": None,
                "lastDetailCheck": None,
            }
            matches.append(new_match)
            matches.sort(key=lambda x: x.get("round") or 99)
            notes.append(f"إضافة مباراة جديدة في الجولة {hint.round_num} (#{hint.match_id})")
            updated = True
            continue

        if target is None:
            continue

        is_cbm_home = str(target.get("home")) == cbm_id
        if hint.kickoff and target.get("kickoff") != hint.kickoff:
            old_ko = target.get("kickoff")
            if old_ko:
                target["rescheduledFrom"] = old_ko
            target["kickoff"] = hint.kickoff
            ko_dt = parse_iso_kickoff(hint.kickoff)
            if ko_dt:
                notes.append(f"الجولة {target.get('round')}: موعد جديد {ko_dt:%Y-%m-%d %H:%M}")
                push_events.append(build_kickoff_push(data, target, ko_dt))
            updated = True

        norm_v = normalize_venue(hint.venue, is_cbm_home=is_cbm_home)
        if norm_v and target.get("venue") != norm_v:
            target["venue"] = norm_v
            notes.append(f"الجولة {target.get('round')}: الملعب {norm_v}")
            updated = True

        if hint.closed_doors and not target.get("closedDoors"):
            target["closedDoors"] = True
            notes.append(f"الجولة {target.get('round')}: بدون جمهور")
            updated = True

        if hint.status in ("postponed", "forfeit") and target.get("status") != hint.status:
            target["status"] = hint.status
            notes.append(f"الجولة {target.get('round')}: الحالة {hint.status}")
            updated = True

        if hint.status == "finished" and hint.score and target.get("status") != "finished":
            target["score"] = {"home": hint.score[0], "away": hint.score[1]}
            target["status"] = "finished"
            notes.append(
                f"الجولة {target.get('round')}: سُجّلت النتيجة {hint.score[0]}-{hint.score[1]}"
            )
            push_events.append(build_result_push(data, target, hint.score))
            updated = True

    known_clubs = {cbm_id} | {str(o.get("id")) for o in data.get("opponents", []) if o.get("id")}
    round_results: list[dict[str, Any]] = data.get("roundResults") or []
    by_pair = {(str(r.get("home")), str(r.get("away"))): r for r in round_results}
    for hint in hints:
        if not hint.home_id or not hint.away_id or hint.round_num is None:
            continue
        if str(hint.home_id) not in known_clubs or str(hint.away_id) not in known_clubs:
            continue
        pair = (str(hint.home_id), str(hint.away_id))
        existing_rr = by_pair.get(pair)
        norm_v = normalize_venue(hint.venue, is_cbm_home=(str(hint.home_id) == cbm_id))
        score_obj = {"home": hint.score[0], "away": hint.score[1]} if hint.score else None
        if existing_rr:
            if hint.match_id and not existing_rr.get("id"):
                existing_rr["id"] = str(hint.match_id)
                updated = True
            if hint.kickoff and existing_rr.get("kickoff") != hint.kickoff:
                existing_rr["kickoff"] = hint.kickoff
                updated = True
            if norm_v and existing_rr.get("venue") != norm_v:
                existing_rr["venue"] = norm_v
                updated = True
            if hint.status and existing_rr.get("status") != hint.status:
                existing_rr["status"] = hint.status
                updated = True
            if score_obj and existing_rr.get("score") != score_obj:
                existing_rr["score"] = score_obj
                existing_rr["status"] = "finished"
                updated = True
            if hint.closed_doors and not existing_rr.get("closedDoors"):
                existing_rr["closedDoors"] = True
                updated = True
        else:
            new_rr = {
                "id": str(hint.match_id) if hint.match_id else None,
                "round": hint.round_num,
                "kickoff": hint.kickoff,
                "venue": norm_v,
                "home": str(hint.home_id),
                "away": str(hint.away_id),
                "status": hint.status or ("finished" if score_obj else "scheduled"),
                "closedDoors": bool(hint.closed_doors),
                "score": score_obj,
            }
            round_results.append(new_rr)
            by_pair[pair] = new_rr
            updated = True

    if round_results:
        data["roundResults"] = round_results

    return updated


def update_matches(
    data: dict[str, Any],
    problems: list[str],
    notes: list[str],
    push_events: list[dict[str, Any]],
    ranking_hints: Optional[list[FixtureHint]] = None,
    fetch_fn: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None,
    now: Optional[datetime] = None,
) -> tuple[bool, Optional[BeautifulSoup]]:
    """
    Update scheduled, live, postponed, and recently-finished matches using:
      1) Fixture hints from `/ar/ranking`, `/ar/calendar`, and `https://www.lirf.dz/`
      2) Individual `/ar/match/{id}` pages (for upcoming rounds and finished matches within the re-check window)
    Returns `(updated, home_soup)`.
    """
    cfg = ScraperConfig.from_data(data)
    getter = fetch_fn or FETCHER.fetch_soup
    now = now or datetime.now(TZ)
    updated = False

    all_hints: list[FixtureHint] = list(ranking_hints or [])
    cal_soup = getter(cfg.calendar_url, problems)
    if cal_soup:
        all_hints.extend(extract_calendar_fixtures(cal_soup, data))
    home_soup = getter(cfg.home_url, problems)
    if home_soup:
        all_hints.extend(extract_calendar_fixtures(home_soup, data))

    if apply_fixture_hints(data, all_hints, notes, push_events):
        updated = True

    matches = data.get("matches", [])
    to_inspect: list[dict[str, Any]] = []

    for m in matches:
        if m.get("id") is None:
            continue
        st = m.get("status")
        ko = parse_iso_kickoff(m.get("kickoff"))
        if st == "finished":
            has_details = bool(m.get("events")) and bool(
                m.get("lineups", {}).get("home", {}).get("starters")
                or m.get("lineups", {}).get("away", {}).get("starters")
            )
            if not has_details and ko and (now - ko) <= DETAIL_RECHECK_WINDOW:
                to_inspect.append(m)
        else:
            to_inspect.append(m)

    to_inspect.sort(key=lambda m: (0 if m.get("status") == "finished" else 1, m.get("round") or 99))
    inspect_slice = to_inspect[:4]
    notes.append(f"صفحات المباريات التي فُحصت: {len(inspect_slice)}")

    for m in inspect_slice:
        match_url = (
            cfg.match_url_template.replace("{id}", str(m["id"]))
            if "{id}" in cfg.match_url_template
            else f"{cfg.match_url_template.rstrip('/')}/{m['id']}"
        )
        soup = getter(match_url, problems)
        if not soup:
            continue

        if not verify_match_page_teams(soup, m.get("home"), m.get("away")):
            log.debug(
                "تخطي الصفحة %s لأن الفريقين في الرأس لا يطابقان (%s ضد %s)",
                match_url,
                m.get("home"),
                m.get("away"),
            )
            continue

        is_cbm_home = str(m.get("home")) == cfg.club_id
        ko = parse_kickoff(soup, m.get("home"), m.get("away"))
        if ko and m.get("kickoff") != ko.isoformat():
            if m.get("kickoff"):
                m["rescheduledFrom"] = m["kickoff"]
            m["kickoff"] = ko.isoformat()
            notes.append(f"الجولة {m.get('round')}: موعد جديد {ko:%Y-%m-%d %H:%M}")
            updated = True
            if cfg.club_id in (str(m.get("home")), str(m.get("away"))):
                push_events.append(build_kickoff_push(data, m, ko))

        raw_venue = parse_venue(soup, m.get("home"), m.get("away"))
        norm_v = normalize_venue(raw_venue, is_cbm_home=is_cbm_home)
        if norm_v and m.get("venue") != norm_v:
            m["venue"] = norm_v
            notes.append(f"الجولة {m.get('round')}: الملعب {norm_v}")
            updated = True

        kick_dt = parse_iso_kickoff(m.get("kickoff"))
        detected_status, sc, closed_doors = detect_match_status(
            soup, m.get("home"), m.get("away"), kick_dt, now=now
        )

        if closed_doors and not m.get("closedDoors"):
            m["closedDoors"] = True
            notes.append(f"الجولة {m.get('round')}: بدون جمهور")
            updated = True
        elif "closedDoors" not in m:
            m["closedDoors"] = False

        if detected_status in ("postponed", "forfeit") and m.get("status") != detected_status:
            m["status"] = detected_status
            if sc:
                m["score"] = {"home": sc[0], "away": sc[1]}
            notes.append(f"الجولة {m.get('round')}: الحالة {detected_status}")
            updated = True
            continue

        if detected_status == "live":
            new_score = {"home": sc[0], "away": sc[1]} if sc else m.get("score")
            if m.get("status") != "live" or m.get("score") != new_score:
                m["status"] = "live"
                m["score"] = new_score
                evs = parse_events(soup, data, m)
                if evs:
                    m["events"] = evs
                notes.append(
                    f"الجولة {m.get('round')}: مباشرة الآن ({new_score['home']}-{new_score['away']})"
                    if new_score
                    else f"الجولة {m.get('round')}: مباشرة الآن"
                )
                updated = True
            continue

        if detected_status == "finished" and sc is not None:
            was_finished = m.get("status") == "finished"
            new_score_obj = {"home": sc[0], "away": sc[1]}
            if not was_finished or m.get("score") != new_score_obj:
                m["score"] = new_score_obj
                m["status"] = "finished"
                notes.append(f"الجولة {m.get('round')}: سُجّلت النتيجة {sc[0]}-{sc[1]}")
                updated = True
                if not was_finished and cfg.club_id in (str(m.get("home")), str(m.get("away"))):
                    push_events.append(build_result_push(data, m, sc))

            evs = parse_events(soup, data, m)
            if evs and m.get("events") != evs:
                m["events"] = evs
                m["detailFetchedAt"] = now.isoformat(timespec="seconds")
                updated = True

            lu = parse_lineups(soup, data, m)
            if lu and m.get("lineups") != lu:
                m["lineups"] = lu
                m["detailFetchedAt"] = now.isoformat(timespec="seconds")
                updated = True

            refs = parse_referees(soup, m.get("home"), m.get("away"))
            if refs and m.get("referees") != refs:
                m["referees"] = refs
                updated = True

    return updated, home_soup


# ════════════════════════ 8. Squad, Statistics & Metadata Sync ════════════════════════
def update_squad_and_staff(
    data: dict[str, Any],
    problems: list[str],
    notes: list[str],
    fetch_fn: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None,
) -> bool:
    """
    Fetch `/ar/club/733` and refresh `players` and `staff` when squad details change
    (updating shirt numbers, positions, approxAge, and photoUrls while handling missing photos).
    """
    cfg = ScraperConfig.from_data(data)
    getter = fetch_fn or FETCHER.fetch_soup
    soup = getter(cfg.club_url, problems)
    if not soup:
        return False

    updated = False
    by_id = {str(p.get("id")): p for p in data.get("players", []) if p.get("id") is not None}

    pos_map = {
        "حراس المرمى": "GK",
        "المدافعون": "DEF",
        "وسط الميدان": "MID",
        "المهاجمون": "FW",
    }

    for a_tag in soup.find_all("a", href=re.compile(r"/player/(\d+)\b")):
        m_pid = re.search(r"/player/(\d+)\b", str(a_tag.get("href", "")))
        if not m_pid:
            continue
        pid = m_pid.group(1)
        card = a_tag.find_parent(["div", "li", "article"]) or a_tag
        card_strings = [normalize_digits(s) for s in card.stripped_strings if normalize_digits(s)]

        pos_code = "MID"
        prev_heading = a_tag.find_previous(
            ["h2", "h3", "h4", "div"],
            string=re.compile(r"حراس المرمى|المدافعون|وسط الميدان|المهاجمون"),
        )
        if isinstance(prev_heading, Tag):
            h_txt = normalize_digits(prev_heading.get_text(" ", strip=True))
            for k_ar, k_pos in pos_map.items():
                if k_ar in h_txt:
                    pos_code = k_pos
                    break

        shirt_num: Optional[int] = None
        approx_age: Optional[int] = None
        raw_name: Optional[str] = None
        for s in card_strings:
            if re.fullmatch(r"\d{1,2}", s):
                if shirt_num is None:
                    shirt_num = int(s)
            elif s.startswith("العمر:"):
                m_age = re.search(r"(\d{1,2})", s)
                if m_age:
                    approx_age = int(m_age.group(1))
            elif "الجزائر" not in s and not re.search(r"\d", s) and len(s) >= 3:
                if raw_name is None:
                    raw_name = s

        img_tag = card.find("img", src=True)
        photo_url: Optional[str] = None
        if isinstance(img_tag, Tag):
            src_val = str(img_tag.get("src") or "").strip()
            if src_val and "default" not in src_val.lower() and "placeholder" not in src_val.lower():
                photo_url = urljoin(cfg.club_url, src_val)

        if pid in by_id:
            p = by_id[pid]
            if shirt_num is not None and p.get("shirt") != shirt_num:
                p["shirt"] = shirt_num
                updated = True
            if photo_url and p.get("photoUrl") != photo_url:
                p["photoUrl"] = photo_url
                updated = True
            if not p.get("birthDate") and approx_age and p.get("approxAge") != approx_age:
                p["approxAge"] = approx_age
                updated = True
        elif raw_name:
            ar_name = "بن صغير حمزة" if raw_name.upper() in ("BENSEGHIER HAMZA", "HAMZA BENSEGHIER") else raw_name
            lat_name = transliterate_ar_name(ar_name)
            new_player = {
                "id": pid,
                "shirt": shirt_num,
                "name": {"ar": ar_name, "latin": lat_name, "en": lat_name},
                "position": pos_code,
                "birthDate": None,
                "approxAge": approx_age,
                "nationality": "الجزائر",
                "photoUrl": photo_url,
                "sourceUrl": f"https://www.lirf.dz/ar/player/{pid}",
                "lastFetchedAt": datetime.now(TZ).isoformat(timespec="seconds"),
                "stats": {"appearances": 0, "goals": 0, "yellowCards": 0, "redCards": 0},
            }
            data.setdefault("players", []).append(new_player)
            by_id[pid] = new_player
            notes.append(f"إضافة لاعب جديد في القائمة: {ar_name} (#{shirt_num})")
            updated = True

    return updated


def _parse_homepage_player_cards(
    home_soup: BeautifulSoup,
    data: dict[str, Any],
    cbm_stats_from_site: dict[str, dict[str, int]],
    parsed_east_scorers: list[dict[str, Any]],
) -> None:
    """
    Parse the LIRF homepage `إحصائيات اللاعبين` section (`شرق`), where player cards render as:
    `<Player Name> <Club Name/Short> أهداف <G> مباريات <M> دقائق اللعب <MIN>`.
    """
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    known_clubs = {cbm_id} | {str(o.get("id")) for o in data.get("opponents", []) if o.get("id")}
    text = home_soup.get_text("\n", strip=True)
    if "إحصائيات اللاعبين" not in text:
        return

    stat_section = text.split("إحصائيات اللاعبين", 1)[1]
    for stop_word in ("أخبار", "مقالات", "الترتيب", "الرزنامة"):
        if stop_word in stat_section:
            stat_section = stat_section.split(stop_word, 1)[0]

    lines = [normalize_digits(ln) for ln in stat_section.splitlines() if normalize_digits(ln)]
    i = 0
    while i < len(lines):
        if lines[i] == "أهداف" and i >= 2 and i + 3 < len(lines):
            raw_pname = lines[i - 2]
            raw_club = lines[i - 1]
            goals_val = to_int(lines[i + 1])
            matches_val: Optional[int] = None
            if i + 3 < len(lines) and lines[i + 2] == "مباريات":
                matches_val = to_int(lines[i + 3])
            cid = resolve_club_id_by_name(data, raw_club)
            if cid and cid in known_clubs and goals_val is not None and goals_val > 0:
                pid_match = match_cbm_player_id(data, raw_pname) if cid == cbm_id else None
                p_obj = (
                    next((p for p in data.get("players", []) if str(p.get("id")) == str(pid_match)), None)
                    if pid_match
                    else None
                )
                shirt = p_obj.get("shirt") if p_obj else None
                if cid == cbm_id and pid_match:
                    st_entry = cbm_stats_from_site.setdefault(
                        pid_match, {"appearances": 0, "goals": 0, "yellowCards": 0, "redCards": 0}
                    )
                    st_entry["goals"] = max(st_entry.get("goals", 0), goals_val)
                    if matches_val is not None:
                        st_entry["appearances"] = max(st_entry.get("appearances", 0), matches_val)
                name_obj = (
                    copy.deepcopy(p_obj["name"])
                    if p_obj and isinstance(p_obj.get("name"), dict)
                    else {"ar": raw_pname, "latin": transliterate_ar_name(raw_pname) or raw_pname.title(), "en": transliterate_ar_name(raw_pname) or raw_pname.title()}
                )
                parsed_east_scorers.append(
                    {
                        "playerId": pid_match,
                        "clubId": cid,
                        "shirt": shirt,
                        "goals": goals_val,
                        "matches": matches_val,
                        "name": name_obj,
                    }
                )
            i += 4
            continue
        i += 1


def update_statistics(
    data: dict[str, Any],
    problems: list[str],
    notes: list[str],
    fetch_fn: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None,
    home_soup: Optional[BeautifulSoup] = None,
) -> bool:
    """
    Fetch `/ar/statistics` (and homepage `إحصائيات اللاعبين` cards) to update:
      1) `data['topScorers']`: Group East (`شرق`) league top scorers
      2) `data['players'][i]['stats']`: Official LIRF goals, yellow cards, red cards, and appearances
         for all CBM Mila (`733`) players, reconciled with match events so finished match goals are never lost.
    """
    cfg = ScraperConfig.from_data(data)
    getter = fetch_fn or FETCHER.fetch_soup
    soup = getter(cfg.statistics_url, problems)
    updated = False

    cbm_id = cfg.club_id
    known_clubs = {cbm_id} | {str(o.get("id")) for o in data.get("opponents", []) if o.get("id")}

    event_goals: dict[str, int] = {}
    event_yc: dict[str, int] = {}
    event_rc: dict[str, int] = {}
    event_apps: dict[str, int] = {}

    for m in data.get("matches", []):
        if m.get("status") != "finished":
            continue
        is_home = str(m.get("home")) == cbm_id
        lu = (m.get("lineups") or {}).get("home" if is_home else "away") or {}
        started_ids = {str(x.get("playerId")) for x in (lu.get("starters") or []) if x.get("playerId")}
        subbed_in_ids: set[str] = set()
        for ev in m.get("events", []):
            if str(ev.get("team")) != cbm_id:
                continue
            pid = str(ev.get("playerId") or "")
            if not pid:
                continue
            if ev.get("type") == "goal":
                event_goals[pid] = event_goals.get(pid, 0) + 1
            elif ev.get("type") == "yellow":
                event_yc[pid] = event_yc.get(pid, 0) + 1
            elif ev.get("type") == "red":
                event_rc[pid] = event_rc.get(pid, 0) + 1
            elif ev.get("type") == "sub-in":
                subbed_in_ids.add(pid)
        for pid in started_ids | subbed_in_ids:
            event_apps[pid] = event_apps.get(pid, 0) + 1

    parsed_east_scorers: list[dict[str, Any]] = []
    cbm_stats_from_site: dict[str, dict[str, int]] = {}

    if home_soup is not None:
        _parse_homepage_player_cards(home_soup, data, cbm_stats_from_site, parsed_east_scorers)

    if soup:
        _parse_homepage_player_cards(soup, data, cbm_stats_from_site, parsed_east_scorers)
        text = soup.get_text("\n", strip=True)
        sections = text.split("رجوع")

        for sec in sections:
            lines = [normalize_digits(ln) for ln in sec.splitlines() if normalize_digits(ln)]
            if not lines:
                continue
            sec_header = " ".join(lines[:4])
            stat_key: Optional[str] = None
            if "هدافين البطولة" in sec_header or "الهداف" in sec_header:
                stat_key = "goals"
            elif "البطاقات الصفراء" in sec_header:
                stat_key = "yellowCards"
            elif "البطاقات الحمراء" in sec_header:
                stat_key = "redCards"
            elif "عدد المشاركات" in sec_header:
                stat_key = "appearances"
            if not stat_key:
                continue

            full_sec_text = " ".join(lines)
            club_patterns = [
                "ش. ميلة", "ن. الفجوج", "إ سدراتة", "ت. قالمة", "CRBF", "شباب الرياضي بلدية فرجيوة",
                "إ.بوخضرة", "ش الميلية", "ش. عين كرشة", "إ. الفوبور", "ش. قايس", "ش عين فكرون",
                "ESFBEA", "ن. تازوقاغت", "ش عين ياقوت", "ESSA", "أ. عين مليلة",
            ]
            regex = re.compile(
                r"(\d{1,4})\s+([A-Za-z؀-ۿ\s\-\.'Ééèêà]+?)\s+("
                + "|".join(re.escape(c) for c in club_patterns)
                + r")\s+(\d{1,3})\s+(\d{1,2})"
            )
            for m_row in regex.finditer(full_sec_text):
                raw_pname = m_row.group(2).strip()
                raw_club = m_row.group(3).strip()
                val = int(m_row.group(4))
                shirt = int(m_row.group(5))
                cid = resolve_club_id_by_name(data, raw_club)
                if not cid or cid not in known_clubs:
                    continue

                if cid == cbm_id:
                    pid = match_cbm_player_id(data, raw_pname)
                    if not pid:
                        for p in data.get("players", []):
                            if p.get("shirt") == shirt:
                                pid = str(p["id"])
                                break
                    if pid:
                        st_entry = cbm_stats_from_site.setdefault(
                            pid, {"appearances": 0, "goals": 0, "yellowCards": 0, "redCards": 0}
                        )
                        st_entry[stat_key] = max(st_entry.get(stat_key, 0), val)

                if stat_key == "goals" and val > 0:
                    pid_match = match_cbm_player_id(data, raw_pname) if cid == cbm_id else None
                    if cid == cbm_id and not pid_match:
                        for p in data.get("players", []):
                            if p.get("shirt") == shirt:
                                pid_match = str(p["id"])
                                break
                    p_obj = next((p for p in data.get("players", []) if str(p.get("id")) == str(pid_match)), None) if pid_match else None
                    name_obj = (
                        copy.deepcopy(p_obj["name"])
                        if p_obj and isinstance(p_obj.get("name"), dict)
                        else {"ar": raw_pname, "latin": raw_pname.title(), "en": raw_pname.title()}
                    )
                    parsed_east_scorers.append(
                        {
                            "playerId": pid_match,
                            "clubId": cid,
                            "shirt": shirt,
                            "goals": val,
                            "matches": None,
                            "name": name_obj,
                        }
                    )

    if parsed_east_scorers:
        existing_scorers = data.get("topScorers") or []
        merged_by_key: dict[str, dict[str, Any]] = {}
        for item in existing_scorers:
            k = f"{item.get('clubId')}:{item.get('playerId') or item.get('shirt') or item.get('name', {}).get('ar')}"
            merged_by_key[k] = copy.deepcopy(item)
        for item in parsed_east_scorers:
            k = f"{item.get('clubId')}:{item.get('playerId') or item.get('shirt') or item.get('name', {}).get('ar')}"
            if k in merged_by_key:
                if item["goals"] > merged_by_key[k].get("goals", 0):
                    merged_by_key[k]["goals"] = item["goals"]
                if item.get("matches") and (
                    not merged_by_key[k].get("matches") or item["matches"] > merged_by_key[k]["matches"]
                ):
                    merged_by_key[k]["matches"] = item["matches"]
            else:
                merged_by_key[k] = item
        merged_list = sorted(
            merged_by_key.values(),
            key=lambda x: (-int(x.get("goals") or 0), int(x.get("matches") or 99), str(x.get("clubId"))),
        )
        for idx, item in enumerate(merged_list, start=1):
            item["rank"] = idx
        if data.get("topScorers") != merged_list:
            data["topScorers"] = merged_list
            notes.append(f"تحديث قائمة هدافي المجموعة ({len(merged_list)} هداف)")
            updated = True

    if soup or home_soup:
        for p in data.get("players", []):
            pid = str(p.get("id"))
            cur = p.get("stats") or {"appearances": 0, "goals": 0, "yellowCards": 0, "redCards": 0}
            site_s = cbm_stats_from_site.get(pid, {})
            new_stats = {
                "appearances": max(cur.get("appearances", 0), site_s.get("appearances", 0), event_apps.get(pid, 0)),
                "goals": max(cur.get("goals", 0), site_s.get("goals", 0), event_goals.get(pid, 0)),
                "yellowCards": max(cur.get("yellowCards", 0), site_s.get("yellowCards", 0), event_yc.get(pid, 0)),
                "redCards": max(cur.get("redCards", 0), site_s.get("redCards", 0), event_rc.get(pid, 0)),
            }
            if p.get("stats") != new_stats:
                p["stats"] = new_stats
                updated = True

    return updated


def enrich_metadata_and_players(data: dict[str, Any], reference_date: Optional[date] = None) -> bool:
    """
    Unify home stadium metadata, transliterate Arabic staff/player names to Latin,
    update `approxAge`, and link `playerId` in match events without mutating timestamps
    when nothing changed.
    """
    changed = False
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    today = reference_date or datetime.now(TZ).date()

    expected_stadium = {
        "name": "Stade Belkacem Belaid",
        "ar": "ملعب بلقاسم بلعيد",
        "source": HOME_STADIUM,
    }
    if data.get("club", {}).get("stadium") != expected_stadium:
        data.setdefault("club", {})["stadium"] = expected_stadium
        changed = True

    for s in data.get("staff", []):
        name_obj = s.get("name") or {}
        ar_n = name_obj.get("ar") or ""
        lat_n = name_obj.get("latin")
        if not lat_n or re.search(r"[\u0600-\u06FF]", str(lat_n)):
            new_lat = transliterate_ar_name(ar_n)
            if name_obj.get("latin") != new_lat or name_obj.get("en") != new_lat:
                s["name"] = {"ar": ar_n, "latin": new_lat, "en": new_lat}
                changed = True

    for p in data.get("players", []):
        name_obj = p.get("name") or {}
        ar_n = name_obj.get("ar") or ""
        if ar_n.upper() in ("BENSEGHIER HAMZA", "HAMZA BENSEGHIER"):
            ar_n = "بن صغير حمزة"
        lat_n = name_obj.get("latin")
        if not lat_n or re.search(r"[\u0600-\u06FF]", str(lat_n)) or name_obj.get("ar") != ar_n:
            new_lat = transliterate_ar_name(ar_n) or lat_n
            if (
                name_obj.get("latin") != new_lat
                or name_obj.get("en") != new_lat
                or name_obj.get("ar") != ar_n
            ):
                p["name"] = {"ar": ar_n, "latin": new_lat, "en": new_lat}
                changed = True

        if "photoUrl" not in p:
            p["photoUrl"] = None
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

    for m in data.get("matches", []):
        if str(m.get("home")) == cbm_id and not m.get("venue"):
            m["venue"] = HOME_STADIUM
            changed = True
        if "closedDoors" not in m:
            m["closedDoors"] = False
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


# ════════════════════════ 9. Sanity Checks, Schema Validation & Diffing ════════════════════════
def strip_volatile_timestamps(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of `data` with volatile timestamps normalized for deep-diff comparison."""
    clone = copy.deepcopy(data)
    clone.pop("lastUpdated", None)
    for p in clone.get("players", []):
        p.pop("lastFetchedAt", None)
    for m in clone.get("matches", []):
        m.pop("lastDetailCheck", None)
    return clone


def has_substantive_changes(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Return True only if normalized `after` differs substantively from `before`."""
    return strip_volatile_timestamps(before) != strip_volatile_timestamps(after)


def summarize_diff(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    """Produce a human-readable list of differences between two dataset states."""
    diffs: list[str] = []
    old_st = {str(s["clubId"]): s for s in before.get("standings", [])}
    for s in after.get("standings", []):
        cid = str(s["clubId"])
        prev = old_st.get(cid)
        if not prev:
            diffs.append(f"+ نادٍ جديد في الترتيب: {cid}")
            continue
        changes = []
        for k in ("position", "played", "wins", "draws", "losses", "goalsFor", "goalsAgainst", "goalDifference", "points", "adjustedPoints", "pointsPenalty"):
            if prev.get(k) != s.get(k):
                changes.append(f"{k}: {prev.get(k)} -> {s.get(k)}")
        if changes:
            diffs.append(f"الترتيب [{get_club_name(after, cid)} #{cid}]: " + ", ".join(changes))

    old_m = {str(m["id"]): m for m in before.get("matches", [])}
    for m in after.get("matches", []):
        mid = str(m["id"])
        prev = old_m.get(mid)
        if not prev:
            diffs.append(f"+ مباراة جديدة #{mid} (الجولة {m.get('round')})")
            continue
        m_changes = []
        for k in ("kickoff", "venue", "status", "score", "closedDoors"):
            if prev.get(k) != m.get(k):
                m_changes.append(f"{k}: {prev.get(k)} -> {m.get(k)}")
        if m_changes:
            diffs.append(f"المباراة #{mid} (الجولة {m.get('round')}): " + ", ".join(m_changes))

    if before.get("topScorers") != after.get("topScorers"):
        diffs.append(f"تحديث ترتيب الهدافين ({len(after.get('topScorers', []))} لاعب)")
    if before.get("roundResults") != after.get("roundResults"):
        diffs.append(f"تحديث نتائج جولة المجموعة ({len(after.get('roundResults', []))} مباراة)")

    return diffs


def validate_dataset(
    data: dict[str, Any],
    previous_data: Optional[dict[str, Any]] = None,
    schema_path: str = SCHEMA_PATH,
    accept_regression: bool = False,
) -> list[str]:
    """
    Run strict sanity checks and JSON Schema validation on `data`.
    When `accept_regression=True`, decreases in `played` are logged loudly rather than blocking.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["ملف البيانات ليس كائناً JSON صالحاً"]

    if data.get("schemaVersion") != 3:
        errors.append(f"schemaVersion غير متوقع: {data.get('schemaVersion')}")

    if jsonschema is not None and os.path.exists(schema_path):
        try:
            with open(schema_path, "r", encoding="utf-8") as sf:
                schema = json.load(sf)
            jsonschema.validate(instance=data, schema=schema)
        except Exception as exc:
            errors.append(f"فشل التحقق من مخطط JSON Schema: {exc}")

    standings = data.get("standings")
    if not isinstance(standings, list) or len(standings) != EXPECTED_CLUB_COUNT:
        errors.append(
            f"عدد أندية جدول الترتيب غير صالح: {len(standings) if isinstance(standings, list) else 0} (المتوقع {EXPECTED_CLUB_COUNT})"
        )
        return errors

    prev_played_map: dict[str, int] = {}
    prev_club_set: set[str] = set()
    if previous_data and isinstance(previous_data.get("standings"), list):
        for ps in previous_data["standings"]:
            if ps.get("clubId") is not None:
                prev_club_set.add(str(ps["clubId"]))
                if isinstance(ps.get("played"), int):
                    prev_played_map[str(ps["clubId"])] = ps["played"]

    seen_positions: set[int] = set()
    seen_clubs: set[str] = set()
    for row in standings:
        cid = str(row.get("clubId", ""))
        pos = row.get("position")
        played = row.get("played")
        w = row.get("wins")
        d = row.get("draws")
        l_cnt = row.get("losses")
        gf = row.get("goalsFor")
        ga = row.get("goalsAgainst")
        gd = row.get("goalDifference")
        pts = row.get("points")
        adj = row.get("adjustedPoints")

        if cid in seen_clubs:
            errors.append(f"تكرار النادي {cid} في جدول الترتيب")
        seen_clubs.add(cid)

        if not isinstance(pos, int) or not (1 <= pos <= EXPECTED_CLUB_COUNT):
            errors.append(f"المركز غير صالح للنادي {cid}: {pos}")
        else:
            seen_positions.add(pos)

        if not all(isinstance(v, int) for v in (played, w, d, l_cnt, gf, ga, gd, pts, adj)):
            errors.append(f"قيم غير رقمية في صف النادي {cid}")
            continue

        if w + d + l_cnt != played:
            errors.append(f"مجموع (ف+ت+خ) لا يساوي لعب للنادي {cid}: {w}+{d}+{l_cnt} != {played}")
        if gf - ga != gd:
            errors.append(f"فارق الأهداف غير متطابق للنادي {cid}: {gf}-{ga} != {gd}")
        if pts != 3 * w + d:
            errors.append(f"النقاط الخام لا تساوي 3*ف+ت للنادي {cid}: {pts} != {3 * w + d}")
        if cid in prev_played_map and played < prev_played_map[cid]:
            if accept_regression:
                log.warning(
                    "validate_dataset (--accept-regression): قبول تراجع عدد المباريات الملعوبة للنادي %s: %s < %s",
                    cid,
                    played,
                    prev_played_map[cid],
                )
            else:
                errors.append(f"تراجع عدد المباريات الملعوبة للنادي {cid}: {played} < {prev_played_map[cid]}")

    if prev_club_set and seen_clubs != prev_club_set:
        errors.append(
            f"مجموعة أندية الترتيب تغيّرت بشكل غير مسموح: {sorted(seen_clubs ^ prev_club_set)}"
        )

    if len(seen_positions) != EXPECTED_CLUB_COUNT:
        errors.append(f"مراكز الترتيب غير مكتملة من 1 إلى {EXPECTED_CLUB_COUNT}")

    return errors


# ════════════════════════ 10. File Persistence, Health & Dedupe State ════════════════════════
def load_data(path: str = DATA_PATH) -> Optional[dict[str, Any]]:
    """Load `data/data.json`."""
    if not os.path.exists(path):
        log.error("ملف البيانات %s غير موجود!", path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("تعذر قراءة ملف البيانات %s: %s", path, type(e).__name__)
        return None


def save_data(data: dict[str, Any], path: str = DATA_PATH, dry_run: bool = False) -> None:
    """Atomically write `data` to `data/data.json` via a temporary file and `os.replace`."""
    data["lastUpdated"] = datetime.now(TZ).isoformat(timespec="seconds")
    if dry_run:
        log.info("[Dry-Run] تم تخطي حفظ التغييرات في %s", path)
        return

    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)
    log.info("تم حفظ التحديثات ذرياً في %s", path)


def persist_status_file(
    status_obj: dict[str, Any],
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> None:
    """Atomically write `status_obj` to `data/status.json`."""
    if dry_run:
        return
    try:
        os.makedirs(os.path.dirname(status_path) or ".", exist_ok=True)
        tmp = f"{status_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(status_obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, status_path)
    except OSError:
        pass


def update_health_status(
    state: str,
    problems: list[str],
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Maintain scraper operational status and notification dedupe state in `data/status.json`,
    writing to disk when the health state (`ok` / `degraded` / `error`) or failure counter changes.
    """
    existing: dict[str, Any] = {
        "state": "ok",
        "consecutiveFailures": 0,
        "lastStateChange": None,
        "lastError": None,
        "alertedHashes": [],
        "sentEvents": [],
        "notificationEvents": {},
    }
    if os.path.exists(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing.update(loaded)
        except Exception:
            pass

    existing.setdefault("alertedHashes", [])
    existing.setdefault("sentEvents", [])
    existing.setdefault("notificationEvents", {})

    prev_state = existing.get("state", "ok")
    prev_fails = int(existing.get("consecutiveFailures") or 0)
    new_fails = 0 if state == "ok" else (prev_fails + 1)
    last_err = "; ".join(problems[:3]) if problems else None

    changed = (
        (not os.path.exists(status_path))
        or (state != prev_state)
        or (new_fails != prev_fails)
        or (last_err != existing.get("lastError"))
    )
    if changed:
        existing["state"] = state
        existing["consecutiveFailures"] = new_fails
        existing["lastError"] = last_err
        if state != prev_state or not existing.get("lastStateChange"):
            existing["lastStateChange"] = datetime.now(TZ).isoformat(timespec="seconds")
        persist_status_file(existing, status_path=status_path, dry_run=dry_run)
    return existing


def build_event_key(ev: dict[str, Any]) -> str:
    """
    Item 8: Compute a deterministic event key (`matchId:kind:score_or_kickoff`)
    used to deduplicate both Telegram and Web Push notifications across runs.
    """
    mid = str(ev.get("matchId") or "unknown")
    kind = str(ev.get("kind") or "event")
    if kind == "result" and ev.get("score"):
        sc = ev["score"]
        return f"{mid}:result:{sc[0]}-{sc[1]}"
    if kind == "kickoff" and ev.get("kickoff"):
        return f"{mid}:kickoff:{ev['kickoff']}"
    return f"{mid}:{kind}:{ev.get('tag') or ''}"


def mark_event_channel_state(
    status_obj: dict[str, Any],
    event_key: str,
    channel: str,
    channel_state: str,
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> None:
    """
    Item 8: Persist notification event state (`pending` BEFORE sending, `sent` AFTER success)
    to `data/status.json` immediately on disk.
    """
    notif_map: dict[str, dict[str, Any]] = status_obj.setdefault("notificationEvents", {})
    entry = notif_map.setdefault(event_key, {})
    entry[channel] = channel_state
    entry["updatedAt"] = datetime.now(TZ).isoformat(timespec="seconds")
    if channel_state == "sent":
        sent_list: list[str] = status_obj.setdefault("sentEvents", [])
        if event_key not in sent_list:
            sent_list.append(event_key)
            status_obj["sentEvents"] = sent_list[-200:]
    persist_status_file(status_obj, status_path=status_path, dry_run=dry_run)


def is_event_channel_sent(status_obj: Optional[dict[str, Any]], event_key: str, channel: str) -> bool:
    """Return True if `event_key` has already been marked `'sent'` for `channel`."""
    if not status_obj:
        return False
    notif_map = status_obj.get("notificationEvents") or {}
    if isinstance(notif_map.get(event_key), dict) and notif_map[event_key].get(channel) == "sent":
        return True
    return False


# ════════════════════════ 11. Telegram & Parallel Web Push Notifications ════════════════════════
def registry_url() -> Optional[str]:
    """Read Google Apps Script web app URL from `REGISTRY_URL` env or `config.js`."""
    url = os.getenv("REGISTRY_URL")
    if url:
        return url.strip()
    try:
        with open("config.js", encoding="utf-8") as f:
            m = re.search(r"https://script\.google\.com/[^'\"\s]+/exec", f.read())
            return m.group(0) if m else None
    except OSError:
        return None


def send_telegram_alert(
    message: str,
    dry_run: bool = False,
    status_obj: Optional[dict[str, Any]] = None,
    event_key: Optional[str] = None,
    status_path: str = STATUS_PATH,
) -> bool:
    """
    Send a deduplicated, HTML-formatted Telegram notification.
    Persists `pending` state before sending and marks `sent` only after HTTP 200.
    """
    msg_hash = event_key or hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    if status_obj is not None:
        if is_event_channel_sent(status_obj, msg_hash, "telegram"):
            log.info("تم تخطي إشعار تليغرام مرسل مسبقاً (%s)", msg_hash)
            return True
        alerted = status_obj.setdefault("alertedHashes", [])
        if msg_hash in alerted:
            log.info("تم تخطي إشعار تليغرام مكرر (%s)", msg_hash)
            return True
        # Item 8: Persist pending state BEFORE sending
        mark_event_channel_state(status_obj, msg_hash, "telegram", "pending", status_path=status_path, dry_run=dry_run)

    if dry_run:
        log.info("[Dry-Run] رسالة تليغرام:\n%s", message)
        return True
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.debug("مفاتيح تليغرام غير مضبوطة؛ تم تخطي إرسال الإشعار.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [
        message[i : i + TELEGRAM_MAX_LEN]
        for i in range(0, max(len(message), 1), TELEGRAM_MAX_LEN)
    ]
    all_ok = True
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            time.sleep(0.5)
        try:
            r = FETCHER.session.post(
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

    if all_ok and status_obj is not None:
        alerted = status_obj.setdefault("alertedHashes", [])
        if msg_hash not in alerted:
            alerted.append(msg_hash)
            status_obj["alertedHashes"] = alerted[-100:]
        # Item 8: Persist sent state ONLY after delivery succeeded
        mark_event_channel_state(status_obj, msg_hash, "telegram", "sent", status_path=status_path, dry_run=dry_run)
    return all_ok


def result_alert(data: dict[str, Any], m: dict[str, Any], score: tuple[int, int]) -> str:
    """Format an HTML-escaped Telegram alert for a CBM Mila final match score."""
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    at_home = str(m.get("home")) == cbm_id
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


def kickoff_alert(data: dict[str, Any], m: dict[str, Any], ko: datetime) -> str:
    """Format an HTML-escaped Telegram alert for a CBM Mila kickoff/venue update."""
    home_name = html.escape(get_club_name(data, m.get("home")))
    away_name = html.escape(get_club_name(data, m.get("away")))
    venue = html.escape(str(m.get("venue") or "يحدد لاحقاً"))
    closed = " · 🚫 بدون جمهور" if m.get("closedDoors") else ""
    return (
        f"📅 <b>تحديد موعد مباراة شباب ميلة — الجولة {html.escape(str(m.get('round', '؟')))}</b>\n"
        f"⚽ {home_name} ضد {away_name}\n"
        f"🕒 {ko:%Y-%m-%d %H:%M} (توقيت الجزائر)\n"
        f"📍 {venue}{closed}"
    )


def build_kickoff_push(data: dict[str, Any], m: dict[str, Any], ko: datetime) -> dict[str, Any]:
    """Build a trilingual Web Push payload for a CBM Mila kickoff update."""
    rnd = m.get("round", "؟")
    h_ar = get_club_name(data, m.get("home"))
    a_ar = get_club_name(data, m.get("away"))
    dt_str = f"{ko:%Y-%m-%d %H:%M}"
    ev: dict[str, Any] = {
        "kind": "kickoff",
        "matchId": str(m.get("id")),
        "kickoff": ko.isoformat(),
        "tag": f"cbm-ko-{m.get('id')}",
        "url": "./#/home",
        "ar": {"title": f"📅 موعد مباراة شباب ميلة — الجولة {rnd}", "body": f"{h_ar} ضد {a_ar} · الموعد: {dt_str}"},
        "fr": {"title": f"📅 Horaire du Match — Journée {rnd}", "body": f"CBM Mila · Coup d'envoi : {dt_str}"},
        "en": {"title": f"📅 Match Schedule — Round {rnd}", "body": f"CBM Mila · Kickoff: {dt_str}"},
    }
    ev["eventKey"] = build_event_key(ev)
    return ev


def build_result_push(data: dict[str, Any], m: dict[str, Any], score: tuple[int, int]) -> dict[str, Any]:
    """Build a trilingual Web Push payload for a CBM Mila final result."""
    cbm_id = str(data.get("club", {}).get("id") or DEFAULT_CLUB_ID)
    rnd = m.get("round", "؟")
    at_home = str(m.get("home")) == cbm_id
    mine, theirs = (score[0], score[1]) if at_home else (score[1], score[0])
    h_ar = get_club_name(data, m.get("home"))
    a_ar = get_club_name(data, m.get("away"))
    v_ar = "🟢 فوز" if mine > theirs else "🟡 تعادل" if mine == theirs else "🔴 خسارة"
    v_fr = "🟢 Victoire" if mine > theirs else "🟡 Match Nul" if mine == theirs else "🔴 Défaite"
    v_en = "🟢 Victory" if mine > theirs else "🟡 Draw" if mine == theirs else "🔴 Defeat"
    ev: dict[str, Any] = {
        "kind": "result",
        "matchId": str(m.get("id")),
        "score": score,
        "tag": f"cbm-res-{m.get('id')}",
        "url": "./#/matches",
        "ar": {"title": f"⚽ نهاية المباراة — الجولة {rnd}", "body": f"{h_ar} {score[0]} - {score[1]} {a_ar} ({v_ar})"},
        "fr": {"title": f"⚽ Fin du Match — Journée {rnd}", "body": f"Score final : {score[0]} - {score[1]} ({v_fr})"},
        "en": {"title": f"⚽ Full Time — Round {rnd}", "body": f"Final Score: {score[0]} - {score[1]} ({v_en})"},
    }
    ev["eventKey"] = build_event_key(ev)
    return ev


def registry_call(url: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Send a POST request to the Google Apps Script registry with `ADMIN_KEY` in the JSON body."""
    try:
        r = FETCHER.session.post(
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


def report_new_supporters(problems: list[str], notes: list[str], dry_run: bool = False) -> None:
    """Fetch newly issued supporter cards from `Code.gs` (`list`) and acknowledge (`ack`) after Telegram alert."""
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
        problems.append(f"سجل المناصرين: رفض الطلب [{code}]")
        return

    raw_items = res.get("items", [])
    items = [
        x
        for x in raw_items
        if isinstance(x, dict) and str(x.get("row", x.get("no", ""))).strip().isdigit()
    ]
    notes.append(f"مناصرون جدد: {len(items)} (الإجمالي {res.get('total', '؟')})")
    if not items:
        return

    all_sent = True
    for i in range(0, len(items), MAX_NAMES_PER_MESSAGE):
        part = items[i : i + MAX_NAMES_PER_MESSAGE]
        lines = [f"👥 <b>مناصرون استخرجوا بطاقاتهم</b> ({i + 1}–{i + len(part)} من {len(items)})"]
        for x in part:
            sid = x.get("supporterId") or f"CBM-{int(x.get('no', 0)):06d}"
            lines.append(
                f"• {html.escape(str(x.get('name', 'بدون اسم')).strip())} — <code>{html.escape(str(sid))}</code>"
            )
        all_sent &= send_telegram_alert("\n".join(lines), dry_run=dry_run)

    if all_sent and not dry_run:
        max_cursor = max(int(x.get("row", x.get("no", 0))) for x in items)
        ack_res = registry_call(url, {"v": 2, "a": "ack", "key": ADMIN_KEY, "upTo": max_cursor})
        if not ack_res or not ack_res.get("ok"):
            problems.append("سجل المناصرين: أُرسلت الأسماء لكن تعذر تأكيد الاستلام (ack)")


def send_web_push_notifications(
    push_events: list[dict[str, Any]],
    problems: list[str],
    notes: list[str],
    dry_run: bool = False,
    status_obj: Optional[dict[str, Any]] = None,
    status_path: str = STATUS_PATH,
    max_workers: int = WEB_PUSH_MAX_WORKERS,
    time_budget_sec: float = WEB_PUSH_TIME_BUDGET_SEC,
    webpush_fn: Optional[Callable[..., Any]] = None,
) -> None:
    """
    Item 8 & Item 9:
    Send Web Push notifications in parallel using a bounded `ThreadPoolExecutor(max_workers=10)`,
    per-request timeout of 10s, and an overall time budget (240s).
    Persists dedupe state (`pending` before sending, `sent` after success) in `data/status.json`,
    collects 404/410 endpoints and prunes once at the end, and logs counts only (never endpoints).
    """
    if not push_events:
        return

    # Filter out events already sent via webpush
    pending_events = [
        ev
        for ev in push_events
        if not is_event_channel_sent(status_obj, ev.get("eventKey") or build_event_key(ev), "webpush")
    ]
    if not pending_events:
        log.info("تم تخطي إشعارات Web Push لأن جميع الأحداث أُرسلت مسبقاً.")
        return

    url = registry_url()
    if not VAPID_PRIVATE_KEY or not ADMIN_KEY or not url:
        notes.append("إشعارات الهواتف (Web Push): غير مفعّلة (VAPID_PRIVATE_KEY أو ADMIN_KEY غير مضبوط)")
        return
    if dry_run:
        log.info("[Dry-Run] سيتم إرسال %d إشعار Web Push للأنصار", len(pending_events))
        return

    if webpush_fn is None:
        try:
            from pywebpush import webpush as _default_webpush
            webpush_fn = _default_webpush
        except ImportError:
            problems.append("إشعارات الهواتف: مكتبة pywebpush غير مثبّتة")
            return

    res = registry_call(url, {"v": 2, "a": "push_list", "key": ADMIN_KEY})
    if not res or not res.get("ok"):
        problems.append("إشعارات الهواتف: تعذر جلب قائمة المشتركين من السجل")
        return

    subs = [
        sub
        for sub in (res.get("items") or [])
        if isinstance(sub, dict)
        and sub.get("endpoint")
        and isinstance(sub.get("keys"), dict)
        and sub["keys"].get("p256dh")
        and sub["keys"].get("auth")
    ]
    if not subs:
        notes.append("إشعارات الهواتف: لا يوجد مشتركون نشطون حالياً")
        return

    dead_endpoints: set[str] = set()
    total_sent = 0
    total_failed = 0
    total_timed_out = 0
    start_monotonic = time.monotonic()

    def _send_one(sub_item: dict[str, Any], payload_str: str) -> tuple[str, Optional[str]]:
        ep = str(sub_item["endpoint"])
        keys = sub_item["keys"]
        try:
            webpush_fn(
                subscription_info={"endpoint": ep, "keys": keys},
                data=payload_str,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=dict(VAPID_CLAIMS),
                timeout=WEB_PUSH_TIMEOUT_SEC,
            )
            return ("sent", None)
        except Exception as ex:
            status_code = getattr(getattr(ex, "response", None), "status_code", None)
            if status_code in (404, 410):
                return ("dead", ep)
            return ("failed", None)

    for ev in pending_events:
        ev_key = ev.get("eventKey") or build_event_key(ev)
        elapsed = time.monotonic() - start_monotonic
        remaining_budget = time_budget_sec - elapsed
        if remaining_budget <= 0:
            log.warning("انتهت المهلة الزمنية الإجمالية لإشعارات Web Push (%.1fs)", time_budget_sec)
            break

        # Item 8: Persist pending state BEFORE sending
        if status_obj is not None:
            mark_event_channel_state(
                status_obj, ev_key, "webpush", "pending", status_path=status_path, dry_run=dry_run
            )

        ev_sent = 0
        ev_failed = 0
        ev_timed_out = 0

        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(subs)))) as pool:
            futures = []
            for sub in subs:
                lang = sub.get("lang") if sub.get("lang") in ("ar", "fr", "en") else "ar"
                msg = ev.get(lang) or ev["ar"]
                payload = json.dumps(
                    {
                        "title": msg["title"],
                        "body": msg["body"],
                        "icon": "./icon-192.png",
                        "badge": "./icon-192.png",
                        "tag": ev.get("tag", "cbm-match"),
                        "url": ev.get("url", "./#/home"),
                    },
                    ensure_ascii=False,
                )
                futures.append(pool.submit(_send_one, sub, payload))

            try:
                for fut in as_completed(futures, timeout=max(0.1, remaining_budget)):
                    outcome, dead_ep = fut.result()
                    if outcome == "sent":
                        ev_sent += 1
                    elif outcome == "dead" and dead_ep:
                        dead_endpoints.add(dead_ep)
                        ev_failed += 1
                    else:
                        ev_failed += 1
            except TimeoutError:
                for fut in futures:
                    if not fut.done():
                        fut.cancel()
                        ev_timed_out += 1

        total_sent += ev_sent
        total_failed += ev_failed
        total_timed_out += ev_timed_out

        # Item 8: Mark event as 'sent' after delivery completes
        if status_obj is not None and (ev_sent > 0 or len(dead_endpoints) == len(subs)):
            mark_event_channel_state(
                status_obj, ev_key, "webpush", "sent", status_path=status_path, dry_run=dry_run
            )

    log.info(
        "Web Push summary: subscribers=%d, sent=%d, failed=%d, pruned=%d, timed_out=%d",
        len(subs),
        total_sent,
        total_failed,
        len(dead_endpoints),
        total_timed_out,
    )
    notes.append(
        f"إشعارات الهواتف الفورية: أُرسلت {total_sent} رسالة لـ {len(subs)} مشترك "
        f"(محذوف={len(dead_endpoints)}, مهلة={total_timed_out})"
    )

    # Item 9: Prune dead 404/410 endpoints once at the end
    if dead_endpoints:
        registry_call(
            url,
            {"v": 2, "a": "push_prune", "key": ADMIN_KEY, "endpoints": sorted(dead_endpoints)},
        )


# ════════════════════════ 12. CLI Entrypoint ════════════════════════
# ════════════════════════ 11b. Notification Queue (exactly-once-ish delivery) ════════════════════════
# Problem solved: notifications used to be sent BEFORE the data commit reached GitHub. If the commit/push
# failed, the next run re-detected the same change and sent every notification again.
# Now (with --defer-notifications) the scrape step only QUEUES events inside data/status.json, which is
# committed together with data/data.json. A separate step (--notify-queued) delivers them AFTER the push
# succeeded; per-channel "sent" markers make delivery idempotent, and the queue is cleared afterwards.
NOTIFY_MAX_ATTEMPTS = 3


def _json_safe(obj: Any) -> Any:
    """Round-trip through JSON so tuples/datetimes become plain JSON values."""
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def _telegram_configured() -> bool:
    return bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)


def _webpush_configured() -> bool:
    return bool(VAPID_PRIVATE_KEY and ADMIN_KEY and registry_url())


def _message_key(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]


def dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return events de-duplicated by their stable eventKey (last one wins)."""
    unique: dict[str, dict[str, Any]] = {}
    for ev in events:
        key = ev.get("eventKey") or build_event_key(ev)
        ev["eventKey"] = key
        unique[key] = ev
    return list(unique.values())


def queue_notifications(
    status_obj: dict[str, Any],
    events: list[dict[str, Any]],
    extra_messages: list[dict[str, str]],
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> int:
    """Store events in `status.json` (committed with the data) instead of sending them now."""
    queue = status_obj.setdefault("queuedNotifications", {"events": [], "telegram": []})
    queue.setdefault("events", [])
    queue.setdefault("telegram", [])
    queued_keys = {e.get("eventKey") for e in queue["events"]}
    queued_msgs = {_message_key(m.get("message", "")) for m in queue["telegram"]}
    added = 0
    for ev in events:
        key = ev.get("eventKey") or build_event_key(ev)
        ev["eventKey"] = key
        if key not in queued_keys:
            queue["events"].append(_json_safe(ev))
            queued_keys.add(key)
            added += 1
    for m in extra_messages:
        mk = _message_key(m.get("message", ""))
        if mk not in queued_msgs:
            queue["telegram"].append({"message": m["message"]})
            queued_msgs.add(mk)
            added += 1
    if added:
        log.info("تمت إضافة %d إشعار إلى طابور الإرسال (يُرسل بعد نجاح رفع البيانات)", added)
        persist_status_file(status_obj, status_path=status_path, dry_run=dry_run)
    return added


def deliver_notifications(
    data: dict[str, Any],
    events: list[dict[str, Any]],
    extra_messages: list[dict[str, str]],
    problems: list[str],
    notes: list[str],
    status_obj: dict[str, Any],
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> None:
    """Send Telegram + Web Push for `events` (idempotent thanks to per-channel sent markers)."""
    for m in extra_messages:
        send_telegram_alert(m["message"], dry_run=dry_run, status_obj=status_obj, status_path=status_path)

    for ev in events:
        ek = ev.get("eventKey") or build_event_key(ev)
        match_obj = next(
            (m for m in data.get("matches", []) if str(m.get("id")) == str(ev.get("matchId"))),
            None,
        )
        if not match_obj:
            continue
        if ev.get("kind") == "result" and ev.get("score"):
            send_telegram_alert(
                result_alert(data, match_obj, tuple(ev["score"])),
                dry_run=dry_run,
                status_obj=status_obj,
                event_key=ek,
                status_path=status_path,
            )
        elif ev.get("kind") == "kickoff" and ev.get("kickoff"):
            ko_dt = parse_iso_kickoff(ev["kickoff"])
            if ko_dt:
                send_telegram_alert(
                    kickoff_alert(data, match_obj, ko_dt),
                    dry_run=dry_run,
                    status_obj=status_obj,
                    event_key=ek,
                    status_path=status_path,
                )

    if events:
        try:
            send_web_push_notifications(
                events,
                problems,
                notes,
                dry_run=dry_run,
                status_obj=status_obj,
                status_path=status_path,
            )
        except Exception as e:
            log.error("خطأ في إرسال إشعارات الهواتف: %s", type(e).__name__)


def flush_queued_notifications(
    data_path: str = DATA_PATH,
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
) -> int:
    """Deliver queued notifications (run AFTER the data commit was pushed). Returns 0 on success."""
    if not os.path.exists(status_path):
        log.info("لا يوجد ملف حالة؛ لا إشعارات في الطابور.")
        return 0
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            status_obj = json.load(f)
    except Exception:
        log.error("تعذّرت قراءة %s", status_path)
        return 1
    if not isinstance(status_obj, dict):
        return 1

    queue = status_obj.get("queuedNotifications") or {}
    events = list(queue.get("events") or [])
    extras = list(queue.get("telegram") or [])
    if not events and not extras:
        log.info("طابور الإشعارات فارغ.")
        return 0

    data = load_data(data_path)
    if not data:
        log.error("تعذّر تحميل %s لإرسال الإشعارات", data_path)
        return 1

    problems: list[str] = []
    notes: list[str] = []
    status_obj.setdefault("alertedHashes", [])
    status_obj.setdefault("sentEvents", [])
    status_obj.setdefault("notificationEvents", {})

    deliver_notifications(data, events, extras, problems, notes, status_obj, status_path, dry_run)

    tg_on, push_on = _telegram_configured(), _webpush_configured()
    keep_events: list[dict[str, Any]] = []
    for ev in events:
        key = ev.get("eventKey") or build_event_key(ev)
        done = (not tg_on or is_event_channel_sent(status_obj, key, "telegram")) and (
            not push_on or is_event_channel_sent(status_obj, key, "webpush")
        )
        ev["_attempts"] = int(ev.get("_attempts") or 0) + 1
        if not done and ev["_attempts"] < NOTIFY_MAX_ATTEMPTS:
            keep_events.append(ev)
    keep_msgs: list[dict[str, str]] = []
    for m in extras:
        key = _message_key(m.get("message", ""))
        done = (not tg_on) or is_event_channel_sent(status_obj, key, "telegram")
        m["_attempts"] = int(m.get("_attempts") or 0) + 1
        if not done and m["_attempts"] < NOTIFY_MAX_ATTEMPTS:
            keep_msgs.append(m)

    status_obj["queuedNotifications"] = {"events": keep_events, "telegram": keep_msgs}
    persist_status_file(status_obj, status_path=status_path, dry_run=dry_run)
    for n in notes:
        log.info(n)
    log.info("اكتمل إرسال الطابور؛ المتبقي للمحاولة لاحقاً: %d", len(keep_events) + len(keep_msgs))
    return 0


def run_scraper(
    data_path: str = DATA_PATH,
    schema_path: str = SCHEMA_PATH,
    status_path: str = STATUS_PATH,
    dry_run: bool = False,
    verbose: bool = False,
    accept_regression: bool = False,
    fetch_fn: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None,
    defer_notifications: bool = False,
) -> int:
    """Execute one full scrape-validate-write cycle. Returns 0 on success, non-zero on failure."""
    if verbose:
        log.setLevel(logging.DEBUG)

    log.info(
        "بدء فحص وتحديث بيانات شباب ميلة (dry_run=%s, verbose=%s, accept_regression=%s)",
        dry_run,
        verbose,
        accept_regression,
    )
    original_data = load_data(data_path)
    if not original_data:
        status_obj = update_health_status("error", ["ملف data/data.json مفقود أو تالف"], status_path, dry_run)
        if status_obj.get("consecutiveFailures", 0) >= CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
            send_telegram_alert(
                "❌ <b>المراقب:</b> ملف data/data.json غير موجود أو تالف!",
                dry_run=dry_run,
                status_obj=status_obj,
                status_path=status_path,
            )
        return 1

    working_data = copy.deepcopy(original_data)
    problems: list[str] = []
    notes: list[str] = []
    push_events: list[dict[str, Any]] = []

    enrich_metadata_and_players(working_data)
    update_squad_and_staff(working_data, problems, notes, fetch_fn=fetch_fn)
    s_updated, ranking_hints = update_standings(
        working_data,
        problems,
        fetch_fn=fetch_fn,
        accept_regression=accept_regression,
    )
    m_updated, home_soup = update_matches(
        working_data,
        problems,
        notes,
        push_events,
        ranking_hints=ranking_hints,
        fetch_fn=fetch_fn,
    )
    update_statistics(working_data, problems, notes, fetch_fn=fetch_fn, home_soup=home_soup)
    enrich_metadata_and_players(working_data)
    notes.append("الترتيب: " + ("تم تحديثه" if s_updated else "بلا تغيير"))

    # Detect if any club's `played` decreased so we can alert loudly when `--accept-regression` is active
    regression_clubs: list[str] = []
    prev_played_map = {
        str(ps.get("clubId")): ps.get("played")
        for ps in original_data.get("standings", [])
        if ps.get("clubId") is not None and isinstance(ps.get("played"), int)
    }
    for row in working_data.get("standings", []):
        cid = str(row.get("clubId"))
        if cid in prev_played_map and isinstance(row.get("played"), int) and row["played"] < prev_played_map[cid]:
            regression_clubs.append(f"{get_club_name(working_data, cid)} (#{cid}: {prev_played_map[cid]} → {row['played']})")

    validation_errors = validate_dataset(
        working_data,
        previous_data=original_data,
        schema_path=schema_path,
        accept_regression=accept_regression,
    )
    if validation_errors:
        problems.extend(validation_errors)
        log.error("فشل التحقق من سلامة البيانات؛ لن يتم استبدال %s: %s", data_path, validation_errors)
        status_obj = update_health_status("error", problems, status_path, dry_run)
        if status_obj.get("consecutiveFailures", 0) >= CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
            alert_lines = [
                "⚠️ <b>تنبيه فشل مراقب CBM Mila</b>",
                f"فشل الفحص لـ {status_obj['consecutiveFailures']} مرات متتالية:",
            ] + ["• " + html.escape(p) for p in problems[:5]]
            send_telegram_alert(
                "\n".join(alert_lines),
                dry_run=dry_run,
                status_obj=status_obj,
                status_path=status_path,
            )
        return 1

    # If `/ar/ranking` failed completely or mismatched competition/clubs, treat as an error and exit non-zero
    if any(
        "عدد الصفوف المقروءة" in p
        or "لم يتم العثور على جدول الترتيب" in p
        or "مجموعة الأندية المستخرجة لا تطابق" in p
        or "المجموعة المحددة" in p
        or "الموسم المحدد" in p
        or "المجموعة النشطة" in p
        or "الموسم النشط" in p
        for p in problems
    ):
        log.error("فشل قراءة جدول الترتيب أو عدم تطابق المجموعة؛ الخروج بكود غير صفري دون الكتابة.")
        status_obj = update_health_status("error", problems, status_path, dry_run)
        if status_obj.get("consecutiveFailures", 0) >= CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
            alert_lines = [
                "⚠️ <b>تنبيه فشل مراقب CBM Mila</b>",
                f"فشل الفحص لـ {status_obj['consecutiveFailures']} مرات متتالية:",
            ] + ["• " + html.escape(p) for p in problems[:5]]
            send_telegram_alert(
                "\n".join(alert_lines),
                dry_run=dry_run,
                status_obj=status_obj,
                status_path=status_path,
            )
        return 1

    changed = has_substantive_changes(original_data, working_data)
    diffs = summarize_diff(original_data, working_data) if changed else []

    if diffs:
        log.info("التغييرات المكتشفة (%d):\n  - %s", len(diffs), "\n  - ".join(diffs))
    else:
        log.info("لا توجد تغييرات جوهرية في البيانات.")

    if changed:
        save_data(working_data, path=data_path, dry_run=dry_run)

    FETCHER.save_cache(dry_run=dry_run)
    health_state = "degraded" if problems else "ok"
    status_obj = update_health_status(health_state, problems, status_path, dry_run)

    # Item 6: loud Telegram alert if `--accept-regression` accepted a decrease in `played`
    extra_messages: list[dict[str, str]] = []
    if accept_regression and regression_clubs:
        extra_messages.append(
            {
                "message": (
                    "⚠️ <b>تنبيه تصحيح رسمي (--accept-regression)</b>\n"
                    "تم قبول تراجع في عدد المباريات الملعوبة بقرار يدوي:\n"
                    + "\n".join("• " + html.escape(c) for c in regression_clubs)
                )
            }
        )

    unique_events = dedupe_events(push_events)

    if defer_notifications:
        # Queue inside status.json: it is committed together with data.json and delivered afterwards
        queue_notifications(status_obj, unique_events, extra_messages, status_path=status_path, dry_run=dry_run)
    else:
        deliver_notifications(
            working_data, unique_events, extra_messages, problems, notes,
            status_obj=status_obj, status_path=status_path, dry_run=dry_run,
        )

    try:
        report_new_supporters(problems, notes, dry_run=dry_run)
    except Exception as e:
        log.error("خطأ غير متوقع في report_new_supporters: %s", type(e).__name__)

    return 0


def main() -> None:
    """CLI entrypoint for `scraper.py`."""
    parser = argparse.ArgumentParser(description="مراقب بيانات شباب ميلة (CBM Mila 1936)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="تشغيل تجريبي مع طباعة الفروقات دون حفظ ملفات أو إرسال إشعارات",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="تفعيل السجلات التفصيلية (DEBUG)",
    )
    parser.add_argument(
        "--accept-regression",
        action="store_true",
        help="السماح لمرة واحدة بتراجع عدد المباريات الملعوبة (played) عند تصحيح رسمي من الرابطة",
    )
    parser.add_argument(
        "--defer-notifications",
        action="store_true",
        help="وضع الطابور: لا يُرسل أي إشعار الآن، بل يُخزَّن في data/status.json ليُرسل بعد نجاح رفع البيانات",
    )
    parser.add_argument(
        "--notify-queued",
        action="store_true",
        help="إرسال الإشعارات المخزّنة في الطابور فقط (يُشغَّل بعد نجاح الـ push) ثم الخروج",
    )
    parser.add_argument(
        "--fixture-dir",
        type=str,
        default=None,
        help="مسار ملفات HTML المحلية للاختبار (اختياري)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    verbose = args.verbose or os.getenv("VERBOSE", "").lower() in ("1", "true", "yes")
    accept_regression = args.accept_regression or os.getenv("ACCEPT_REGRESSION", "").lower() in ("1", "true", "yes")

    fixture_fetcher: Optional[Callable[[str, list[str]], Optional[BeautifulSoup]]] = None
    if args.fixture_dir:
        fdir = args.fixture_dir

        def _local_fetch(url: str, problems: list[str]) -> Optional[BeautifulSoup]:
            fname = "ranking.html"
            if "/calendar" in url or url.rstrip("/") == "https://www.lirf.dz":
                fname = "calendar.html"
            elif "/statistics" in url:
                fname = "statistics.html"
            elif "/club/733" in url:
                fname = "club_733.html"
            elif "/match/226410" in url:
                fname = "match_226410_finished.html"
            elif "/match/226424" in url:
                fname = "match_226424_mismatched.html"
            elif "/player/" in url:
                fname = "player_43091.html"
            fpath = os.path.join(fdir, fname)
            if not os.path.exists(fpath):
                return None
            with open(fpath, "r", encoding="utf-8") as f:
                return BeautifulSoup(f.read(), "html.parser")

        fixture_fetcher = _local_fetch

    if args.notify_queued:
        if verbose:
            log.setLevel(logging.DEBUG)
        sys.exit(flush_queued_notifications(dry_run=dry_run))

    defer = args.defer_notifications or os.getenv("DEFER_NOTIFICATIONS", "").lower() in ("1", "true", "yes")
    rc = run_scraper(
        dry_run=dry_run,
        verbose=verbose,
        accept_regression=accept_regression,
        fetch_fn=fixture_fetcher,
        defer_notifications=defer,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
