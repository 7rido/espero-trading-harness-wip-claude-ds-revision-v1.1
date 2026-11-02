"""Funding overlay: the state is computed from trailing hourly funding only."""
import importlib.util
import pathlib
import unittest

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_funding", ROOT / "research" / "forecast_funding.py")
funding = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(funding)


class TestFundingState(unittest.TestCase):
    def test_state_reads_trailing_window(self):
        end = pd.Timestamp("2026-11-01 00:00:00")
        ts = pd.date_range(end=end, periods=400 * 24, freq="h")
        rate = np.full(len(ts), 0.00001)
        rate[-168:] = 0.00003
        df = pd.DataFrame({"coin": "TEST", "ts": ts, "rate": rate, "interval_hours": 1.0})
        out = funding.state("TEST", df)
        self.assertEqual(out["coin"], "TEST")
        self.assertEqual(out["rows"], 400 * 24)
        self.assertIsNotNone(out["fund7_bps_hour"])
        self.assertAlmostEqual(out["last_rate_bps_hour"], 0.3, places=6)
        self.assertIn(out["fund_state"], {"high", "low"})
        self.assertGreaterEqual(out["fund_pct"], 0.0)
        self.assertLessEqual(out["fund_pct"], 1.0)


if __name__ == "__main__":
    unittest.main()
