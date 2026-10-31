"""Signal provenance and the dashboard's research card."""
import json
import pathlib
import sqlite3
import tempfile
import unittest

from espero2.dashboard import research_state
from espero2.store import Store


class TestSignalMetadata(unittest.TestCase):
    def test_new_signals_carry_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(pathlib.Path(d) / "j.db")
            s.signal(1, "BTC", "long", 100.0, "sma", prereg_id="P1",
                     model_version="sma20/50", inputs_hash="abc", gate_state="retired")
            row = s.db.execute("SELECT reason, prereg_id, model_version, inputs_hash, gate_state "
                               "FROM signals").fetchone()
            s.close()
        self.assertEqual(row, ("sma", "P1", "sma20/50", "abc", "retired"))

    def test_an_old_journal_migrates(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "old.db"
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE signals(ts INTEGER, coin TEXT, side TEXT, price REAL, reason TEXT)")
            con.execute("INSERT INTO signals VALUES (1,'BTC','long',1.0,'old')")
            con.commit(); con.close()
            s = Store(path)
            cols = {r[1] for r in s.db.execute("PRAGMA table_info(signals)").fetchall()}
            rows = s.db.execute("SELECT reason, prereg_id FROM signals").fetchall()
            s.close()
        self.assertTrue({"prereg_id", "model_version", "inputs_hash", "gate_state"} <= cols)
        self.assertEqual(rows[0][0], "old")          # old rows keep their reason, empty provenance


class TestResearchCard(unittest.TestCase):
    def test_state_reads_e1_and_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "e1_status.json").write_text(json.dumps(
                {"window": ["2026-10-31", "2027-04-30"], "window_state": "open",
                 "events": 0, "days_with_events": 0, "forced_down_breaks": 0}))
            st = research_state(root)
        self.assertEqual(st["e1"]["window_state"], "open")
        self.assertIn("counts", st["ledger"])


class TestAlpacaCard(unittest.TestCase):
    def test_a_card_with_positions_and_orders_renders(self):
        from espero2.dashboard import _alpaca_card
        html = _alpaca_card({"account": {"cash": "100000", "buying_power": "394587",
                                         "portfolio_value": "100000", "status": "ACTIVE"},
                             "positions": [{"symbol": "BTCUSD", "qty": "0.001", "market_value": "99.8",
                                            "unrealized_pl": "0.03"}],
                             "orders": [{"symbol": "AAPL", "side": "buy", "qty": "1",
                                         "type": "market", "status": "accepted"}]})
        self.assertIn("BTCUSD", html)
        self.assertIn("AAPL", html)
        self.assertIn("394587", html)

    def test_unavailable_is_a_sentence_not_a_crash(self):
        from espero2.dashboard import _alpaca_card
        self.assertIn("unavailable", _alpaca_card({}))

    def test_fetch_failure_returns_empty(self):
        from unittest.mock import patch
        from espero2 import dashboard, alpaca
        with patch.object(alpaca, "account", side_effect=RuntimeError("down")):
            self.assertEqual(dashboard.alpaca_state(), {})
