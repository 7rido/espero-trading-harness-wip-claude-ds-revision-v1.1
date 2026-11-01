"""Manual buy/close must handle shorts and never double-count a replacement."""
import types
import unittest
from unittest.mock import patch

from espero2 import ui


class FakeStore:
    def __init__(self, qty, cash=1000.0, entry=100.0):
        self.state = {"cash": cash, "qty": qty, "entry_px": entry, "entry_ts": 0}
        self.orders = []

    def get_state(self, coin):
        return dict(self.state)

    def set_state(self, coin, **kw):
        self.state.update(kw)

    def order(self, *a, **k):
        self.orders.append(a)

    def mark(self, *a, **k):
        pass


class Book:
    bid, ask, mid = 99.0, 101.0, 100.0


class TestManual(unittest.TestCase):
    def test_buy_refused_while_short(self):
        store = FakeStore(qty=-0.5)
        with patch.object(ui.hl, "book", return_value=Book()):
            ui.buy_manual(types.SimpleNamespace(print=lambda *a, **k: None), store, "BTC", 100)
        self.assertEqual(store.orders, [])
        self.assertEqual(store.state["qty"], -0.5)

    def test_close_short_buys_back_at_ask(self):
        store = FakeStore(qty=-0.5, cash=1500.0, entry=100.0)
        with patch.object(ui.hl, "book", return_value=Book()):
            ui.close_manual(types.SimpleNamespace(print=lambda *a, **k: None), store, "BTC")
        self.assertEqual(store.orders[0][2], "buy")
        self.assertEqual(store.state["qty"], 0.0)
        self.assertLess(store.state["cash"], 1500.0)      # covering a short costs cash

    def test_close_long_sells_bid(self):
        store = FakeStore(qty=0.5, cash=500.0, entry=100.0)
        with patch.object(ui.hl, "book", return_value=Book()):
            ui.close_manual(types.SimpleNamespace(print=lambda *a, **k: None), store, "BTC")
        self.assertEqual(store.orders[0][2], "sell")
        self.assertGreater(store.state["cash"], 500.0)
