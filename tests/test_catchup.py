"""After the machine sleeps, the journal must have no hole — and no invented fills."""
import tempfile
import unittest
from pathlib import Path

from espero2 import hl, paper
from espero2.store import Store

STEP = 3600


def series(n):
    return [{"ts": i * STEP, "open": 100 + i, "high": 101 + i, "low": 99 + i,
             "close": 100 + i, "volume": 1.0} for i in range(n)]


class TestCatchUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "p.db")
        self._orig = hl.closed_candles

    def tearDown(self):
        hl.closed_candles = self._orig
        self.store.close()
        self.tmp.cleanup()

    def test_marks_every_bar_missed_and_places_no_order(self):
        self.store.add_bars("BTC", series(3))
        self.store.mark("BTC", 0, 1000.0, 0.0, 0.0, 100.0)          # last mark before the sleep
        hl.closed_candles = lambda *a, **k: series(6)         # 5 more bars closed meanwhile
        out = paper.catch_up(self.store, "BTC")
        self.assertEqual(out["marks"], 5)
        self.assertEqual(self.store.last_mark_ts("BTC"), 5 * STEP)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)

    def test_a_fresh_journal_is_not_backfilled(self):
        hl.closed_candles = lambda *a, **k: series(6)
        out = paper.catch_up(self.store, "BTC")
        self.assertEqual(out["marks"], 0)                     # last_mark_ts == 0

    def test_running_again_marks_nothing(self):
        self.store.add_bars("BTC", series(5))
        self.store.mark("BTC", 0, 1000.0, 0.0, 0.0, 100.0)
        hl.closed_candles = lambda *a, **k: series(5)
        self.assertEqual(paper.catch_up(self.store, "BTC")["marks"], 4)
        self.assertEqual(paper.catch_up(self.store, "BTC")["marks"], 0)

    def test_marks_use_the_open_position(self):
        self.store.add_bars("BTC", series(4))
        self.store.set_state("BTC", cash=900.0, qty=1.0, entry_px=100.0, entry_ts=0)
        self.store.mark("BTC", 0, 900.0, 1.0, 100.0, 100.0)
        hl.closed_candles = lambda *a, **k: series(4)
        paper.catch_up(self.store, "BTC")
        eq = self.store.db.execute("SELECT equity FROM equity ORDER BY ts DESC LIMIT 1").fetchone()[0]
        self.assertAlmostEqual(eq, 900.0 + 1.0 * 103.0)       # marked at the last close, held


if __name__ == "__main__":
    unittest.main()
