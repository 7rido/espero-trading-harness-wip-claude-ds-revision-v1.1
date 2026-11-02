"""The liquidity map: book pools, taker flow, and the sampled Hyperliquid liquidation ladder."""
import csv
import gzip
import importlib.util
import math
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("liquidity_map_mod", ROOT / "research" / "liquidity_map.py")
lm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lm)

COLUMNS = ["ts", "address", "coin", "szi", "entry", "value", "liq", "lev", "lev_type",
           "margin", "upnl", "account_value"]


def position(coin="BTC", szi=1.0, liq=90.0, value=100.0, entry=100.0, ts=1793500000):
    return {"ts": ts, "address": "0xabc", "coin": coin, "szi": szi, "entry": entry,
            "value": value, "liq": liq, "lev": 10, "lev_type": "cross", "margin": 10,
            "upnl": 0, "account_value": 1000}


def write_positions(root: pathlib.Path, day: str, slot: str, rows):
    path = root / "positions" / day
    path.mkdir(parents=True, exist_ok=True)
    dest = path / f"{slot}.csv.gz"
    with gzip.open(dest, "wt", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return dest


class TestSnapshots(unittest.TestCase):
    def test_newest_snapshot_spans_roots(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            write_positions(pathlib.Path(a), "2026-10-31", "2300", [position()])
            latest = write_positions(pathlib.Path(b), "2026-11-01", "0600", [position()])
            self.assertEqual(lm.newest_snapshot([a, b]), latest)

    def test_newest_ctx(self):
        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root)
            (root / "ctx" / "2026-11-01").mkdir(parents=True)
            for slot in ("0600", "0635"):
                with gzip.open(root / "ctx" / "2026-11-01" / f"{slot}.csv.gz", "wt") as fh:
                    fh.write("ts,coin,mark,mid,open_interest\n1,BTC,100,100,10\n")
            self.assertEqual(lm.newest_ctx([root]).name, "0635.csv.gz")


class TestPositions(unittest.TestCase):
    def test_load_keeps_open_positions_and_falls_back_on_value(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [position(szi=2, value=0, entry=100, liq=""),
                    position(coin="ETH", szi=-2, value=250, liq=110),
                    position(szi=0)]
            path = write_positions(pathlib.Path(root), "2026-11-01", "0600", rows)
            out = lm.load_positions(path)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["side"], "long")
        self.assertAlmostEqual(out[0]["value"], 200.0)
        self.assertTrue(math.isnan(out[0]["liq"]))
        self.assertEqual(out[1]["side"], "short")

    def test_load_ctx(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "ctx.csv.gz"
            with gzip.open(path, "wt") as fh:
                fh.write("ts,coin,mark,mid,open_interest,funding,day_volume\n"
                         "1,BTC,101,100.5,10,0.0001,500\n")
            out = lm.load_ctx(path)
        self.assertEqual(out["BTC"]["mark"], 101.0)
        self.assertEqual(out["BTC"]["open_interest"], 10.0)


class TestBookPools(unittest.TestCase):
    def test_largest_pools_away_from_the_touch(self):
        bids = [(99.99, 1000), (99.9, 10), (99.5, 50), (98.0, 1)]
        asks = [(100.01, 1000), (100.1, 20), (100.5, 80), (102.0, 1)]
        pools = lm.book_pools(bids, asks, 100.0, bucket_bps=10, top_n=2, min_dist_bps=5,
                              max_dist_pct=2.0)
        bid = [p for p in pools if p["side"] == "bid"]
        ask = [p for p in pools if p["side"] == "ask"]
        self.assertEqual(len(bid), 2)
        self.assertEqual(len(ask), 2)
        self.assertAlmostEqual(bid[0]["price"], 99.5, places=2)
        self.assertAlmostEqual(ask[0]["price"], 100.5, places=2)
        self.assertLess(bid[0]["distance_pct"], 0)
        self.assertGreater(ask[0]["distance_pct"], 0)
        self.assertLessEqual(bid[0]["share"], 1.0)

    def test_adjacent_buckets_merge_into_one_pool(self):
        bids = [(99.95, 1), (99.85, 100), (99.75, 100)]
        pools = lm.book_pools(bids, [], 100.0, bucket_bps=10, top_n=3, min_dist_bps=5,
                              max_dist_pct=2.0)
        self.assertEqual(len(pools), 1)
        self.assertLess(pools[0]["price"], 99.9)
        self.assertGreater(pools[0]["price"], 99.7)
        self.assertEqual(pools[0]["levels"], 2)

    def test_touch_and_far_levels_are_ignored(self):
        bids = [(99.999, 1_000_000), (99.5, 10), (90.0, 1_000_000)]
        pools = lm.book_pools(bids, [], 100.0, bucket_bps=10, top_n=1, min_dist_bps=5,
                              max_dist_pct=2.0)
        self.assertEqual(len(pools), 1)
        self.assertAlmostEqual(pools[0]["price"], 99.5, places=2)

    def test_empty_book(self):
        self.assertEqual(lm.book_pools([], [], 100.0), [])


class TestFlow(unittest.TestCase):
    def test_buy_share_and_net(self):
        now = 1_000_000.0
        trades = [{"ts": now - 60, "price": 100.0, "size": 2.0, "side": "buy"},
                  {"ts": now - 30, "price": 99.0, "size": 1.0, "side": "sell"}]
        flow = lm.flow_stats(trades, now=now, window_min=30)
        self.assertEqual(flow["prints"], 2)
        self.assertAlmostEqual(flow["buy_share"], 200 / 299)
        self.assertAlmostEqual(flow["net_usd"], 101.0)
        self.assertAlmostEqual(flow["span_min"], 0.5)
        self.assertTrue(flow["side_verified"])

    def test_thin_window_uses_available_prints(self):
        now = 1_000_000.0
        trades = [{"ts": now - 3600, "price": 100.0, "size": 1.0, "side": "buy"},
                  {"ts": now - 1800, "price": 101.0, "size": 1.0, "side": "sell"}]
        flow = lm.flow_stats(trades, now=now, window_min=30)
        self.assertEqual(flow["prints"], 2)
        self.assertAlmostEqual(flow["span_min"], 30.0)

    def test_empty_flow(self):
        flow = lm.flow_stats([], now=1_000_000.0)
        self.assertEqual(flow["prints"], 0)
        self.assertTrue(math.isnan(flow["buy_share"]))


class TestLiquidationClusters(unittest.TestCase):
    def setUp(self):
        self.positions = [
            {"side": "long", "liq": 90.0, "value": 700.0, "ts": 0},
            {"side": "long", "liq": 90.1, "value": 500.0, "ts": 0},
            {"side": "long", "liq": 80.0, "value": 1000.0, "ts": 0},
            {"side": "long", "liq": 95.0, "value": 10.0, "ts": 0},
            {"side": "long", "liq": 60.0, "value": 9999.0, "ts": 0},     # outside -30 %
            {"side": "long", "liq": 105.0, "value": 9999.0, "ts": 0},    # wrong side
            {"side": "short", "liq": 110.0, "value": 300.0, "ts": 0},
            {"side": "short", "liq": 120.0, "value": 100.0, "ts": 0},
            {"side": "short", "liq": 140.0, "value": 9999.0, "ts": 0},   # outside +30 %
            {"side": "short", "liq": 95.0, "value": 9999.0, "ts": 0},    # wrong side
            {"side": "long", "liq": float("nan"), "value": 9999.0, "ts": 0},
        ]

    def test_clusters_keep_the_right_side_and_distance(self):
        out = lm.liquidation_clusters(self.positions, 100.0, bucket_bps=50, min_sep_bps=100,
                                      top_n=2, max_dist_pct=30.0)
        longs = [c for c in out if c["side"] == "long"]
        shorts = [c for c in out if c["side"] == "short"]
        self.assertEqual(len(longs), 2)
        self.assertEqual(len(shorts), 2)
        self.assertTrue(all(c["price"] < 100.0 for c in longs))
        self.assertTrue(all(c["price"] > 100.0 for c in shorts))

    def test_adjacent_prices_form_one_cluster(self):
        out = lm.liquidation_clusters(self.positions, 100.0, bucket_bps=50, min_sep_bps=100,
                                      top_n=2, max_dist_pct=30.0)
        top = [c for c in out if c["side"] == "long"][0]
        self.assertAlmostEqual(top["price"], (90 * 700 + 90.1 * 500) / 1200, places=3)
        self.assertEqual(top["count"], 2)

    def test_outside_window_and_wrong_side_are_dropped(self):
        out = lm.liquidation_clusters(self.positions, 100.0, bucket_bps=50, min_sep_bps=100,
                                      top_n=5, max_dist_pct=30.0)
        self.assertFalse(any(c["side"] == "long" and round(c["price"], 2) == 60.0 for c in out))
        self.assertFalse(any(c["side"] == "long" and round(c["price"], 2) == 105.0 for c in out))
        self.assertFalse(any(c["side"] == "short" and round(c["price"], 2) == 140.0 for c in out))
        self.assertFalse(any(c["side"] == "short" and round(c["price"], 2) == 95.0 for c in out))

    def test_empty_positions(self):
        self.assertEqual(lm.liquidation_clusters([], 100.0), [])


class TestLadder(unittest.TestCase):
    def test_summary_totals_nearest_and_coverage(self):
        positions = [
            {"side": "long", "liq": 90.0, "value": 600.0, "ts": 1793500000},
            {"side": "long", "liq": 110.0, "value": 999.0, "ts": 1793500000},
            {"side": "short", "liq": 110.0, "value": 400.0, "ts": 1793500000},
            {"side": "short", "liq": 90.0, "value": 999.0, "ts": 1793500000},
        ]
        summary = lm.ladder_summary(positions, 100.0, max_dist_pct=30.0)
        self.assertEqual(summary["positions"], 4)
        self.assertEqual(summary["with_liq"], 4)
        self.assertAlmostEqual(summary["sample_usd"], 2998.0)
        self.assertAlmostEqual(summary["long_usd"], 600.0)
        self.assertAlmostEqual(summary["short_usd"], 400.0)
        self.assertAlmostEqual(summary["nearest_long_pct"], 10.0)
        self.assertAlmostEqual(summary["nearest_short_pct"], 10.0)


class TestMarket(unittest.TestCase):
    def test_three_layers_share_one_snapshot(self):
        book = {"bids": [(99.9, 10), (99.5, 100), (99.0, 1)],
                "asks": [(100.1, 10), (100.5, 100), (101.0, 1)]}
        trades = [{"ts": 1_000_000 - 10, "price": 100.0, "size": 2.0, "side": "buy"},
                  {"ts": 1_000_000 - 5, "price": 100.0, "size": 1.0, "side": "sell"}]
        positions = [{"side": "long", "liq": 90.0, "value": 1000.0, "ts": 0},
                     {"side": "short", "liq": 110.0, "value": 500.0, "ts": 0}]
        ctx = {"mark": 101.0, "mid": 100.5, "open_interest": 100.0}
        m = lm.market_snapshot("BTC", book, trades, positions, ctx, now=1_000_000.0)
        self.assertAlmostEqual(m["mid"], 100.0)
        self.assertAlmostEqual(m["mark"], 101.0)
        self.assertAlmostEqual(m["basis_bps"], 100.0)
        self.assertEqual(len(m["clusters"]), 2)
        self.assertGreaterEqual(len(m["pools"]), 2)
        self.assertAlmostEqual(m["ladder"]["coverage_pct"], 1500 / (100 * 101) * 100, places=3)
        self.assertAlmostEqual(m["flow"]["net_usd"], 100.0)


if __name__ == "__main__":
    unittest.main()
