"""Fetch the raw carry inputs from data.binance.vision. Monthly files only; no prepared panels.

    python research/carry_fetch.py design     # 2024 funding + perp/spot 1d klines for candidates
    python research/carry_fetch.py holdout    # 2025-01..2025-06, only after the seal commit
    python research/carry_fetch.py depth      # bookDepth samples for capacity

Every file is written to data_carry/<kind>/<symbol>/<file> and hashed into data_carry/manifest.sha256.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data_carry"
BASE = "https://data.binance.vision/data"
UA = {"User-Agent": "espero2-carry/1.0"}

# pairs of (perp symbol, spot symbol); the same ticker on both venues, USD-S-M and spot
CANDIDATES = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
              "AVAXUSDT", "LINKUSDT", "DOTUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT",
              "ETCUSDT", "XLMUSDT", "NEARUSDT", "OPUSDT", "FILUSDT", "RUNEUSDT", "AAVEUSDT",
              "EOSUSDT", "THETAUSDT", "XTZUSDT", "ALGOUSDT", "WLDUSDT", "SUIUSDT", "APTUSDT",
              "ARBUSDT", "TIAUSDT", "INJUSDT", "SEIUSDT", "PEPEUSDT", "FTMUSDT", "SANDUSDT",
              "MANAUSDT", "GALAUSDT", "APEUSDT", "CRVUSDT", "LDOUSDT"]


def months(year: int, end_month: int) -> list[str]:
    return [f"{year}-{m:02d}" for m in range(1, end_month + 1)]


def url_for(kind: str, sym: str, month: str) -> str:
    if kind == "funding":
        return f"{BASE}/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{month}.zip"
    if kind == "perp":
        return f"{BASE}/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{month}.zip"
    if kind == "spot":
        return f"{BASE}/spot/monthly/klines/{sym}/1d/{sym}-1d-{month}.zip"
    if kind == "premium":
        return f"{BASE}/futures/um/monthly/premiumIndexKlines/{sym}/1d/{sym}-1d-{month}.zip"
    if kind == "premium1h":
        return f"{BASE}/futures/um/monthly/premiumIndexKlines/{sym}/1h/{sym}-1h-{month}.zip"
    if kind == "depth":
        return f"{BASE}/futures/um/daily/bookDepth/{sym}/{sym}-bookDepth-{month}.zip"
    raise ValueError(kind)


def fetch(job: tuple[str, str, str]) -> tuple[str, str, str, int]:
    kind, sym, month = job
    url = url_for(kind, sym, month)
    dest = OUT / kind / sym / f"{month}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        return kind, sym, month, dest.stat().st_size
    req = Request(url, headers=UA)
    try:
        with urlopen(req, timeout=60) as r:      # noqa: S310 - fixed https host
            data = r.read()
    except Exception as exc:                      # noqa: BLE001 - a missing file is data, not a crash
        dest.parent.mkdir(parents=True, exist_ok=True)
        (OUT / kind / sym / f"{month}.missing").write_text(type(exc).__name__)
        return kind, sym, month, 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return kind, sym, month, len(data)


def run(jobs: list[tuple[str, str, str]], workers: int = 16) -> None:
    total = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for kind, sym, month, size in pool.map(fetch, jobs):
            total += size
    print(f"{len(jobs)} files, {total/1e6:.1f} MB")


def manifest() -> None:
    lines = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.suffix in (".zip",):
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}")
    (OUT / "manifest.sha256").write_text("\n".join(lines) + "\n")
    print(f"manifest: {len(lines)} files")


def universe() -> list[str]:
    path = ROOT / "research" / "carry_universe.csv"
    if not path.exists():
        return CANDIDATES
    return [line.split(",")[0] for line in path.read_text().splitlines()[1:] if line.strip()]


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "design"
    if what == "design":
        jobs = [(k, s, m) for s in CANDIDATES for m in months(2024, 12) for k in ("funding", "perp", "spot")]
        run(jobs)
    elif what == "holdout":
        jobs = [(k, s, f"2025-{m:02d}") for s in universe() for m in range(1, 7) for k in ("funding", "perp", "spot")]
        run(jobs)
    elif what == "depth":
        jobs = []
        for day in ("2024-03-15", "2024-06-15", "2024-09-15", "2024-12-15"):
            for sym in universe()[:15]:
                jobs.append(("depth", sym, day))
        run([j for j in jobs], workers=8)
    else:
        print("usage: design|holdout|depth", file=sys.stderr)
        return 2
    manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
