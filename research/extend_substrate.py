"""Phase 0: extend the substrate with 2020-2026 daily bars and realised variance from the 5m archive.

    python research/extend_substrate.py build
    python research/extend_substrate.py report
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import zipfile

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
LOWS = ROOT / "data_raw" / "lows"
COLS = ["ts", "open", "high", "low", "close", "volume", "close_time", "qvol", "count",
        "taker_buy", "taker_buy_qvol", "ignore"]


def month_frame(path: pathlib.Path) -> pd.DataFrame | None:
    try:
        with zipfile.ZipFile(path) as z:
            df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), header=None)
    except (zipfile.BadZipFile, IndexError, OSError):
        return None
    if df.empty or str(df.iloc[0, 0]) == "open_time":
        df = df.iloc[1:] if str(df.iloc[0, 0]) == "open_time" else df
    if df.empty:
        return None
    df.columns = COLS[: df.shape[1]]
    for c in ("open", "high", "low", "close", "volume", "qvol"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts", "close"])
    if df.empty:
        return None
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", errors="coerce")
    df["date"] = df["dt"].dt.normalize()
    df["r"] = np.log(df["close"]).diff()
    return df


def daily_from_symbol(sym_dir: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    frames = []
    for p in sorted(sym_dir.glob("*.zip")):
        f = month_frame(p)
        if f is not None:
            frames.append(f)
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True).sort_values("dt")
    d["r"] = np.log(d["close"]).diff()
    g = d.groupby("date", sort=True)
    daily = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
        "close": g["close"].last(), "volume": g["volume"].sum(), "qvol": g["qvol"].sum(),
        "bars": g["close"].count(),
    })
    rv = g["r"].apply(lambda x: float(np.nansum(np.square(x.to_numpy(dtype=float)))))
    park = np.square(np.log(daily["high"] / daily["low"])) / (4 * np.log(2))
    hl = np.log(daily["high"] / daily["low"])
    co = np.log(daily["close"] / daily["open"])
    gk = 0.5 * np.square(hl) - (2 * np.log(2) - 1) * np.square(co)
    rv_df = pd.DataFrame({"rv": rv, "parkinson": park, "gk": gk.clip(lower=0)})
    rv_df["rv_w"] = rv_df["rv"].rolling(5).mean()
    rv_df["rv_m"] = rv_df["rv"].rolling(22).mean()
    return daily.reset_index(), rv_df.reset_index()


def build() -> None:
    con = duckdb.connect(str(DB))
    con.execute("DROP TABLE IF EXISTS bars_daily")
    con.execute("DROP TABLE IF EXISTS rv")
    con.execute("""CREATE TABLE bars_daily(symbol VARCHAR, date DATE, open DOUBLE, high DOUBLE,
                    low DOUBLE, close DOUBLE, volume DOUBLE, qvol DOUBLE, bars INTEGER,
                    known_time TIMESTAMP)""")
    con.execute("""CREATE TABLE rv(symbol VARCHAR, date DATE, rv DOUBLE, rv_w DOUBLE, rv_m DOUBLE,
                    parkinson DOUBLE, gk DOUBLE, known_time TIMESTAMP)""")
    symbols = 0
    for sym_dir in sorted(LOWS.iterdir()):
        if not sym_dir.is_dir():
            continue
        out = daily_from_symbol(sym_dir)
        if out is None:
            continue
        daily, rv = out
        known = pd.Timestamp.utcnow().tz_localize(None)
        daily = daily.assign(symbol=sym_dir.name, known_time=known)
        rv = rv.assign(symbol=sym_dir.name, known_time=known)
        con.register("d", daily[["symbol", "date", "open", "high", "low", "close", "volume",
                                 "qvol", "bars", "known_time"]])
        con.execute("INSERT INTO bars_daily SELECT * FROM d")
        con.unregister("d")
        con.register("r", rv[["symbol", "date", "rv", "rv_w", "rv_m", "parkinson", "gk", "known_time"]])
        con.execute("INSERT INTO rv SELECT * FROM r")
        con.unregister("r")
        symbols += 1
    con.close()
    print(f"{symbols} symbols ingested")


def report() -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    out = {}
    for t in ("bars_daily", "rv"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        dup = con.execute(f"SELECT COUNT(*) - COUNT(DISTINCT (symbol, date)) FROM {t}").fetchone()[0]
        syms = con.execute(f"SELECT COUNT(DISTINCT symbol) FROM {t}").fetchone()[0]
        span = con.execute(f"SELECT MIN(date), MAX(date) FROM {t}").fetchone()
        out[t] = {"rows": n, "duplicates": dup, "symbols": syms, "span": [str(span[0]), str(span[1])]}
    con.close()
    (ROOT / "data_substrate" / "extend_report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "build"
    if what == "build":
        build()
        report()
    elif what == "report":
        report()
    else:
        print("usage: build|report", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
