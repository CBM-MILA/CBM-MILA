"""Tests for the rich Telegram digest / 'no news' message (no network, no HTML fixtures needed)."""
import copy, json, os, sys
from datetime import datetime, timedelta
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scraper

NOW = datetime.fromisoformat("2026-10-24T09:05:00+01:00")


def final_data():
    with open(os.path.join(ROOT, "data", "data.json"), encoding="utf-8") as f:
        return json.load(f)


def scenario():
    """(original, final): the state before / after one scrape run that brought many changes."""
    final = final_data()
    orig = copy.deepcopy(final)
    by = lambda d, i: next(m for m in d["matches"] if m["id"] == i)
    by(orig, "226424").update(status="scheduled", score=None, kickoff=None, venue=None)
    by(final, "226431").update(kickoff="2026-10-31T15:00:00+01:00", venue="سدراتة أفروخ الطاهر")
    by(final, "226424")["events"] = [
        {"minute": "13", "type": "goal", "team": "729", "playerId": None, "playerName": "بوالغالح محمد"},
        {"minute": "60", "type": "goal", "team": "733", "playerId": None, "playerName": "رملي ناجي"},
    ]
    for r in orig["standings"]:
        if r["clubId"] == "733":
            r.update(position=10, played=3, adjustedPoints=3, points=3, wins=1, losses=2, goalDifference=-2)
        if r["clubId"] == "997":
            r["position"] = 4
    orig["roundResults"] = [r for r in orig["roundResults"] if r["id"] != "226422"]
    for t in orig["topScorers"]:
        if t["name"]["ar"].startswith("رملي"):
            t["goals"] = 1
    orig["players"] = orig["players"][:-1]
    return orig, final


class _Balanced(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack = []
    def handle_starttag(self, t, a): self.stack.append(t)
    def handle_endtag(self, t): assert self.stack.pop() == t


def assert_valid_telegram_html(text):
    p = _Balanced(); p.feed(text)
    assert not p.stack
    assert len(text) <= 4096


def test_digest_describes_every_change():
    orig, final = scenario()
    msg = scraper.build_change_digest(orig, final, NOW)
    assert_valid_telegram_html(msg)
    for needle in ("نهاية المباراة", "2 - 1", "فوووز", "بوالغالح", "تحدّد موعد مباراة الجولة 5", "السبت 31 أكتوبر 2026",
                   "15:00", "بعد 7 أيام و5 ساعات", "تحديث جدول الترتيب", "#10 ← #8", "6 نقاط", "(+3)",
                   "نتائج أخرى", "الهدّافون", "+1", "انضم"):
        assert needle in msg, needle


def test_digest_is_none_when_nothing_changed():
    d = final_data()
    assert scraper.build_change_digest(d, copy.deepcopy(d), NOW) is None


def test_kickoff_change_shows_old_and_new_dates():
    orig, final = scenario()
    orig_m = next(m for m in orig["matches"] if m["id"] == "226431"); orig_m["kickoff"] = "2026-10-31T15:00:00+01:00"
    next(m for m in final["matches"] if m["id"] == "226431")["kickoff"] = "2026-11-07T16:00:00+01:00"
    msg = scraper.build_change_digest(orig, final, NOW)
    assert "تغيّر موعد مباراة الجولة 5" in msg and "كان:" in msg and "الآن:" in msg and "7 نوفمبر" in msg


def test_long_digest_drops_whole_sections_and_stays_valid(monkeypatch):
    orig, final = scenario()
    full = scraper.build_change_digest(orig, final, NOW)
    monkeypatch.setattr(scraper, "DIGEST_MAX_CHARS", 700)
    msg = scraper.build_change_digest(orig, final, NOW)
    assert_valid_telegram_html(msg)
    assert len(msg) < len(full) and "تحديثات أخرى" in msg


def test_arabic_number_agreement():
    assert scraper._pts_ar(1) == "نقطة واحدة" and scraper._pts_ar(2) == "نقطتان"
    assert scraper._pts_ar(6) == "6 نقاط" and scraper._pts_ar(11) == "11 نقطة"
    assert scraper._countdown_ar(timedelta(days=7, hours=5)) == "بعد 7 أيام و5 ساعات"
    assert scraper._countdown_ar(timedelta(days=2)) == "بعد يومين"


def test_no_news_message_content_and_rate_limit():
    final = final_data()
    msg = scraper.build_no_news_message(final, NOW)
    assert_valid_telegram_html(msg)
    assert "لا جديد" in msg and "😴" in msg and "المباراة القادمة" in msg and "#8" in msg
    assert "ملاحظة" in scraper.build_no_news_message(final, NOW, ["x"])

    st = {}
    assert scraper.should_send_no_news(st, NOW, 6)                       # never sent -> send
    st["lastNoNewsAt"] = (NOW - timedelta(hours=2)).isoformat()
    assert not scraper.should_send_no_news(st, NOW, 6)                   # 2h < 6h -> stay quiet
    assert scraper.should_send_no_news(st, NOW, 6, force=True)           # manual run -> always answer
    assert scraper.should_send_no_news(st, NOW, 0)                       # 0 = every run
    assert not scraper.should_send_no_news({}, NOW, -1)                  # -1 = disabled
    st["lastNoNewsAt"] = (NOW - timedelta(hours=7)).isoformat()
    assert scraper.should_send_no_news(st, NOW, 6)


def test_telegram_message_carries_inline_buttons(monkeypatch):
    sent = {}
    class R: status_code = 200
    monkeypatch.setattr(scraper, "TELEGRAM_TOKEN", "t"); monkeypatch.setattr(scraper, "TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(scraper.FETCHER.session, "post", lambda url, json=None, timeout=0: sent.update(json) or R())
    assert scraper.send_telegram_alert("hi", buttons=scraper.TELEGRAM_BUTTONS)
    kb = sent["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["url"].startswith("https://cbm-mila.github.io/CBM-MILA/") and kb[0][1]["url"].endswith("#/table")


def test_digest_mode_sends_one_message_events_mode_sends_more(monkeypatch):
    calls = []
    monkeypatch.setattr(scraper, "send_telegram_alert", lambda msg, **kw: calls.append((msg, kw.get("buttons"))) or True)
    monkeypatch.setattr(scraper, "send_web_push_notifications", lambda *a, **k: None)
    data = final_data()
    ev = {"matchId": "226424", "kind": "result", "score": (2, 1), "tag": "t"}
    extras = [{"message": "DIGEST", "buttons": scraper.TELEGRAM_BUTTONS}]
    monkeypatch.delenv("TELEGRAM_MODE", raising=False)
    scraper.deliver_notifications(data, [ev], extras, [], [], status_obj={}, dry_run=True)
    assert [c[0] for c in calls] == ["DIGEST"] and calls[0][1]          # digest only, with buttons
    calls.clear(); monkeypatch.setenv("TELEGRAM_MODE", "events")
    scraper.deliver_notifications(data, [ev], extras, [], [], status_obj={}, dry_run=True)
    assert len(calls) == 2
