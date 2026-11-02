"""Forecast audit scoring helpers: empirical CRPS and the summary shape."""
import importlib.util
import math
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_audit", ROOT / "research" / "forecast_audit.py")
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class TestCRPS(unittest.TestCase):
    def test_two_point_ensemble(self):
        self.assertAlmostEqual(audit.crps_ensemble(0.5, [0.0, 1.0]), 0.25)

    def test_single_point_is_absolute_error(self):
        self.assertAlmostEqual(audit.crps_ensemble(1.0, [3.0]), 2.0)

    def test_constant_ensemble(self):
        self.assertAlmostEqual(audit.crps_ensemble(4.0, [5.0, 5.0]), 1.0)

    def test_empty_or_nonfinite_is_nan(self):
        self.assertTrue(math.isnan(audit.crps_ensemble(1.0, [])))
        self.assertTrue(math.isnan(audit.crps_ensemble(float("nan"), [1.0])))

    def test_infinite_sample_values_are_ignored(self):
        self.assertAlmostEqual(audit.crps_ensemble(1.0, [1.0, float("nan")]), 0.0)


class TestScore(unittest.TestCase):
    def test_summary_uses_only_finite_rows(self):
        rows = [
            {"crps": 1.0, "brier": 0.25, "pit": 0.5},
            {"crps": 2.0, "brier": 0.25, "pit": float("nan")},
            {"crps": float("nan"), "brier": 0.0, "pit": 0.5},
        ]
        out = audit._score(rows)
        self.assertEqual(out["n"], 1)
        self.assertAlmostEqual(out["crps_mean"], 1.0)
        self.assertEqual(len(out["pit_bins"]), 10)

    def test_empty(self):
        self.assertEqual(audit._score([]), {"n": 0})


if __name__ == "__main__":
    unittest.main()
