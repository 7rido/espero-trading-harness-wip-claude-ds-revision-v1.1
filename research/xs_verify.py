"""Close the three verification gaps in the XS momentum result (P2 capacity, aggTrades prints,
independent re-computation).

    python research/xs_verify.py capacity
    python research/xs_verify.py prints
    python research/xs_verify.py sql
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW_XS = ROOT / "data_xs"
DEPTH = ROOT / "data_xs" / "depth"
AGG = ROOT / "data_xs" / "agg"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UA = {"User-Agent": "espero2-xs-verify/1.0"}
UNIVERSE = [l.split(",")[0] for l in (ROOT / "research" / "xs_universe.csv").read_text().splitlines()[1:] if l]
OUT = ROOT / "research" / "xs_verify.json"


def get(url: str, dest: pathlib.Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    except Exception:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def read_zip(path: pathlib.Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        return pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=0)


def capacity() -> dict:
    """$ notional that moves the book by 25 bps (half a 0.5%/week net edge)."""
    dates = ["2022-03-15", "2022-06-15", "2022-09-15", "2022-12-15",
             "2023-03-15", "2023-06-15", "2023-09-15", "2023-12-15"]
    rows = []
    for sym in UNIVERSE[:15]:
        caps = []
        for day in dates:
            z = DEPTH / f"{sym}-{day}.zip"
            url = f"{S3}/data/futures/um/daily/bookDepth/{sym}/{sym}-bookDepth-{day}.zip"
            if not get(url, z):
                continue
            try:
                df = read_zip(z)
            except Exception:
                continue
            df.columns = ["ts", "pct", "depth", "notional"]
            one = pd.to_numeric(df.loc[df["pct"] == 1, "notional"], errors="coerce")
            if len(one):
                caps.append(float(one.median()) * 0.25)     # 0.25% of price = 25 bps
        if caps:
            rows.append({"symbol": sym, "capacity_usd": float(np.median(caps))})
    if not rows:
        return {"computed": False}
    by = pd.DataFrame(rows)
    return {"computed": True, "symbols": int(len(by)),
            "median_capacity_usd": float(by["capacity_usd"].median()),
            "total_usd": float(by["capacity_usd"].sum()),
            "per_symbol": {r["symbol"]: r["capacity_usd"] for _, r in by.iterrows()}}


def _closes(sym: str) -> pd.Series:
    closes = []
    for y in (2022, 2023):
        for m in range(1, 13):
            p = RAW_XS / "perp" / sym / f"{y}-{m:02d}.zip"
            if not p.exists():
                continue
            df = pd.read_csv(io.BytesIO(zipfile.ZipFile(p).read(zipfile.ZipFile(p).namelist()[0])),
                             header=None)
            if str(df.iloc[0, 0]) == "open_time":
                df = df.iloc[1:]
            t = pd.to_numeric(df[0], errors="coerce")
            unit = "us" if t.max() > 1e14 else ("ms" if t.max() > 1e11 else "s")
            idx = pd.to_datetime(t, unit=unit).dt.normalize()
            closes.append(pd.Series(pd.to_numeric(df[4], errors="coerce").to_numpy(), index=idx))
    return pd.concat(closes).sort_index() if closes else pd.Series(dtype=float)


def prints(n: int = 10, seed: int = 3) -> dict:
    """The day's last hourly aggTrades print against the klines daily close."""
    rng = np.random.default_rng(seed)
    checks = []
    syms = UNIVERSE[:12]
    for _ in range(n):
        sym = syms[int(rng.integers(0, len(syms)))]
        day = f"2023-{int(rng.integers(1, 13)):02d}-{int(rng.integers(10, 26)):02d}"
        z = AGG / f"{sym}-{day}.zip"
        url = f"{S3}/data/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"
        if not get(url, z):
            checks.append({"symbol": sym, "day": day, "status": "file missing"})
            continue
        try:
            df = read_zip(z)
            last = float(df["price"].iloc[-1])
        except Exception as exc:                      # noqa: BLE001
            checks.append({"symbol": sym, "day": day, "status": f"parse: {type(exc).__name__}"})
            continue
        close = _closes(sym)
        day_val = close.get(pd.Timestamp(day))
        ok = day_val is not None and np.isfinite(day_val) and abs(last / float(day_val) - 1) < 1e-6
        checks.append({"symbol": sym, "day": day, "last_print": last,
                       "kline_close": None if day_val is None else float(day_val), "match": bool(ok)})
    matched = [c for c in checks if c.get("match")]
    return {"checked": len(checks), "matched": len(matched), "details": checks}


