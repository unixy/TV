"""CLI entry point: backtest the Session Pullback System over a 5-minute
OHLCV CSV.

Usage:
    python run_backtest.py --csv synthetic_5m.csv --out-dir results/

CSV must have columns: timestamp,open,high,low,close,volume, with timestamp
in UTC (see README.md - "Timezones") - crypto trades 24/7, so the default
session blocks are anchored to 00:00 UTC.
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

from sps.engine import SPSParams, build_features, run_backtest

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    return df[["open", "high", "low", "close", "volume"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to 5m OHLCV CSV (timestamp,open,high,low,close,volume)")
    ap.add_argument("--out-dir", default="results", help="Where to write trade_log.csv / equity_curve.png / metrics.json")
    ap.add_argument("--capital", type=float, default=25_000.0)
    ap.add_argument("--risk-pct", type=float, default=0.4)
    ap.add_argument("--commission-pct", type=float, default=0.001, help="Fraction, e.g. 0.001 = 0.1%% per fill")
    ap.add_argument("--slippage-pct", type=float, default=0.0002, help="Fraction, e.g. 0.0002 = 0.02%% per fill")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    df = load_csv(args.csv)

    params = SPSParams(
        initial_capital=args.capital, risk_pct_per_trade=args.risk_pct,
        commission_pct=args.commission_pct, slippage_pct=args.slippage_pct,
    )
    feat = build_features(df, params)
    trades_df, equity, metrics = run_backtest(feat, params)

    trades_path = os.path.join(args.out_dir, "trade_log.csv")
    trades_df.to_csv(trades_path, index=False)

    metrics_path = os.path.join(args.out_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    print("\n=== Session Pullback System - Backtest Results ===")
    for k, v in metrics.items():
        print(f"{k:>22}: {v}")

    if HAVE_MPL:
        fig, ax = plt.subplots(figsize=(10, 5))
        equity.plot(ax=ax)
        ax.set_title("Equity Curve (marked-to-market)")
        ax.set_ylabel("Equity ($)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out_dir, "equity_curve.png"), dpi=130)
        print(f"\nSaved: {trades_path}\nSaved: {metrics_path}\nSaved: {os.path.join(args.out_dir, 'equity_curve.png')}")
    else:
        print(f"\nSaved: {trades_path}\nSaved: {metrics_path}\n(matplotlib not installed - skipped equity_curve.png)")


if __name__ == "__main__":
    main()
