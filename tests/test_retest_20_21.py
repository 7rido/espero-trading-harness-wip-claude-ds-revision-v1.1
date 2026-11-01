"""Tests for the #20/#21 forecast helpers. No market data is read."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from research.retest_20_21 import classify, evaluate_events


def frame(signal, target, days=20, per_day=10):
    rows = []
    for d in range(days):
        for i in range(per_day):
            rows.append({"day": pd.Timestamp("2026-01-01") + pd.Timedelta(days=d),
                         "signal": signal[i], "target": target[i]})
    return pd.DataFrame(rows)


class EvaluateEventsTest(unittest.TestCase):
    def test_perfect_signal_has_ic_one(self):
        vals = np.arange(10, dtype=float)
        out = evaluate_events(frame(vals, vals * 0.001), "day", "signal", "target")
        self.assertAlmostEqual(out["ic"], 1.0)
        self.assertGreater(out["spread_bps"], 0)
        self.assertEqual(out["n_days"], 20)

    def test_reversed_signal_has_ic_minus_one(self):
        vals = np.arange(10, dtype=float)
        out = evaluate_events(frame(vals, -vals * 0.001), "day", "signal", "target")
        self.assertAlmostEqual(out["ic"], -1.0)

    def test_thin_days_are_dropped(self):
        vals = np.arange(10, dtype=float)
        df = frame(vals, vals * 0.001)
        thin = pd.DataFrame({"day": [pd.Timestamp("2026-02-01")] * 3,
                             "signal": [1.0, 2.0, 3.0], "target": [0.1, 0.2, 0.3]})
        out = evaluate_events(pd.concat([df, thin], ignore_index=True), "day",
                              "signal", "target")
        self.assertEqual(out["n_days"], 20)
        self.assertEqual(out["n_events"], 200)

    def test_constant_signal_has_no_ic(self):
        vals = np.arange(10, dtype=float)
        df = frame(np.ones(10), vals * 0.001)
        out = evaluate_events(df, "day", "signal", "target")
        self.assertEqual(out["verdict"], "NO DATA")


class ClassifyTest(unittest.TestCase):
    def test_forecasts(self):
        r = {"ic": 0.05, "ic_lo": 0.01, "spread_net_bps": 2.0}
        self.assertEqual(classify(r), "FORECASTS")

    def test_weak(self):
        r = {"ic": 0.05, "ic_lo": 0.01, "spread_net_bps": -5.0}
        self.assertEqual(classify(r), "WEAK FORECAST")

    def test_none(self):
        r = {"ic": 0.05, "ic_lo": -0.01, "spread_net_bps": 2.0}
        self.assertEqual(classify(r), "NO FORECAST")

    def test_no_data(self):
        self.assertEqual(classify({"verdict": "NO DATA"}), "NO DATA")


if __name__ == "__main__":
    unittest.main()
