"""Tests for the deferred notification queue (no network, no HTML fixtures needed)."""
import json, os, shutil, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scraper

DATA = os.path.join(ROOT, "data", "data.json")
EVENT = {"matchId": "226424", "kind": "result", "score": (2, 1), "tag": "cbm-res-226424",
         "ar": {"title": "t", "body": "b"}}


def setup(tmp):
    d = os.path.join(tmp, "data.json"); shutil.copy(DATA, d)
    s = os.path.join(tmp, "status.json")
    with open(s, "w", encoding="utf-8") as f:
        json.dump({"state": "ok", "consecutiveFailures": 0, "alertedHashes": []}, f)
    return d, s


def patch(mp, tg_ok=True, push_ok=True):
    sent = {"tg": [], "push": []}
    mp.setenv("TELEGRAM_MODE", "events")  # legacy per-event Telegram messages (digest mode is covered in test_digest.py)
    mp.setattr(scraper, "TELEGRAM_TOKEN", "x")
    mp.setattr(scraper, "TELEGRAM_CHAT_ID", "y")
    mp.setattr(scraper, "VAPID_PRIVATE_KEY", "v")
    mp.setattr(scraper, "ADMIN_KEY", "a")
    mp.setattr(scraper, "registry_url", lambda: "https://script.google.com/macros/s/x/exec")

    def fake_tg(message, dry_run=False, status_obj=None, event_key=None, status_path=scraper.STATUS_PATH, **kw):
        key = event_key or scraper._message_key(message)
        if scraper.is_event_channel_sent(status_obj, key, "telegram"):
            return True
        if tg_ok:
            sent["tg"].append(message)
            scraper.mark_event_channel_state(status_obj, key, "telegram", "sent", status_path=status_path)
        return tg_ok

    def fake_push(events, problems, notes, dry_run=False, status_obj=None, status_path=scraper.STATUS_PATH, **kw):
        for ev in events:
            key = ev.get("eventKey") or scraper.build_event_key(ev)
            if scraper.is_event_channel_sent(status_obj, key, "webpush"):
                continue
            if push_ok:
                sent["push"].append(key)
                scraper.mark_event_channel_state(status_obj, key, "webpush", "sent", status_path=status_path)

    mp.setattr(scraper, "send_telegram_alert", fake_tg)
    mp.setattr(scraper, "send_web_push_notifications", fake_push)
    return sent


def load(p):
    return json.load(open(p, encoding="utf-8"))


def test_queue_then_flush_is_exactly_once(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        d, s = setup(tmp); sent = patch(monkeypatch)
        st = load(s); ev = dict(EVENT)
        assert scraper.queue_notifications(st, scraper.dedupe_events([ev]), [{"message": "reg"}], s) == 2
        assert scraper.queue_notifications(st, scraper.dedupe_events([dict(EVENT)]), [{"message": "reg"}], s) == 0  # no dup
        assert sent == {"tg": [], "push": []}, "nothing may be sent while only queued"
        q = load(s)["queuedNotifications"]
        assert q["events"][0]["score"] == [2, 1] and len(q["events"]) == 1 and len(q["telegram"]) == 1
        assert scraper.flush_queued_notifications(d, s) == 0
        assert len(sent["tg"]) == 2 and len(sent["push"]) == 1          # result alert + extra msg, 1 push
        assert "نهاية المباراة" in sent["tg"][0] or "نهاية المباراة" in sent["tg"][1]
        after = load(s)["queuedNotifications"]
        assert after == {"events": [], "telegram": []}
        assert scraper.flush_queued_notifications(d, s) == 0              # idempotent
        assert len(sent["tg"]) == 2 and len(sent["push"]) == 1


def test_failed_delivery_is_retried_then_not_duplicated(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        d, s = setup(tmp); sent = patch(monkeypatch, tg_ok=False, push_ok=True)
        st = load(s); scraper.queue_notifications(st, scraper.dedupe_events([dict(EVENT)]), [], s)
        scraper.flush_queued_notifications(d, s)
        q = load(s)["queuedNotifications"]
        assert len(q["events"]) == 1 and q["events"][0]["_attempts"] == 1   # kept for retry
        assert len(sent["push"]) == 1
        sent = patch(monkeypatch, tg_ok=True, push_ok=True)                               # network recovered
        scraper.flush_queued_notifications(d, s)
        assert len(sent["tg"]) == 1 and sent["push"] == []                   # push NOT re-sent
        assert load(s)["queuedNotifications"]["events"] == []


def test_gives_up_after_max_attempts(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        d, s = setup(tmp); patch(monkeypatch, tg_ok=False, push_ok=False)
        scraper.queue_notifications(load(s), scraper.dedupe_events([dict(EVENT)]), [], s)
        for _ in range(scraper.NOTIFY_MAX_ATTEMPTS):
            scraper.flush_queued_notifications(d, s)
        assert load(s)["queuedNotifications"]["events"] == []


def test_dry_run_writes_nothing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        d, s = setup(tmp); patch(monkeypatch); before = open(s, encoding="utf-8").read()
        scraper.queue_notifications(load(s), scraper.dedupe_events([dict(EVENT)]), [], s, dry_run=True)
        assert open(s, encoding="utf-8").read() == before


def test_unconfigured_channels_do_not_pile_up(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        d, s = setup(tmp); patch(monkeypatch)
        monkeypatch.setattr(scraper, "TELEGRAM_TOKEN", None)
        monkeypatch.setattr(scraper, "TELEGRAM_CHAT_ID", None)
        monkeypatch.setattr(scraper, "VAPID_PRIVATE_KEY", None)
        scraper.queue_notifications(load(s), scraper.dedupe_events([dict(EVENT)]), [], s)
        scraper.flush_queued_notifications(d, s)
        assert load(s)["queuedNotifications"]["events"] == []
