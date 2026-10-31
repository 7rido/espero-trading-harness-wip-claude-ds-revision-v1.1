"""A rate-limited optics run must not overwrite the last good snapshot."""
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from research import optics


class FakeCon:
    def execute(self, *a, **k):
        return self

    def fetchone(self):
        return (0, 0)

    def close(self):
        pass


def http429(*a, **k):
    raise urllib.error.HTTPError("https://api.hyperliquid.xyz/info", 429, "Too Many Requests", None, None)


class TestOpticsGuard(unittest.TestCase):
    def test_rate_limited_run_keeps_the_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            out = tmp / "optics.json"
            out.write_text('{"sentinel": true}')
            saved = (optics.OUT, optics.ROOT)
            optics.OUT, optics.ROOT = out, tmp
            try:
                with patch.object(optics.duckdb, "connect", lambda *a, **k: FakeCon()), \
                     patch.object(optics, "get", lambda url: []), \
                     patch.object(optics, "freshness", lambda con: []), \
                     patch.object(optics.hl, "_post", side_effect=http429):
                    rc = optics.main()
            finally:
                optics.OUT, optics.ROOT = saved
            self.assertEqual(rc, 2)
            self.assertEqual(out.read_text(), '{"sentinel": true}')
            self.assertTrue((tmp / "research" / "optics.failed.json").exists())
