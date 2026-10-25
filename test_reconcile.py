"""Regression tests for the flip-flopping kickoff notifications (23-Oct <-> 31-Oct). No network/fixtures needed."""
import copy, json, os, sys
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scraper

K23 = "2026-10-23T15:00:00+01:00"
K31 = "2026-10-31T15:00:00+01:00"
K07 = "2026-11-07T15:00:00+01:00"


def data():
    with open(os.path.join(ROOT, "data", "data.json"), encoding="utf-8") as f:
        return json.load(f)


def m5(d):
    return next(m for m in d["matches"] if str(m["id"]) == "226431")


def ko_ev(k):
    return {"matchId": "226431", "kind": "kickoff", "kickoff": k}


def spans(*tokens):
    return "".join(f"<span>{t}</span>" for t in tokens)


def test_subrow_next_match_keeps_its_own_date():
    """prev + next links share ONE parent (as on lirf.dz): the next match must NOT inherit the previous date."""
    prev = spans("المباراة السابقة", "شباب ميلة", "ش. ميلة", "2", "1", "نجم تازوقاغت", "ن. تازوقاغت",
                 "الجمعة 23 أكتوبر 2026", "15:00", "بلقاسم بلعيد ميلة")
    nxt = spans("المباراة التالية", "إتحاد سدراتة", "إ سدراتة", "15:00", "شباب ميلة", "ش. ميلة",
                "السبت 31 أكتوبر 2026", "15:00", "سدراتة أفروخ الطاهر")
    html = (f'<table><tr><td colspan="11"><div>'
            f'<a href="https://www.lirf.dz/ar/match/226424">{prev}</a> '
            f'<a href="https://www.lirf.dz/ar/match/226431">{nxt}</a></div></td></tr></table>')
    row = BeautifulSoup(html, "html.parser").find("tr")
    hints = {h.match_id: h for h in scraper.extract_subrow_fixtures(row, data())}
    assert hints["226431"].kickoff == K31, hints["226431"].kickoff
    assert hints["226431"].score is None and hints["226431"].status == "scheduled"
    assert hints["226424"].kickoff == K23 and hints["226424"].score == (2, 1)


def test_flip_that_ends_where_it_started_sends_nothing():
    orig = data(); m5(orig)["kickoff"] = K31
    final = copy.deepcopy(orig); m5(final)["rescheduledFrom"] = K23  # artefact of the flip
    kept = scraper.reconcile_with_baseline(orig, final, [ko_ev(K23), ko_ev(K31)])
    assert kept == []
    assert "rescheduledFrom" not in m5(final)


def test_real_reschedule_sends_only_the_final_value():
    orig = data(); m5(orig)["kickoff"] = K31
    final = copy.deepcopy(orig); m5(final)["kickoff"] = K07; m5(final)["rescheduledFrom"] = K31
    kept = scraper.reconcile_with_baseline(orig, final, [ko_ev(K23), ko_ev(K31), ko_ev(K07)])
    assert [e["kickoff"] for e in kept] == [K07]
    assert m5(final)["rescheduledFrom"] == K31


def test_stuck_bogus_rescheduled_marker_is_cleaned():
    orig = data(); m5(orig)["kickoff"] = K31; m5(orig)["rescheduledFrom"] = K23  # K23 = CBM-NRB match time
    final = copy.deepcopy(orig)
    scraper.reconcile_with_baseline(orig, final, [])
    assert "rescheduledFrom" not in m5(final)
    assert scraper.has_substantive_changes(orig, final)  # so the cleanup gets committed


def test_result_events_are_net_changes_only():
    orig = data(); final = copy.deepcopy(orig)
    m4 = next(m for m in final["matches"] if str(m["id"]) == "226424")
    ev = lambda a, b: {"matchId": "226424", "kind": "result", "score": (a, b)}
    # already finished with the same score in the committed data -> nothing
    assert scraper.reconcile_with_baseline(orig, final, [ev(m4["score"]["home"], m4["score"]["away"])]) == []
    # score changed during the run (live 1-0 then final 2-1 vs. committed 'scheduled') -> only the final one
    orig2 = copy.deepcopy(orig)
    o4 = next(m for m in orig2["matches"] if str(m["id"]) == "226424"); o4["status"] = "scheduled"; o4["score"] = None
    kept = scraper.reconcile_with_baseline(orig2, final, [ev(1, 0), ev(m4["score"]["home"], m4["score"]["away"])])
    assert len(kept) == 1 and tuple(kept[0]["score"]) == (m4["score"]["home"], m4["score"]["away"])


def test_disagreeing_hints_are_ignored():
    d = data(); notes, events = [], []
    H = lambda k: scraper.FixtureHint(match_id="226431", home_id="891", away_id="733", kickoff=k, status="scheduled")
    scraper.apply_fixture_hints(d, [H(K23), H(K31)], notes, events)
    assert m5(d)["kickoff"] is None and events == []   # ambiguous -> the match page decides later
    scraper.apply_fixture_hints(d, [H(K31)], notes, events)
    assert m5(d)["kickoff"] == K31 and len(events) == 1
