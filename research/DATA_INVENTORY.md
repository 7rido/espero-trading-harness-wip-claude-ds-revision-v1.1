# Data inventory

Database: `substrate.duckdb` · tables: 16

| table | rows | span | key columns |
|---|---|---|---|
| `bars` | 128,959 | 2021-01-01 → 2025-06-30 | symbol, date, close, qvol, venue, known_time |
| `bars_daily` | 82,774 | 2020-01-01 → 2026-03-31 | symbol, date, open, high, low, close |
| `book_ticker` | 45,547,988 | 2023-07-10 → 2023-07-10 | symbol, ts, bid, ask, day |
| `depth` | 1,728,000 | 0001-03-15 → 0001-12-15 | symbol, day, pct, notional, known_time |
| `funding` | 108,374 | 2023-01-01 → 2025-06-30 | symbol, ts, rate, known_time |
| `funding_multi` | 3,818 | 2025-07-01 → 2026-10-31 | venue, symbol, ts, rate, interval_hours, known_time |
| `liquidation_multi` | 100 | 2026-10-30 → 2026-10-31 | venue, symbol, ts, price, qty, usd |
| `metrics` | 105,120 | 2025-10-31 → 2026-10-30 | symbol, ts, oi, oi_value, top_ls, global_ls |
| `obi` | 4,320 | 2024-01-02 → 2024-01-02 | symbol, minute, bid, ask, bid_qty, ask_qty |
| `premium` | 13,675 | 2024-01-01 → 2025-06-30 | symbol, date, premium, known_time |
| `prints` | 0 |  | symbol, day, last_price, known_time |
| `rv` | 82,774 | 2020-01-01 → 2026-03-31 | symbol, date, rv, rv_w, rv_m, parkinson |
| `tardis_book` | 1,440 | 2026-10-01 → 2026-10-01 | symbol, minute, bid, ask, bid_amt, ask_amt |
| `tardis_derivative` | 4,415,916 | 2025-01-01 → 2026-10-01 | symbol, ts, funding, predicted, oi, mark |
| `tardis_liquidations` | 44,353 | 2025-01-01 → 2026-10-01 | symbol, ts, side, price, amount, usd |
| `trades` | 3,296,200 | 2023-07-10 → 2023-07-10 | symbol, ts, price, qty, buyer_is_maker, day |
