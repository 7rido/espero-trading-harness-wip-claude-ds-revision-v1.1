"""The optics card renders markets, connections and sources; empty without a snapshot."""
import json
import pathlib
import tempfile
import unittest

from espero2 import dashboard


def _sample():
    return {
        "at": "2026-10-31T13:40:00Z",
        "markets": [{"coin": "BTC", "product": "BTC-USD", "price": 77478.0, "state": "up/low/low",
                     "funding_binance": 2.7, "funding_hl": 11.0, "oi_hl": 41000,
                     "liq_long": 5106000, "liq_short": 39925000, "e1": {"down_break": False}},
                    {"coin": "SOL", "product": "SOL-USD", "price": 95.0, "state": "down/high/high",
                     "funding_binance": 2.0, "funding_hl": 8.2, "oi_hl": 5400000,
                     "liq_long": 167000, "liq_short": 67000, "e1": {"down_break": True}}],
        "connections": [{"name": "coinbase products", "via": "GET /products", "ok": True,
                         "latency_ms": 120, "detail": ""},
                        {"name": "hyperliquid perps", "via": "POST /info", "ok": True,
                         "latency_ms": 80, "detail": ""}],
        "sources": [{"source": "substrate.metrics", "ok": True, "detail": "105,120 rows"},
                    {"source": "aggr.forward5m", "ok": False, "detail": "no files"}],
        "flags": ["HL spot book-only"],
    }


class TestOpticsCard(unittest.TestCase):
    def setUp(self):
        self.saved = dashboard.OPTICS

    def tearDown(self):
        dashboard.OPTICS = self.saved

    def _write(self, payload):
        d = tempfile.mkdtemp()
        p = pathlib.Path(d) / "optics.json"
        p.write_text(json.dumps(payload))
        return p

    def test_renders_markets_connections_and_sources(self):
        dashboard.OPTICS = self._write(_sample())
        card = dashboard._optics_card()
        for needle in ("operator optics", "BTC", "SOL", "connections", "coinbase products",
                       "substrate.metrics", "BREAK", "41.0k"):
            self.assertIn(needle, card)

    def test_is_empty_without_a_snapshot(self):
        dashboard.OPTICS = pathlib.Path(tempfile.gettempdir()) / "does-not-exist-optics.json"
        self.assertEqual(dashboard._optics_card(), "")
