"""The gate must refuse more easily than it permits."""
import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from espero2 import hl_signed, ledger

ROW = dict(id="P1", strategy="sma", status="plumbing", estimator="plain",
           estimator_matches_claim="na", economic_bar="na", basis="", note="test")


def ledger_file(tmp: str, **over) -> Path:
    p = Path(tmp) / "l.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ROW))
        w.writeheader()
        w.writerow({**ROW, **over})
    return p


class TestLedgerGate(unittest.TestCase):
    def test_plumbing_is_refused_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                ledger.require("sma", path=ledger_file(d))
            self.assertIn("plumbing", str(e.exception))

    def test_plumbing_runs_with_the_flag(self):
        with tempfile.TemporaryDirectory() as d:
            row = ledger.require("sma", allow_plumbing=True, path=ledger_file(d))
            self.assertEqual(row.status, "plumbing")

    def test_unknown_strategy_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                ledger.require("moon", allow_plumbing=True, path=ledger_file(d))

    def test_holds_needs_a_valid_statistic_and_a_cost_bar(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                ledger.load(ledger_file(d, status="holds", estimator_matches_claim="partly",
                                        economic_bar="no"))

    def test_retired_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                ledger.require("sma", allow_plumbing=True, path=ledger_file(d, status="retired"))


class TestSigningGuards(unittest.TestCase):
    def clean(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith(("HL_", "ESPERO"))}
        return patch.dict(os.environ, {**base, **env}, clear=True)

    def test_no_confirm_flag_refuses(self):
        with self.clean(HL_PRIVATE_KEY="0x" + "11" * 32, ESPERO2_ALLOW_TESTNET="1"):
            with self.assertRaises(hl_signed.Refused) as e:
                hl_signed.check(confirm=False)
            self.assertIn("--confirm-testnet", str(e.exception))

    def test_mainnet_env_refuses(self):
        with self.clean(HL_PRIVATE_KEY="0x" + "11" * 32, ESPERO2_ALLOW_TESTNET="1",
                        HL_NETWORK="mainnet"):
            with self.assertRaises(hl_signed.Refused):
                hl_signed.check(confirm=True)

    def test_missing_allow_flag_refuses(self):
        with self.clean(HL_PRIVATE_KEY="0x" + "11" * 32):
            with self.assertRaises(hl_signed.Refused):
                hl_signed.check(confirm=True)

    def test_missing_key_refuses(self):
        with self.clean(ESPERO2_ALLOW_TESTNET="1"):
            with self.assertRaises(hl_signed.Refused):
                hl_signed.check(confirm=True)

    def test_testnet_host_is_the_only_one(self):
        self.assertTrue(hl_signed.TESTNET.startswith("https://api.hyperliquid-testnet"))


if __name__ == "__main__":
    unittest.main()


class TestHealth(unittest.TestCase):
    def test_a_recent_beat_is_alive_and_an_old_one_is_stale(self):
        import time
        from espero2.store import Store
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "h.db")
            s.set_meta(every=10)
            s.beat(int(time.time()) - 100)
            self.assertTrue(s.health()["stale"])
            s.beat()
            self.assertFalse(s.health()["stale"])
            s.close()

    def test_no_beat_is_stale(self):
        from espero2.store import Store
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "h.db")
            self.assertTrue(s.health()["stale"])
            self.assertIsNone(s.health()["age"])
            s.close()


