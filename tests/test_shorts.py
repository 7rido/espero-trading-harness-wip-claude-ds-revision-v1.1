"""Shorts: signed positions, mirrored stops, flips, funding, and the long-only switch."""
import tempfile
import unittest
from pathlib import Path

from espero2 import hl, paper
from espero2.paper import Costs, Rules, tick
from espero2.store import Store

STEP = 3600


def series(n, start=200.0, step=-1.0):
    out = []
    for i in range(n):
        c = start + i * step
        out.append({"ts": i * STEP, "open": c, "high": c, "low": c, "close": c, "volume": 1.0})
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "s.db")
        self.orig = (hl.closed_candles, hl.book)

    def tearDown(self):
        hl.closed_candles, hl.book = self.orig
        self.store.close()
        self.tmp.cleanup()

    def market(self, bars, bid=100.0, ask=100.2):
        hl.closed_candles = lambda *a, **k: bars
        hl.book = lambda coin, base=None: hl.Book(coin, bid=bid, ask=ask)


class TestShorts(Base):
    def test_a_falling_regime_opens_a_short(self):
        self.market(series(80, 200, -1.0))          # SMA20 below SMA50 -> short
        r = tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
                 kill=Path(self.tmp.name) / "KILL")
        st = self.store.get_state("BTC")
        self.assertLess(st["qty"], 0)
        self.assertGreater(st["cash"], 1000.0)       # short proceeds credited
        self.assertTrue(any("opened short" in a for a in r["actions"]))
        side = self.store.db.execute("SELECT side, note FROM orders").fetchone()
        self.assertEqual(side[0], "sell")
        self.assertIn("open", side[1])

    def test_a_short_stop_closes_on_the_way_up(self):
        self.market(series(80, 200, -1.0), bid=100.0, ask=100.0)
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        entry = self.store.get_state("BTC")["entry_px"]
        self.market(series(80, 200, -1.0), bid=entry * 1.05, ask=entry * 1.05)   # +5% against a 3% stop
        r = tick(self.store, "BTC", costs=Costs(), rules=Rules(),
                 kill=Path(self.tmp.name) / "KILL")
        self.assertEqual(self.store.get_state("BTC")["qty"], 0.0)
        self.assertTrue(any("stop closed short" in a for a in r["actions"]))

    def test_a_flip_closes_then_opens_two_orders(self):
        self.market(series(80, 100, +1.0))          # rising: long
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        self.assertGreater(self.store.get_state("BTC")["qty"], 0)
        self.market(series(80, 200, -1.0))          # now falling: short
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        st = self.store.get_state("BTC")
        self.assertLess(st["qty"], 0)
        notes = [n for (n,) in self.store.db.execute("SELECT note FROM orders ORDER BY oid")]
        self.assertIn("close flip", notes)
        self.assertEqual(len(notes), 3)             # open long, close long, open short

    def test_long_only_mode_ignores_a_short_signal(self):
        self.market(series(80, 200, -1.0))
        r = tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
                 kill=Path(self.tmp.name) / "KILL", allow_short=False)
        self.assertEqual(self.store.get_state("BTC")["qty"], 0.0)
        self.assertTrue(any("ignored" in a for a in r["actions"]))


class TestFunding(Base):
    def test_venue_funding_is_used_when_available(self):
        import time
        self.market(series(80, 200, -1.0), bid=100.0, ask=100.0)
        tick(self.store, "BTC", costs=Costs(), rules=Rules(), kill=Path(self.tmp.name) / "KILL")
        self.assertLess(self.store.get_state("BTC")["qty"], 0)
        before = self.store.get_state("BTC")["cash"]
        self.store.set_state("BTC", last_funding=int(time.time()) - 3600)
        orig = hl.funding_history
        hl.funding_history = lambda coin, since, venue="mainnet": [(int(time.time()) - 60, 0.001)]
        try:
            r = tick(self.store, "BTC", costs=Costs(), rules=Rules(funding_source="venue"),
                     kill=Path(self.tmp.name) / "KILL")
        finally:
            hl.funding_history = orig
        self.assertTrue(any("venue" in a for a in r["actions"]), r["actions"])
        self.assertGreater(self.store.get_state("BTC")["cash"], before)   # short received funding

    def test_a_short_receives_when_funding_is_positive(self):
        st = {"qty": -1.0}
        self.assertAlmostEqual(paper._funding(self.store, "BTC", st, 100.0, 1.0, 1.0), +0.01)

    def test_a_long_pays_when_funding_is_positive(self):
        st = {"qty": 1.0}
        self.assertAlmostEqual(paper._funding(self.store, "BTC", st, 100.0, 1.0, 1.0), -0.01)

    def test_flat_pays_nothing(self):
        self.assertEqual(paper._funding(self.store, "BTC", {"qty": 0.0}, 100.0, 5.0, 1.0), 0.0)


class TestLiquidationFloor(Base):
    def test_a_short_is_liquidated_at_the_liquidation_price(self):
        self.market(series(80, 200, -1.0), bid=100.0, ask=100.0)
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        entry = self.store.get_state("BTC")["entry_px"]
        self.market(series(80, 200, -1.0), bid=entry * 2.1, ask=entry * 2.1)  # past 1x liq (~1.99x)
        r = tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
                 kill=Path(self.tmp.name) / "KILL")
        st = self.store.get_state("BTC")
        self.assertEqual(st["qty"], 0.0)
        self.assertTrue(any("LIQUIDATED" in a for a in r["actions"]), r["actions"])
        self.assertGreater(st["cash"], 500.0)          # a $100 short cannot lose more than its stake

    def test_a_gap_through_liquidation_can_leave_a_negative_balance(self):
        self.market(series(80, 200, -1.0), bid=100.0, ask=100.0)
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        entry = self.store.get_state("BTC")["entry_px"]
        self.market(series(80, 200, -1.0), bid=entry * 20, ask=entry * 20)    # gap far beyond
        tick(self.store, "BTC", costs=Costs(), rules=Rules(max_notional=100.0),
             kill=Path(self.tmp.name) / "KILL")
        self.assertEqual(self.store.get_state("BTC")["qty"], 0.0)
        self.assertLess(self.store.get_state("BTC")["cash"], 0.0)  # honest: a gap can exceed the stake
