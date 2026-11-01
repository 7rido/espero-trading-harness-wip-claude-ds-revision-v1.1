"""E1 progress is calendar and counts only."""
import datetime as dt
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("e1p", ROOT / "research" / "e1_progress.py")
e1p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e1p)


class TestProgress(unittest.TestCase):
    def test_start_of_window(self):
        p = e1p.progress(dt.date(2026, 10, 31), forced=0, events=0)
        self.assertEqual(p["elapsed_days"], 0)
        self.assertEqual(p["pct"], 0.0)
        self.assertEqual(p["next_look"], "2026-11-30")

    def test_mid_window(self):
        p = e1p.progress(dt.date(2027, 1, 15), forced=12, events=40)
        self.assertEqual(p["next_look"], "2027-01-31")
        self.assertEqual(p["look_number"], 3)
        self.assertGreater(p["pct"], 40)

    def test_after_last_look(self):
        p = e1p.progress(dt.date(2027, 4, 30), forced=30, events=100)
        self.assertEqual(p["next_look"], "2027-04-30")
        self.assertEqual(p["pct"], 100.0)

    def test_no_statistic_fields(self):
        p = e1p.progress(dt.date(2027, 2, 1), forced=5, events=20)
        for banned in ("return", "t_stat", "z", "mean_bps"):
            self.assertNotIn(banned, p)
