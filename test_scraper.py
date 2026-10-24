"""
Unit & Integration Test Suite for CBM Mila Scraper (`scraper.py`)
"""
from __future__ import annotations

import copy
from datetime import datetime
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
import yaml

import scraper

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))


def _read_fixture_soup(name: str) -> BeautifulSoup:
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "html.parser")


def _load_sample_data() -> dict:
    with open(os.path.join(REPO_ROOT, "data", "data.json"), "r", encoding="utf-8") as f:
        return json.load(f)


class TestCBMScraper(unittest.TestCase):
    """Comprehensive test suite compatible with both `pytest` and `unittest`."""

    def test_workflow_yaml_files_are_valid_and_skip_ci_removed(self) -> None:
        workflow_files = sorted(
            glob.glob(os.path.join(REPO_ROOT, ".github", "workflows", "*.yml"))
            + glob.glob(os.path.join(REPO_ROOT, ".github", "workflows", "*.yaml"))
        )
        self.assertTrue(len(workflow_files) >= 2)
        for wf_path in workflow_files:
            with open(wf_path, "r", encoding="utf-8") as f:
                raw = f.read()
                parsed = yaml.safe_load(raw)
            self.assertIsInstance(parsed, dict, f"Invalid YAML in {wf_path}")
            self.assertIn("jobs", parsed, f"Missing jobs key in {wf_path}")
            if os.path.basename(wf_path) == "update-data.yml":
                self.assertNotIn("[skip ci]", raw)
            if os.path.basename(wf_path) == "ci.yml":
                on_block = parsed.get("on") or parsed.get(True) or {}
                push_cfg = on_block.get("push") or {}
                self.assertIn("data/**", push_cfg.get("paths-ignore", []))

    def test_standings_parsing_and_deduction_model(self) -> None:
        soup = _read_fixture_soup("ranking.html")
        data = _load_sample_data()
        problems: list[str] = []

        rows, hints = scraper.parse_standings_from_soup(soup, data, problems)
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 16)

        by_id = {r["clubId"]: r for r in rows}

        # Club 651 (ASM Ain M'lila): 0W 0D 3L -> raw points = 0, adjustedPoints = -4, pointsPenalty = 4
        asm = by_id["651"]
        self.assertEqual(asm["position"], 16)
        self.assertEqual(asm["played"], 3)
        self.assertEqual(asm["wins"], 0)
        self.assertEqual(asm["draws"], 0)
        self.assertEqual(asm["losses"], 3)
        self.assertEqual(asm["goalsFor"], 2)
        self.assertEqual(asm["goalsAgainst"], 9)
        self.assertEqual(asm["goalDifference"], -7)
        self.assertEqual(asm["points"], 0)
        self.assertEqual(asm["adjustedPoints"], -4)
        self.assertEqual(asm["pointsPenalty"], 4)
        self.assertTrue(asm["officialDeduction"])

        # Club 733 (CBM Mila): #10 in fixture, 3 pts, 3P 1W 0D 2L, GF 3, GA 5, GD -2
        cbm = by_id["733"]
        self.assertEqual(cbm["position"], 10)
        self.assertEqual(cbm["played"], 3)
        self.assertEqual(cbm["points"], 3)
        self.assertEqual(cbm["adjustedPoints"], 3)
        self.assertEqual(cbm["pointsPenalty"], 0)
        self.assertFalse(cbm["officialDeduction"])

        # Club 997 (CRBE Milia): #4 with 6 pts (2W 0D 1L, GF 5, GA 2, GD +3)
        milia = by_id["997"]
        self.assertEqual(milia["position"], 4)
        self.assertEqual(milia["played"], 3)
        self.assertEqual(milia["points"], 6)
        self.assertEqual(milia["goalsFor"], 5)
        self.assertEqual(milia["goalsAgainst"], 2)

        cbm_next = [h for h in hints if h.home_id == "733" and h.away_id == "729"]
        self.assertTrue(len(cbm_next) >= 1)
        self.assertEqual(cbm_next[0].kickoff, "2026-10-23T15:00:00+01:00")

    def test_ranking_competition_pinning_and_foreign_club_rejection(self) -> None:
        """Item 4: Verify wrong group/season is rejected and foreign club IDs abort update without appending."""
        data = _load_sample_data()
        orig_standings = copy.deepcopy(data["standings"])

        # 1) Wrong group selected in <select> ("جنوب غرب فوج ب" instead of "شرق")
        wrong_group_html = _read_fixture_soup("ranking.html")
        for opt in wrong_group_html.find_all("option"):
            if opt.get("value") == "4275":
                del opt["selected"]
            if opt.get("value") == "4280":
                opt["selected"] = "selected"
        problems_wg: list[str] = []
        updated_wg, _ = scraper.update_standings(
            data, problems_wg, fetch_fn=lambda u, p: wrong_group_html
        )
        self.assertFalse(updated_wg)
        self.assertTrue(any("ليست 'شرق'" in p for p in problems_wg))
        self.assertEqual(data["standings"], orig_standings)

        # 2) Foreign club ID in table (e.g., club 9999 replacing club 651)
        foreign_club_html = BeautifulSoup(
            str(_read_fixture_soup("ranking.html")).replace("/club/651", "/club/9999").replace("clubs-logos/651-", "clubs-logos/9999-"),
            "html.parser",
        )
        problems_fc: list[str] = []
        updated_fc, _ = scraper.update_standings(
            data, problems_fc, fetch_fn=lambda u, p: foreign_club_html
        )
        self.assertFalse(updated_fc)
        self.assertTrue(any("مجموعة الأندية المستخرجة لا تطابق" in p for p in problems_fc))
        self.assertEqual(len(data["standings"]), 16)
        self.assertNotIn("9999", {str(s["clubId"]) for s in data["standings"]})

    def test_forfeit_and_postponed_strict_badge_detection_ignores_unrelated_ghiyab(self) -> None:
        """Item 5: Verify unrelated text containing 'غياب' or 'مؤجل' does NOT trigger forfeit/postponed."""
        html_with_unrelated_words = """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl"><body><main>
          <section>
            <div>
              <span>03 أكتوبر 2026</span><span>15:00</span><span>بلقاسم بلعيد ميلة</span>
              <p>ملاحظة: شهد اللقاء غياب بعض اللاعبين بسبب الإصابة بعد نقاش مؤجل من الأسبوع الماضي.</p>
            </div>
            <div>
              <a href="https://www.lirf.dz/ar/club/733">شباب ميلة</a>
              <span>3</span><span>0</span>
              <a href="https://www.lirf.dz/ar/club/734">شباب عين ياقوت</a>
            </div>
          </section>
          <section>
            <h4>أحداث المباراة</h4>
            <p>25'</p><p>هدف من بن صغير حمزة</p>
            <p>'90</p>
          </section>
        </main></body></html>
        """
        soup_normal = BeautifulSoup(html_with_unrelated_words, "html.parser")
        ko = scraper.parse_kickoff(soup_normal, "733", "734")
        st, sc, cd = scraper.detect_match_status(
            soup_normal, "733", "734", ko, now=datetime(2026, 10, 23, 13, 0, tzinfo=scraper.TZ)
        )
        self.assertEqual(st, "finished")
        self.assertEqual(sc, (3, 0))
        self.assertFalse(cd)

        # Now test an actual forfeit badge between the two clubs
        html_real_forfeit = """
        <!DOCTYPE html>
        <html lang="ar" dir="rtl"><body><main>
          <section>
            <div><span>03 أكتوبر 2026</span><span>15:00</span></div>
            <div>
              <a href="https://www.lirf.dz/ar/club/733">شباب ميلة</a>
              <span>3</span><span>0</span>
              <span>على البساط</span>
              <a href="https://www.lirf.dz/ar/club/734">شباب عين ياقوت</a>
            </div>
          </section>
        </main></body></html>
        """
        soup_forfeit = BeautifulSoup(html_real_forfeit, "html.parser")
        st_f, sc_f, _ = scraper.detect_match_status(soup_forfeit, "733", "734", ko)
        self.assertEqual(st_f, "forfeit")
        self.assertEqual(sc_f, (3, 0))

    def test_accept_regression_override_flag(self) -> None:
        """Item 6: Verify played decrease blocks by default and succeeds with accept_regression=True."""
        data = _load_sample_data()
        # Set all clubs in sample data to played=4, while ranking.html fixture has played=3
        for s in data["standings"]:
            s["played"] = 4
            s["wins"] = 2
            s["draws"] = 1
            s["losses"] = 1
            s["points"] = 7
            s["adjustedPoints"] = 7 - s.get("pointsPenalty", 0)

        soup_rank = _read_fixture_soup("ranking.html")

        # 1) Default (accept_regression=False) blocks update
        d_blocked = copy.deepcopy(data)
        problems_block: list[str] = []
        updated_block, _ = scraper.update_standings(
            d_blocked, problems_block, fetch_fn=lambda u, p: soup_rank, accept_regression=False
        )
        self.assertFalse(updated_block)
        self.assertTrue(any("تراجع غير منطقي" in p for p in problems_block))

        # 2) With accept_regression=True, update_standings and validate_dataset allow the regression once
        d_allowed = copy.deepcopy(data)
        problems_allow: list[str] = []
        updated_allow, _ = scraper.update_standings(
            d_allowed, problems_allow, fetch_fn=lambda u, p: soup_rank, accept_regression=True
        )
        self.assertTrue(updated_allow)
        self.assertEqual(problems_allow, [])
        val_errs_blocked = scraper.validate_dataset(d_allowed, previous_data=data, accept_regression=False)
        self.assertTrue(any("تراجع عدد المباريات" in e for e in val_errs_blocked))
        val_errs_allowed = scraper.validate_dataset(d_allowed, previous_data=data, accept_regression=True)
        self.assertEqual(val_errs_allowed, [])

    def test_http_retry_policy_is_get_only(self) -> None:
        """Item 7: Ensure non-idempotent POST requests are never auto-retried."""
        adapter = scraper.FETCHER.session.get_adapter("https://")
        self.assertEqual(adapter.max_retries.allowed_methods, frozenset(["GET"]))

    def test_notification_dedupe_persisted_before_and_after_send(self) -> None:
        """Item 8: Verify dedupe state is persisted to disk before and after sending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = os.path.join(tmpdir, "status.json")
            status_obj = scraper.update_health_status("ok", [], status_path=status_file, dry_run=False)
            ev_key = "226424:result:2-1"

            with patch.object(scraper, "TELEGRAM_TOKEN", "fake-token"), patch.object(
                scraper, "TELEGRAM_CHAT_ID", "12345"
            ):
                observed_states_during_post: list[str] = []

                def _mock_post(url: str, **kwargs):
                    # Read status.json from disk *during* the network call to verify 'pending' was persisted BEFORE send
                    with open(status_file, "r", encoding="utf-8") as sf:
                        disk_st = json.load(sf)
                    observed_states_during_post.append(
                        disk_st.get("notificationEvents", {}).get(ev_key, {}).get("telegram")
                    )

                    class _Resp:
                        status_code = 200

                    return _Resp()

                with patch.object(scraper.FETCHER.session, "post", side_effect=_mock_post) as post_mock:
                    ok1 = scraper.send_telegram_alert(
                        "⚽ نهاية المباراة",
                        dry_run=False,
                        status_obj=status_obj,
                        event_key=ev_key,
                        status_path=status_file,
                    )
                    self.assertTrue(ok1)
                    self.assertEqual(observed_states_during_post, ["pending"])
                    self.assertEqual(post_mock.call_count, 1)

                    # Verify disk now has 'sent'
                    with open(status_file, "r", encoding="utf-8") as sf:
                        disk_after = json.load(sf)
                    self.assertEqual(
                        disk_after["notificationEvents"][ev_key]["telegram"], "sent"
                    )
                    self.assertIn(ev_key, disk_after["sentEvents"])

                    # Second call with same event_key must be skipped without calling POST
                    ok2 = scraper.send_telegram_alert(
                        "⚽ نهاية المباراة",
                        dry_run=False,
                        status_obj=disk_after,
                        event_key=ev_key,
                        status_path=status_file,
                    )
                    self.assertTrue(ok2)
                    self.assertEqual(post_mock.call_count, 1)

    def test_parallel_web_push_bounded_pool_and_single_prune(self) -> None:
        """Item 9: Verify parallel Web Push delivery, 404/410 collection, and single push_prune call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status_file = os.path.join(tmpdir, "status.json")
            status_obj = scraper.update_health_status("ok", [], status_path=status_file, dry_run=False)
            data = _load_sample_data()
            m4 = next(m for m in data["matches"] if str(m["id"]) == "226424")
            ev = scraper.build_result_push(data, m4, (2, 1))

            fake_subs = [
                {"endpoint": f"https://fcm.googleapis.com/fcm/send/sub-{i}", "keys": {"p256dh": "k", "auth": "a"}, "lang": "ar"}
                for i in range(15)
            ]
            registry_calls: list[dict] = []

            def _fake_registry_call(url: str, payload: dict):
                registry_calls.append(payload)
                if payload.get("a") == "push_list":
                    return {"ok": True, "items": fake_subs}
                if payload.get("a") == "push_prune":
                    return {"ok": True, "pruned": len(payload.get("endpoints", []))}
                return {"ok": True}

            def _fake_webpush(subscription_info: dict, **kwargs):
                ep = subscription_info["endpoint"]
                if ep.endswith("sub-3") or ep.endswith("sub-9"):
                    class _FakeResp:
                        status_code = 410

                    exc = Exception("Gone")
                    exc.response = _FakeResp()  # type: ignore[attr-defined]
                    raise exc
                return True

            problems: list[str] = []
            notes: list[str] = []
            with patch.object(scraper, "VAPID_PRIVATE_KEY", "fake-vapid"), patch.object(
                scraper, "ADMIN_KEY", "fake-admin"
            ), patch.object(scraper, "registry_url", return_value="https://script.google.com/macros/s/x/exec"), patch.object(
                scraper, "registry_call", side_effect=_fake_registry_call
            ):
                scraper.send_web_push_notifications(
                    [ev],
                    problems,
                    notes,
                    dry_run=False,
                    status_obj=status_obj,
                    status_path=status_file,
                    max_workers=10,
                    webpush_fn=_fake_webpush,
                )

            self.assertEqual(problems, [])
            prune_calls = [c for c in registry_calls if c.get("a") == "push_prune"]
            self.assertEqual(len(prune_calls), 1)
            self.assertEqual(
                prune_calls[0]["endpoints"],
                [
                    "https://fcm.googleapis.com/fcm/send/sub-3",
                    "https://fcm.googleapis.com/fcm/send/sub-9",
                ],
            )
            self.assertTrue(scraper.is_event_channel_sent(status_obj, ev["eventKey"], "webpush"))

    def test_finished_match_parsing(self) -> None:
        soup = _read_fixture_soup("match_226410_finished.html")
        data = _load_sample_data()
        self.assertTrue(scraper.verify_match_page_teams(soup, "733", "734"))

        ko = scraper.parse_kickoff(soup, "733", "734")
        self.assertIsNotNone(ko)
        assert ko is not None
        self.assertEqual(ko.isoformat(), "2026-10-03T15:00:00+01:00")

        venue = scraper.normalize_venue(scraper.parse_venue(soup, "733", "734"), is_cbm_home=True)
        self.assertEqual(venue, "Stade Belkacem Belaid, Mila")

        status, sc, closed_doors = scraper.detect_match_status(
            soup, "733", "734", ko, now=datetime(2026, 10, 23, 13, 0, tzinfo=scraper.TZ)
        )
        self.assertEqual(status, "finished")
        self.assertEqual(sc, (3, 0))
        self.assertFalse(closed_doors)

        m_obj = {"id": "226410", "home": "733", "away": "734"}
        evs = scraper.parse_events(soup, data, m_obj)
        goals = [e for e in evs if e["type"] == "goal"]
        self.assertEqual(len(goals), 3)
        self.assertEqual(goals[0]["playerId"], "40725")  # Hamza Benseghier

    def test_scheduled_and_mismatched_match_pages(self) -> None:
        soup_sched = _read_fixture_soup("match_226424_scheduled.html")
        ko = scraper.parse_kickoff(soup_sched, "733", "729")
        self.assertIsNotNone(ko)
        assert ko is not None
        self.assertEqual(ko.isoformat(), "2026-10-23T15:00:00+01:00")
        st, sc, cd = scraper.detect_match_status(soup_sched, "733", "729", ko)
        self.assertEqual(st, "scheduled")
        self.assertIsNone(sc)
        self.assertFalse(cd)

        soup_mis = _read_fixture_soup("match_226424_mismatched.html")
        self.assertFalse(scraper.verify_match_page_teams(soup_mis, "733", "729"))
        self.assertIsNone(scraper.parse_kickoff(soup_mis, "733", "729"))
        self.assertIsNone(scraper.parse_score(soup_mis, "733", "729"))

    def test_live_and_postponed_and_closed_doors_states(self) -> None:
        soup_live = _read_fixture_soup("match_live.html")
        ko_live = scraper.parse_kickoff(soup_live, "733", "729")
        st_live, sc_live, cd_live = scraper.detect_match_status(
            soup_live,
            "733",
            "729",
            ko_live,
            now=datetime(2026, 10, 23, 16, 10, tzinfo=scraper.TZ),
        )
        self.assertEqual(st_live, "live")
        self.assertEqual(sc_live, (1, 0))
        self.assertFalse(cd_live)

        soup_post = _read_fixture_soup("match_postponed.html")
        ko_post = scraper.parse_kickoff(soup_post, "891", "733")
        st_post, sc_post, cd_post = scraper.detect_match_status(soup_post, "891", "733", ko_post)
        self.assertEqual(st_post, "postponed")
        self.assertIsNone(sc_post)
        self.assertTrue(cd_post)

    def test_calendar_extraction_and_today_kickoff_update(self) -> None:
        data = _load_sample_data()
        for m in data["matches"]:
            if str(m["id"]) == "226424":
                m["kickoff"] = None
                m["status"] = "scheduled"
                m["score"] = None
        cal_soup = _read_fixture_soup("calendar.html")
        hints = scraper.extract_calendar_fixtures(cal_soup, data)
        self.assertTrue(len(hints) >= 3)

        notes: list[str] = []
        push_events: list[dict] = []
        changed = scraper.apply_fixture_hints(data, hints, notes, push_events)
        self.assertTrue(changed)

        m4 = next(m for m in data["matches"] if str(m["id"]) == "226424")
        self.assertEqual(m4["kickoff"], "2026-10-23T15:00:00+01:00")
        self.assertEqual(m4["venue"], "Stade Belkacem Belaid, Mila")
        self.assertEqual(m4["status"], "finished")
        self.assertEqual(m4["score"], {"home": 2, "away": 1})

    def test_change_detection_ignores_volatile_timestamps(self) -> None:
        d1 = _load_sample_data()
        d2 = copy.deepcopy(d1)
        d2["lastUpdated"] = "2026-10-23T19:00:00+01:00"
        d2["players"][0]["lastFetchedAt"] = "2026-10-23T19:00:00+01:00"
        self.assertFalse(scraper.has_substantive_changes(d1, d2))

        d2["matches"][3]["kickoff"] = "2026-10-24T16:00:00+01:00"
        self.assertTrue(scraper.has_substantive_changes(d1, d2))

    def test_empty_table_failure_does_not_overwrite_data(self) -> None:
        orig_data = _load_sample_data()
        with tempfile.TemporaryDirectory() as tmpdir:
            data_file = os.path.join(tmpdir, "data.json")
            status_file = os.path.join(tmpdir, "status.json")
            schema_file = os.path.join(REPO_ROOT, "data", "schema.json")
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(orig_data, f)

            empty_soup = BeautifulSoup("<html><body><table></table></body></html>", "html.parser")

            def _empty_fetcher(url: str, problems: list[str]) -> BeautifulSoup:
                return empty_soup

            rc = scraper.run_scraper(
                data_path=data_file,
                schema_path=schema_file,
                status_path=status_file,
                dry_run=False,
                fetch_fn=_empty_fetcher,
            )
            self.assertNotEqual(rc, 0)

            with open(data_file, "r", encoding="utf-8") as f:
                after_data = json.load(f)
            self.assertEqual(after_data["lastUpdated"], orig_data["lastUpdated"])
            self.assertEqual(after_data["standings"], orig_data["standings"])

            with open(status_file, "r", encoding="utf-8") as f:
                st = json.load(f)
            self.assertEqual(st["state"], "error")
            self.assertEqual(st["consecutiveFailures"], 1)

    def test_lineups_and_statistics_and_squad_sync(self) -> None:
        data = _load_sample_data()
        soup_match = _read_fixture_soup("match_226410_finished.html")
        m_obj = {"id": "226410", "home": "733", "away": "734"}
        lu = scraper.parse_lineups(soup_match, data, m_obj)
        self.assertIsNotNone(lu)
        assert lu is not None
        self.assertEqual(len(lu["home"]["starters"]), 11)
        self.assertEqual(lu["home"]["starters"][0]["playerId"], "43091")
        self.assertEqual(lu["home"]["coach"], "بلعريبي سعيد")
        self.assertEqual(lu["away"]["coach"], "وسار فاتح")

        soup_stats = _read_fixture_soup("statistics.html")
        soup_home = _read_fixture_soup("calendar.html")
        problems: list[str] = []
        notes: list[str] = []
        scraper.update_statistics(
            data,
            problems,
            notes,
            fetch_fn=lambda url, p: soup_stats,
            home_soup=soup_home,
        )
        self.assertEqual(problems, [])
        self.assertTrue(len(data.get("topScorers", [])) >= 8)
        self.assertEqual(data["topScorers"][0]["clubId"], "736")
        self.assertEqual(data["topScorers"][0]["goals"], 3)

        # Nadji Ramli (49698) updated to 2 goals & 4 appearances from homepage player stats card
        ramli = next(p for p in data["players"] if str(p["id"]) == "49698")
        self.assertEqual(ramli["stats"]["goals"], 2)
        self.assertEqual(ramli["stats"]["appearances"], 4)

        hamza = next(p for p in data["players"] if str(p["id"]) == "40725")
        self.assertEqual(hamza["stats"]["goals"], 1)
        self.assertEqual(hamza["stats"]["appearances"], 3)

        soup_club = _read_fixture_soup("club_733.html")
        scraper.update_squad_and_staff(
            data,
            problems,
            notes,
            fetch_fn=lambda url, p: soup_club,
        )
        self.assertEqual(problems, [])



    def test_http_cache_size_and_entry_bounds_and_workflow_timeouts(self) -> None:
        """Items 10 & 11: Verify HTTP cache caps body size/entries and every workflow job sets timeout-minutes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "http_cache.json")
            pf = scraper.PoliteFetcher(polite_delay=0.0, cache_path=cache_file)
            for idx in range(30):
                pf._cache[f"https://www.lirf.dz/page/{idx}"] = {"etag": f"e{idx}", "last_modified": "", "body": "x" * 100}
            pf._cache_dirty = True
            pf.save_cache(dry_run=False)
            with open(cache_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(len(saved), scraper.MAX_CACHE_ENTRIES)

        workflow_files = sorted(glob.glob(os.path.join(REPO_ROOT, ".github", "workflows", "*.yml")))
        for wf_path in workflow_files:
            with open(wf_path, "r", encoding="utf-8") as f:
                raw = f.read()
                parsed = yaml.safe_load(raw)
            for job_name, job_cfg in (parsed.get("jobs") or {}).items():
                self.assertIn("timeout-minutes", job_cfg, f"Job {job_name} in {wf_path} missing timeout-minutes")
            if os.path.basename(wf_path) == "update-data.yml":
                self.assertIn("actions/cache/restore@v4", raw)
                self.assertIn("actions/cache/save@v4", raw)
                self.assertNotIn("cbm-http-cache-${{ github.run_id }}", raw)
                self.assertEqual(parsed.get("concurrency", {}).get("group"), "cbm-mila-update-data")



    def test_frontend_and_sw_invariants_group4(self) -> None:
        """Items 13–16: Verify empty-state D0, shared notification tags, sw.js network-first & font precache, and CSS themes."""
        with open(os.path.join(REPO_ROOT, "app.js"), "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn('"lastUpdated":"1970-01-01T00:00:00Z"', app_js)
        self.assertIn('"matches":[],"standings":[]', app_js)
        self.assertIn("hasActivePushSubscription()", app_js)
        self.assertIn("`cbm-res-${m.id}`", app_js)
        self.assertIn("`cbm-ko-${m.id}`", app_js)
        self.assertIn("swUpdateToast", app_js)

        with open(os.path.join(REPO_ROOT, "sw.js"), "r", encoding="utf-8") as f:
            sw_js = f.read()
        self.assertIn("importScripts('./config.js')", sw_js)
        self.assertIn("./cairo-bold.woff2", sw_js)
        self.assertIn("./cairo-regular.woff2", sw_js)
        self.assertIn("networkFirstShell", sw_js)
        self.assertIn("CBM_SW_UPDATED", sw_js)

        with open(os.path.join(REPO_ROOT, "config.js"), "r", encoding="utf-8") as f:
            cfg_js = f.read()
        self.assertIn("self.CBM_BUILD_VERSION", cfg_js)

        with open(os.path.join(REPO_ROOT, "style.css"), "r", encoding="utf-8") as f:
            style_css = f.read()
        for sel in (".sync-bar.ok", ".sync-bar.stale", ".tag.live-b", ".tag.post-b", ".tag.resch-b", ".tag.closed-b", ".noscript-banner"):
            self.assertIn(sel, style_css)
            self.assertIn(f'[data-theme="light"] {sel}', style_css)



    def test_code_gs_v8_behaviour_in_node_vm(self) -> None:
        """Runs tests/code_gs.test.js: old sheet layout compatibility, verify/register/restore limits, push allow-list."""
        proc = subprocess.run(
            ["node", os.path.join("tests", "code_gs.test.js")],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("CHECKS PASSED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
