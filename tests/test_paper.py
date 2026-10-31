"""The four properties the paper loop must keep, each one a way to cheat."""
import tempfile
import unittest
from pathlib import Path

from espero2 import hl
from espero2.paper import Costs, _fill_px
from espero2.store import Store
from espero2.strategy import sma_cross, stop_hit


def bars_from(closes):
    return [{"ts": i * 3600, "open": c, "high": c, "low": c, "close": c, "volume": 1.0}
            for i, c in enumerate(closes)]


class TestCausality(unittest.TestCase):
    def test_a_cross_on_the_last_closed_bar_is_detected(self):
        bars = bars_from([100.0] * 60 + [200.0])
        self.assertEqual(sma_cross(bars).side, "buy")

    def test_the_same_cross_is_invisible_while_its_bar_is_still_forming(self):
        # the 200 print is the bar that is still forming, so it must not produce a signal
        rows = [{"ts": i * 3600, "close": c, "open": c, "high": c, "low": c, "volume": 1.0}
                for i, c in enumerate([100.0] * 60 + [200.0])]
        closed = hl.closed_only(rows, 3600, now_s=60 * 3600 + 10, bars=100)
        self.assertEqual(sma_cross(closed).side, None)

    def test_forming_bar_cannot_be_used(self):
        rows = [{"ts": 0}, {"ts": 3600}, {"ts": 7200}]
        closed = hl.closed_only(rows, 3600, now_s=7200 + 10, bars=10)   # 7200 bar has not ended
        self.assertEqual([r["ts"] for r in closed], [0, 3600])

    def test_refuses_an_unknown_host(self):
        with self.assertRaises(hl.Refused):
            hl._post("/info", {"type": "allMids"}, base="https://example.com")

    def test_reading_mainnet_is_allowed_but_signing_is_not(self):
        from espero2 import hl_signed
        self.assertEqual(hl.MAINNET, "https://api.hyperliquid.xyz")
        self.assertTrue(hl_signed.TESTNET.startswith("https://api.hyperliquid-testnet"))


class TestFills(unittest.TestCase):
    def test_buy_pays_the_ask_plus_slippage(self):
        self.assertAlmostEqual(_fill_px(100.0, "buy", Costs(4.5, 2.0)), 100.02)

    def test_sell_pays_the_bid_minus_slippage(self):
        self.assertAlmostEqual(_fill_px(100.0, "sell", Costs(4.5, 2.0)), 99.98)

    def test_stop_is_level_triggered(self):
        self.assertTrue(stop_hit(100.0, 96.9, 0.03))
        self.assertFalse(stop_hit(100.0, 97.1, 0.03))


class TestJournal(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "p.db")
            s.add_bars("BTC", bars_from([1, 2, 3]))
            self.assertEqual(len(s.bars("BTC")), 3)
            s.set_state("BTC", cash=900.0, qty=0.1, entry_px=1000.0, entry_ts=5)
            st = s.get_state()
            self.assertAlmostEqual(st["cash"], 900.0)
            s.mark("BTC", 10, st["cash"], st["qty"], st["entry_px"], 1100.0)
            self.assertAlmostEqual(s.summary()["last"][1], 900.0 + 0.1 * 1100.0)
            s.close()

    def test_duplicate_bars_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "p.db")
            s.add_bars("BTC", bars_from([1, 2]))
            s.add_bars("BTC", bars_from([1, 2]))
            self.assertEqual(len(s.bars("BTC", limit=10)), 2)
            s.close()


if __name__ == "__main__":
    unittest.main()


class TestCoinsAreSeparateBooks(unittest.TestCase):
    def test_a_btc_fill_does_not_appear_in_the_eth_book(self):
        import tempfile
        from pathlib import Path
        from espero2 import hl, paper
        from espero2.paper import Costs, tick
        from espero2.store import Store

        series = [{"ts": i * 3600, "open": 100.0, "high": 100.0, "low": 100.0,
                   "close": 100.0, "volume": 1.0} for i in range(60)]
        series.append({"ts": 60 * 3600, "open": 100.0, "high": 200.0, "low": 100.0,
                       "close": 200.0, "volume": 1.0})
        orig_c, orig_b = hl.closed_candles, hl.book
        hl.closed_candles = lambda *a, **k: series
        hl.book = lambda coin, base=None: hl.Book(coin, bid=199.8, ask=200.2)
        try:
            with tempfile.TemporaryDirectory() as d:
                st = Store(Path(d) / "b.db")
                tick(st, "BTC", notional=100.0, costs=Costs(4.5, 2.0), kill=Path(d) / "KILL")
                self.assertGreater(st.get_state("BTC")["qty"], 0)
                self.assertEqual(st.get_state("ETH")["qty"], 0.0)
                self.assertEqual(st.get_state("ETH")["cash"], 1000.0)
                st.close()
        finally:
            hl.closed_candles, hl.book = orig_c, orig_b