def sql() -> dict:
    """Independent DuckDB recomputation of the weekly long/short gross spread."""
    import duckdb
    rows = []
    for sym in UNIVERSE:
        c = _closes(sym)
        if len(c) < 60:
            continue
        for d, v in c.items():
            rows.append({"symbol": sym, "date": d.date(), "close": float(v)})
    pq = ROOT / "data_xs" / "panel.parquet"
    pq.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(pq, index=False)
    q = """
    WITH px AS (
      SELECT symbol, date, close,
             LEAD(close, 7) OVER (PARTITION BY symbol ORDER BY date) AS fwd
      FROM read_parquet(?)
    ), sig AS (
      SELECT symbol, date, close,
             close / LAG(close, 30) OVER (PARTITION BY symbol ORDER BY date) - 1 AS r
      FROM read_parquet(?)
    ), fri AS (
      SELECT DISTINCT date FROM sig WHERE dayofweek(date) = 5 AND r IS NOT NULL
    ), ranked AS (
      SELECT s.date, s.symbol, s.r,
             ROW_NUMBER() OVER (PARTITION BY s.date ORDER BY s.r DESC) AS rn,
             COUNT(*) OVER (PARTITION BY s.date) AS n
      FROM sig s JOIN fri f USING (date)
      WHERE s.r IS NOT NULL
    ), picks AS (
      SELECT date, symbol, n,
             CASE WHEN rn <= floor(n/5) THEN 1.0/floor(n/5)
                  WHEN rn > n - floor(n/5) THEN -1.0/floor(n/5) END AS w
      FROM ranked
    ), joined AS (
      SELECT p.date, p.w, px.fwd / px.close - 1 AS fwd_ret
      FROM picks p JOIN px ON px.symbol = p.symbol AND px.date = p.date
      WHERE p.w IS NOT NULL AND px.fwd IS NOT NULL
    )
    SELECT date, SUM(w * fwd_ret) AS gross FROM joined GROUP BY date ORDER BY date
    """
    df = duckdb.connect().execute(q, [str(pq), str(pq)]).df()
    design = df[df["date"].astype(str) < "2023-01-01"]["gross"]
    hold = df[df["date"].astype(str) >= "2023-01-01"]["gross"]
    return {"weeks_design": int(len(design)), "weeks_holdout": int(len(hold)),
            "design_ann_pct": 100 * 52 * float(design.mean()),
            "holdout_ann_pct": 100 * 52 * float(hold.mean())}


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "all"
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    if what in ("capacity", "all"):
        out["capacity"] = capacity()
    if what in ("prints", "all"):
        out["prints"] = prints()
    if what in ("sql", "all"):
        out["sql_gross"] = sql()
    OUT.write_text(json.dumps(out, indent=1, default=str))
    if "capacity" in out:
        c = out["capacity"]
        if c.get("computed"):
            print(f"capacity: median ${c['median_capacity_usd']:,.0f}/symbol (25 bps impact), "
                  f"${c['total_usd']:,.0f} across {c['symbols']}")
        else:
            print("capacity: no depth files fetched")
    if "prints" in out:
        p = out["prints"]
        print(f"aggTrades prints: {p['matched']}/{p['checked']} match the daily close")
    if "sql_gross" in out:
        s = out["sql_gross"]
        print(f"duckdb gross: design {s['design_ann_pct']:+.1f}%/yr over {s['weeks_design']} weeks, "
              f"holdout {s['holdout_ann_pct']:+.1f}%/yr over {s['weeks_holdout']} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
