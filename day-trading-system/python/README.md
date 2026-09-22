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

`make_synthetic_data.py` generates a random-walk-with-regime-drift CSV.
**This is not real market data and proves nothing about whether the system
has an edge** - it exists only to let you confirm the code runs on your
machine before you point it at real data.

```bash
python make_synthetic_data.py --days 90 --out synthetic_5m.csv
python run_backtest.py --csv synthetic_5m.csv --out-dir results
```

This writes `results/trade_log.csv` (every trade, with entry/exit/stop/
target/R-multiple), `results/metrics.json`, and `results/equity_curve.png`.

## Using real data

Get real 5-minute OHLCV bars for your instrument (your broker's export,
a data vendor, or a library like `yfinance` or `ccxt`) and save as a CSV
with columns:

```
timestamp,open,high,low,close,volume
```

Then:

```bash
python run_backtest.py --csv your_data.csv --out-dir results --capital 25000 --risk-pct 0.4
```

### Timezones

`timestamp` must already be in the timezone you want session blocks
measured in (e.g. US equities: `America/New_York` local time, naive - no
UTC offset). The engine does not do timezone conversion; if your data is in
UTC and your session anchor (default 09:30) is meant to be exchange-local
time, convert before loading, e.g.:

```python
import pandas as pd
df = pd.read_csv("raw_utc.csv", parse_dates=["timestamp"])
df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
df.to_csv("your_data.csv", index=False)
```

### Session block length vs. trading hours

4-hour blocks tile cleanly across a 24/7 market (crypto). For a 6.5-hour
equity RTH session anchored at 09:30, two 4-hour blocks (09:30-13:30 and
13:30-17:30) overrun the 16:00 close - the second block just runs short.
That's fine mechanically (the no-new-entries-in-the-last-20-minutes rule
still applies relative to the block's own boundary, and nothing stops you
at the actual close), but be aware the "4 hours" is measured from your
anchor, not from market open/close. If you want blocks that map exactly to
your session, pick an anchor and adjust `--block anchor`/length via
`SPSParams` directly in a small script instead of the CLI defaults.

## Tuning parameters

All rule knobs live in `sps.engine.SPSParams` (risk %, loss limits, fib
levels, filters, etc.) - the CLI only exposes the few you'll change most
often (`--capital`, `--risk-pct`, `--tick-size`). For anything else, write a
short script:

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
