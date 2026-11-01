"""The #45 forecast retest: tags, causal features, scores and metrics on synthetic data."""
import importlib.util
import pathlib
import unittest

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("liq45_forecast", ROOT / "research" / "liq45_forecast.py")
lf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lf)


class TestTags(unittest.TestCase):
    def test_prior_observed_day_only(self):
        ev = pd.DataFrame({"day": [100, 100, 100, 101, 101, 101, 102],
                           "ts": [1, 2, 3, 4, 5, 6, 7],
                           "s": [0.1, 0.2, 0.3, 0.1, 0.2, 0.3, 0.25]})
        tags = lf.prior_day_tags(ev).tolist()
        self.assertEqual(tags[:3], ["middle", "middle", "middle"])
        self.assertEqual(tags[3:6], ["organic", "middle", "forced"])
        # 0.25 is above day 101's 2/3 quantile (0.233) -> forced. A same-day quantile
        # (single 0.25 -> q1=q2=0.25) would call it organic, so this catches a same-day leak.
        self.assertEqual(tags[6], "forced")

    def test_terciles_are_cross_sectional(self):
        ev = pd.DataFrame({"day": [1, 1, 1, 2], "ts": [1, 2, 3, 4], "s": [0.1, 0.2, 0.3, 0.2]})
        self.assertEqual(lf.prior_day_tags(ev).tolist()[-1], "middle")


class TestScores(unittest.TestCase):
    def test_percentile_ties(self):
        np.testing.assert_allclose(lf.percentile(np.array([1.0, 2.0, 3.0]), np.array([2.0])), [2 / 3])

    def test_composite_sign_flip(self):
        train = pd.DataFrame({"x": [-0.1, -0.05, 0.0, 0.05]})
        frame = pd.DataFrame({"x": [-0.2, 0.0]})
        score = lf.composite(frame, train, [("x", -1)])
        np.testing.assert_allclose(score, [1.0, 0.5])

    def test_ridge_recovers_a_line(self):
        X = np.array([[0.0], [1.0], [2.0], [3.0]])
        y = 1.0 + 2.0 * X[:, 0]
        w = lf.ridge_fit(X, y, lam=0.0)
        np.testing.assert_allclose(w, [1.0, 2.0], atol=1e-9)
        np.testing.assert_allclose(lf.ridge_predict(w, X), y, atol=1e-9)

    def test_auc_and_top_quantile(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([0.1, 0.2, 0.8, 0.9])
        self.assertAlmostEqual(lf.auc(y, p), 1.0)
        top = lf.top_quantile(np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
                              np.array([0.1, 0.2, 0.3, 0.4, 0.5]), 0.4)
        self.assertEqual(top["n"], 2)
        self.assertAlmostEqual(top["mean"], 4.5)


class TestCalendar(unittest.TestCase):
    def test_first_two_and_last_day_are_dropped(self):
        self.assertFalse(lf._day_allowed(int(pd.Timestamp("2024-06-01", tz="UTC").timestamp()) // 86400))
        self.assertFalse(lf._day_allowed(int(pd.Timestamp("2024-06-02", tz="UTC").timestamp()) // 86400))
        self.assertTrue(lf._day_allowed(int(pd.Timestamp("2024-06-15", tz="UTC").timestamp()) // 86400))
        self.assertFalse(lf._day_allowed(int(pd.Timestamp("2024-06-30", tz="UTC").timestamp()) // 86400))

    def test_cut_is_before_the_forward_window(self):
        self.assertLess(lf.CUT, "2026-10-30")
        self.assertLess(lf.MONTHLY_CUT, "2026-10-30")


class TestNoLookahead(unittest.TestCase):
    def _bars(self):
        idx = np.array([int(t.timestamp()) for t in
                        pd.date_range("2024-06-01", periods=400, freq="5min", tz="UTC")])
        n = len(idx)
        close = np.full(n, 100.0)
        high = np.full(n, 100.5)
        low = np.full(n, 99.5)
        close[300] = 90.0
        high[300] = 91.0
        low[300] = 89.0
        volume = np.ones(n)
        volume[300] = 100.0
        quote = np.full(n, 1_000_000.0)
        taker = np.full(n, 500_000.0)
        return pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                             "volume": volume, "quote": quote, "taker": taker},
                            index=idx // 300 * 300), idx

    def _liq(self, t):
        return pd.DataFrame({"ts": [t + 100], "side": ["sell"], "usd": [1000.0]})

    def test_future_bars_do_not_change_entry_features(self):
        bars, idx = self._bars()
        t = int(idx[300] // 300 * 300)
        liq = self._liq(t)
        kwargs = dict(start="2024-06-01", end="2024-06-03", monthly=True,
                      btc_map={}, funding=(np.array([], dtype="int64"), np.array([], dtype=float)))
        ev1 = lf.build_events("X", bars, liq, **kwargs)
        first = ev1[ev1["ts"] == t].iloc[0]
        bars2 = bars.copy()
        bars2.loc[bars2.index > t, "close"] = 50.0
        bars2.loc[bars2.index > t, "high"] = 51.0
        bars2.loc[bars2.index > t, "low"] = 49.0
        bars2.loc[bars2.index > t, "volume"] = 7.0
        ev2 = lf.build_events("X", bars2, liq, **kwargs)
        second = ev2[ev2["ts"] == t].iloc[0]
        for col in ("s", "liq_count", "ret_1h", "atr_pct", "vol_z", "taker_imb"):
            self.assertEqual(first[col], second[col], col)
        self.assertNotEqual(first["4h_gross"], second["4h_gross"])


if __name__ == "__main__":
    unittest.main()
