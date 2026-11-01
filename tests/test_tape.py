"""Tape metrics on synthetic prints: CVD, blocks, sweeps, profile, absorption, divergence."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tape_mod", ROOT / "research" / "tape.py")
tape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tape)

T0 = pd.Timestamp("2026-10-29T00:00:00")


def frame(rows):
    return pd.DataFrame(rows, columns=["ts", "price", "quantity", "buyer_maker"])


class TestMinuteTable(unittest.TestCase):
    def test_cvd_and_buy_share(self):
        df = frame([(T0, 100.0, 1.0, False), (T0 + pd.Timedelta(seconds=30), 100.0, 0.5, True),
                    (T0 + pd.Timedelta(minutes=1), 101.0, 0.5, False)])
        m = tape.minute_table(df)
        self.assertAlmostEqual(m.loc[0, "buy_qty"], 1.0)
        self.assertAlmostEqual(m.loc[0, "sell_qty"], 0.5)
        self.assertAlmostEqual(m.loc[0, "cvd"], 0.5)
        self.assertAlmostEqual(m.loc[0, "buy_share"], 2 / 3, places=3)
        self.assertAlmostEqual(m.loc[1, "cvd"], 1.0)


class TestBlocks(unittest.TestCase):
    def test_threshold(self):
        df = frame([(T0, 60_000.0, 2.0, False), (T0, 60_000.0, 0.0001, True)])
        b = tape.block_stats(df, 100_000.0)
        self.assertEqual(b["count"], 1)
        self.assertAlmostEqual(b["usd"], 120_000.0)


class TestSweeps(unittest.TestCase):
    def test_three_prints_same_ms_and_price_is_one_sweep(self):
        df = frame([(T0, 100.0, 1.0, False)] * 3 + [(T0 + pd.Timedelta(milliseconds=1), 100.0, 1.0, False)])
        self.assertEqual(tape.sweep_stats(df)["count"], 1)

    def test_two_prints_are_not_a_sweep(self):
        df = frame([(T0, 100.0, 1.0, False)] * 2)
        self.assertEqual(tape.sweep_stats(df)["count"], 0)


class TestProfile(unittest.TestCase):
    def test_poc_sits_in_the_heavier_cluster(self):
        rows = [(T0, 100.0, 10.0, False)] * 10 + [(T0, 101.0, 1.0, False)]
        df = frame(rows)
        p = tape.profile(df)
        self.assertAlmostEqual(p["poc"], 100.0, delta=0.2)
        self.assertLessEqual(p["va70"][0], p["poc"])
        self.assertGreaterEqual(p["va70"][1], p["poc"])


class TestAbsorption(unittest.TestCase):
    def test_high_volume_flat_price_counts(self):
        m = pd.DataFrame({"vol_z": [3.0, 1.0, 3.0], "ret_bp": [0.01, 50.0, 100.0]})
        a = tape.absorption(m)
        self.assertAlmostEqual(a["share"], 0.5)


class TestDivergence(unittest.TestCase):
    def _series(self, first_low, second_low, first_cvd, second_cvd):
        rows = []
        for i in range(20):
            rows.append({"low": first_low, "high": first_low + 1, "cvd": first_cvd + i})
        for i in range(20):
            rows.append({"low": second_low, "high": second_low + 1, "cvd": second_cvd + i})
        return pd.DataFrame(rows)

    def test_price_lower_low_with_cvd_higher_low_is_bullish(self):
        self.assertEqual(tape.divergence(self._series(100, 99, -50, -10)), "bullish")

    def test_mirror_is_bearish(self):
        self.assertEqual(tape.divergence(self._series(100, 101, 50, -50)), "bearish")

    def test_flat_is_none(self):
        self.assertEqual(tape.divergence(self._series(100, 100, 0, 0)), "none")


class TestSummarise(unittest.TestCase):
    def test_read_sentence_and_fields(self):
        df = frame([(T0, 60_000.0, 1.0, False), (T0 + pd.Timedelta(seconds=1), 60_000.0, 0.5, True)])
        out = tape.summarise(df, "binance-um", "BTCUSDT", "2026-10-29", 100_000.0)
        self.assertEqual(out["prints"], 2)
        self.assertGreater(out["buy_share"], 0.6)
        self.assertGreater(out["cvd"], 0)
        self.assertIn("taker buys", out["read"])


class TestLiveValidation(unittest.TestCase):
    def test_side_sign_test_verifies_buy_prints_rising(self):
        now = datetime.now(timezone.utc)
        trades, price = [], 60_000
        for i in range(60):
            side = "buy" if i % 2 else "sell"
            price += 1 if side == "buy" else -1             # buys lift, sells hit
            trades.append({"trade_id": 1_000_000 - i, "side": side, "size": "0.01",
                           "price": str(price),
                           "time": (now - timedelta(seconds=120 - i)).isoformat().replace("+00:00", "Z")})
        trades.reverse()                                   # newest first, like the API

        def fake_get(url):
            if "trades" in url:
                return trades
            return {"bid": "60000", "ask": "60001"}

        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "live.json"
            saved = (tape.LIVE_OUT, tape._get)
            tape.LIVE_OUT, tape._get = out, fake_get
            try:
                rc = tape.live()
            finally:
                tape.LIVE_OUT, tape._get = saved
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text())
        self.assertTrue(payload["side_verified"])
        self.assertGreaterEqual(payload["side_agreement"], 0.55)
