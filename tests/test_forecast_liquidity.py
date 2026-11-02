"""Liquidity snapshot parsing: units, percentages and one exchange table."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forecast_liquidity", ROOT / "research" / "forecast_liquidity.py")
liquidity = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(liquidity)

SAMPLE = """
<div class="stat-grid">
  <div class="cell"><b>$10.74B</b><span>Open interest</span></div>
  <div class="cell"><b>$2.50B</b><span>Volume 24h</span></div>
  <div class="cell"><b class="up">+0.0013%</b><span>Funding rate</span></div>
  <div class="cell"><b>$27.65M</b><span>Liq. 24h</span></div>
  <div class="cell"><b>180</b><span>Contracts</span></div>
  <div class="cell"><b>+4.5000%</b><span>Taker fee</span></div>
  <div class="cell"><b>+1.5000%</b><span>Maker fee</span></div>
</div>
<p class="hm-note"><span class="up">Long $20.78M (75%)</span> ·
<span class="down">Short $6.87M (25%)</span></p>
<table><tbody>
<tr><td>1</td><td class="l"><a href="/coin/BTC"><span class="coin-cell">
<img src="/btc.png" alt=""><span class="name">BTC</span></span></a></td>
<td>$78,410</td><td>$3.15B</td><td class="up">+0.0013%</td>
<td class="l"><span class="mini-label">29.6%</span></td></tr>
</tbody></table>
"""


class TestLiquidityParsing(unittest.TestCase):
    def test_units(self):
        self.assertEqual(liquidity.parse_usd("$10.74B"), 10_740_000_000)
        self.assertEqual(liquidity.parse_usd("$27.65M"), 27_650_000)
        self.assertIsNone(liquidity.parse_usd("n/a"))
        self.assertAlmostEqual(liquidity.parse_pct("+0.0013%"), 0.0013)
        self.assertEqual(liquidity.parse_price("$78,410"), 78_410.0)

    def test_exchange_snapshot(self):
        out = liquidity.parse_exchange(SAMPLE)
        self.assertEqual(out["open_interest_usd"], 10_740_000_000)
        self.assertEqual(out["volume_24h_usd"], 2_500_000_000)
        self.assertEqual(out["liq_24h_usd"], 27_650_000)
        self.assertEqual(out["contracts"], 180)
        self.assertEqual(out["long_share"], 0.75)
        self.assertEqual(out["short_share"], 0.25)
        self.assertEqual(len(out["coins"]), 1)
        self.assertEqual(out["coins"][0]["coin"], "BTC")
        self.assertEqual(out["coins"][0]["oi_usd"], 3_150_000_000)


if __name__ == "__main__":
    unittest.main()
