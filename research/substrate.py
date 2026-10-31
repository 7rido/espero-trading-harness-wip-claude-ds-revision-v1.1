"""The research substrate: one DuckDB database with valid_time/known_time, manifests, gap reports,
and a universe that is a query rather than a frozen file.

    python research/substrate.py build
    python research/substrate.py universe 2022-12-31 47
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import zipfile
import datetime as dt

import duckdb
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "data_substrate"
MANIFEST = OUT / "manifest.sha256"


def read_zip(path: pathlib.Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    if str(df.iloc[0, 0]) in {"open_time", "calc_time"}:
        df = df.iloc[1:].reset_index(drop=True)
    return df


def to_date(v) -> pd.Series:
    v = pd.to_numeric(v, errors="coerce")
    unit = "us" if v.max() > 1e14 else ("ms" if v.max() > 1e11 else "s")
    return pd.to_datetime(v, unit=unit).dt.normalize()


def known(path: pathlib.Path) -> dt.datetime:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).replace(tzinfo=None)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute("""CREATE TABLE bars(symbol VARCHAR, date DATE, close DOUBLE, qvol DOUBLE,
                                    venue VARCHAR, known_time TIMESTAMP)""")
    con.execute("""CREATE TABLE funding(symbol VARCHAR, ts TIMESTAMP, rate DOUBLE,
                                         known_time TIMESTAMP)""")
    con.execute("""CREATE TABLE premium(symbol VARCHAR, date DATE, premium DOUBLE,
                                         known_time TIMESTAMP)""")
    con.execute("""CREATE TABLE depth(symbol VARCHAR, day DATE, pct DOUBLE, notional DOUBLE,
                                       known_time TIMESTAMP)""")
    con.execute("""CREATE TABLE prints(symbol VARCHAR, day DATE, last_price DOUBLE,
                                        known_time TIMESTAMP)""")

    def add_bars(root: pathlib.Path, venue: str) -> int:
        n = 0
        for d in sorted(root.iterdir()) if root.exists() else []:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.zip")):
                df = read_zip(p)
                if df.shape[1] < 8:
                    continue
                df.columns = ["ts", "open", "high", "low", "close", "vol", "ct", "qvol",
                              "n", "tb", "tbq", "ignore"][: df.shape[1]]
                rows = pd.DataFrame({
                    "symbol": d.name, "date": to_date(df["ts"]).dt.date,
                    "close": pd.to_numeric(df["close"], errors="coerce"),
                    "qvol": pd.to_numeric(df["qvol"], errors="coerce"),
                    "venue": venue, "known_time": known(p)})
                con.register("tmp", rows)
                con.execute("INSERT INTO bars SELECT * FROM tmp")
                con.unregister("tmp")
                n += len(rows)
        return n

    n_bars = add_bars(ROOT / "data_xs" / "perp", "binance-um") + add_bars(ROOT / "data_carry" / "perp", "binance-um")

    def add_funding(root: pathlib.Path) -> int:
        n = 0
        for d in sorted(root.iterdir()) if root.exists() else []:
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.zip")):
                df = read_zip(p)
                if df.shape[1] < 3:
                    continue
                df.columns = ["ts", "hours", "rate"][: df.shape[1]]
                rows = pd.DataFrame({"symbol": d.name, "ts": to_date(df["ts"]),
                                     "rate": pd.to_numeric(df["rate"], errors="coerce"),
                                     "known_time": known(p)})
                con.register("tmp", rows)
                con.execute("INSERT INTO funding SELECT * FROM tmp")
                con.unregister("tmp")
                n += len(rows)
        return n

    n_fund = add_funding(ROOT / "data_xs" / "funding") + add_funding(ROOT / "data_carry" / "funding")

    n_prem = n_depth = n_prints = 0
    for d in sorted((ROOT / "data_carry" / "premium").iterdir()) if (ROOT / "data_carry" / "premium").exists() else []:
        for p in sorted(d.glob("*.zip")):
            df = read_zip(p)
            if df.shape[1] < 5:
                continue
            df.columns = ["ts", "open", "high", "low", "close", "vol", "ct", "qvol", "n", "tb", "tbq", "ignore"][: df.shape[1]]
            rows = pd.DataFrame({"symbol": d.name, "date": to_date(df["ts"]).dt.date,
                                 "premium": pd.to_numeric(df["close"], errors="coerce"),
                                 "known_time": known(p)})
            con.register("tmp", rows)
            con.execute("INSERT INTO premium SELECT * FROM tmp")
            con.unregister("tmp")
            n_prem += len(rows)
    for root in (ROOT / "data_xs" / "depth", ROOT / "data_carry" / "depth"):
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.zip")):
                try:
                    df = pd.read_csv(io.BytesIO(zipfile.ZipFile(p).read(zipfile.ZipFile(p).namelist()[0])))
                except Exception:
                    continue
                day = p.stem.split("-", 1)[1]
                rows = pd.DataFrame({"symbol": d.name, "day": pd.Timestamp(day).date(),
                                     "pct": pd.to_numeric(df.get("percentage"), errors="coerce"),
                                     "notional": pd.to_numeric(df.get("notional"), errors="coerce"),
                                     "known_time": known(p)})
                con.register("tmp", rows)
                con.execute("INSERT INTO depth SELECT * FROM tmp")
                con.unregister("tmp")
                n_depth += len(rows)

    con.execute("CREATE INDEX IF NOT EXISTS idx_bars ON bars(symbol, date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fund ON funding(symbol, ts)")
    con.close()

    # the source archives already carry their own manifests; record them plus the database itself
    lines = []
    for m in (ROOT / "data_xs" / "manifest.sha256", ROOT / "data_carry" / "manifest.sha256"):
        if m.exists():
            lines.append(f"# from {m.relative_to(ROOT)}")
            lines += m.read_text().splitlines()
    lines.append(f"{hashlib.sha256(DB.read_bytes()).hexdigest()}  {DB.relative_to(ROOT)}")
    MANIFEST.write_text("\n".join(lines) + "\n")
    report = {"bars": n_bars, "funding": n_fund, "premium": n_prem, "depth": n_depth,
              "manifest_files": len(lines)}
    (OUT / "build.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


def gaps() -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    dupes = con.execute("""SELECT 'bars' t, COUNT(*) - COUNT(DISTINCT (symbol, date)) AS dupes FROM bars
        UNION ALL SELECT 'funding', COUNT(*) - COUNT(DISTINCT (symbol, ts)) FROM funding
        UNION ALL SELECT 'premium', COUNT(*) - COUNT(DISTINCT (symbol, date)) FROM premium
        UNION ALL SELECT 'depth', COUNT(*) - COUNT(DISTINCT (symbol, day, pct)) FROM depth
        UNION ALL SELECT 'prints', COUNT(*) - COUNT(DISTINCT (symbol, day)) FROM prints""").df()
    per_symbol = con.execute("""
        WITH d AS (SELECT symbol, date, LAG(date) OVER (PARTITION BY symbol ORDER BY date) AS prev FROM bars)
        SELECT symbol, COUNT(*) AS gaps, MAX(date - prev) AS max_gap_days
        FROM d WHERE prev IS NOT NULL AND date - prev > 1 GROUP BY symbol ORDER BY gaps DESC LIMIT 10
    """).df()
    con.close()
    return {"duplicates": dupes.to_dict("records"), "largest_gaps": per_symbol.to_dict("records")}


def universe(date: str = "2022-12-31", n: int = 47, min_history: int = 30) -> list[str]:
    """A query, not a file: top N by trailing 30-day mean quote volume at a date."""
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""
        WITH windows AS (
          SELECT symbol, AVG(qvol) AS av, COUNT(*) AS days
          FROM bars
          WHERE date > CAST(? AS DATE) - INTERVAL 30 DAY AND date <= CAST(? AS DATE)
          GROUP BY symbol
        )
        , ranked AS (
          SELECT symbol, av,
                 ROW_NUMBER() OVER (PARTITION BY regexp_replace(symbol, '(USDT|BUSD|USDC|USD)$', '')
                                    ORDER BY av DESC) AS rn
          FROM windows WHERE days >= 20
        )
        SELECT symbol FROM ranked WHERE rn = 1 ORDER BY av DESC LIMIT ?
    """, [date, date, n]).df()
    con.close()
    return df["symbol"].tolist()


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "build"
    if what == "build":
        build()
        print(json.dumps(gaps(), indent=1)[:800])
    elif what == "universe":
        date = argv[1] if len(argv) > 1 else "2022-12-31"
        n = int(argv[2]) if len(argv) > 2 else 47
        found = universe(date, n)
        frozen = [l.split(",")[0] for l in (ROOT / "research" / "xs_universe.csv").read_text().splitlines()[1:]]
        overlap = len(set(found) & set(frozen))
        print(f"query universe at {date}: {len(found)} names; overlap with frozen 47: {overlap}")
        print("only in query:", sorted(set(found) - set(frozen))[:10])
        print("only in frozen:", sorted(set(frozen) - set(found))[:10])
    else:
        print("usage: build|universe [date] [n]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
