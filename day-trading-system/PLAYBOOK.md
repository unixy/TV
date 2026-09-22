# Session Pullback System (SPS) — 5-Minute Intraday Playbook

## Read this first

No rule set here produces a guaranteed edge. Retail day trading on a 5-minute
chart is a hard game: spread, commission, and slippage eat a meaningful slice
of a typical winning trade, and most discretionary or semi-mechanical 5-minute
systems that look good on a chart die in live costs and execution slippage.
This document is a **conservative, fully specified, testable framework** —
not a promise. Treat every number in here as a hypothesis to validate on your
own data before it ever touches live capital (see "Validation Path" at the
bottom).

Everything below is written to be mechanical enough that the Pine indicator,
Pine strategy, and Python backtester in this folder all implement the exact
same rules. If you change a rule, change it in all three places.

---

## 1. Structure: why 4-hour blocks + 5-minute execution

- **Bias timeframe: 4-hour (240m).** Filters out 5-minute noise and tells you
  the only direction you're allowed to trade.
- **Execution timeframe: 5-minute.** Entries, stops, and management happen
  here.
- **Session block: 4 hours, flat at the end, no exceptions.** You said you
  want to sit down, trade a 4-hour block, and be flat when it's over whether
  you're up or down. That's encoded as a hard time-stop — it is not
  optional, and it is not "close if I feel like it." It fires automatically.
  A trade that "would have won if I'd just held it" is not a system failure;
  a trader who overrides the time-stop is the system failure.

This is a **trend-continuation pullback system**, not a breakout or reversal
system. You only ever trade in the direction of the 4-hour trend. No
counter-trend trades, ever, under this system.

## 2. Instrument selection (conservative filter)

Only trade instruments that are:
- Liquid (tight spread relative to typical 5-min range — large-cap equities/
  ETFs, major FX pairs, top-10-by-volume crypto pairs).
- Free of a scheduled binary event (earnings, FOMC, CPI, major token
  unlock) inside the session block you intend to trade. If one falls inside
  your 4-hour block, skip that block entirely.
- Trading at "normal" volatility for itself — see the ATR filter below.
  Illiquid or event-driven names turn a structure-based stop into a coin
  flip, which is exactly what this system is designed to avoid.

## 3. Bias filter (4-hour chart)

Bullish bias only when **all** of:
- EMA(20, 4H) > EMA(50, 4H)
- Close(4H) > EMA(20, 4H)
- The EMA(20)/EMA(50) spread, normalized by 4H ATR(14), exceeds a minimum
  separation (default 0.15 ATR) — this is the chop filter. A market where
  the two EMAs are braided together has no tradeable trend; skip it.

Bearish bias is the mirror image. If neither condition is cleanly met, bias
is **neutral — no trades this block.** "No trade" is a position, and under
this system it should be the single most common outcome, not the exception.

## 4. Volatility filter (5-min chart, per block)

Compute ATR(14) on the 5-minute chart as a percentage of price. Skip the
block if:
- ATR% is in the bottom 10% of its own trailing 20-day distribution (dead
  market, poor reward-to-risk, stops rarely reached but targets aren't
  either), or
- ATR% is more than 2.5x its trailing 20-day median (abnormal/event
  volatility — structure stops become unreliable, gap risk rises).

## 5. Setup: fibonacci pullback into VWAP/EMA confluence

1. Identify the active leg using confirmed pivots (default: 3 bars left / 3
   bars right) on the 5-minute chart:
   - In a bullish bias, track the most recent confirmed pivot low, then the
     running high made since that pivot low (the impulse leg up).
   - In a bearish bias, the mirror: most recent pivot high, running low
     since.
2. Draw the retracement of that leg. The **entry zone is the 38.2%–61.8%
   retracement band**, and it must overlap either the session VWAP (anchored
   to the start of the current 4-hour block) or the EMA(21, 5m) — confluence
   of at least two of {fib zone, VWAP, EMA21} is required. A fib pullback in
   free space with nothing else there is a lower-quality signal than this
   system takes.
3. Wait for price to actually trade into that zone. No anticipatory entries.

## 6. Trigger (confirmation, not just "price touched the zone")

Long trigger, all required:
- Close back above the 61.8% fib level after having traded into the zone
  (i.e., the pullback is over, not still developing).
- RSI(14, 5m) crosses back above 45 from below (momentum turning back up,
  not still falling).
- Volume on the trigger candle ≥ its own 20-bar average (real participation,
  not a drift back up on no volume).
- Trigger candle closes green (close > open).
- We are **not** inside the first 10 minutes of the session block (let
  opening noise settle) or the last 20 minutes of the block (not enough
  runway left for a stop to be meaningfully tested before the forced
  flatten — a trade taken here is mostly just time-stop roulette).

Short trigger is the exact mirror.

## 7. Stop loss (structure first, volatility floor second)

Stop = the tighter of:
- Structure stop: a few ticks beyond the pivot low/high that started the
  leg (long) or pivot high/low (short), plus a small buffer (0.1x ATR).
