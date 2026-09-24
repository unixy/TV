"""Pull real 5-minute OHLCV history for a crypto pair via ccxt and save it
in the CSV format run_backtest.py expects (timestamp,open,high,low,close,
volume, UTC).

Defaults to Coinbase, which pages properly through deep history via ccxt's
`since` parameter. Two exchange-specific gotchas worth knowing before you
pick one:
  - Binance's main api.binance.com endpoint geo-blocks many cloud/US-hosted
    IPs (HTTP 451) - try --exchange binance if you're running this
    somewhere Binance isn't blocked.
  - Kraken's public OHLC REST endpoint only ever returns its most recent
    ~720 candles, regardless of `since` - it does not page through deep
    history, so it's a poor fit for pulling 6-12 months of 5m data even
    though ccxt will run without erroring.

Usage:
    python fetch_data.py --exchange coinbase --symbol BTC/USD --days 180 --out btc_5m.csv
"""
from __future__ import annotations

import argparse
import time

import ccxt
import pandas as pd


def fetch(exchange_id: str, symbol: str, timeframe: str, days: int, out_path: str) -> None:
    exchange_cls = getattr(ccxt, exchange_id)
    ex = exchange_cls({"enableRateLimit": True})
    ms_per_bar = ex.parse_timeframe(timeframe) * 1000
    since = ex.milliseconds() - days * 24 * 60 * 60 * 1000
    end = ex.milliseconds()

    all_rows: list[list] = []
    cursor = since
    while cursor < end:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=1000)
        if not batch:
            break
        all_rows.extend(batch)
        last_ts = batch[-1][0]
        if last_ts <= cursor:
            break
        cursor = last_ts + ms_per_bar
        print(f"  fetched {len(all_rows)} bars so far, up to {pd.to_datetime(last_ts, unit='ms', utc=True)}", end="\r")
        time.sleep(ex.rateLimit / 1000.0)

    print()
    if not all_rows:
        raise SystemExit(f"No data returned for {symbol} on {exchange_id}. Check the symbol format for this exchange.")

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} bars ({df['timestamp'].min()} to {df['timestamp'].max()}, UTC) to {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="coinbase", help="ccxt exchange id, e.g. coinbase, binance, kraken (kraken caps at ~720 recent bars, see module docstring)")
    ap.add_argument("--symbol", default="BTC/USD", help="e.g. BTC/USD, BTC/USDT, ETH/USD - check the exchange's listed symbols if unsure")
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--days", type=int, default=180, help="How many days of history to pull, working backward from now")
    ap.add_argument("--out", default="real_5m.csv")
    args = ap.parse_args()
    fetch(args.exchange, args.symbol, args.timeframe, args.days, args.out)
