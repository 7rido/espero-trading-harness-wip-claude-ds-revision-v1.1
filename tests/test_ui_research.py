"""The TUI research view renders the live state dicts without touching the network."""
import unittest
from unittest import mock

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


class TestUiPolish(unittest.TestCase):
    def test_clip_keeps_short_and_marks_long(self):
        self.assertEqual(ui._clip("short", 10), "short")
        out = ui._clip("a much longer note that must not wrap", 12)
        self.assertEqual(len(out), 12)
        self.assertTrue(out.endswith("…"))

    def test_status_line_uses_snapshots(self):
        with mock.patch.object(ui, "_json", side_effect=lambda p: {
                "research/e1_progress.json": {"forced": 3, "next_look": "2026-11-30", "boundary": 4.8},
                "research/carry_sleeve.json": {"net": 1.25, "positions": {"BTC": {}}},
                "research/optics.json": {"at": "2026-11-01T02:30:00+00:00"}}.get(p, {})):
            line = ui.status_line()
        self.assertIn("E1 3 forced", line)
        self.assertIn("carry net +1.25", line)
        self.assertIn("optics", line)


class TestLiquidityRows(unittest.TestCase):
    def test_rows_from_snapshot(self):
        d = {"open_interest_usd": 10.75e9, "volume_24h_usd": 2.51e9, "liq_24h_usd": 27.65e6,
             "long_share": 0.75, "contracts": 180, "taker_fee_pct": 4.5, "maker_fee_pct": 1.5}
        rows = ui.liquidity_rows(d)
        self.assertEqual(rows[0][1], "$10.75B")
        self.assertIn("75%", rows[2][1])

    def test_empty_is_empty(self):
        self.assertEqual(ui.liquidity_rows({}), [])
