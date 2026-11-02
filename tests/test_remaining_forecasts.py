"""Tests for the remaining-findings forecast helpers. No market data is read."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from research.remaining_forecasts import (
    bh,
    block_bootstrap,
    clustered_mean,
    deflated_sharpe,
    mad_winsor_row,
    max_drawdown,
    normal_p,
    nw_t,
    rank_ic,
)


class RankIcTest(unittest.TestCase):
    def test_perfect_positive(self):
        x = pd.Series([1, 2, 3, 4, 5])
        self.assertAlmostEqual(rank_ic(x, x * 2 + 1), 1.0)

    def test_perfect_negative(self):
        x = pd.Series([1, 2, 3, 4, 5])
        self.assertAlmostEqual(rank_ic(x, -x), -1.0)

    def test_monotone_transform_is_invariant(self):
        x = pd.Series([1, 2, 3, 4, 5, 6])
        y = pd.Series([2, 1, 4, 3, 6, 5])
        self.assertAlmostEqual(rank_ic(x, np.exp(y)), rank_ic(x, y))

    def test_degenerate_is_nan(self):
        x = pd.Series([1, 1, 1, 1, 1])
        y = pd.Series([1, 2, 3, 4, 5])
        self.assertTrue(np.isnan(rank_ic(x, y)))


class NeweyWestTest(unittest.TestCase):
    def test_positive_mean_is_significant(self):
        rng = np.random.default_rng(3)
        x = rng.normal(1.0, 1.0, 500)
        self.assertGreater(nw_t(x, lags=4), 5.0)

    def test_zero_mean_is_not(self):
        rng = np.random.default_rng(3)
        x = rng.normal(0.0, 1.0, 500)
        self.assertLess(abs(nw_t(x, lags=4)), 3.0)

    def test_autocorrelated_series_has_a_wider_error(self):
        rng = np.random.default_rng(4)
        e = rng.normal(0.0, 1.0, 2000)
        x = np.zeros_like(e)
        for i in range(1, len(x)):
            x[i] = 0.9 * x[i - 1] + e[i]
        # the same mean, but the NW error at a long lag is larger than the iid error
        naive = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        self.assertLess(abs(nw_t(x, lags=5)), abs(naive))


class BootstrapTest(unittest.TestCase):
    def test_ci_brackets_mean(self):
        x = np.linspace(-1, 1, 100)
        out = block_bootstrap(x, reps=500)
        self.assertLessEqual(out["lo"], out["mean"])
        self.assertGreaterEqual(out["hi"], out["mean"])

    def test_small_sample_is_nan_ci(self):
        out = block_bootstrap([0.1, 0.2])
        self.assertTrue(np.isnan(out["lo"]))


class MultipleTestingTest(unittest.TestCase):
    def test_bh_matches_expected_order(self):
        q = bh([0.01, 0.04, 0.03, 0.20])
        self.assertLess(q[0], q[2])
        self.assertLessEqual(q[2], q[1])
        self.assertAlmostEqual(q[3], 0.20)

    def test_nan_passes_through(self):
        q = bh([0.01, float("nan"), 0.5])
        self.assertTrue(np.isnan(q[1]))


class WinsorTest(unittest.TestCase):
    def test_clips_one_outlier(self):
        row = pd.Series([0.0, 0.01, -0.01, 0.02, 0.0, 10.0])
        out = mad_winsor_row(row)
        self.assertLess(out.iloc[-1], 1.0)
        self.assertAlmostEqual(out.iloc[1], 0.01)

    def test_small_row_unchanged(self):
        row = pd.Series([0.0, 0.01, 10.0])
        self.assertTrue(mad_winsor_row(row).equals(row))


class SharpeTest(unittest.TestCase):
    def test_deflated_sharpe_is_a_probability(self):
        p = deflated_sharpe(1.0, 4, 60, 12)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_more_trials_lowers_the_probability(self):
        one = deflated_sharpe(0.8, 1, 60, 12)
        many = deflated_sharpe(0.8, 50, 60, 12)
        self.assertGreater(one, many)

    def test_max_drawdown(self):
        r = pd.Series([0.1, -0.2, 0.05])
        self.assertAlmostEqual(max_drawdown(r), -0.2)


class ClusteredMeanTest(unittest.TestCase):
    def test_trade_weighted_not_day_mean(self):
        df = pd.DataFrame({
            "day": ["a", "a", "a", "b", "c"],
            "x": [0.01, 0.01, 0.01, 0.10, 0.02],
        })
        out = clustered_mean(df, "x")
        self.assertAlmostEqual(out["mean_bps"], 300.0)
        self.assertAlmostEqual(out["day_mean_bps"], 433.3333333333333)
        self.assertEqual(out["events"], 5)

    def test_normal_p(self):
        self.assertAlmostEqual(normal_p(0.0), 1.0)
        self.assertLess(normal_p(3.0), 0.01)


if __name__ == "__main__":
    unittest.main()
