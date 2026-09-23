# SPS Python Backtester

A pure-pandas/numpy event-driven backtest of the Session Pullback System
(see `../PLAYBOOK.md`). It implements the exact same rules as
`../pine/Session_Pullback_5m_Strategy.pine`, bar by bar, so you can validate
the system on historical data before ever loading it onto a TradingView
chart with real capital behind it.

## Install

```bash
pip install -r requirements.txt
```

## Quick start (synthetic data smoke test)

`make_synthetic_data.py` generates a continuous 24/7, random-walk-with-
regime-drift CSV starting at a BTC-like price level. **This is not real
market data and proves nothing about whether the system has an edge** - it
exists only to let you confirm the code runs on your machine before you
point it at real data.

```bash
python make_synthetic_data.py --days 90 --out synthetic_5m.csv
python run_backtest.py --csv synthetic_5m.csv --out-dir results
```

This writes `results/trade_log.csv` (every trade, with entry/exit/stop/
target/R-multiple), `results/metrics.json`, and `results/equity_curve.png`.

## Using real data

Get real 5-minute OHLCV bars for a **top-10-by-market-cap coin on a major
exchange** (spot, e.g. BTC/USDT or ETH/USDT on Binance/Coinbase/Kraken) -
`ccxt` is the standard library for this. Save as a CSV with columns:

```
timestamp,open,high,low,close,volume
```

Then:

```bash
python run_backtest.py --csv your_data.csv --out-dir results --capital 25000 --risk-pct 0.4 --commission-pct 0.001 --slippage-pct 0.0002
```

Set `--commission-pct` to your actual account's taker fee (spot majors are
commonly ~0.1% = 0.001, less with a fee-token discount - check your own fee
tier) rather than trusting the default.

### Timezones

`timestamp` must already be **in UTC**, tz-naive (no offset suffix). Crypto
trades 24/7 so there's no exchange-local session to convert to - the
default session anchor (00:00) lines up 4-hour blocks at
00:00/04:00/08:00/12:00/16:00/20:00 UTC, which also happens to match
funding-settlement times on most perpetual futures venues. If your raw data
has a UTC offset or is in another timezone, normalize it first:

```python
import pandas as pd
df = pd.read_csv("raw.csv", parse_dates=["timestamp"])
df["timestamp"] = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)  # if already tz-aware
# or: df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_localize(None)  # if naive but actually UTC
df.to_csv("your_data.csv", index=False)
```

Since blocks tile the day exactly in a 24/7 market, there's no equivalent
here of the equities "the last block runs past the close" compromise - the
six blocks a day are always full 4-hour blocks, every day, weekends
included.

## Tuning parameters

All rule knobs live in `sps.engine.SPSParams` (risk %, loss limits, fib
levels, filters, `allow_shorts`, `qty_step` for exchange lot-size rounding,
etc.) - the CLI only exposes the few you'll change most often (`--capital`,
`--risk-pct`, `--commission-pct`, `--slippage-pct`). For anything else,
write a short script:

```python
from sps.engine import SPSParams, build_features, run_backtest
import pandas as pd

df = pd.read_csv("your_data.csv", parse_dates=["timestamp"]).set_index("timestamp")
params = SPSParams(risk_pct_per_trade=0.3, max_trades_per_block=1, daily_loss_limit_pct=1.0)
feat = build_features(df, params)
trades, equity, metrics = run_backtest(feat, params)
print(metrics)
```

## Reading the output

- **win_rate_pct / profit_factor / expectancy_r**: the headline numbers,
  but see PLAYBOOK.md - do not trust these until you have ~100+ trades.
- **max_drawdown_pct**: peak-to-trough on the marked-to-market equity
  curve. If this exceeds your weekly loss limit's implied tolerance by a
  wide margin, the loss-limit rules didn't fully contain a bad stretch and
  the parameters need revisiting before going anywhere near live capital.
- **exit_reason_counts**: how trades actually ended (`stop`, `target`,
  `session_end`). A system where most trades end in `session_end` rather
  than `stop`/`target` is telling you the setup rarely gets enough runway
  before the hard time-stop - worth knowing before you trade it live.
- **breakeven_saves**: trades that reached +1R and got the stop moved to
  breakeven. Compare this to how many of those would otherwise have ended
  as losers - it's the single best sanity check on whether that rule is
  pulling its weight.

Two things this backtester does **not** model, and you should account for
mentally: (1) partial/limited fills on illiquid names or during fast
markets, and (2) the psychological cost of executing a mechanical time-stop
against your own read of the tape in real time. Both matter more than
another decimal place of optimization.
