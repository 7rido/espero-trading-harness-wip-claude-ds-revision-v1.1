"""Data inventory straight from the substrate: every table, rows, span, key columns.

    python research/inventory.py            # markdown to stdout
    python research/inventory.py --write    # also research/DATA_INVENTORY.md
"""
from __future__ import annotations

import argparse
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data_substrate" / "substrate.duckdb"
OUT = ROOT / "research" / "DATA_INVENTORY.md"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    con = duckdb.connect(str(DB), read_only=True)
    tables = [r[0] for r in con.execute("SELECT table_name FROM information_schema.tables "
                                        "WHERE table_schema='main' ORDER BY 1").fetchall()]
    lines = ["# Data inventory", "", f"Database: `{DB.name}` · tables: {len(tables)}", "",
             "| table | rows | span | key columns |", "|---|---|---|---|"]
    for t in tables:
        info = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name=? "
            "ORDER BY ordinal_position", [t]).fetchall()
        cols = [c for c, _ in info]
        types = dict(info)
        n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        time_col = next((c for c in ("ts", "date", "minute", "hour", "day")
                         if c in cols and types[c] in ("DATE", "TIMESTAMP", "TIMESTAMP WITH TIME ZONE")), None)
        span = ""
        if time_col and n:
            lo, hi = con.execute(f'SELECT MIN("{time_col}"), MAX("{time_col}") FROM "{t}"').fetchone()
            span = f"{str(lo)[:10]} → {str(hi)[:10]}"
        lines.append(f"| `{t}` | {n:,} | {span} | {', '.join(cols[:6])} |")
    con.close()
    text = "\n".join(lines) + "\n"
    print(text)
    if args.write:
        OUT.write_text(text)
        print(f"[written {OUT.relative_to(ROOT)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
