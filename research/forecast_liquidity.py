"""Snapshot the Hyperliquid liquidity dashboard as a candidate feature source.

    python research/forecast_liquidity.py

The page has no documented JSON API. It is server-rendered HTML with live OI,
funding, volume, liquidation splits and per-coin OI. This script parses one
snapshot and appends it to a research-only DuckDB table. It does not modify the
forecast, paper books, ledger or any order path.

Important: the dashboard's "liquidation heatmap" is a model-based estimate from
open interest, price and realized liquidations — not raw exchange liquidation
levels. A single snapshot cannot be a predictor. Use it as a candidate feature
only after it has a historical sample and beats the unconditional baseline in
the walk-forward audit.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import time
import urllib.request

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "forecast_liquidity.duckdb"
SUMMARY = ROOT / "research" / "forecast_liquidity.json"
URL = "https://bitcoinliquidityheatmap.com/exchange/hyperliquid"
UA = {"User-Agent": "espero2-liquidity-snapshot/0.1"}


def parse_usd(text: str) -> float | None:
    text = html.unescape(text).strip().replace(",", "")
    m = re.fullmatch(r"\$?([-+]?\d+(?:\.\d+)?)\s*([KMBT]?)", text)
    if not m:
        return None
    value = float(m.group(1))
    return value * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[m.group(2)]


def parse_pct(text: str) -> float | None:
    text = html.unescape(text).strip().replace(",", "")
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None


def parse_price(text: str) -> float | None:
    text = html.unescape(text).strip().replace("$", "").replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_exchange(page: str) -> dict:
    def cell(label: str) -> str | None:
        m = re.search(
            r'class="cell"><b[^>]*>([^<]+)</b><span>' + re.escape(label) + r"</span>",
            page,
        )
        return html.unescape(m.group(1)).strip() if m else None

    long_short = re.search(
        r"Long \$([\d.,]+[KMB]?)\s*\((\d+)%\).*?Short \$([\d.,]+[KMB]?)\s*\((\d+)%\)",
        page, re.S,
    )
    coins = []
    for m in re.finditer(
        r'<tr><td>\d+</td><td class="l"><a href="/coin/([A-Z0-9]+)">'
        r'.*?<span class="name">[^<]+</span>.*?</td>\s*'
        r'<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td[^>]*>([^<]+)</td>',
        page, re.S,
    ):
        coin, price, oi, funding = m.groups()
        coins.append({
            "coin": coin,
            "price": parse_price(price),
            "oi_usd": parse_usd(oi),
            "funding_pct": parse_pct(funding),
        })
    return {
        "open_interest_usd": parse_usd(cell("Open interest") or ""),
        "volume_24h_usd": parse_usd(cell("Volume 24h") or ""),
        "funding_pct": parse_pct(cell("Funding rate") or ""),
        "liq_24h_usd": parse_usd(cell("Liq. 24h") or ""),
        "contracts": int(float((cell("Contracts") or "0").replace(",", ""))),
        "taker_fee_pct": parse_pct(cell("Taker fee") or ""),
        "maker_fee_pct": parse_pct(cell("Maker fee") or ""),
        "long_liq_usd": parse_usd(long_short.group(1)) if long_short else None,
        "long_share": float(long_short.group(2)) / 100 if long_short else None,
        "short_liq_usd": parse_usd(long_short.group(3)) if long_short else None,
        "short_share": float(long_short.group(4)) / 100 if long_short else None,
        "coins": coins,
    }


def fetch() -> str:
    req = urllib.request.Request(URL, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=URL)
    ap.add_argument("--offline", default=None, help="parse a saved HTML file instead of fetching")
    args = ap.parse_args()
    page = pathlib.Path(args.offline).read_text() if args.offline else fetch()
    parsed = parse_exchange(page)
    fetched_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    payload = {
        "source": args.url,
        "fetched_at": fetched_at.isoformat(),
        "exchange": "hyperliquid",
        **{k: v for k, v in parsed.items() if k != "coins"},
        "coins": parsed["coins"],
        "methodology": (
            "Dashboard values are aggregated from live derivatives data; liquidation bands are "
            "model-based estimates from OI, price and realized liquidations, not raw exchange levels."
        ),
    }
    SUMMARY.write_text(json.dumps(payload, indent=1))

    con = duckdb.connect(str(OUT))
    con.execute("""CREATE TABLE IF NOT EXISTS exchange_snapshots (
        fetched_at TIMESTAMP, exchange VARCHAR, open_interest_usd DOUBLE, volume_24h_usd DOUBLE,
        funding_pct DOUBLE, liq_24h_usd DOUBLE, contracts INTEGER, taker_fee_pct DOUBLE,
        maker_fee_pct DOUBLE, long_liq_usd DOUBLE, long_share DOUBLE,
        short_liq_usd DOUBLE, short_share DOUBLE)""")
    con.execute("""CREATE TABLE IF NOT EXISTS coin_snapshots (
        fetched_at TIMESTAMP, coin VARCHAR, price DOUBLE, oi_usd DOUBLE, funding_pct DOUBLE)""")
    con.execute(
        "INSERT INTO exchange_snapshots VALUES (?, 'hyperliquid', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [fetched_at, parsed["open_interest_usd"], parsed["volume_24h_usd"],
         parsed["funding_pct"], parsed["liq_24h_usd"], parsed["contracts"],
         parsed["taker_fee_pct"], parsed["maker_fee_pct"], parsed["long_liq_usd"],
         parsed["long_share"], parsed["short_liq_usd"], parsed["short_share"]],
    )
    for coin in parsed["coins"]:
        con.execute(
            "INSERT INTO coin_snapshots VALUES (?, ?, ?, ?, ?)",
            [fetched_at, coin["coin"], coin["price"], coin["oi_usd"], coin["funding_pct"]],
        )
    con.close()
    print(f"wrote {SUMMARY.relative_to(ROOT)} and {OUT.relative_to(ROOT)}")
    print(f"OI ${parsed['open_interest_usd']/1e9:.2f}B · volume ${parsed['volume_24h_usd']/1e9:.2f}B "
          f"· liq ${parsed['liq_24h_usd']/1e6:.2f}M · {len(parsed['coins'])} coins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
