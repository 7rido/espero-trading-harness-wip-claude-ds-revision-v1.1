"""SQLite journal: bars, signals, orders, equity and per-coin paper state.

Each coin is its own paper book (`{coin}:cash`, `{coin}:qty`, ...): a BTC position must not
appear in ETH's account. Global facts (heartbeat, cadence) live under plain keys.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars(coin TEXT, ts INTEGER, open REAL, high REAL, low REAL,
                                close REAL, volume REAL, PRIMARY KEY(coin, ts));
CREATE TABLE IF NOT EXISTS signals(ts INTEGER, coin TEXT, side TEXT, price REAL, reason TEXT,
                                   prereg_id TEXT DEFAULT '', model_version TEXT DEFAULT '',
                                   inputs_hash TEXT DEFAULT '', gate_state TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS orders(oid INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, coin TEXT,
                                  side TEXT, qty REAL, px REAL, fee REAL, kind TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS equity(coin TEXT, ts INTEGER, cash REAL, qty REAL, entry_px REAL,
                                  mark REAL, equity REAL, PRIMARY KEY(coin, ts));
CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
"""

MIGRATE_EQUITY = """
ALTER TABLE equity RENAME TO equity_old;
CREATE TABLE equity(coin TEXT, ts INTEGER, cash REAL, qty REAL, entry_px REAL,
                    mark REAL, equity REAL, PRIMARY KEY(coin, ts));
INSERT INTO equity(coin, ts, cash, qty, entry_px, mark, equity)
    SELECT 'BTC', ts, cash, qty, entry_px, mark, equity FROM equity_old;
DROP TABLE equity_old;
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self._migrate()
        self.db.commit()

    def _migrate(self) -> None:
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(signals)").fetchall()}
        for name in ("prereg_id", "model_version", "inputs_hash", "gate_state"):
            if name not in cols:
                self.db.execute(f"ALTER TABLE signals ADD COLUMN {name} TEXT DEFAULT ''")
        self.db.commit()
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(equity)")]
        if cols and "coin" not in cols:            # v1 journal: one unnamed book
            self.db.executescript(MIGRATE_EQUITY)
            for k in ("cash", "qty", "entry_px", "entry_ts"):
                row = self.db.execute("SELECT value FROM state WHERE key=?", (k,)).fetchone()
                if row:
                    self.db.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (f"BTC:{k}", row[0]))
                    self.db.execute("DELETE FROM state WHERE key=?", (k,))

    def close(self) -> None:
        self.db.close()

    # ---------------------------------------------------------------- bars
    def add_bars(self, coin: str, rows: Iterable[dict]) -> int:
        cur = self.db.executemany(
            "INSERT OR IGNORE INTO bars(coin, ts, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            [(coin, r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in rows],
        )
        self.db.commit()
        return cur.rowcount

    def bars(self, coin: str, limit: int = 500) -> list[dict]:
        q = self.db.execute(
            "SELECT ts, open, high, low, close, volume FROM bars WHERE coin=? ORDER BY ts DESC LIMIT ?",
            (coin, limit)).fetchall()
        return [{"ts": t, "open": o, "high": h, "low": lo, "close": c, "volume": v}
                for t, o, h, lo, c, v in reversed(q)]

    # ------------------------------------------------------------- records
    def signal(self, ts: int, coin: str, side: str, price: float, reason: str, *,
               prereg_id: str = "", model_version: str = "", inputs_hash: str = "",
               gate_state: str = "") -> None:
        self.db.execute("INSERT INTO signals(ts, coin, side, price, reason, prereg_id, model_version,"
                        " inputs_hash, gate_state) VALUES (?,?,?,?,?,?,?,?,?)",
                        (ts, coin, side, price, reason, prereg_id, model_version, inputs_hash, gate_state))
        self.db.commit()

    def order(self, ts: int, coin: str, side: str, qty: float, px: float, fee: float,
              kind: str, note: str = "") -> None:
        self.db.execute("INSERT INTO orders(ts, coin, side, qty, px, fee, kind, note) VALUES (?,?,?,?,?,?,?,?)",
                        (ts, coin, side, qty, px, fee, kind, note))
        self.db.commit()

    def mark(self, coin: str, ts: int, cash: float, qty: float, entry_px: float, mark: float) -> None:
        eq = cash + qty * mark
        self.db.execute("INSERT OR REPLACE INTO equity VALUES (?,?,?,?,?,?,?)",
                        (coin, ts, cash, qty, entry_px, mark, eq))
        self.db.commit()

    def last_mark_ts(self, coin: str) -> int:
        row = self.db.execute("SELECT COALESCE(MAX(ts),0) FROM equity WHERE coin=?", (coin,)).fetchone()
        return int(row[0])

    def has_marks(self, coin: str) -> bool:
        return self.db.execute("SELECT COUNT(*) FROM equity WHERE coin=?", (coin,)).fetchone()[0] > 0

    # --------------------------------------------------------------- state
    def get_state(self, coin: str = "BTC") -> dict:
        rows = dict(self.db.execute("SELECT key, value FROM state").fetchall())
        return {"cash": float(rows.get(f"{coin}:cash", 1000.0)),
                "qty": float(rows.get(f"{coin}:qty", 0.0)),
                "entry_px": float(rows.get(f"{coin}:entry_px", 0.0)),
                "entry_ts": int(float(rows.get(f"{coin}:entry_ts", 0))),
                "last_funding": int(float(rows.get(f"{coin}:last_funding", 0))),
                "blocked": rows.get(f"{coin}:blocked", "")}

    def set_state(self, coin: str = "BTC", **kw) -> None:
        self.db.executemany("INSERT OR REPLACE INTO state VALUES (?,?)",
                            [(f"{coin}:{k}", str(v)) for k, v in kw.items()])
        self.db.commit()

    def set_meta(self, **kw) -> None:
        self.db.executemany("INSERT OR REPLACE INTO state VALUES (?,?)",
                            [(k, str(v)) for k, v in kw.items()])
        self.db.commit()

    def meta(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def beat(self, ts: int | None = None) -> None:
        self.set_meta(heartbeat=int(ts if ts is not None else time.time()))

    def health(self) -> dict:
        beat = int(float(self.meta("heartbeat", 0) or 0))
        every = int(float(self.meta("every", 60) or 60))
        age = int(time.time()) - beat if beat else None
        return {"heartbeat": beat or None, "every": every, "age": age,
                "stale": age is None or age > 3 * every}

    # -------------------------------------------------------------- report
    def coins(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT DISTINCT coin FROM equity ORDER BY coin")]

    def summary(self, coin: str | None = None) -> dict:
        where, args = ("WHERE coin=?", (coin,)) if coin else ("", ())
        n = self.db.execute(f"SELECT COUNT(*) FROM orders {where}", args).fetchone()[0]
        fees = self.db.execute(f"SELECT COALESCE(SUM(fee),0) FROM orders {where}", args).fetchone()[0]
        last = self.db.execute(f"SELECT ts, equity FROM equity {where} ORDER BY ts DESC LIMIT 1", args).fetchone()
        first = self.db.execute(f"SELECT ts, equity FROM equity {where} ORDER BY ts ASC LIMIT 1", args).fetchone()
        return {"coin": coin, "orders": n, "fees": fees, "first": first, "last": last}
