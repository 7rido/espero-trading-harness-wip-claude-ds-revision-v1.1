"""Coverage overlay feature math: trailing state and no future leakage."""
import importlib.util
import pathlib
import unittest

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_coverage", ROOT / "research" / "forecast_coverage.py")
coverage = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(coverage)


def bars(n: int = 90) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100.0 * np.power(1.005, np.arange(n))
    return pd.DataFrame({
        "coin": "TEST",
        "date": dates,
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": np.full(n, 1000.0),
    })


class TestCoverageFeatures(unittest.TestCase):
    def test_trailing_state_exists_after_warmup(self):
        out = coverage.features(bars(90))
        last = out.dropna(subset=["state2"]).iloc[-1]
        self.assertEqual(last["trend"], "up")
        self.assertIn(last["state2"], {"up/low", "up/high"})
        self.assertGreater(last["rv"], 0)
        self.assertEqual(last["known_time"], last["date"] + pd.Timedelta(days=1))

    def test_future_bars_do_not_change_past_features(self):
        full = coverage.features(bars(90))
        cut = coverage.features(bars(70))
        cols = ["ret60", "rv", "rv_w", "rv_m", "vol_pct", "state2"]
        pd.testing.assert_frame_equal(
            full.loc[:69, cols].reset_index(drop=True),
            cut.loc[:, cols].reset_index(drop=True),
            check_dtype=False,
        )


if __name__ == "__main__":
    unittest.main()
