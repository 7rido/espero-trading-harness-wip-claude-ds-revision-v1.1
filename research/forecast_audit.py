"""Forecast audit and walk-forward evaluation.

Two jobs, both read-only with respect to the live substrate:

    python research/forecast_audit.py --coverage
    python research/forecast_audit.py --eval

`--coverage` reports which substrate tables can support a forecast for the
current forecast universe. `--eval` runs a purged walk-forward comparison of
the existing state-cell forecast against the unconditional baseline, scored by
CRPS, Brier and PIT. It does not touch paper books, the ledger, or any order
path.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import pathlib
from collections import defaultdict

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
FORECAST = ROOT / "research" / "forecast.json"
OUT_COVERAGE = ROOT / "research" / "forecast_audit.json"
OUT_EVAL = ROOT / "research" / "forecast_eval.json"
TEST_START = "2023-01-01"
EMBARGO_DAYS = 20
MIN_TRAIN = 100
TARGET = "x20"
TABLES = (
    ("bars_daily", "date"),
    ("rv", "date"),
    ("funding", "ts"),
    ("funding_multi", "ts"),
    ("metrics", "ts"),
    ("tardis_derivative", "ts"),
    ("tardis_liquidations", "ts"),
)


def _regime_module():
    path = ROOT / "research" / "regime_signs.py"
    spec = importlib.util.spec_from_file_location("regime_signs", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _symbol_variants(coin: str) -> tuple[str, ...]:
    return (coin, f"{coin}USDT", f"{coin}-USDT-SWAP")


def _table_stats(con: duckdb.DuckDBPyConnection) -> dict:
    out = {}
    for table, date_col in TABLES:
        try:
            row = con.execute(
                f"SELECT count(*), count(DISTINCT symbol), min({date_col}), max({date_col}) FROM {table}"
            ).fetchone()
            out[table] = {
                "rows": int(row[0]),
                "symbols": int(row[1]),
                "from": str(row[2]) if row[2] is not None else None,
                "to": str(row[3]) if row[3] is not None else None,
            }
        except Exception as exc:  # a missing table is coverage information, not a crash
            out[table] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def coverage() -> dict:
    """Report substrate coverage for the live forecast universe, if present."""
    con = duckdb.connect(str(DB), read_only=True)
    stats = _table_stats(con)
    forecast_rows = []
    if FORECAST.exists():
        forecast_rows = json.loads(FORECAST.read_text()).get("rows", [])
    coins = sorted({str(row.get("coin")) for row in forecast_rows if row.get("coin")})
    current = []
    for coin in coins:
        variants = _symbol_variants(coin)
        marks: dict[str, int | None] = {}
        for table in ("bars_daily", "rv", "funding_multi", "metrics", "tardis_derivative"):
            try:
                if table == "funding_multi":
                    marks[table] = int(con.execute(
                        "SELECT count(*) FROM funding_multi WHERE symbol IN (?, ?, ?)", variants
                    ).fetchone()[0])
                else:
                    marks[table] = int(con.execute(
                        f"SELECT count(*) FROM {table} WHERE symbol IN (?, ?, ?)", variants
                    ).fetchone()[0])
            except Exception:
                marks[table] = None
        if not marks.get("bars_daily"):
            verdict = "no price history"
        elif not marks.get("rv"):
            verdict = "no RV history"
        elif not marks.get("funding_multi"):
            verdict = "no current funding"
        else:
            verdict = "covered"
        current.append({"coin": coin, "counts": marks, "verdict": verdict})
    con.close()
    result = {
        "tables": stats,
        "forecast_at": json.loads(FORECAST.read_text()).get("at") if FORECAST.exists() else None,
        "current_universe": current,
        "notes": [
            "bars_daily/rv are the historical state inputs; funding is the old funding table.",
            "funding_multi, metrics and tardis_* are newer and are not used by regime_signs.py yet.",
            "A current coin with no bars/rv cannot be mapped to a historical state cell.",
        ],
    }
    OUT_COVERAGE.write_text(json.dumps(result, indent=1))
    print(f"wrote {OUT_COVERAGE.relative_to(ROOT)}")
    for table, row in stats.items():
        if "error" in row:
            print(f"{table:20s} ERROR {row['error']}")
        else:
            print(f"{table:20s} rows={row['rows']:>10,} symbols={row['symbols']:>3} "
                  f"{row['from']} -> {row['to']}")
    print("\ncurrent forecast universe:")
    for row in current:
        marks = row["counts"]
        print(f"  {row['coin']:5s} {row['verdict']:20s} "
              f"bars={marks.get('bars_daily')} rv={marks.get('rv')} "
              f"funding_multi={marks.get('funding_multi')}")
    return result


def _state_frame() -> pd.DataFrame:
    rs = _regime_module()
    df = rs.build(rs.load())
    df["date"] = pd.to_datetime(df["date"])
    df["state2"] = (np.where(df["ret60"] > 0, "up", "down") + "/"
                    + np.where(df["vol_pct"] > 0.5, "high", "low"))
    df["state"] = (df["state2"] + "/"
                   + np.where(df["fund_pct"] > 0.5, "high", "low"))
    cols = ["symbol", "date", "state", "state2", TARGET]
    return df[cols].dropna(subset=["state", TARGET]).sort_values("date").reset_index(drop=True)


def crps_ensemble(observation: float, sample: np.ndarray) -> float:
    """Empirical CRPS (lower is better), O(n log n)."""
    x = np.sort(np.asarray(sample, dtype=float))
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0 or not math.isfinite(observation):
        return float("nan")
    term1 = float(np.mean(np.abs(x - observation)))
    ranks = np.arange(1, n + 1, dtype=float)
    term2 = float(np.sum((2.0 * ranks - n - 1.0) * x) / (n * n))
    return term1 - term2


def _score(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    crps = np.array([r["crps"] for r in rows], dtype=float)
    brier = np.array([r["brier"] for r in rows], dtype=float)
    pit = np.array([r["pit"] for r in rows], dtype=float)
    ok = np.isfinite(crps) & np.isfinite(brier) & np.isfinite(pit)
    if not ok.any():
        return {"n": 0}
    pit_hist = np.histogram(pit[ok], bins=np.linspace(0, 1, 11))[0].tolist()
    return {
        "n": int(ok.sum()),
        "crps_mean": float(crps[ok].mean()),
        "brier_mean": float(brier[ok].mean()),
        "pit_mean": float(pit[ok].mean()),
        "pit_bins": pit_hist,
    }


def evaluate() -> dict:
    """Purged walk-forward: train on outcomes known before the test outcome opens."""
    data = _state_frame()
    dates = sorted(data.loc[data["date"] >= pd.Timestamp(TEST_START), "date"].unique())
    if not dates:
        raise SystemExit("no test dates; check the substrate")
    conditional: list[dict] = []
    conditional2d: list[dict] = []
    unconditional: list[dict] = []
    skipped_no_history = 0
    for date in dates:
        cutoff = pd.Timestamp(date) - pd.Timedelta(days=EMBARGO_DAYS)
        history = data[data["date"] <= cutoff]
        test = data[data["date"] == pd.Timestamp(date)]
        if len(history) < MIN_TRAIN or test.empty:
            skipped_no_history += 1
            continue
        global_sample = history[TARGET].to_numpy(dtype=float)
        by_state: dict[str, np.ndarray] = {
            state: group[TARGET].to_numpy(dtype=float)
            for state, group in history.groupby("state")
        }
        by_state2: dict[str, np.ndarray] = {
            state: group[TARGET].to_numpy(dtype=float)
            for state, group in history.groupby("state2")
        }
        for row in test.itertuples(index=False):
            actual = float(getattr(row, TARGET))
            state_sample = by_state.get(str(row.state), np.empty(0))
            if len(state_sample) >= MIN_TRAIN:
                sample = state_sample
                used_fallback = False
            else:
                sample = global_sample
                used_fallback = True
            sample2 = by_state2.get(str(row.state2), np.empty(0))
            if len(sample2) >= MIN_TRAIN:
                sample2_values = sample2
                used_fallback2 = False
            else:
                sample2_values = global_sample
                used_fallback2 = True
            for bucket, values, fallback in (
                (conditional, sample, used_fallback),
                (conditional2d, sample2_values, used_fallback2),
                (unconditional, global_sample, False),
            ):
                if len(values) < MIN_TRAIN:
                    continue
                p_up = float(np.mean(values > 0))
                bucket.append({
                    "date": str(pd.Timestamp(date).date()),
                    "symbol": str(row.symbol),
                    "state": str(row.state),
                    "actual": actual,
                    "crps": crps_ensemble(actual, values),
                    "brier": (p_up - (1.0 if actual > 0 else 0.0)) ** 2,
                    "pit": float(np.mean(values <= actual)),
                    "fallback": bool(fallback),
                })
    result = {
        "as_of": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "design": {
            "target": "20-day market-relative return (x20)",
            "test_start": TEST_START,
            "embargo_days": EMBARGO_DAYS,
            "min_train": MIN_TRAIN,
            "fallback": "unconditional when a state has fewer than min_train outcomes",
        },
        "rows": len(conditional),
        "conditional": _score(conditional),
        "conditional2d": _score(conditional2d),
        "unconditional": _score(unconditional),
        "fallback_rows": int(sum(1 for row in conditional if row["fallback"])),
        "fallback_rows_2d": int(sum(1 for row in conditional2d if row["fallback"])),
        "skipped_dates": skipped_no_history,
        "notes": [
            "Walk-forward, no random splits; training outcomes end at least 20 days before the test outcome opens.",
            "Conditional is the current 16-state empirical distribution; unconditional is the pooled baseline.",
            "CRPS and Brier are proper scores; lower is better. PIT should be roughly uniform for calibration.",
            "This evaluates the distribution, not the WATCH/context label gate.",
        ],
    }
    OUT_EVAL.write_text(json.dumps(result, indent=1))
    print(f"wrote {OUT_EVAL.relative_to(ROOT)}")
    print(f"test rows: {result['rows']:,} · fallback {result['fallback_rows']:,} "
          f"· skipped dates {result['skipped_dates']}")
    for key in ("conditional", "conditional2d", "unconditional"):
        s = result[key]
        print(f"{key:13s} n={s['n']:>7,} CRPS={s.get('crps_mean', float('nan')):.5f} "
              f"Brier={s.get('brier_mean', float('nan')):.5f} PIT={s.get('pit_mean', float('nan')):.3f}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", action="store_true", help="write the coverage audit")
    parser.add_argument("--eval", action="store_true", help="run the walk-forward evaluation")
    args = parser.parse_args()
    if not args.coverage and not args.eval:
        args.coverage = args.eval = True
    if args.coverage:
        coverage()
    if args.eval:
        evaluate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
