"""Phase 1c: factor model. PCA loadings on design returns, factor books evaluated on 2023.

    python research/factor_model.py
Design 2020-2022, validation 2023. The holdout (2025-07..2026-03) is not read here.
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "factor_model.json"
DESIGN = ("2020-01-01", "2022-12-31")
VALID = ("2023-01-01", "2023-12-31")
FEE = 5e-4
N_PCS = 3


def returns() -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("SELECT symbol, date, close FROM bars_daily ORDER BY date").df()
    con.close()
    df["date"] = pd.to_datetime(df["date"])
    px = df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    px = px.replace([np.inf, -np.inf], np.nan)
    px = px.where(px > 0)
    return np.log(px).diff()


def pcs(ret: pd.DataFrame, fit_end: str) -> tuple[np.ndarray, list[str], pd.DataFrame]:
    d = ret.loc[:fit_end].dropna(axis=1, thresh=int(0.8 * len(ret.loc[:fit_end])))
    d = d.dropna()
    z = (d - d.mean()) / d.std(ddof=1)
    u, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    load = pd.DataFrame(vt[:N_PCS].T, index=d.columns, columns=[f"pc{i+1}" for i in range(N_PCS)])
    return load.to_numpy(), list(d.columns), load


def book_returns(ret: pd.DataFrame, load: np.ndarray, cols: list[str], start: str, end: str) -> dict:
    """Fixed design loadings -> long the top quintile, short the bottom, equal weight, no rebalancing.

    Raw returns are used; the loadings come from the design window only, so nothing in the book
    knows a future price.
    """
    sub = ret.loc[start:end].reindex(columns=cols)
    out = {}
    for k in range(N_PCS):
        w = pd.Series(load[:, k], index=cols).astype(float)
        w = w - w.mean()
        thr = w.abs().quantile(0.8)
        pos = w.where(w.abs() >= thr, 0.0)
        pos = pos / max(pos.abs().sum(), 1e-9)
        daily = (sub.fillna(0.0) * pos).sum(axis=1)
        ann = float(daily.mean() * 365)
        t = float(daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily)))) if daily.std(ddof=1) > 0 else float("nan")
        out[f"pc{k+1}"] = {"ann_pct": 100 * ann, "t": t, "days": int(len(daily)),
                           "sharpe": float(daily.mean() / daily.std(ddof=1) * np.sqrt(365)) if daily.std(ddof=1) > 0 else None,
                           "avg_abs_weight": float(pos.abs().sum())}
    return out


def main() -> int:
    ret = returns()
    load, cols, load_df = pcs(ret, DESIGN[1])
    load_df.to_csv(ROOT / "research" / "factor_loadings.csv")
    d = ret.loc[DESIGN[0]:DESIGN[1]]
    d = d.dropna(axis=1, thresh=int(0.8 * len(d))).dropna()
    z = ((d - d.mean()) / d.std(ddof=1)).to_numpy()
    sv = np.linalg.svd(z, compute_uv=False) ** 2
    var_explained = (sv[:3] / sv.sum()).tolist()
    design = book_returns(ret, load, cols, DESIGN[0], DESIGN[1])
    valid = book_returns(ret, load, cols, VALID[0], VALID[1])
    out = {"design": DESIGN, "validation": VALID, "n_names": len(cols),
           "variance_explained_pc": [float(x) for x in var_explained],
           "design": design, "validation": valid}
    OUT.write_text(json.dumps(out, indent=1))
    for label, res in (("design", design), ("validation", valid)):
        for k, v in res.items():
            print(f"{label:10s} {k}: {v['ann_pct']:+.1f}%/yr  t {v['t']:+.2f}  Sharpe {v['sharpe']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