- Volatility stop: entry ± 1.5x ATR(14, 5m).

But never tighter than **1.0x ATR(14, 5m)** from entry — a stop tighter than
that is just noise, not risk management, on a 5-minute chart. If the
structure stop would be tighter than 1.0x ATR, skip the trade rather than
widen it artificially; a good setup with no room to place a real stop is not
a trade.

**The stop never moves against the position.** It only tightens (e.g., to
breakeven), never widens, and it is never removed.

## 8. Target and trade management

- Minimum acceptable reward:risk at entry is **1.5R**; default target is
  **2R**, or the 127.2% fibonacci extension of the pullback leg, whichever
  is closer (more conservative, higher hit-rate target).
- At **+1R**, move the stop to breakeven (entry price) and optionally take
  partial profit (default: close 50% of size). This is the single highest-
  value risk-management habit in this system — it converts a full-loss
  scenario into a scratch on any trade that ever worked at all.
- Full exit at target, at stop, or at the **hard time-stop** (end of the
  4-hour block) — whichever comes first. The time-stop overrides everything:
  a trade sitting at +0.8R with 2 minutes left in the block gets closed at
  the time-stop, not held hoping for +2R.

## 9. Risk management — this is the actual system

Position sizing (every trade, no exceptions):

```
risk_dollars   = account_equity * risk_pct_per_trade
stop_distance  = |entry_price - stop_price|
position_size  = floor(risk_dollars / stop_distance)
```

Conservative defaults (change these up only after you have live evidence
your edge supports it — never before):

| Control | Default | Hard ceiling |
|---|---|---|
| Risk per trade | 0.4% of account | 0.5% |
| Max trades per 4H block | 2 | 3 |
| Max concurrent positions | 1 | 1 |
| Daily loss limit | 1.2% of account (~3R) | stop trading, no exceptions |
| Weekly loss limit | 3.0% of account | stop trading, review week before resuming |
| Consecutive-loss circuit breaker | 2 losses in a block → done for that block | — |
| Min reward:risk to enter | 1.5R | — |

Rules that make these numbers mean something:

- **The daily loss limit is checked before every new entry, not just at
  end of day.** The instant realized P&L for the day hits -1.2%, no new
  trades regardless of how good the next setup looks. This is the rule most
  systems fail on in practice, because the very next setup after a loss
  always looks compelling. It is not special. Stop anyway.
- **Never add to a loser. Never move a stop to give a trade "more room."**
  Both are the two most common ways a well-designed system gets destroyed by
  its own trader.
- **One instrument, one position, one decision at a time** while you're
  building a track record. Trading three symbols at once to "increase
  opportunity" also triples your ability to break the daily loss limit
  rule before you notice.
- Every trade gets logged in the trade journal (see `spreadsheets/`) —
  entry/stop/target reasoning, what actually happened, and whether every
  rule above was followed exactly. A rule you didn't follow doesn't count
  as evidence for or against the system.

## 10. Session routine (what "sitting down for a 4-hour block" looks like)

1. Before the block starts: confirm instrument passes the liquidity/news/
   volatility filters (Sections 2 and 4). Check the 4H bias (Section 3). If
   bias is neutral, you already know this block is a "no trade" block —
   don't open the 5-minute chart looking for reasons to override that.
2. First 10 minutes of the block: observe only, no entries.
3. Middle of the block: work the setup (Sections 5–6) in the bias direction
   only. Max 2 entries. Manage per Section 8. Respect the daily loss limit
   and consecutive-loss breaker at all times.
4. Last 20 minutes of the block: no new entries. Manage existing position
   toward the time-stop.
5. At the 4-hour mark: flat, no exceptions, whether winning or losing.
6. After the block: fill in the journal for every trade taken (and, ideally,
   note every A+ setup you correctly skipped due to the filters — that's
   evidence the filters are working).

## 11. Validation path — do this before risking real money

1. **Backtest** (`python/`) over at least 6–12 months of 5-minute data for
   your instrument, with realistic commission and slippage assumptions.
   Look for a minimum of ~100 closed trades before trusting any statistic
   from it. Read the expectancy and max-drawdown numbers, not just the
   headline win rate.
2. **Paper trade** the system live (real-time, real setups, no hindsight)
   for 4–6 weeks. This catches everything the backtest can't: hesitation,
   fills that weren't really available, discipline under real emotion.
3. **Live, at reduced size** (e.g., 25% of the risk_pct default above) for
   another 2–4 weeks. Only scale to full size once you have live evidence,
   not backtest or paper evidence, that you can execute the rules.
4. Re-validate periodically. An edge that worked in one volatility regime
   is not guaranteed to keep working when the regime changes — that's a
   reason to keep the journal and keep re-running the backtest, not a flaw
   unique to this system.

If at any point the honest answer is "the backtest doesn't show a real
edge after costs," the correct response is to stop and rework the setup
criteria — not to lower the bar for what counts as validation.
