"""The tape card renders the flow metrics, prefers a fresh live slice, and disappears cleanly."""
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone

from espero2 import dashboard


def snapshot(source="binance-um", at=None):
    return {"at": at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source, "symbol": "BTCUSDT", "day": "2026-10-29", "prints": 1804397,
            "buy_share": 0.48, "cvd": -9891.4, "blocks": {"count": 45226, "usd": 12_166_200_000},
            "sweeps": {"count": 2881, "usd": 1_000_000}, "profile": {"poc_distance_pct": -2.77},
            "absorption": {"share": 0.23}, "divergence": "none",
            "read": "taker buys 48% of volume, CVD -9891.4 BTC"}


class TestTapeCard(unittest.TestCase):
    def setUp(self):
        self.saved = (dashboard.TAPE, dashboard.TAPE_LIVE)

    def tearDown(self):
        dashboard.TAPE, dashboard.TAPE_LIVE = self.saved

    def _write(self, data: dict) -> pathlib.Path:
        p = pathlib.Path(tempfile.mkdtemp()) / "tape.json"
        p.write_text(json.dumps(data))
        return p

    def test_daily_card(self):
        dashboard.TAPE = self._write(snapshot())
        dashboard.TAPE_LIVE = pathlib.Path(tempfile.gettempdir()) / "no-live-tape.json"
        card = dashboard._tape_card()
        for needle in ("BTC tape", "binance-um", "48%", "45,226", "none"):
            self.assertIn(needle, card)

    def test_fresh_live_is_preferred(self):
        dashboard.TAPE = self._write(snapshot())
        dashboard.TAPE_LIVE = self._write(snapshot(source="coinbase-spot"))
        self.assertIn("coinbase-spot", dashboard._tape_card())

    def test_missing_renders_nothing(self):
        dashboard.TAPE = pathlib.Path(tempfile.gettempdir()) / "nope-daily.json"
        dashboard.TAPE_LIVE = pathlib.Path(tempfile.gettempdir()) / "nope-live.json"
        self.assertEqual(dashboard._tape_card(), "")

    def test_stale_daily_is_flagged(self):
        dashboard.TAPE = self._write(snapshot(at="2000-01-01T00:00:00Z"))
        dashboard.TAPE_LIVE = pathlib.Path(tempfile.gettempdir()) / "no-live-tape.json"
        self.assertIn("stale", dashboard._tape_card())
