"""The forecast card renders its banner and rows, and flags stale snapshots."""
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timezone

from espero2 import dashboard


def payload(at: str | None = None) -> dict:
    now = at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"at": now, "optics_at": now,
            "guardrails": {"holds": 0, "max_label": "WATCH", "cost_bps": 9.0},
            "rows": [
                {"coin": "BTC", "state": "up/low/low", "n": 2000, "median5": -30,
                 "median20": -200, "share_up": 0.4, "ci_lo": 0.36, "ci_hi": 0.44,
                 "net_median20": -210, "label": "CONTEXT ONLY", "reason": "fails multiplicity"},
                {"coin": "SOL", "state": "down/low/high", "n": 1986, "median5": -37,
                 "median20": -205, "share_up": 0.39, "ci_lo": 0.35, "ci_hi": 0.43,
                 "net_median20": -215, "label": "E1-FORWARD", "reason": "down-break live"},
            ]}


class TestForecastCard(unittest.TestCase):
    def setUp(self):
        self.saved = dashboard.FORECAST

    def tearDown(self):
        dashboard.FORECAST = self.saved

    def _write(self, data: dict) -> pathlib.Path:
        p = pathlib.Path(tempfile.mkdtemp()) / "forecast.json"
        p.write_text(json.dumps(data))
        return p

    def test_renders_banner_and_labels(self):
        dashboard.FORECAST = self._write(payload())
        card = dashboard._forecast_card()
        for needle in ("forecasts &amp; recommendations", "capped at", "CONTEXT ONLY",
                       "E1-FORWARD", "BTC"):
            self.assertIn(needle, card)

    def test_missing_file_renders_nothing(self):
        dashboard.FORECAST = pathlib.Path(tempfile.gettempdir()) / "no-forecast-here.json"
        self.assertEqual(dashboard._forecast_card(), "")

    def test_stale_snapshot_is_flagged(self):
        dashboard.FORECAST = self._write(payload(at="2000-01-01T00:00:00Z"))
        self.assertIn("stale", dashboard._forecast_card())
