"""The silent-job check: stale sync and a dead feed must fail the run."""
import datetime as dt
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hc", ROOT / "scripts" / "health_check.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)

UTC = dt.timezone.utc


class TestHealth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "logs").mkdir()
        (self.root / "data/aggr/forward5m").mkdir(parents=True)
        feed = self.root / "data/aggr/forward5m/2026-11-01.csv.gz"
        feed.write_text("x")
        ts = dt.datetime(2026, 11, 2, 12, tzinfo=UTC).timestamp()
        os.utime(feed, (ts, ts))
        (self.root / "liqbreak_trades.csv").write_text("coin,day\nBTC,2026-11-01\n")
        src = self.root / "source"
        src.mkdir()
        self.write_sync(dt.datetime(2026, 11, 2, 12, tzinfo=UTC), src)

    def tearDown(self):
        self.tmp.cleanup()

    def write_sync(self, at, src):
        (self.root / "logs" / "sync-status.json").write_text(json.dumps(
            {"at": at.isoformat(), "source": str(src), "copied": 1}))

    def test_healthy_tree_passes(self):
        out = hc.run(self.root, now=dt.datetime(2026, 11, 2, 13, tzinfo=UTC))
        self.assertTrue(out["ok"], out["checks"])

    def test_a_stale_copy_fails(self):
        out = hc.run(self.root, now=dt.datetime(2026, 11, 5, 13, tzinfo=UTC))
        self.assertFalse(out["ok"])
        self.assertIn("sync", out["failures"])

    def test_a_missing_source_fails(self):
        self.write_sync(dt.datetime(2026, 11, 2, 12, tzinfo=UTC), self.root / "gone")
        out = hc.run(self.root, now=dt.datetime(2026, 11, 2, 13, tzinfo=UTC))
        self.assertIn("sync", out["failures"])

    def test_an_empty_feed_fails_after_the_grace_day(self):
        for f in (self.root / "data/aggr/forward5m").glob("*"):
            f.unlink()
        out = hc.run(self.root, now=dt.datetime(2026, 11, 10, 13, tzinfo=UTC))
        self.assertIn("feed", out["failures"])

    def test_an_empty_feed_on_day_one_is_only_a_warning(self):
        for f in (self.root / "data/aggr/forward5m").glob("*"):
            f.unlink()
        self.write_sync(dt.datetime(2026, 10, 31, 12, tzinfo=UTC), self.root / "source")
        (self.root / "liqbreak_trades.csv").write_text("")
        out = hc.run(self.root, now=dt.datetime(2026, 10, 31, 13, tzinfo=UTC))
        self.assertEqual(out["checks"]["feed"]["state"], "WARN")

    def test_a_silent_ledger_fails_seven_days_in(self):
        (self.root / "liqbreak_trades.csv").write_text("")
        out = hc.run(self.root, now=dt.datetime(2026, 11, 8, 13, tzinfo=UTC))
        self.assertIn("ledger", out["failures"])
