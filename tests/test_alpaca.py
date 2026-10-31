"""Alpaca: live refused, confirm required, keys required, bars URL built correctly."""
import importlib.util
import os
import pathlib
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alpaca", ROOT / "espero2" / "alpaca.py")
# load through the package so the relative import of .coinbase works
from espero2 import alpaca as ap  # noqa: E402


class TestAlpaca(unittest.TestCase):
    def test_the_live_host_is_refused(self):
        with self.assertRaises(ap.Refused):
            ap._call(ap.LIVE, "/v2/account")

    def test_missing_keys_are_refused(self):
        with patch.dict(os.environ, {"APCA_API_KEY_ID": "", "APCA_API_SECRET_KEY": ""}, clear=False):
            with self.assertRaises(ap.Refused):
                ap._headers()

    def test_a_paper_order_needs_confirmation(self):
        with self.assertRaises(ap.Refused):
            ap.place_order("AAPL", 1, "buy", confirm=False)

    def test_bars_builds_the_documented_query(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            import io, json
            return io.BytesIO(json.dumps({"bars": {}}).encode())

        with patch.dict(os.environ, {"APCA_API_KEY_ID": "k", "APCA_API_SECRET_KEY": "s"}, clear=False):
            with patch.object(ap.urllib.request, "urlopen", fake_urlopen):
                ap.bars(["AAPL", "MSFT"], "1Day", "2026-01-01", "2026-02-01")
        self.assertIn("symbols=AAPL%2CMSFT", captured["url"])
        self.assertIn("timeframe=1Day", captured["url"])
        self.assertIn("feed=iex", captured["url"])
