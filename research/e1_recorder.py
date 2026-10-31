"""E1 recorder: the executable forced-liquidation bounce, status now, score after 2027-04-30.

    python research/e1_recorder.py                 # status only: days, events, holds, gaps
    python research/e1_recorder.py --score         # refused until the window closes

Events come from #27's ledger (`liqbreak_trades.csv`), prices from the 5-minute bars in
`data/lows/forward/`, funding from `data/funding/`. Tagging is **prior-day**: today's break is
classified against yesterday's terciles of the forced share, so the rule is executable at entry.
Registration: research/PREREGISTRATION_2026-10-30-liq-executable.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import pathlib
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "liqbreak_trades.csv"
LEDGER = DEFAULT_LEDGER
BARS = ROOT / "data" / "lows" / "forward"
FUNDING = ROOT / "data" / "funding"
OUT = ROOT / "research" / "e1_status.json"
BAR = 300
HOLDS = {"4h": 48, "12h": 144, "1d": 288}
COST = 0.0009                       # 9 bps round trip: two Hyperliquid taker fills at 4.5 bps
WINDOW_FROM = dt.date(2026, 10, 31)
WINDOW_TO = dt.date(2027, 4, 30)
COIN_SYMBOL = {"SHIB": "1000SHIBUSDT"}


def load_events(path: pathlib.Path | None = None) -> pd.DataFrame:
    """Prefer the locally derived feed (raw aggr + 5m bars) over the maintainer's ledger, which can
    fail without anything being wrong in the market."""
    local = ROOT / "research" / "e1_events.csv"
    if path is None:
        if LEDGER != DEFAULT_LEDGER:                 # a test or caller redirected the ledger
            path = LEDGER
        else:
            path = local if local.exists() and local.stat().st_size > 10 else LEDGER
    empty = pd.DataFrame(columns=["coin", "day", "ts", "direction", "s"])
    if not path.exists() or path.stat().st_size < 2:
        return empty
    try:
        ev = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return empty
    if ev.empty or "coin" not in ev.columns:
        return empty
    keep = [c for c in ("coin", "day", "ts", "direction", "s", "group") if c in ev.columns]
    return ev[keep].dropna(subset=["coin", "day", "ts", "direction", "s"])


def _bars_from_zip(path: pathlib.Path) -> pd.DataFrame | None:
    try:
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                raw = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])))
        else:
            raw = pd.read_csv(gzip.open(path))
    except (zipfile.BadZipFile, IndexError, OSError):
        return None
    if raw.empty:
        return None
    ts = raw["open_time"].to_numpy("int64") // 1000
    return pd.DataFrame({"open": raw["open"].to_numpy(float), "close": raw["close"].to_numpy(float)},
                        index=ts // BAR * BAR).sort_index()[lambda d: ~d.index.duplicated()]


def bars(coin: str, day: str) -> pd.DataFrame | None:
    sym = COIN_SYMBOL.get(coin, f"{coin}USDT")
    folder = BARS / sym
    if not folder.is_dir():
        return None
    for name in (f"{day}.zip", f"{day}.csv", f"{day}.csv.gz"):
        p = folder / name
        if p.exists():
            return _bars_from_zip(p)
    return None


def prior_day_tags(ev: pd.DataFrame) -> pd.Series:
    """Today's s against yesterday's terciles (all coins that day). No same-day distribution."""
    if ev.empty:
        return pd.Series(dtype=object)
    ev = ev.sort_values(["day", "ts"])
    q = ev.groupby("day")["s"].apply(lambda x: (x.quantile(1 / 3), x.quantile(2 / 3))).to_dict()
    order = sorted(q)
    prev = {order[i]: q[order[i - 1]] for i in range(1, len(order))}
    tags = []
    for day, s in zip(ev["day"], ev["s"]):
        lo_hi = prev.get(day)
        if lo_hi is None:
            tags.append("middle")
        else:
            lo, hi = lo_hi
            tags.append("forced" if s > hi else ("organic" if s <= lo else "middle"))
    out = pd.Series(tags, index=ev.index, dtype=object)
    return out.reindex(ev.index)


def funding_cost(coin: str, start: int, end: int) -> tuple[float, bool]:
    """Sum of realised funding rates in (start, end]; a long pays a positive rate. Missing data
    returns (0.0, False) so the caller can report coverage instead of pretending."""
    folder = FUNDING / COIN_SYMBOL.get(coin, f"{coin}USDT")
    if not folder.is_dir():
        return 0.0, False
    total, seen = 0.0, False
    for z in sorted(folder.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                raw = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])))
        except (zipfile.BadZipFile, IndexError, OSError):
            continue
        cols = {c.lower(): c for c in raw.columns}
        rate_col = next((cols[c] for c in cols if "funding" in c and "rate" in c), None)
        time_col = next((cols[c] for c in cols if "time" in c), None)
        if not rate_col or not time_col:
            continue
        t = raw[time_col].to_numpy("int64")
        t = t // 1000 if t.max() > 10 ** 12 else t
        m = (t > start) & (t <= end)
        if m.any():
            total += float(raw.loc[m, rate_col].sum())
            seen = True
    return total, seen


def trades(ev: pd.DataFrame, tags: pd.Series) -> pd.DataFrame:
    """Buy forced down-breaks, hold 4 h / 12 h / 1 d, net of cost and funding."""
    if ev.empty:
        return pd.DataFrame()
    ev = ev.assign(tag=tags)
    sel = ev[(ev["direction"] == -1) & (ev["tag"] == "forced")]
    rows = []
    for _, r in sel.iterrows():
        day = str(r["day"])[:10]
        b = bars(r["coin"], day)
        if b is None or b.empty:
            rows.append({"coin": r["coin"], "day": day, "ts": int(r["ts"]), "missing": True})
            continue
        entry_i = b.index.searchsorted(int(r["ts"]))
        if entry_i >= len(b):
            rows.append({"coin": r["coin"], "day": day, "ts": int(r["ts"]), "missing": True})
            continue
        entry = float(b["open"].iloc[entry_i])
        rec = {"coin": r["coin"], "day": day, "ts": int(r["ts"]), "missing": False}
        for name, k in HOLDS.items():
            j = b.index.searchsorted(int(r["ts"]) + k * BAR)
            if j >= len(b) or entry <= 0:
                rec[name] = np.nan
                continue
            gross = float(b["close"].iloc[j]) / entry - 1
            fund, seen = funding_cost(r["coin"], int(r["ts"]), int(b.index[j]))
            rec[name] = gross - COST - fund
            rec[f"{name}_funding_seen"] = seen
        rows.append(rec)
    return pd.DataFrame(rows)


def status(ev: pd.DataFrame, tr: pd.DataFrame) -> dict:
    days = sorted({str(d)[:10] for d in ev["day"]}) if len(ev) else []
    today = dt.date.today()
    return {
        "window": [str(WINDOW_FROM), str(WINDOW_TO)],
        "window_state": ("not opened" if today < WINDOW_FROM else
                         "open" if today <= WINDOW_TO else "closed"),
        "ledger_exists": LEDGER.exists(),
        "ledger_bytes": LEDGER.stat().st_size if LEDGER.exists() else 0,
        "events": int(len(ev)),
        "days_with_events": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "forced_down_breaks": int(len(tr)),
        "complete_holds": {h: int(tr[h].notna().sum()) if len(tr) else 0 for h in HOLDS},
        "missing_bars": int(tr["missing"].sum()) if len(tr) else 0,
        "coins": sorted(ev["coin"].unique().tolist()) if len(ev) else [],
        "trades_scored": False,
    }


def clustered(df: pd.DataFrame, col: str) -> dict:
    d = df.dropna(subset=[col])
    if d.empty:
        return {"events": 0, "mean_bps": None, "t": None, "days": 0}
    g = d.groupby("day")[col].agg(["sum", "count"])
    if len(g) < 3:
        return {"events": int(len(d)), "mean_bps": None, "t": None, "days": int(len(g))}
    m = g["sum"].sum() / g["count"].sum()
    k = len(g)
    se = np.sqrt(k / (k - 1) * ((g["sum"] - m * g["count"]) ** 2).sum()) / g["count"].sum()
    return {"events": int(len(d)), "mean_bps": 1e4 * float(m),
            "t": float(m / se) if se > 0 else None, "days": int(k)}


def score(ev: pd.DataFrame, tr: pd.DataFrame) -> dict:
    if len(tr) == 0:
        return {"verdict": "no trades yet"}
    out = {h: clustered(tr, h) for h in HOLDS}
    first = dt.date.fromisoformat(str(tr["day"].min()))
    c1 = (out["4h"]["mean_bps"] or 0) > 0 and (out["4h"]["t"] or 0) >= 3
    c2 = all((out[h]["mean_bps"] or -1) > 0 and (out[h]["t"] or 0) > 2 for h in ("12h", "1d"))
    half = first + (WINDOW_TO - first) / 2
    a = tr[pd.to_datetime(tr["day"]).dt.date <= half]
    b = tr[pd.to_datetime(tr["day"]).dt.date > half]
    c3 = (clustered(a, "4h")["mean_bps"] or -1) > 0 and (clustered(b, "4h")["mean_bps"] or -1) > 0
    return {"horizons": out, "criteria": {"1_4h": c1, "2_longer": c2, "3_halves": c3,
                                          "4_D": "reported in the result, needs the Y series"},
            "verdict": "PASS" if (c1 and c2 and c3) else "FAIL"}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true")
    args = ap.parse_args(argv)
    ev = load_events()
    tr = trades(ev, prior_day_tags(ev)) if not ev.empty else pd.DataFrame()
    st = status(ev, tr)
    if args.score:
        if dt.date.today() <= WINDOW_TO:
            print(f"refused: E1 closes {WINDOW_TO}; scoring before then would read interim P&L",
                  flush=True)
            return 2
        st["score"] = score(ev, tr)
        st["trades_scored"] = True
    OUT.write_text(json.dumps(st, indent=1, default=str))
    for k, v in st.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