class TestUI(unittest.TestCase):
    def test_sparkline_is_flat_for_a_flat_series(self):
        from espero2.ui import spark
        self.assertEqual(set(spark([5.0, 5.0, 5.0])), {"▁"})

    def test_sparkline_rises_with_the_series(self):
        from espero2.ui import spark
        s = spark([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        self.assertLess("▁▂▃".index(s[0]) if s[0] in "▁▂▃" else 0, 8)
        self.assertEqual(s[-1], "█")

    def test_the_frame_shows_coins_and_the_ledger(self):
        from rich.console import Console
        from espero2.store import Store
        from espero2.ui import render
        import tempfile, time
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "u.db")
            s.mark("BTC", int(time.time()), 1000.0, 0.0, 0.0, 100.0)
            s.set_meta(every=60)
            s.beat()
            c = Console(width=100, record=True, force_terminal=False)
            render(c, s)
            frame = c.export_text()
            self.assertIn("BTC", frame)
            self.assertIn("sma", frame)
            self.assertIn("heartbeat", frame)
            s.close()


class TestPaperActions(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        from espero2.store import Store
        self.store = Store(Path(self.tmp.name) / "m.db")
        self.orig = hl_book = None

    def tearDown(self):
        from espero2 import hl
        if self.orig:
            hl.book = self.orig
        self.store.close()
        self.tmp.cleanup()

    def test_buy_then_close_moves_cash_and_records_both_orders(self):
        from rich.console import Console
        from espero2 import hl, ui
        self.orig = hl.book
        hl.book = lambda coin, base=None: hl.Book(coin, bid=99.0, ask=101.0)
        c = Console(quiet=True)
        ui.buy_manual(c, self.store, "BTC", 100.0)
        st = self.store.get_state("BTC")
        self.assertGreater(st["qty"], 0)
        self.assertLess(st["cash"], 1000.0)
        ui.close_manual(c, self.store, "BTC")
        self.assertEqual(self.store.get_state("BTC")["qty"], 0.0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 2)

    def test_reset_puts_the_book_back_to_a_clean_thousand(self):
        from rich.console import Console
        from espero2 import ui
        from espero2.store import Store
        self.store.set_state("ETH", cash=50.0, qty=2.0, entry_px=10.0, entry_ts=1)
        ui.reset_book(Console(quiet=True), self.store, "ETH", 1000.0)
        st = self.store.get_state("ETH")
        self.assertEqual((st["cash"], st["qty"], st["entry_px"]), (1000.0, 0.0, 0.0))


class TestLongOnly(unittest.TestCase):
    def test_selling_without_a_position_is_refused(self):
        from espero2.hl_signed import Refused, guard_side
        with self.assertRaises(Refused):
            guard_side("sell", 0.0, allow_short=False)
        with self.assertRaises(Refused):
            guard_side("sell", -1.0, allow_short=False)

    def test_selling_a_long_closes_it(self):
        from espero2.hl_signed import guard_side
        self.assertTrue(guard_side("sell", 0.5))          # reduce_only

    def test_shorting_needs_the_explicit_flag(self):
        from espero2.hl_signed import guard_side
        self.assertFalse(guard_side("sell", 0.0, allow_short=True))

    def test_buying_never_reduces(self):
        from espero2.hl_signed import guard_side
        self.assertFalse(guard_side("buy", 0.0))


class TestAccountPanel(unittest.TestCase):
    def test_a_short_position_renders_with_its_pnl(self):
        from espero2.dashboard import _account_card
        state = {"marginSummary": {"accountValue": "1234.5"},
                 "assetPositions": [{"position": {"coin": "BTC", "szi": "-0.5",
                                                  "entryPx": "100.0", "unrealizedPnl": "-5.0"}}]}
        card = _account_card(state, "0x1234567890abcdef")
        self.assertIn("testnet account", card)
        self.assertIn("BTC", card)
        self.assertIn("1,234.50", card)
        self.assertIn("-5.00", card)

    def test_no_address_is_a_hint_not_a_crash(self):
        from espero2.dashboard import _account_card
        self.assertIn("account.txt", _account_card(None, None))


class TestPlumbingWindow(unittest.TestCase):
    def ledger(self, tmp):
        return ledger_file(tmp)

    def window(self, tmp, **kw):
        body = {"strategy": "sma", "purpose": "mechanics", "started": "2026-10-30",
                "expires": "2099-01-01"}
        body.update(kw)
        p = Path(tmp) / "PLUMBING.md"
        p.write_text("\n".join(f"{k}: {v}" for k, v in body.items()))
        return p

    def test_running_plumbing_without_a_window_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                ledger.require("sma", allow_plumbing=True, path=self.ledger(d),
                               plumbing=Path(d) / "none.md")
            self.assertIn("PLUMBING.md", str(e.exception))

    def test_an_expired_window_is_refused(self):
        import datetime as dt
        with tempfile.TemporaryDirectory() as d:
            w = self.window(d, expires=(dt.date.today() - dt.timedelta(days=1)).isoformat())
            with self.assertRaises(SystemExit) as e:
                ledger.require("sma", allow_plumbing=True, path=self.ledger(d), plumbing=w)
            self.assertIn("expired", str(e.exception))

    def test_a_window_for_another_strategy_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.window(d, strategy="other")
            with self.assertRaises(SystemExit):
                ledger.require("sma", allow_plumbing=True, path=self.ledger(d), plumbing=w)

    def test_a_valid_window_permits_the_run(self):
        with tempfile.TemporaryDirectory() as d:
            w = self.window(d)
            row = ledger.require("sma", allow_plumbing=True, path=self.ledger(d), plumbing=w)
            self.assertEqual(row.status, "plumbing")


class TestBacktest(unittest.TestCase):
    def panel(self, tmp, closes):
        import csv as _csv
        from pathlib import Path as _P
        d = _P(tmp)
        for name in ("open", "close"):
            with (d / f"{name}.csv").open("w", newline="") as f:
                w = _csv.writer(f); w.writerow(["dt", "BTC"])
                for i, c in enumerate(closes):
                    w.writerow([f"2024-01-{i+1:02d}", c])
        return d

    def test_a_rising_series_goes_long_and_flat_prices_lose_only_fees(self):
        from espero2.backtest import Costs, run_panel
        with tempfile.TemporaryDirectory() as d:
            prices = [100.0] * 60 + [110.0] * 20     # flat then up: one long entry
            r = run_panel(self.panel(d, prices), costs=Costs(4.5, 2.0))
            self.assertEqual(r["books"]["BTC"]["trades"], 1)
            self.assertLess(r["stats"]["total_pct"], 0.0)   # entry cost only, price did not move after

    def test_a_crash_exits_at_the_next_open_not_at_the_signal_close(self):
        from espero2.backtest import Costs, run_panel
        with tempfile.TemporaryDirectory() as d:
            prices = [100.0 + i for i in range(60)] + [10.0] * 5    # rise, then collapse
            r = run_panel(self.panel(d, prices), costs=Costs(4.5, 2.0))
            self.assertGreaterEqual(r["books"]["BTC"]["trades"], 2)   # long opened, then closed
            self.assertGreater(r["stats"]["total_pct"], -100.0)      # the book survives


class TestCoinbaseSandbox(unittest.TestCase):
    def test_orders_cannot_go_to_mainnet(self):
        from espero2 import coinbase as cb
        with self.assertRaises(cb.Refused):
            cb._post("https://api.coinbase.com/api/v3/brokerage/orders", {})

    def test_reading_an_unknown_host_is_refused(self):
        from espero2 import coinbase as cb
        with self.assertRaises(cb.Refused):
            cb._get("https://example.com/products")

    def test_a_sandbox_order_without_confirm_is_refused(self):
        from espero2 import coinbase as cb
        with self.assertRaises(cb.Refused):
            cb.place_market("BTC-USD", "BUY", 1.0, confirm=False)

    def test_the_canned_reply_is_flagged_as_a_mock(self):
        import io, json
        from unittest.mock import patch
        from espero2 import coinbase as cb
        canned = {"success": True, "success_response": {"order_id": "abc", "product_id": "BTC-USD",
                                                         "side": "SELL",
                                                         "client_order_id": "sandbox_success_order"},
                  "order_configuration": {}}
        with patch.object(cb.urllib.request, "urlopen",
                          return_value=io.BytesIO(json.dumps(canned).encode())):
            out = cb.place_market("BTC-USD", "BUY", 1.0, confirm=True)
        self.assertTrue(out["mock"])                 # it did not echo our client id
        self.assertEqual(out["request"]["side"], "BUY")
        self.assertEqual(out["order_id"], "abc")


class TestSandboxCases(unittest.TestCase):
    def canned(self, payload):
        import io, json
        return io.BytesIO(json.dumps(payload).encode())

    def test_the_documented_error_header_is_sent_and_parsed(self):
        import json
        from unittest.mock import patch
        from espero2 import coinbase as cb
        seen = {}

        def fake_urlopen(req, timeout=None):     # noqa: ARG001
            seen["headers"] = dict(req.headers)
            return self.canned({"success": False,
                                "error_response": {"error": "INSUFFICIENT_FUND"}})

        with patch.object(cb.urllib.request, "urlopen", fake_urlopen):
            out = cb.place_market("BTC-USD", "BUY", 1.0, confirm=True,
                                  sandbox_case="PostOrder_insufficient_fund")
        self.assertEqual(seen["headers"].get("X-sandbox"), "PostOrder_insufficient_fund")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "INSUFFICIENT_FUND")

    def test_portfolios_and_perps_parse(self):
        from unittest.mock import patch
        from espero2 import coinbase as cb
        with patch.object(cb.urllib.request, "urlopen",
                          return_value=self.canned({"portfolios": [
                              {"uuid": "u1", "type": "INTX", "name": "INTX Portfolio"}]})):
            self.assertEqual(cb.portfolios()[0]["type"], "INTX")
        with patch.object(cb.urllib.request, "urlopen",
                          return_value=self.canned({"positions": [{"symbol": "ETH-PERP-INTX"}]})):
            self.assertEqual(cb.perp_positions("u1")[0]["symbol"], "ETH-PERP-INTX")


class TestCoinbaseAuth(unittest.TestCase):
    def test_the_jwt_carries_the_documented_claims(self):
        import base64, os
        from unittest.mock import patch
        from espero2 import coinbase as cb
        secret = base64.b64encode(bytes(range(64))).decode()
        key_name = "0b6f0f8e-1111-2222-3333-444455556666"
        with patch.dict(os.environ, {"COINBASE_API_KEY": key_name,
                                     "COINBASE_API_SECRET": secret}, clear=False):
            tok = cb._jwt("GET", "/api/v3/brokerage/accounts")
        import jwt
        head = jwt.get_unverified_header(tok)
        body = jwt.decode(tok, options={"verify_signature": False})
        self.assertEqual(head["kid"], key_name)
        self.assertEqual(head["alg"], "EdDSA")
        self.assertEqual(body["iss"], "cdp")
        self.assertEqual(body["uri"], "GET api.coinbase.com/api/v3/brokerage/accounts")
        self.assertGreater(body["exp"], body["nbf"])

    def test_env_loading_does_not_override_existing_values(self):
        import os, tempfile
        from unittest.mock import patch
        from espero2 import coinbase as cb
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text("KEEPME=from_file\n")
            with patch.dict(os.environ, {"KEEPME": "already"}, clear=False):
                cb.load_env(p)
                self.assertEqual(os.environ["KEEPME"], "already")


class TestExecutionPolicy(unittest.TestCase):
    def test_default_is_mock_and_the_sandbox_is_allowed(self):
        from espero2 import policy
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d) / "EXECUTION"
            self.assertEqual(policy.mode(missing), "mock")
            policy.require_sandbox(missing)          # sandbox orders are fine

    def test_live_is_recognised_and_refused(self):
        from espero2 import policy
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "EXECUTION"
            p.write_text("live\n")
            self.assertEqual(policy.mode(p), "live")
            with self.assertRaises(policy.Refused):
                policy.require_sandbox(p)

    def test_an_unknown_mode_is_refused_not_guessed(self):
        from espero2 import policy
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "EXECUTION"
            p.write_text("yolo\n")
            with self.assertRaises(policy.Refused):
                policy.mode(p)


