"""Generate a synthetic 5-minute OHLCV CSV for smoke-testing the backtester.

This is NOT real market data and should never be used to judge whether the
system has an edge - it exists only so `run_backtest.py` has something to
run against without requiring an external data source. Swap in real
5-minute bars for a top-10-by-market-cap coin (e.g. pulled with ccxt from a
major exchange) before drawing any conclusions.

Generates continuous 24/7 bars (crypto never closes) starting at a
BTC-like price level, in UTC.
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd


def generate(n_days: int, seed: int, start: str, start_price: float, out_path: str) -> None:
    rng = np.random.default_rng(seed)
    bars_per_day = 288  # 24h / 5m, crypto trades every day, all day
    start_ts = pd.Timestamp(start, tz=None)
    times = pd.date_range(start_ts, periods=n_days * bars_per_day, freq="5min")

    price = start_price
    rows = []
    regime = 0
    regime_bars_left = 0
    for t in times:
        if regime_bars_left <= 0:
            regime = rng.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
            regime_bars_left = rng.integers(bars_per_day // 2, bars_per_day * 3)
        regime_bars_left -= 1

        drift = regime * rng.uniform(0.00002, 0.00006)
        vol_base = rng.uniform(0.0008, 0.0020)  # crypto is noisier than the earlier equity model
        ret = rng.normal(drift, vol_base)
        o = price
        path = np.cumsum(rng.normal(0, vol_base / 2, 4))
        closes_intrabar = o * (1 + path)
        c = o * (1 + ret)
        h = max(o, c, *closes_intrabar) * (1 + abs(rng.normal(0, vol_base / 3)))
        l = min(o, c, *closes_intrabar) * (1 - abs(rng.normal(0, vol_base / 3)))
        vol = max(1.0, rng.normal(120, 40))  # coins traded, not $ volume
        rows.append((t, round(o, 2), round(h, 2), round(l, 2), round(c, 2), round(vol, 4)))
        price = c

    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} bars ({n_days} days, 24/7) to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--start", type=str, default="2025-01-01T00:00:00")
    ap.add_argument("--start-price", type=float, default=60_000.0, help="e.g. ~60000 for a BTC-like series")
    ap.add_argument("--out", type=str, default="synthetic_5m.csv")
    args = ap.parse_args()
    generate(args.days, args.seed, args.start, args.start_price, args.out)
