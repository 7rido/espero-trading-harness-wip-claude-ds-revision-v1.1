"""The optics card renders from the snapshot and disappears when the snapshot is absent."""
import json
import pathlib
import tempfile
import unittest

from espero2 import dashboard


class TestOpticsCard(unittest.TestCase):
    def setUp(self):
        self.saved = dashboard.OPTICS

    def tearDown(self):
        dashboard.OPTICS = self.saved

    def test_renders_a_snapshot(self):
        sample = {"at": "2026-10-31T13:40:00Z", "coins": [{
            "coin": "BTC", "price": 77478.0, "state": "up/low/low",
            "funding_binance": 2.7, "funding_hl": 10.9, "oi_hl": 41000,
            "liq_long": 5106000, "liq_short": 39925000, "e1": {"down_break": False}}], "flags": []}
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "optics.json"
            p.write_text(json.dumps(sample))
            dashboard.OPTICS = p
            card = dashboard._optics_card()
        for needle in ("operator optics", "BTC", "up/low/low", "41.0k", "L $5,106k"):
            self.assertIn(needle, card)

    def test_is_empty_without_a_snapshot(self):
        dashboard.OPTICS = pathlib.Path(tempfile.gettempdir()) / "does-not-exist-optics.json"
        self.assertEqual(dashboard._optics_card(), "")

    def test_break_is_highlighted(self):
        sample = {"at": "x", "coins": [{
            "coin": "SOL", "price": 95.0, "state": "down/high/high",
            "funding_binance": 2.0, "funding_hl": 10.9, "oi_hl": 5400000,
            "liq_long": 167000, "liq_short": 67000, "e1": {"down_break": True}}], "flags": []}
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "optics.json"
            p.write_text(json.dumps(sample))
            dashboard.OPTICS = p
            card = dashboard._optics_card()
        self.assertIn("BREAK", card)