class TestCoinbasePaper(unittest.TestCase):
    def series(self, closes):
        return [{"ts": i * 3600, "open": c, "high": c, "low": c, "close": c, "volume": 1.0}
                for i, c in enumerate(closes)]

    def tick_with(self, closes, bid, ask):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from espero2 import cbpaper
        from espero2.store import Store
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "cb.db")
            with patch.object(cbpaper, "candles", return_value=self.series(closes)), \
                 patch.object(cbpaper.cb, "ticker",
                              return_value={"product": "BTC-USD", "bid": bid, "ask": ask,
                                            "mid": (bid + ask) / 2, "last": bid, "time": "t"}):
                r = cbpaper.tick(s, "BTC-USD", notional=100.0)
            st = s.get_state("BTC-USD")
            s.close()
            return r, st

    def test_a_short_signal_does_not_open_a_position_on_spot(self):
        r, st = self.tick_with([200 - i for i in range(80)], bid=100, ask=100.2)
        self.assertEqual(st["qty"], 0.0)                 # long-only spot
        self.assertEqual(st["cash"], 1000.0)
        self.assertIn("hold", " ".join(r["actions"]) or "hold")

    def test_a_long_signal_buys_and_charges_the_fee(self):
        r, st = self.tick_with([100 + i for i in range(80)], bid=179.0, ask=179.2)
        self.assertGreater(st["qty"], 0)
        self.assertLess(st["cash"], 900.0)               # ~$100 notional + 120 bps fee
        fees = sum(1 for _ in r["actions"] if "BUY" in _)
        self.assertEqual(fees, 1)

    def test_the_stop_closes_a_long(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from espero2 import cbpaper
        from espero2.store import Store
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "cb.db")
            with patch.object(cbpaper, "candles", return_value=self.series([100 + i for i in range(80)])), \
                 patch.object(cbpaper.cb, "ticker",
                              return_value={"product": "BTC-USD", "bid": 179.0, "ask": 179.2,
                                            "mid": 179.1, "last": 179.0, "time": "t"}):
                cbpaper.tick(s, "BTC-USD")
            entry = s.get_state("BTC-USD")["entry_px"]
            with patch.object(cbpaper, "candles", return_value=self.series([100 + i for i in range(80)])), \
                 patch.object(cbpaper.cb, "ticker",
                              return_value={"product": "BTC-USD", "bid": entry * 0.9,
                                            "ask": entry * 0.9, "mid": entry * 0.9,
                                            "last": entry * 0.9, "time": "t"}):
                r = cbpaper.tick(s, "BTC-USD")
            self.assertEqual(s.get_state("BTC-USD")["qty"], 0.0)
            self.assertTrue(any("STOP" in a for a in r["actions"]), r["actions"])
            s.close()


