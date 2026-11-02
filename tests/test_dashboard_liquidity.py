"""The liquidity card renders the three layers, disappears cleanly, and flags a stale snapshot."""
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone

from espero2 import dashboard


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def snapshot(at=None, coin="BTC"):
    return {
        "at": at or now(),
        "errors": [],
        "markets": [{
            "coin": coin, "mid": 77810.61, "mark": 77933.0,
            "spread_bps": 0.12, "basis_bps": 21.3,
            "flow": {"prints": 1000, "span_min": 5.1, "buy_share": 0.657, "net_usd": 83_334.6},
            "pools": [
                {"side": "bid", "price": 77555.4, "distance_pct": -0.273, "usd": 12_120_000,
                 "share": 0.63, "levels": 26},
                {"side": "ask", "price": 77969.64, "distance_pct": 0.26, "usd": 15_240_000,
                 "share": 0.78, "levels": 30},
            ],
            "clusters": [
                {"side": "long", "price": 69940.64, "distance_pct": -10.26, "usd": 75_980_000,
                 "count": 1, "long_usd": 75_980_000, "short_usd": 0.0},
                {"side": "short", "price": 87655.82, "distance_pct": 12.48, "usd": 133_970_000,
                 "count": 2, "long_usd": 0.0, "short_usd": 133_970_000},
            ],
            "ladder": {"positions": 234, "with_liq": 182, "positions_at": at or now(),
                       "sample_usd": 1_670_000_000, "oi_usd": 3_160_000_000,
                       "coverage_pct": 53.0, "nearest_long_pct": 7.3, "nearest_short_pct": 10.4},
        }],
        "read": "Neither is a forecast.",
    }


class TestLiquidityCard(unittest.TestCase):
    def setUp(self):
        self.saved = dashboard.LIQUIDITY_MAP

    def tearDown(self):
        dashboard.LIQUIDITY_MAP = self.saved

    def _write(self, data) -> pathlib.Path:
        p = pathlib.Path(tempfile.mkdtemp()) / "liquidity_map.json"
        p.write_text(json.dumps(data))
        return p

    def test_card_renders_all_three_layers(self):
        dashboard.LIQUIDITY_MAP = self._write(snapshot())
        card = dashboard._order_flow_liquidity_card()
        for needle in ("order flow &amp; liquidity map", "BTC", "12.12M", "15.24M",
                       "long liq", "short liq", "1.67B", "3.16B", "53%", "hyperliquid",
                       "not a signal", "Neither is a forecast"):
            self.assertIn(needle, card)

    def test_missing_snapshot_renders_nothing(self):
        dashboard.LIQUIDITY_MAP = pathlib.Path(tempfile.gettempdir()) / "no-liquidity-map.json"
        self.assertEqual(dashboard._order_flow_liquidity_card(), "")

    def test_stale_snapshot_is_flagged(self):
        dashboard.LIQUIDITY_MAP = self._write(snapshot(at="2000-01-01T00:00:00+00:00"))
        self.assertIn("stale", dashboard._order_flow_liquidity_card())

    def test_coin_name_is_escaped(self):
        dashboard.LIQUIDITY_MAP = self._write(snapshot(coin="<script>"))
        card = dashboard._order_flow_liquidity_card()
        self.assertIn("&lt;script&gt;", card)
        self.assertNotIn("<script>", card)

    def test_unavailable_market_keeps_the_card(self):
        data = snapshot()
        data["markets"].append({"coin": "ETH", "error": "boom"})
        dashboard.LIQUIDITY_MAP = self._write(data)
        card = dashboard._order_flow_liquidity_card()
        self.assertIn("ETH", card)
        self.assertIn("unavailable", card)
        self.assertIn("boom", card)

    def test_no_position_snapshot_is_named(self):
        data = snapshot()
        data["markets"][0]["ladder"] = {"positions": 0}
        dashboard.LIQUIDITY_MAP = self._write(data)
        self.assertIn("no local Hyperliquid position snapshot", dashboard._order_flow_liquidity_card())


if __name__ == "__main__":
    unittest.main()
