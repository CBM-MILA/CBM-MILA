"""Heartbeat: refresh lastUpdated on quiet runs so the site never looks stale (no network / fixtures needed)."""
import os, sys
from datetime import datetime, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scraper

NOW = datetime.fromisoformat("2026-10-29T15:00:00+01:00")


def test_heartbeat_due_only_when_old():
    fresh = {"lastUpdated": (NOW - timedelta(hours=2)).isoformat()}
    old = {"lastUpdated": (NOW - timedelta(hours=7)).isoformat()}
    assert not scraper.heartbeat_due(fresh, NOW, 6)
    assert scraper.heartbeat_due(old, NOW, 6)
    assert scraper.heartbeat_due({}, NOW, 6)                       # missing -> refresh
    assert scraper.heartbeat_due({"lastUpdated": "garbage"}, NOW, 6)


def test_heartbeat_can_be_disabled(monkeypatch):
    old = {"lastUpdated": (NOW - timedelta(days=3)).isoformat()}
    assert not scraper.heartbeat_due(old, NOW, 0)
    monkeypatch.setenv("HEARTBEAT_HOURS", "-1")
    assert not scraper.heartbeat_due(old, NOW)


def test_heartbeat_is_not_a_substantive_change():
    a = {"lastUpdated": "2026-10-26T10:00:00+01:00", "matches": [], "players": [], "standings": []}
    b = dict(a, lastUpdated="2026-10-29T10:00:00+01:00")
    assert not scraper.has_substantive_changes(a, b)               # so no digest / notifications are triggered
