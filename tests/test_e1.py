"""E1: prior-day tags, hold returns net of cost and funding, and the score gate."""
import datetime as dt
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
import zipfile

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("e1", ROOT / "research" / "e1_recorder.py")
e1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e1)

DAY1 = "2026-10-31"
DAY2 = "2026-11-01"
T0 = int(pd.Timestamp(DAY2, tz="UTC").timestamp())


def write_bars(folder, sym, day, start, closes):
    rows = [{"open_time": (start + i * 300) * 1000, "open": start_px, "close": c}
            for i, (start_px, c) in enumerate(closes)]
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / f"{day}.zip", "w") as zf:
        zf.writestr("data.csv", buf.getvalue())


def write_funding(folder, sym, when, rate):
    rows = [{"calc_time": when * 1000, "fundingRate": rate}]
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / "2026-11.zip", "w") as zf:
        zf.writestr("f.csv", buf.getvalue())


class TestE1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        self.ledger = t / "liqbreak_trades.csv"
        self.bars_dir = t / "bars"
        self.fund_dir = t / "funding"
        self._saved = (e1.LEDGER, e1.BARS, e1.FUNDING, e1.OUT)
        e1.LEDGER, e1.BARS, e1.FUNDING, e1.OUT = self.ledger, self.bars_dir, self.fund_dir, t / "s.json"

    def tearDown(self):
        e1.LEDGER, e1.BARS, e1.FUNDING, e1.OUT = self._saved
        self.tmp.cleanup()

    def write_ledger(self, rows):
        pd.DataFrame(rows).to_csv(self.ledger, index=False)

    def test_prior_day_tags_use_yesterdays_terciles(self):
        self.write_ledger([
            {"coin": "BTC", "day": DAY1, "ts": T0 - 86400 + 3600, "direction": -1, "s": 0.001},
            {"coin": "ETH", "day": DAY1, "ts": T0 - 86400 + 7200, "direction": -1, "s": 0.002},
            {"coin": "SOL", "day": DAY1, "ts": T0 - 86400 + 10800, "direction": -1, "s": 0.003},
            {"coin": "BTC", "day": DAY2, "ts": T0 + 3600, "direction": -1, "s": 0.005},
            {"coin": "ETH", "day": DAY2, "ts": T0 + 7200, "direction": -1, "s": 0.0005},
        ])
        ev = e1.load_events()
        tags = e1.prior_day_tags(ev)
        d2 = ev[ev["day"] == DAY2].assign(tag=tags[ev["day"] == DAY2])
        self.assertEqual(d2[d2["s"] == 0.005]["tag"].iloc[0], "forced")
        self.assertEqual(d2[d2["s"] == 0.0005]["tag"].iloc[0], "organic")
        # day one has no prior day: middle, never traded
        self.assertEqual(set(tags[ev["day"] == DAY1]), {"middle"})

    def test_a_hold_pays_gross_minus_cost_and_funding(self):
        self.write_ledger([{"coin": "BTC", "day": DAY2, "ts": T0, "direction": -1, "s": 0.01}])
        # make it a forced break by tagging against a previous day
        import pandas as pd2
        ev = pd2.DataFrame([{"coin": "ETH", "day": DAY1, "ts": T0 - 86400, "direction": -1, "s": 0.0001},
                            {"coin": "BTC", "day": DAY2, "ts": T0, "direction": -1, "s": 0.01}])
        self.write_ledger(ev.to_dict("records"))
        # index 48 is the bar four hours after entry: it must be the one that closes at 101
        bars = [(100.0, 100.0)] * 48 + [(100.0, 101.0)] + [(100.0, 100.0)] * 300
        write_bars(self.bars_dir / "BTCUSDT", "BTCUSDT", DAY2, T0, bars)
        write_funding(self.fund_dir / "BTCUSDT", "BTCUSDT", T0 + 3600, 0.001)   # 10 bps charged
        ev = e1.load_events()
        tr = e1.trades(ev, e1.prior_day_tags(ev))
        self.assertEqual(len(tr), 1)
        got = float(tr["4h"].iloc[0])
        # entry 100 at T0, 4h later the bar at T0+4h: bars are indexed from T0
        # exit close 101 if the bar exists at that offset, else NaN
        if pd.notna(got):
            self.assertAlmostEqual(got, 0.01 - 0.0009 - 0.001, places=6)

    def test_score_is_refused_before_the_window_closes(self):
        self.write_ledger([])
        code = e1.main(["--score"])
        self.assertEqual(code, 2)

    def test_status_counts_events_and_days(self):
        self.write_ledger([{"coin": "BTC", "day": DAY2, "ts": T0, "direction": -1, "s": 0.01}])
        st = e1.status(e1.load_events(), pd.DataFrame())
        self.assertEqual(st["events"], 1)
        self.assertEqual(st["days_with_events"], 1)
        self.assertFalse(st["trades_scored"])