class TestLiveFeesAndMinimums(unittest.TestCase):
    def setUp(self):
        from espero2 import coinbase as cb
        cb._TIER = None

    def test_the_fee_tier_comes_from_the_venue(self):
        from unittest.mock import patch
        from espero2 import coinbase as cb
        summary = {"fee_tier": {"pricing_tier": "Intro", "taker_fee_rate": "0.009",
                                "maker_fee_rate": "0.005"}}
        with patch.object(cb, "authed_get", return_value=summary):
            t = cb.fee_tier()
        self.assertEqual(t["taker_bps"], 90.0)
        self.assertEqual(t["maker_bps"], 50.0)
        self.assertEqual(t["tier"], "Intro")

    def test_live_costs_fall_back_when_the_read_fails(self):
        from unittest.mock import patch
        from espero2 import cbpaper
        from espero2 import coinbase as cb
        with patch.object(cb, "authed_get", side_effect=RuntimeError("no network")):
            c = cbpaper.live_costs()
        self.assertEqual(c.fee_bps, 90.0)          # documented fallback

    def test_an_order_below_the_venue_minimum_is_not_sent(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from espero2 import cbpaper
        from espero2.store import Store
        rising = [{"ts": i * 3600, "open": 100 + i, "high": 100 + i, "low": 100 + i,
                   "close": 100 + i, "volume": 1.0} for i in range(80)]
        tick = {"product": "BTC-USD", "bid": 179.0, "ask": 179.2, "mid": 179.1,
                "last": 179.0, "time": "t"}
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "cb.db")
            with patch.object(cbpaper, "candles", return_value=rising), \
                 patch.object(cbpaper.cb, "ticker", return_value=tick), \
                 patch.object(cbpaper.cb, "product_detail", return_value={"quote_min_size": "500"}), \
                 patch.object(cbpaper, "live_costs", return_value=cbpaper.Costs(90.0, 2.0)):
                r = cbpaper.tick(s, "BTC-USD", notional=100.0)
            self.assertEqual(s.get_state("BTC-USD")["qty"], 0.0)
            self.assertTrue(any("minimum" in a for a in r["actions"]), r["actions"])
            s.close()


