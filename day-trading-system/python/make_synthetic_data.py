"""Generate a synthetic 5-minute OHLCV CSV for smoke-testing the backtester.

This is NOT real market data and should never be used to judge whether the
system has an edge - it exists only so `run_backtest.py` has something to
run against without requiring an external data source. Swap in real
5-minute bars (e.g. exported from your broker/data vendor, or pulled with
yfinance/ccxt) before drawing any conclusions.
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd


def generate(n_days: int, seed: int, start: str, out_path: str) -> None:
    rng = np.random.default_rng(seed)
    bars_per_day = 78  # 6.5h RTH session, 5m bars
    all_rows = []
    price = 100.0
    day0 = pd.Timestamp(start)
    day = day0
    days_emitted = 0
    while days_emitted < n_days:
        if day.weekday() < 5:  # weekdays only
            # a slow regime-switching drift so 4H trend bias actually engages sometimes
            regime = rng.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
            drift = regime * rng.uniform(0.00002, 0.00008)
            session_start = day + pd.Timedelta(hours=9, minutes=30)
            times = pd.date_range(session_start, periods=bars_per_day, freq="5min")
            vol_base = rng.uniform(0.0006, 0.0016)
            for t in times:
                ret = rng.normal(drift, vol_base)
                o = price
                path = np.cumsum(rng.normal(0, vol_base / 2, 4))
                closes_intrabar = o * (1 + path)
                c = o * (1 + ret)
                h = max(o, c, *closes_intrabar) * (1 + abs(rng.normal(0, vol_base / 3)))
                l = min(o, c, *closes_intrabar) * (1 - abs(rng.normal(0, vol_base / 3)))
                vol = max(1000, rng.normal(50_000, 15_000))
                all_rows.append((t, round(o, 4), round(h, 4), round(l, 4), round(c, 4), int(vol)))
                price = c
            days_emitted += 1
        day += pd.Timedelta(days=1)

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} bars ({n_days} sessions) to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=str, default="2025-01-06")
    ap.add_argument("--out", type=str, default="synthetic_5m.csv")
    args = ap.parse_args()
    generate(args.days, args.seed, args.start, args.out)
