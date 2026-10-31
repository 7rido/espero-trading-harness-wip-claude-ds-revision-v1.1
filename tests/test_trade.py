"""The unified trade router: guards intact, no live host anywhere."""
import unittest
from unittest.mock import patch

from espero2 import trade


class TestTradeRouter(unittest.TestCase):
    def test_unknown_venue_is_refused(self):
        with self.assertRaises(trade.Refused):
            trade.place("kraken", "BTC", "buy", notional=1.0, confirm=True)

    def test_alpaca_needs_qty(self):
        with self.assertRaises(trade.Refused):
            trade.place("alpaca", "AAPL", "buy", notional=1.0, confirm=True)

    def test_coinbase_needs_notional_and_confirm(self):
        with self.assertRaises(trade.Refused):
            trade.place("coinbase", "BTC-USD", "buy", qty=1, confirm=True)
        with self.assertRaises(trade.cb.Refused):
            trade.place("coinbase", "BTC-USD", "buy", notional=1.0, confirm=False)

    def test_hyperliquid_needs_notional_and_confirm(self):
        with self.assertRaises(trade.Refused):
            trade.place("hyperliquid", "BTC", "buy", qty=1, confirm=True)
        with self.assertRaises(trade.hl_signed.Refused):
            trade.place("hyperliquid", "BTC", "buy", notional=12.0, confirm=False)

    def test_routing_passes_the_right_arguments(self):
        with patch.object(trade.alpaca, "place_order", return_value={"id": "x"}) as m:
            out = trade.place("alpaca", "AAPL", "buy", qty=3, confirm=True)
        m.assert_called_once_with("AAPL", 3, "buy", order_type="market", limit_price=None,
                                 confirm=True)
        self.assertEqual(out["venue"], "alpaca")
        self.assertEqual(out["mode"], "paper")
