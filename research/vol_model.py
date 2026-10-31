"""Phase 1a: volatility model. HAR-RV against EWMA and a trailing mean, scored by QLIKE.

    python research/vol_model.py
Design 2020-2022, validation 2023. A risk instrument: it sizes and limits positions, it is not a signal.
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "vol_model.json"
DESIGN = ("2020-01-01", "2022-12-31")
VALID = ("2023-01-01", "2023-12-31")


def qlike(actual: np.ndarray, forecast: np.ndarray) -> float:
    ok = np.isfinite(actual) & np.isfinite(forecast) & (actual > 0) & (forecast > 0)
    if ok.sum() < 10:
        return float("nan")
    x = actual[ok] / forecast[ok]
    return float(np.mean(x - np.log(x) - 1))


def har_fit(df: pd.DataFrame) -> dict:
    """OLS on logs: log rv_{t+1} ~ log rv_t + log rv_w + log rv_m."""
    m = df.copy()
    for c in ("rv", "rv_w", "rv_m"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m = m[(m["rv"] > 0) & (m["rv_w"] > 0) & (m["rv_m"] > 0)].dropna(subset=["rv", "rv_w", "rv_m"])
    y = np.log(m["rv"].shift(-1)).to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(m)), np.log(m["rv"].to_numpy(dtype=float)),
                         np.log(m["rv_w"].to_numpy(dtype=float)),
                         np.log(m["rv_m"].to_numpy(dtype=float))])
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    if ok.sum() < 60:
        return None
    beta, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
    resid = y[ok] - X[ok] @ beta
    sigma2 = float(resid @ resid / max(1, len(resid) - X.shape[1]))
    return {"beta": beta.tolist(), "sigma2": sigma2}


def har_forecast(beta: list[float], row: pd.Series) -> float:
    x = np.array([1.0, np.log(row["rv"]), np.log(row["rv_w"]), np.log(row["rv_m"])])
    return float(np.exp(x @ np.array(beta) + 0.5 * 0))       # median forecast of log-normal


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""SELECT symbol, date, rv, rv_w, rv_m FROM rv ORDER BY symbol, date""").df()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    d = df[(df["date"] >= DESIGN[0]) & (df["date"] <= DESIGN[1])]
    v = df[(df["date"] >= VALID[0]) & (df["date"] <= VALID[1])]
    rows = []
    for sym, g in d.groupby("symbol"):
        model = har_fit(g)
        if model is None:
            continue
        vg = v[v["symbol"] == sym].copy()
        if len(vg) < 60:
            continue
        vg = vg[(vg["rv"] > 0) & (vg["rv_w"] > 0) & (vg["rv_m"] > 0)].copy()
        if vg.empty:
            continue
        vg["har"] = vg.apply(lambda r: har_forecast(model["beta"], r), axis=1)
        lam = 0.94
        ew = []
        prev = float(g["rv"].iloc[-22:].mean())
        for rv in vg["rv"].to_numpy():
            prev = lam * prev + (1 - lam) * (rv if np.isfinite(rv) else prev)
            ew.append(prev)
        vg["ewma"] = ew
        vg["mean22"] = vg["rv"].rolling(22).mean()
        actual = vg["rv"].shift(-1).to_numpy()
        rows.append({"symbol": sym,
                     "har": qlike(actual, vg["har"].to_numpy()),
                     "ewma": qlike(actual, vg["ewma"].to_numpy()),
                     "mean22": qlike(actual, vg["mean22"].to_numpy())})
    res = pd.DataFrame(rows)
    summary = {k: {"mean_qlike": float(res[k].mean()), "median_qlike": float(res[k].median()),
                   "wins": int((res[k] < res["ewma"]).sum()), "n": int(len(res))}
               for k in ("har", "ewma", "mean22")}
    out = {"design": DESIGN, "validation": VALID, "symbols": len(res), "summary": summary,
           "per_symbol": res.to_dict("records")}
    OUT.write_text(json.dumps(out, indent=1))
    for k, v in summary.items():
        print(f"{k:7s} QLIKE mean {v['mean_qlike']:.4f} median {v['median_qlike']:.4f} "
              f"(beats EWMA on {v['wins']}/{v['n']} symbols)" if k != "ewma" else
              f"{k:7s} QLIKE mean {v['mean_qlike']:.4f} median {v['median_qlike']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