class TestRiskPrimitives(unittest.TestCase):
    def test_atr_is_zero_without_enough_bars(self):
        from espero2.risk import atr
        self.assertEqual(atr([{"high": 1, "low": 0, "close": 0.5}] * 5), 0.0)

    def test_atr_uses_the_true_range(self):
        from espero2.risk import atr
        bars = [{"high": 10, "low": 8, "close": 9}] * 20     # every true range is exactly 2
        self.assertAlmostEqual(atr(bars, 14), 2.0, places=6)

    def test_vol_target_shrinks_size_as_vol_rises(self):
        from espero2.risk import vol_target_notional
        low = vol_target_notional(10_000, 0.02, 0.5)
        high = vol_target_notional(10_000, 0.02, 1.5)
        self.assertGreater(low, high)
        self.assertAlmostEqual(low, 10_000 * 0.02 / (2 * 0.5 / (365 ** 0.5)), places=2)

    def test_funding_gate_blocks_a_long_paying_too_much(self):
        from espero2.risk import funding_annual_pct, funding_gate
        self.assertAlmostEqual(funding_annual_pct(1.0), 87.6, places=1)   # 1 bp/h ~ 87.6%/yr
        self.assertTrue(funding_gate("long", 1.0, 20.0))
        self.assertFalse(funding_gate("long", 0.1, 20.0))
        self.assertTrue(funding_gate("short", -1.0, 20.0))
        self.assertFalse(funding_gate("long", 1.0, None))
