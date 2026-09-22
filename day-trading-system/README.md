# Session Pullback System (SPS) — 5-Minute Day Trading System

A conservative, fully-specified, risk-first day trading system: 4-hour
trend bias, 5-minute execution, hard flat-at-end-of-block exits, and a risk
management layer designed to survive being wrong more often than it's
right.

**Start here: [`PLAYBOOK.md`](PLAYBOOK.md).** It's the single source of
truth for every rule (bias filter, setup, trigger, stop, target, risk
limits, session routine, and the validation path you should follow before
risking real money). The Pine scripts and the Python backtester below both
implement those exact rules — if you tune one, tune the doc too.

## What's in here

```
day-trading-system/
├── PLAYBOOK.md                                  <- the rules (read first)
├── pine/
│   ├── Session_Pullback_5m_Indicator.pine       <- chart tool + alerts (visual only, no trades)
│   └── Session_Pullback_5m_Strategy.pine        <- backtestable TradingView strategy (sizing, exits, risk limits)
├── python/
│   ├── sps/engine.py                            <- feature computation + event-driven backtest (mirrors the Pine strategy bar-for-bar)
│   ├── sps/indicators.py                        <- EMA/ATR/RSI/pivot/percentrank helpers
│   ├── run_backtest.py                          <- CLI: CSV in, trade log + equity curve + metrics out
│   ├── make_synthetic_data.py                   <- generates fake data for smoke-testing only (not real market data)
│   └── README.md                                <- how to run it against real data
└── spreadsheets/
    ├── build_workbook.py                        <- regenerates the workbook below
    └── Session_Pullback_Risk_Toolkit.xlsx        <- position size calculator, daily/weekly risk tracker, trade journal, rules reference
```

## Honest framing

No file in this folder guarantees an edge. A 5-minute day trading system
has to overcome spread, commission, and slippage on every single trade —
that's a real, structural headwind, not a detail. What you're getting here
is:

- A **specific, mechanical rule set** (not vibes) that you can test, not
  just trust.
- A **risk management layer that's the actual point of the system** — the
  entry logic decides when you might be right; the risk rules decide
  whether being wrong a lot can still leave you solvent.
- **Three matching implementations** (chart indicator, backtestable
  strategy, Python engine) so you can go from "does this even work on
  history" to "watch it live on a chart" to "trade it on TradingView" using
  the same rules throughout.

Follow the validation path in PLAYBOOK.md section 11 — backtest, then
paper trade, then live at reduced size — before this touches real capital.
If the backtest doesn't show a real edge after realistic costs, that's the
system telling you something useful; the right response is to rework the
setup criteria, not to lower the bar for what counts as validation.

## Quick start

1. Read `PLAYBOOK.md`.
2. Load `pine/Session_Pullback_5m_Indicator.pine` on a 5-minute chart in
   TradingView to see the bias/VWAP/fib-zone/signals visually.
3. Load `pine/Session_Pullback_5m_Strategy.pine` in Strategy Tester to
   backtest it directly on TradingView with your instrument's real spread
   settings.
4. Or run the Python backtester (`python/README.md`) against your own
   historical 5-minute CSV for faster iteration and cleaner metrics/trade
   logs outside TradingView.
5. Use `spreadsheets/Session_Pullback_Risk_Toolkit.xlsx` every session:
   size every position with the calculator tab, check the daily/weekly
   tracker before taking a new trade, and log every trade in the journal.
