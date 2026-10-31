"""The forecast rubric: labels are gated, capped and never trade words."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_mod", ROOT / "research" / "forecast.py")
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)


def cell(fdr: bool = False, median: float = -200.0, n: int = 2000, share: float = 0.4) -> dict:
    return {"state": "up/low/low", "h": 20, "n": n, "median_bps": median, "p10": -1000,
            "p90": 1000, "share_up": share, "fdr_pass": fdr}


def states(fdr: bool = False) -> dict:
    return {("up/low/low", 20): cell(fdr=fdr),
            ("up/low/low", 5): {**cell(fdr=fdr), "h": 5, "median_bps": -30.0}}


def market(break_: bool = False, spread: float = 1.0) -> dict:
    return {"coin": "BTC", "product": "BTC-USD", "state": "up/low/low",
            "spread_bps": spread, "e1": {"down_break": break_}}


E1_OPEN = {"window_state": "open", "forced_down_breaks": 0}


class TestRubric(unittest.TestCase):
    def build(self, fdr=False, break_=False, spread=1.0):
        return fc.build_rows([market(break_, spread)], states(fdr), E1_OPEN, holds=0)[0]

    def test_fdr_failure_is_context_only(self):
        row = self.build()
        self.assertEqual(row["label"], "CONTEXT ONLY")
        self.assertIn("fails multiplicity", row["reason"])
        self.assertAlmostEqual(row["net_median20"], -200.0 - 10.0)

    def test_fdr_pass_without_holds_is_watch(self):
        self.assertEqual(self.build(fdr=True)["label"], "WATCH")

    def test_e1_break_is_forward_test(self):
        self.assertEqual(self.build(break_=True)["label"], "E1-FORWARD")

    def test_missing_cell_is_unmapped(self):
        row = fc.build_rows([market()], {}, E1_OPEN, holds=0)[0]
        self.assertEqual(row["label"], "UNMAPPED")

    def test_no_trade_words_ever(self):
        for fdr in (False, True):
            for brk in (False, True):
                self.assertNotIn(self.build(fdr, brk)["label"], {"BUY", "SELL", "TRADE"})

    def test_cost_hurdle_is_added(self):
        row = self.build(spread=100.0)
        self.assertAlmostEqual(row["cost_bps"], 109.0)
        self.assertAlmostEqual(row["net_median20"], -309.0)


class TestCap(unittest.TestCase):
    def test_cap_blocks_anything_above_watch_without_holds(self):
        self.assertEqual(fc.cap("TRADE", 0), "WATCH")
        self.assertEqual(fc.cap("WATCH", 0), "WATCH")
        self.assertEqual(fc.cap("UNMAPPED", 0), "UNMAPPED")

    def test_cap_allows_hold_rank_when_holds_exist(self):
        self.assertEqual(fc.cap("TRADE", 1), "TRADE")


class TestWilson(unittest.TestCase):
    def test_bounds_for_half_of_a_hundred(self):
        lo, hi = fc.wilson(0.5, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)

    def test_empty_sample_is_nan(self):
        lo, hi = fc.wilson(0.5, 0)
        self.assertNotEqual(lo, lo)
        self.assertNotEqual(hi, hi)
