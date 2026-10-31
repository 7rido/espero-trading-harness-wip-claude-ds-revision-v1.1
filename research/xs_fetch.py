"""Fetch the raw cross-sectional inputs: every USD-M symbol the archive ever had, then the design
(2021-2022) klines for those with enough history, then the frozen universe's 2023 files.

    python research/xs_fetch.py scan      # symbol list + month coverage (metadata only)
    python research/xs_fetch.py design    # 2021-2022 monthly klines for candidates
    python research/xs_fetch.py holdout   # 2023 klines + funding for the frozen universe
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data_xs"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
UA = {"User-Agent": "espero2-xs/1.0"}


def listing(prefix: str, marker: str | None = None) -> tuple[list[str], str | None]:
    url = f"{S3}?delimiter=/&prefix={prefix}" + (f"&marker={marker}" if marker else "")
    xml = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    root = ET.fromstring(xml)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = [e.text for e in root.findall(".//s3:Key", ns) if e.text]
    prefixes = [e.text for e in root.findall(".//s3:CommonPrefixes/s3:Prefix", ns) if e.text]
    truncated = (root.findtext(".//s3:IsTruncated", namespaces=ns) or "false") == "true"
    nxt = root.findtext(".//s3:NextMarker", namespaces=ns)
    return (keys + prefixes), (nxt if truncated else None)


def all_symbols() -> list[str]:
    """Every symbol prefix, paginated by first character so no 1000-key page truncates it."""
    found = set()
    for ch in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        prefix = f"data/futures/um/monthly/klines/{ch}"
        marker = None
        while True:
            url = f"{S3}?delimiter=/&prefix={prefix}" + (f"&marker={marker}" if marker else "")
            xml = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            root = ET.fromstring(xml)
            ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            for e in root.findall(".//s3:CommonPrefixes/s3:Prefix", ns):
                m = re.findall(r"klines/([^/]+)/$", e.text or "")
                if m:
                    found.add(m[0])
            marker = root.findtext(".//s3:NextMarker", namespaces=ns)
            if (root.findtext(".//s3:IsTruncated", namespaces=ns) or "false") != "true" or not marker:
                break
    return sorted(found)


def months(sym: str) -> list[str]:
    items, marker = listing(f"data/futures/um/monthly/klines/{sym}/1d/")
    out = [re.findall(r"(\d{4}-\d{2})\.zip$", p)[0] for p in items if p.endswith(".zip")]
    return sorted(out)


def fetch(job: tuple[str, str, str]) -> int:
    kind, sym, month = job
    if kind == "perp":
        url = f"{S3}/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{month}.zip"
    elif kind == "funding":
        url = f"{S3}/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{month}.zip"
    else:
        raise ValueError(kind)
    dest = OUT / kind / sym / f"{month}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        return dest.stat().st_size
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    except Exception:
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def run(jobs: list[tuple[str, str, str]], workers: int = 16) -> None:
    total = 0
    with ThreadPoolExecutor(workers) as pool:
        for size in pool.map(fetch, jobs):
            total += size
    print(f"{len(jobs)} files, {total/1e6:.1f} MB")


def manifest() -> None:
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}"
             for p in sorted(OUT.rglob("*.zip"))]
    (OUT / "manifest.sha256").write_text("\n".join(lines) + "\n")
    print(f"manifest: {len(lines)} files")


def main(argv: list[str]) -> int:
    what = argv[0] if argv else "scan"
    if what == "scan":
        syms = all_symbols()
        (ROOT / "research" / "um_symbols_all.txt").write_text("\n".join(syms) + "\n")
        print(f"{len(syms)} symbols ever listed")
        with ThreadPoolExecutor(16) as pool:
            cov = dict(zip(syms, pool.map(months, syms)))
        want = [s for s, ms in cov.items() if sum("2021-01" <= m <= "2022-12" for m in ms) >= 12]
        (ROOT / "research" / "xs_candidates.txt").write_text("\n".join(sorted(want)) + "\n")
        print(f"{len(want)} have 12+ months in 2021-2022")
    elif what == "design":
        cands = (ROOT / "research" / "xs_candidates.txt").read_text().split()
        months_ = [f"{y}-{m:02d}" for y in (2021, 2022) for m in range(1, 13)]
        jobs = [("perp", s, m) for s in cands for m in months_]
        print(f"{len(cands)} candidates x {len(months_)} months")
        run(jobs)
        manifest()
    elif what == "holdout":
        uni = [l.split(",")[0] for l in (ROOT / "research" / "xs_universe.csv").read_text().splitlines()[1:] if l]
        months_ = [f"2023-{m:02d}" for m in range(1, 13)]
        run([("perp", s, m) for s in uni for m in months_])
        run([("funding", s, m) for s in uni for m in months_])
        manifest()
    else:
        print("usage: scan|design|holdout", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
