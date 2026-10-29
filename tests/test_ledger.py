import unittest
from datetime import datetime, timedelta, timezone

from ledger import card, dashboard, options, score
from ledger.common import canonical_hash, wilson
from ledger.metrics import spearman

ITEM = {"symbol": "SPY", "bias": "breakout", "close": 769.66, "atr": 7.28, "rank": 4, "score": 4.05,
        "resistance": {"price": 770.41, "name": "MA20/PDH/WTDH"}, "support": {"price": 767.53, "name": "MA50"},
        "breakout_above": 770.41, "hold_above": 767.53,
        "target_up": {"price": 774.44, "name": "PWH/PMH"}, "target_down": {"price": 761.63, "name": "WTDL"}}
CARD = {"session": "2026-10-28", "picked_at": "2026-10-27T21:55:23+00:00", "items": [ITEM],
        "premarket": {"as_of": "2026-10-28T12:54:39+00:00",
                      "items": [{"symbol": "SPY", "price": 771.3, "gap_pct": 0.21, "where": "above_resistance"}]}}


def bars(rows, start="2026-10-28T13:30:00Z", step=120):
    t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
    ts = [(t0 + timedelta(seconds=step * i)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(len(rows))]
    o, h, l, c = zip(*rows)
    return {"symbol": "SPY", "source": "IBKR", "bar_seconds": step, "rth_only": True, "time": ts,
            "open": list(o), "high": list(h), "low": list(l), "close": list(c), "volume": [1] * len(rows)}


class CardTest(unittest.TestCase):
    def test_matches_screenshot_numbers(self):
        call = card.derive_levels(ITEM, "call")
        put = card.derive_levels(ITEM, "put")
        self.assertEqual((call["entry"], call["stop"], call["t1"], call["t2"]), (770.48, 769.68, 772.08, 774.44))
        self.assertEqual((put["entry"], put["stop"], put["t1"], put["t2"]), (767.46, 768.26, 765.86, 761.63))

    def test_records_are_hashed_and_confidence_set(self):
        recs = card.predictions_from_card(CARD, recorded_at="2026-10-28T13:00:00Z")
        self.assertEqual([r["id"] for r in recs], ["2026-10-28-SPY-call", "2026-10-28-SPY-put"])
        self.assertTrue(all(r["sha256"] == canonical_hash(r) for r in recs))
        self.assertEqual([r["confidence"] for r in recs], ["high", "low"])


    def test_rebuilt_tag_and_missing_level(self):
        it = dict(ITEM, breakout_above=None, resistance=None, target_up=None)
        recs = card.predictions_from_card(dict(CARD, items=[it], card_source="rebuilt", rebuild={"levels": "x"}),
                                          recorded_at="t", backfilled=True)
        self.assertEqual([r["side"] for r in recs], ["put"])
        self.assertEqual((recs[0]["card_source"], recs[0]["rebuild"]), ("rebuilt", {"levels": "x"}))
        self.assertNotIn("card_source", card.predictions_from_card(CARD, recorded_at="t")[0])


class ScoreTest(unittest.TestCase):
    def setUp(self):
        self.call = card.predictions_from_card(CARD, recorded_at="x")[0]

    def run_bars(self, rows):
        return score.score(self.call, bars(rows), bars_sha256="h", recorded_at="y")

    def test_break_retest_target(self):
        o = self.run_bars([(770, 771, 769.9, 770.6),    # 13:30 trigger close above 770.41
                           (770.6, 770.8, 770.4, 770.5),  # 13:32 retest inside 09:30-09:35 ET window: skipped
                           (770.5, 770.9, 770.45, 770.6),  # 13:34 still inside the window
                           (770.6, 770.7, 770.42, 770.5),  # 13:36 fill
                           (770.5, 772.2, 770.5, 772.0)])  # T1 772.08
        self.assertEqual(o["retests_in_blocked_window"], 2)
        self.assertEqual(o["fill_time"], "2026-10-28T13:36:00Z")
        self.assertEqual((o["result"], o["r"]), ("target1", 2.0))

    def test_stop_on_close_not_wick(self):
        o = self.run_bars([(770, 771, 769.9, 770.6), (770.6, 770.8, 770.4, 770.5), (770.5, 770.9, 770.45, 770.6),
                           (770.6, 770.7, 770.42, 770.5),
                           (770.5, 770.6, 769.0, 769.9),   # wick through the stop, close above: still alive
                           (769.9, 770.0, 769.2, 769.5)])  # close below 769.68: stopped
        self.assertEqual(o["result"], "stopped")
        self.assertAlmostEqual(o["r"], (769.5 - 770.48) / 0.8, delta=0.01)

    def test_same_bar_conflict_scores_stop(self):
        o = self.run_bars([(770, 771, 769.9, 770.6), (770.6, 770.8, 770.4, 770.5), (770.5, 770.9, 770.45, 770.6),
                           (770.6, 770.7, 770.42, 770.5), (770.5, 772.5, 769.0, 769.3)])
        self.assertEqual(o["result"], "stopped")
        self.assertTrue(o["policies"]["card"]["same_bar_conflict"])

    def test_five_min_rule_only_cuts_losers(self):
        o = self.run_bars([(770, 771, 769.9, 770.6), (770.6, 770.8, 770.4, 770.5), (770.5, 770.9, 770.45, 770.6),
                           (770.6, 770.7, 770.42, 770.45), (770.45, 770.5, 770.3, 770.4), (770.4, 770.5, 770.2, 770.3),
                           (770.3, 772.2, 770.3, 772.1)])
        self.assertEqual(o["policies"]["five_min"]["result"], "time_exit")
        self.assertEqual(o["policies"]["card"]["result"], "target1")

    def test_range_card_has_no_bias_verdict(self):
        p = dict(self.call, bias="range")
        self.assertIsNone(score.score(p, bars([(770, 770.3, 769.9, 770.2)] * 5), bars_sha256="h", recorded_at="y")["bias_correct"])

    def test_no_trigger(self):
        o = self.run_bars([(770, 770.3, 769.9, 770.2)] * 5)
        self.assertEqual(o["result"], "no_trigger")
        self.assertIsNone(o["r"])


class OptionTest(unittest.TestCase):
    def test_choose_first_strike_under_two_dollars(self):
        b = lambda px: bars([(px, px, px, px)] * 3)
        chain = [(771.0, b(2.4)), (772.0, b(1.7)), (773.0, b(1.1))]
        strike, _, prem = options.choose("call", 770.48, "2026-10-28T13:32:00Z", chain)
        self.assertEqual((strike, prem), (772.0, 1.7))

    def test_option_stop(self):
        o = {"id": "x", "session": "s", "symbol": "SPY", "side": "call", "sha256": "h", "filled": True,
             "fill_time": "2026-10-28T13:30:00Z",
             "policies": {"card": {"result": "target1", "exit_time": "2026-10-28T13:36:00Z"}}}
        ob = bars([(2, 2, 2, 2.0), (2, 2, 1.4, 1.6), (1.6, 2.6, 1.6, 2.5), (2.5, 2.6, 2.4, 2.6)])
        rec = options.score_option(o, strike=772, expiry="20261028", description="d", bars=ob, bars_sha256="h", recorded_at="t")
        self.assertEqual(rec["policies"]["card"]["reason"], "option_stop_25pct")
        self.assertEqual(rec["policies"]["card"]["pnl_usd"], -50.0)


class StatsTest(unittest.TestCase):
    def test_wilson(self):
        self.assertEqual(wilson(10, 15)[0], 0.417)
        self.assertEqual(wilson(0, 0), (None, None))

    def test_spearman(self):
        self.assertEqual(spearman([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]), 1.0)


if __name__ == "__main__":
    unittest.main()


class DashboardTest(unittest.TestCase):
    """The edition for the dashboard, built from the ledger's own files for 28 Oct 2026."""

    def test_day_matches_the_daily_report(self):
        doc = dashboard.build("2026-10-28", as_of="2026-10-28T21:00:00Z")
        self.assertEqual([n["symbol"] for n in doc["names"]], ["AVGO", "AMD", "NVDA", "SPY"])
        d = doc["day"]
        self.assertEqual((d["sides"], d["filled"], d["t1"], d["stopped"], d["r"], d["option_usd"]), (8, 5, 3, 1, 5.06, -87.0))
        self.assertEqual(doc["card_source"], "published")
        avgo = doc["names"][0]
        self.assertEqual(avgo["bars"]["t"][0], 0)  # 09:30 New York
        self.assertLessEqual(max(avgo["bars"]["t"]), 390)
        call = avgo["sides"][0]
        self.assertEqual((call["result"], call["r"], call["option"]["reason"], call["option"]["expiry"]), ("target1", 2.0, "option_stop_25pct", "2026-10-28"))

    def test_run_id_follows_the_content_not_the_clock(self):
        a = dashboard.build("2026-10-28", as_of="2026-10-28T21:00:00Z")
        b = dashboard.build("2026-10-28", as_of="2026-10-29T09:00:00Z")
        self.assertEqual(a["run_id"], b["run_id"])

    def test_record_holds_only_days_up_to_the_session(self):
        doc = dashboard.build("2026-10-21", as_of="2026-10-21T21:00:00Z")
        self.assertEqual([d["session"] for d in doc["record"]["days"]], ["2026-10-19", "2026-10-20", "2026-10-21"])
        self.assertIn("rebuilt_2min", doc["record"]["tiers"])

    def test_send_needs_both_secrets(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"RADAR_INGEST_SECRET": "", "VERCEL_AUTOMATION_BYPASS_SECRET": ""}):
            status, text = dashboard.send({"schema_version": 1})
        self.assertEqual(status, 2)
        self.assertIn("RADAR_INGEST_SECRET", text)
