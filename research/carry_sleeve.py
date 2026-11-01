"""Paper delta-neutral funding-carry sleeve (pre-registered in PREREGISTRATION_carry_sleeve.md).

    python research/carry_sleeve.py            # daily check: accrue, mark, enter/exit
    python research/carry_sleeve.py --status   # show state without touching the venue

Long Coinbase spot, short Hyperliquid perp, $1,000 per side, fees 5 + 4.5 bps + 2 bps slippage per fill.
Nothing here can place an order; fills are simulated at the quoted touch plus slippage.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from espero2 import hl  # noqa: E402

STATE = ROOT / "research" / "carry_sleeve.json"
CURVE = ROOT / "research" / "carry_sleeve_curve.csv"
COINS = ["BTC", "ETH", "SOL"]
NOTIONAL = 1_000.0
CAPITAL = 10_000.0
ENTRY_FUNDING = 5.0        # %/yr, 7-day mean on HL
SPREAD_MAX = 5.0           # bps
EXIT_FUNDING_DAYS = 2
EXIT_BASIS_BPS = -10.0
EXIT_BASIS_DAYS = 2
BUFFER_MIN = 0.25
FEE_SPOT = 5e-4            # 5 bps
FEE_HL = 4.5e-4            # 4.5 bps
SLIP = 2e-4                # 2 bps per fill
UA = {"User-Agent": "espero2/0.1"}


def coinbase(coin: str) -> dict:
    url = f"https://api.exchange.coinbase.com/products/{coin}-USD/ticker"
    t = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())
    bid, ask = float(t["bid"]), float(t["ask"])
    mid = (bid + ask) / 2
    return {"bid": bid, "ask": ask, "mid": mid, "spread_bps": 1e4 * (ask - bid) / mid}


def hl_market(coin: str) -> dict:
    meta, ctxs = hl._post("/info", {"type": "metaAndAssetCtxs"}, base=hl.MAINNET)  # noqa: SLF001
    names = [u["name"] for u in meta["universe"]]
    c = ctxs[names.index(coin)]
    return {"mark": float(c["markPx"]), "funding": float(c["funding"]),
            "premium": 1e4 * float(c.get("premium", 0) or 0)}


def funding_annual(coin: str, days: int = 7) -> float:
    now = int(time.time() * 1000)
    hist = hl._post("/info", {"type": "fundingHistory", "coin": coin,  # noqa: SLF001
                              "startTime": now - days * 86_400_000}, base=hl.MAINNET)
    rates = [float(x["fundingRate"]) for x in hist if int(x["time"]) > now - days * 86_400_000]
    return 1e2 * (sum(rates) / len(rates)) * 8760 if rates else 0.0


def funding_since(coin: str, since_ms: int) -> float:
    now = int(time.time() * 1000)
    hist = hl._post("/info", {"type": "fundingHistory", "coin": coin,  # noqa: SLF001
                              "startTime": since_ms}, base=hl.MAINNET)
    return sum(float(x["fundingRate"]) for x in hist if int(x["time"]) > since_ms)


def should_enter(funding_ann: float, basis_bps: float, spread_bps: float) -> bool:
    return funding_ann >= ENTRY_FUNDING and basis_bps >= 0 and spread_bps <= SPREAD_MAX


def should_exit(pos: dict, funding_ann: float, basis_bps: float) -> str | None:
    if pos["neg_funding_days"] >= EXIT_FUNDING_DAYS:
        return "funding negative two checks"
    if pos["neg_basis_days"] >= EXIT_BASIS_DAYS:
        return "basis inverted two checks"
    buffer = (NOTIONAL + pos["perp_pnl"]) / NOTIONAL
    if buffer < BUFFER_MIN:
        return "margin buffer below 25%"
    return None


def load() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"started": None, "positions": {}, "closed": [], "last_check": int(time.time() * 1000),
            "funding_cum": 0.0, "fees_cum": 0.0}


def mark(coin: str, pos: dict, spot: dict, perp: dict) -> dict:
    spot_pnl = (spot["mid"] - pos["spot_entry"]) * pos["spot_qty"]
    perp_pnl = (pos["perp_entry"] - perp["mark"]) * pos["perp_qty"]
    pos["spot_pnl"] = spot_pnl
    pos["perp_pnl"] = perp_pnl
    pos["funding_pnl"] = pos["funding_cum"]
    pos["net"] = spot_pnl + perp_pnl + pos["funding_cum"] - pos["fees"]
    return pos


def check() -> int:
    st = load()
    now_ms = int(time.time() * 1000)
    st.setdefault("started", now_ms)
    for coin in COINS:
        spot, perp = coinbase(coin), hl_market(coin)
        basis = 1e4 * (perp["mark"] / spot["mid"] - 1)
        fund = funding_annual(coin)
        pos = st["positions"].get(coin)
        if pos:
            accrued = funding_since(coin, st["last_check"]) * pos["perp_qty"] * pos["perp_entry"]
            pos["funding_cum"] += accrued
            st["funding_cum"] += accrued
            pos["neg_funding_days"] = pos["neg_funding_days"] + 1 if fund < 0 else 0
            pos["neg_basis_days"] = pos["neg_basis_days"] + 1 if basis < EXIT_BASIS_BPS else 0
            pos = mark(coin, pos, spot, perp)
            reason = should_exit(pos, fund, basis)
            if reason:
                close_spot = spot["bid"] * (1 - SLIP)
                close_perp = perp["mark"] * (1 + SLIP)
                fees = (pos["spot_qty"] * close_spot + pos["perp_qty"] * close_perp) * (FEE_SPOT + FEE_HL)
                pos["fees"] += fees
                st["fees_cum"] += fees
                pos["closed"] = True
                pos["exit_reason"] = reason
                st["closed"].append({"coin": coin, "reason": reason, "net": pos["net"] - fees})
                del st["positions"][coin]
            else:
                st["positions"][coin] = pos
        elif should_enter(fund, basis, spot["spread_bps"]):
            buy = spot["ask"] * (1 + SLIP)
            sell = perp["mark"] * (1 - SLIP)
            qty_spot = NOTIONAL / buy
            qty_perp = NOTIONAL / sell
            fees = NOTIONAL * (FEE_SPOT + FEE_HL)
            st["fees_cum"] += fees
            st["positions"][coin] = {
                "opened": now_ms, "spot_entry": buy, "spot_qty": qty_spot,
                "perp_entry": sell, "perp_qty": qty_perp,
                "funding_cum": 0.0, "fees": fees, "neg_funding_days": 0, "neg_basis_days": 0,
                "perp_pnl": 0.0, "net": -fees}
        print(f"  {coin}: spot {spot['mid']:,.2f} spread {spot['spread_bps']:.2f}bps · "
              f"HL {perp['mark']:,.2f} basis {basis:+.1f}bps · funding {fund:+.1f}%/yr · "
              f"{'OPEN' if coin in st['positions'] else 'flat'}")
    st["last_check"] = now_ms
    total = (sum(p.get("net", 0.0) for p in st["positions"].values())
             + sum(c["net"] for c in st["closed"]) + sum(p.get("funding_cum", 0.0)
                                                          for p in st["positions"].values()))
    st["net"] = total
    STATE.write_text(json.dumps(st, indent=1))
    header = not CURVE.exists()
    import csv
    with CURVE.open("a", newline="") as f:
        w = csv.writer(f)
        if header:
            w.writerow(["at", "positions", "funding_cum", "fees_cum", "net"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), len(st["positions"]),
                    round(st["funding_cum"], 4), round(st["fees_cum"], 4), round(total, 4)])
    print(f"sleeve: {len(st['positions'])} open · funding {st['funding_cum']:+.2f} · "
          f"fees {st['fees_cum']:.2f} · net {total:+.2f}")
    return 0


def status() -> int:
    st = load()
    print(json.dumps({k: st.get(k) for k in ("started", "funding_cum", "fees_cum", "net")}, indent=1))
    for coin, p in st.get("positions", {}).items():
        print(f"  {coin}: entry spot {p['spot_entry']:,.2f} perp {p['perp_entry']:,.2f} "
              f"net {p.get('net', 0):+.2f} funding {p['funding_cum']:+.4f}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)
    return status() if args.status else check()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
