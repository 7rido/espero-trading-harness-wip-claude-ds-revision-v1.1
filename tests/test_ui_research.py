"""The TUI research view renders the live state dicts without touching the network."""
import unittest

from espero2 import ui


class TestResearchRows(unittest.TestCase):
    def test_e1_rows_have_no_statistic(self):
        d = {"window": ["2026-10-31", "2027-04-30"], "pct": 12.5, "elapsed_days": 22,
             "total_days": 181, "events": 40, "forced": 12, "next_look": "2026-11-30",
             "look_number": 1, "boundary": 4.8}
        rows = ui.e1_rows(d)
        text = " ".join(str(x) for r in rows for x in r)
        self.assertIn("12", text)
        for banned in ("return", "t-stat", "z="):
            self.assertNotIn(banned, text)

    def test_carry_rows(self):
        d = {"positions": {"BTC": {"spot_entry": 77000.0, "perp_entry": 77100.0,
                                   "funding_cum": 1.2, "fees": 0.95, "net": 0.3}}}
        rows = ui.carry_rows(d)
        self.assertEqual(rows[0][0], "BTC")

    def test_optics_rows_flag_cascade(self):
        d = {"markets": [{"coin": "BTC", "state": "up/low/low", "funding_binance": 2.7,
                          "funding_hl": 11.0, "oi_hl": 40000, "cascade": True, "e1": {}}]}
        self.assertEqual(ui.optics_rows(d)[0][-1], "CASCADE")

    def test_forecast_rows_keep_label(self):
        d = {"rows": [{"coin": "BTC", "state": "up/low/low", "median20": -9,
                       "share_up": 0.5, "label": "CONTEXT ONLY"}]}
        self.assertEqual(ui.forecast_rows(d)[0][-1], "CONTEXT ONLY")

    def test_tape_row(self):
        d = {"source": "coinbase-spot", "prints": 1000, "buy_share": 0.47,
             "cvd": -0.23, "divergence": "none"}
        self.assertEqual(ui.tape_row(d)[0][0], "coinbase-spot")
