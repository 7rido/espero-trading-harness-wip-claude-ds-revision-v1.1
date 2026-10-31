"""Post-hoc information only: the intercept of net carry on the funding it collected.

NOT part of the sealed test. The registered P2 ("net/funding < 1") was mis-specified; this computes
what the right question would have been: is there return left after the funding is accounted for?
"""
from __future__ import annotations
import importlib.util, json, pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cd", ROOT / "research" / "carry_deep.py")
cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)


def track(df: pd.DataFrame, entry: float, exit_: float):
    df = cd.signal_table(df).dropna(subset=["f3", "basis", "spot_ret"]).reset_index(drop=True)
    rows, in_pos, held = [], False, 0
    for i in range(len(df)):
        day = df.at[i, "date"]
        if in_pos:
            rows.append({"date": day, "ret": float(df.at[i, "fund_sum"] + df.at[i, "basis_pnl"]),
                         "fund": float(df.at[i, "fund_sum"])})
            held += 1
            if df.at[i, "f3"] < exit_ or held >= cd.MAX_HOLD:
                rows[-1]["ret"] -= cd.COST / 2
                in_pos, held = False, 0
        if not in_pos and df.at[i, "f3"] > entry and df.at[i, "basis"] > 0:
            in_pos, held = True, 0
            rows.append({"date": day, "ret": -cd.COST / 2, "fund": 0.0})
    out = pd.DataFrame(rows)
    return out.groupby("date", as_index=False).agg({"ret": "sum", "fund": "sum"})


def main() -> int:
    dfs = {s: cd.daily(s, 2024, 12) for s in cd.UNIVERSE}
    dfs = {s: d for s, d in dfs.items() if len(d) > 40}
    tracks = {s: track(d, cd.ENTRY, cd.EXIT).set_index("date") for s, d in dfs.items()}
    rets = pd.concat({s: t["ret"] for s, t in tracks.items()}, axis=1).mean(axis=1)
    funds = pd.concat({s: t["fund"] for s, t in tracks.items()}, axis=1).mean(axis=1)
    port = pd.DataFrame({"ret": rets, "fund": funds}).dropna()
    x, y = port["fund"].to_numpy(), port["ret"].to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    lags = 10
    S = (resid[:, None] * X).T @ (resid[:, None] * X) / n
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        G = (resid[lag:, None] * X[lag:]).T @ (resid[:-lag, None] * X[:-lag]) / n
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv / n
    alpha, beta_hat = beta
    t_alpha = alpha / np.sqrt(cov[0, 0])
    out = {"days": int(n), "alpha_annual_pct": 100 * alpha * 365,
           "alpha_t": float(t_alpha), "beta_on_funding": float(beta_hat),
           "funding_annual_pct": 100 * x.mean() * 365, "return_annual_pct": 100 * y.mean() * 365}
    (ROOT / "research" / "carry_p2_alpha.json").write_text(json.dumps(out, indent=1))
    print(f"{out['days']} days: alpha {out['alpha_annual_pct']:+.1f}%/yr (t {out['alpha_t']:.2f}), "
          f"beta on funding {beta_hat:.2f}, funding {out['funding_annual_pct']:+.1f}%/yr, "
          f"total {out['return_annual_pct']:+.1f}%/yr")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
