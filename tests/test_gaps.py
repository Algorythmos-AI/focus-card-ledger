"""The missed-session check (ledger validate --gaps), on fixture sets only."""
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from ledger import sessions, validate
from ledger.validate import find_gaps

# The week of 9 Nov 2026 as it happened: Monday to Thursday recorded, Friday 13 Nov missed.
WEEK = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"]
MISSED_13 = {"session": "2026-11-13", "missing": ["predictions", "outcomes"], "reason": "both routines fired late"}


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def gaps(predicted, scored, missed=(), now="2026-11-16T13:00:00"):
    preds = predicted if isinstance(predicted, dict) else {s: True for s in predicted}
    return find_gaps(preds, set(scored), list(missed), utc(now))


class CalendarTest(unittest.TestCase):
    def test_weekends_and_holidays_are_closed(self):
        self.assertTrue(sessions.is_session("2026-11-13"))
        self.assertFalse(sessions.is_session("2026-11-14"))   # Saturday
        self.assertFalse(sessions.is_session("2026-11-26"))   # Thanksgiving
        self.assertTrue(sessions.is_session("2026-11-27"))    # half day, still a session
        self.assertFalse(sessions.is_session("2026-07-03"))   # Independence Day observed

    def test_only_plain_iso_dates(self):
        for s in ("20261113", "2026-W46-5"):
            with self.assertRaises(ValueError):
                sessions.is_session(s)

    def test_outside_the_calendar_raises(self):
        with self.assertRaises(ValueError):
            sessions.is_session("2030-01-02")

    def test_sessions_between_skips_closures(self):
        self.assertEqual(sessions.sessions_between(date(2026, 11, 25), date(2026, 11, 30)),
                         ["2026-11-25", "2026-11-27", "2026-11-30"])


class GapTest(unittest.TestCase):
    def test_full_ledger_is_clean(self):
        self.assertEqual(gaps(WEEK + ["2026-11-13"], WEEK + ["2026-11-13"]), [])

    def test_13_nov_is_reported(self):
        errs = gaps(WEEK, WEEK)
        self.assertEqual(len(errs), 2)
        self.assertTrue(errs[0].startswith("2026-11-13: no predictions"))
        self.assertTrue(errs[1].startswith("2026-11-13: no outcomes"))

    def test_due_times_follow_new_york(self):
        # 13 Nov is EST: predictions are due at 14:30 UTC, outcomes at 22:00 UTC.
        self.assertEqual(gaps(WEEK, WEEK, now="2026-11-13T14:29:59"), [])
        self.assertEqual([e[:30] for e in gaps(WEEK, WEEK, now="2026-11-13T21:22:00")], ["2026-11-13: no predictions, an"])
        self.assertEqual(len(gaps(WEEK, WEEK, now="2026-11-13T22:00:00")), 2)
        # 30 Oct is EDT: predictions are due at 13:30 UTC.
        before = ["2026-10-29"]
        self.assertEqual(gaps(before, before, now="2026-10-30T13:29:00"), [])
        self.assertEqual(len(gaps(before, before, now="2026-10-30T13:30:00")), 1)
        # ...and outcomes at 21:00 UTC.
        pred = before + ["2026-10-30"]
        self.assertEqual(gaps(pred, before, now="2026-10-30T20:59:00"), [])
        self.assertEqual(len(gaps(pred, before, now="2026-10-30T21:00:00")), 1)

    def test_predictions_without_outcomes_after_the_close(self):
        errs = gaps(WEEK + ["2026-11-13"], WEEK, now="2026-11-13T22:30:00")
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("2026-11-13: no outcomes"))

    def test_listed_session_passes(self):
        self.assertEqual(gaps(WEEK, WEEK, [MISSED_13]), [])

    def test_listing_only_predictions_still_reports_outcomes(self):
        errs = gaps(WEEK, WEEK, [dict(MISSED_13, missing=["predictions"])])
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("2026-11-13: no outcomes"))

    def test_holidays_and_weekends_are_not_gaps(self):
        days = ["2026-11-25", "2026-11-27", "2026-11-30"]
        self.assertEqual(gaps(days, days, now="2026-12-01T12:00:00"), [])

    def test_records_on_a_closed_day_are_errors(self):
        errs = gaps(["2026-11-25", "2026-11-26"], ["2026-11-25"], now="2026-11-26T23:00:00")
        self.assertEqual(errs, ["predictions/2026/2026-11-26.jsonl: NYSE was closed on 2026-11-26"])

    def test_a_backfill_may_follow_a_listed_miss_but_live_records_contradict_it(self):
        both = WEEK + ["2026-11-13"]
        backfilled = {s: s != "2026-11-13" for s in both}
        self.assertEqual(gaps(backfilled, both, [MISSED_13]), [])
        errs = gaps(both, both, [MISSED_13])
        self.assertEqual(len(errs), 1)
        self.assertIn("listed as missed but has live predictions", errs[0])

    def test_bad_entries_are_reported(self):
        bad = [dict(MISSED_13, session="2026-11-14"),
               dict(MISSED_13, session="13 Nov"),
               dict(MISSED_13, session="2026-11-12", missing=["bars"]),
               dict(MISSED_13, reason=" "),
               dict(MISSED_13, session="2026-11-16")]
        errs = gaps(WEEK, WEEK, bad)
        self.assertTrue(any("NYSE was closed on 2026-11-14" in e for e in errs))
        self.assertTrue(any("'13 Nov' is not a date" in e for e in errs))
        self.assertTrue(any("'missing' must list" in e for e in errs))
        self.assertTrue(any("2026-11-13 needs a reason" in e for e in errs))
        self.assertTrue(any("2026-11-16 predictions are not due" in e for e in errs))

    def test_duplicate_entry(self):
        errs = gaps(WEEK, WEEK, [MISSED_13, MISSED_13])
        self.assertEqual(errs, [f"{validate.MISSED} entry 2: 2026-11-13 is listed twice"])

    def test_today_outside_the_calendar(self):
        errs = gaps(WEEK, WEEK, now="2030-01-02T12:00:00")
        self.assertEqual(len(errs), 1)
        self.assertIn("extend ledger/sessions.py", errs[0])

    def test_empty_ledger_has_no_gaps(self):
        self.assertEqual(gaps([], []), [])

    def test_missed_list_is_append_only(self):
        self.assertEqual(validate.dropped_entries([MISSED_13], [MISSED_13]), [])
        self.assertEqual(validate.dropped_entries([], [MISSED_13]), [])
        self.assertEqual(validate.dropped_entries([MISSED_13], []),
                         [f"{validate.MISSED}: 2026-11-13 was listed on the base branch and is gone; the list is append-only"])


class ArgsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(validate.parse_args([]), (None, False))
        self.assertEqual(validate.parse_args(["--gaps"]), (None, True))
        self.assertEqual(validate.parse_args(["--gaps", "abc123"]), ("abc123", True))
        self.assertEqual(validate.parse_args(["origin/main"]), ("origin/main", False))
        with self.assertRaises(SystemExit):
            validate.parse_args(["a", "b"])

    def test_cli_passes_gaps_and_base(self):
        from unittest import mock
        from ledger import __main__ as cli
        with mock.patch.object(validate, "main", return_value=0) as m:
            cli.main(["validate", "--gaps", "abc123"])
            cli.main(["validate"])
        self.assertEqual(m.call_args_list[0].args[0], ["abc123", "--gaps"])
        self.assertEqual(m.call_args_list[1].args[0], [])


class GapFilesTest(unittest.TestCase):
    """check_gaps reads the folders and the missed list from a ledger root (a temporary fixture here)."""

    def make(self, root, kind, session, rows):
        p = root / kind / session[:4] / f"{session}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r) + "\n" for r in rows))

    def test_reads_folders_and_missed_list(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for s in WEEK:
                self.make(root, "predictions", s, [{"id": f"{s}-SPY-call"}])
                self.make(root, "outcomes", s, [{"id": f"{s}-SPY-call"}])
            self.make(root, "predictions", "2026-11-13", [])   # an empty file is not a record
            now = utc("2026-11-16T13:00:00")
            self.assertEqual(len(validate.check_gaps(now, root)), 2)
            (root / validate.MISSED).write_text(json.dumps([MISSED_13]))
            self.assertEqual(validate.check_gaps(now, root), [])

    def test_backfilled_flag_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.make(root, "predictions", "2026-11-13", [{"backfilled": True}, {"backfilled": True}])
            self.make(root, "predictions", "2026-11-12", [{"backfilled": True}, {}])
            predicted, _ = validate.ledger_sessions(root)
            self.assertEqual(predicted, {"2026-11-13": False, "2026-11-12": True})


if __name__ == "__main__":
    unittest.main()
