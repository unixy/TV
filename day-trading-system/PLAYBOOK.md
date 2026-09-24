# Session Pullback System (SPS) — 5-Minute Crypto Day Trading Playbook

## Read this first

No rule set here produces a guaranteed edge. Day trading on a 5-minute chart
is a hard game even before crypto-specific costs: spread, exchange fees, and
slippage eat a meaningful slice of a typical winning trade, and most
discretionary or semi-mechanical 5-minute systems that look good on a chart
die in live costs and execution slippage. This document is a **conservative,
fully specified, testable framework** — not a promise. Treat every number in
here as a hypothesis to validate on your own data before it ever touches
live capital (see "Validation Path" at the bottom).

Everything below is written to be mechanical enough that the Pine indicator,
Pine strategy, and Python backtester in this folder all implement the exact
same rules. If you change a rule, change it in all three places.

**Scope: spot trading, top-10-by-market-cap crypto, no leverage, by
default.** Section 2 covers instrument selection and Section 9 covers why
leverage/perpetual futures are treated as an optional, explicitly riskier
variant rather than the default.

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

Crypto is actually a cleaner fit for this structure than a market with fixed
hours: it trades 24/7, so 4-hour blocks tile the day exactly — **00:00,
04:00, 08:00, 12:00, 16:00, 20:00 UTC**, six blocks a day, every day,
weekends included. There's no "the last block runs past the close" problem.
It also means the 4-hour bias candle that gates each block is literally *the
4-hour candle that just closed right before the block starts* — the bias
timeframe and the block length are the same clock. Trade UTC time, not your
local time, so the blocks match what every exchange and every other trader
watching 4H candles is looking at.

If you're trading perpetual futures rather than spot: most venues (e.g.
Binance) settle funding every 8 hours, at 00:00/08:00/16:00 UTC — exactly
two of the six block boundaries. Being flat at the end of every block means
you are essentially never holding through a full funding settlement, which
cuts funding cost and the volatility spike that sometimes accompanies it, as
a free side effect of a rule that exists for other reasons.

This is a **trend-continuation pullback system**, not a breakout or reversal
system. You only ever trade in the direction of the 4-hour trend. No
counter-trend trades, ever, under this system.

**A note on shorting**: the rules below are written symmetrically (long
setups in an uptrend, short setups in a downtrend) because that's how the
underlying pattern works. But a genuine spot account has no borrow
mechanism and cannot short at all — on spot, this system is long-only in
practice, and a bearish bias simply means "no trade" rather than "go
short." Shorting requires a margin or perpetual futures account, which
brings in the leverage/liquidation cautions in Section 9. The short side
isn't free optionality; treat it as a separate, explicit decision.

## 2. Instrument selection (conservative filter)

**Default: spot market, top 10 by market capitalization, on a major
exchange (Binance, Coinbase, Kraken), quoted in USDT or USD.** In practice
that means you're choosing among BTC, ETH, and a handful of large, liquid
majors (SOL, BNB, XRP, and similar) — not the full top-10 list blindly.

Two caveats worth taking seriously:

- **"Top 10 by market cap" is not the same as "safe to trade."** Market cap
  can be inflated by low float, concentrated holdings, or a listing/
  narrative pump, and the top-10 list occasionally includes a highly
  volatile, sentiment-driven asset (memecoins have entered it before) with
  wick behavior that's a poor match for a structure-based stop. Cross-check
  24h spot volume and order book depth, not just market cap rank — BTC and
  ETH are the cleanest fits for this system; treat anything past that with
  more scrutiny, not less.
- **Stablecoins are not a trading instrument for this system.** If a
  stablecoin ever shows up in a "top 10" list you're screening, skip it —
  there's no trend to trade.

Beyond that, only trade instruments/venues that are:
- Liquid (tight spread relative to typical 5-min range, deep order book at
  the sizes you trade — this is easy to satisfy for BTC/ETH on a major
  exchange, much less so further down the cap table).
- Free of a scheduled, foreseeable event (a major token unlock, a known
  exchange listing/delisting, a scheduled protocol upgrade) inside the
  session block you intend to trade. If one falls inside your 4-hour block,
  skip that block entirely.
- Trading at "normal" volatility for itself — see the ATR filter below.
  Illiquid or event-driven conditions turn a structure-based stop into a
  coin flip, which is exactly what this system is designed to avoid. Be
  extra alert to this around low-liquidity windows (weekend overnight UTC
  hours can be thinner even though the market never technically closes).

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
- ATR% is in the bottom 10% of its own trailing distribution (dead market,
  poor reward-to-risk, stops rarely reached but targets aren't either), or
- ATR% is more than 2.5x its trailing median (abnormal/event volatility —
  structure stops become unreliable, gap risk rises).

Crypto trades every 5-minute bar around the clock, so a "20 trading day"
lookback isn't 20 calendar days of bars the way it would be for a market
that closes overnight and on weekends — 20 full calendar days of 5-minute
bars would be 20 × 288 = 5,760 bars. In practice the default lookback here
is **4,800 bars (~17 calendar days)**, because TradingView's `ta.percentrank()`
has a hard 5,000-bar limit — not a design choice, a platform ceiling. The
Python engine has no such limit and could run a longer window, but it
defaults to the same 4,800 so the two implementations stay comparable;
shrink either one if you want the filter to adapt faster to a changing
volatility regime, at the cost of a noisier threshold.

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

Position sizing (every trade, no exceptions; sizes are fractional coin
amounts, not whole units — 0.0142 BTC is a completely normal position size):

```
risk_dollars   = account_equity * risk_pct_per_trade
stop_distance  = |entry_price - stop_price|
position_size  = risk_dollars / stop_distance      (fractional; round down
                                                      to your exchange's
                                                      lot/step size)
```

**A spot-specific wrinkle**: with no leverage, you can never buy more
notional than your cash — `position_size * entry_price` is hard-capped at
your account equity. On a high-priced coin like BTC with a tight ATR-based
stop, the risk-based formula above can imply a position worth more than
your entire account. If that happens, cap the size to `equity / entry_price`
instead and accept that your realized dollar risk on that trade will come
in under your target risk% — that's safe (under-risking, not over-risking)
and is a sign your account size is small relative to that stop distance,
not a reason to add leverage to hit the "intended" size. The Position Size
Calculator in `spreadsheets/` flags this automatically.

Conservative defaults (change these up only after you have live evidence
your edge supports it — never before):

| Control | Default | Hard ceiling |
|---|---|---|
| Risk per trade | 0.4% of account | 0.5% |
| Max trades per 4H block | 2 | 3 |
| Max concurrent positions | 1 | 1 |
| Daily loss limit | 1.2% of account (~3R) | stop trading, no exceptions |
| Weekly loss limit (any rolling 7-day window — crypto trades every day) | 3.0% of account | stop trading, review before resuming |
| Consecutive-loss circuit breaker | 2 losses in a block → done for that block | — |
| Min reward:risk to enter | 1.5R | — |
| Leverage | **1x (spot, no leverage)** | see below if you deviate |

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

### On leverage and perpetual futures

This system is specified for **spot trading with no leverage** by default.
If you choose to trade perpetual futures instead of spot, understand that
you're adding a risk this playbook doesn't otherwise carry: **liquidation**.
A stock or spot position that gaps through your stop still fills you out
(at a worse price, but it fills you out, per the earlier stop-loss
discussion). A leveraged position that reaches its liquidation price gets
force-closed by the exchange, often at a worse price than your own stop
would have given you, with an additional liquidation fee on top — and
crypto's volatility makes that price level closer than most people
intuitively expect. If you do use perpetuals:
- Cap leverage at **2x, never above 3x**, regardless of what the exchange
  allows.
- Treat your liquidation price as a hard third boundary, tighter than your
  stop must ever be — if your calculated stop distance would put the
  liquidation price closer than, say, 3x your stop distance away, that's a
  sign your leverage is too high for the position size, not a reason to
  loosen the stop.
- Budget for funding payments in your expectancy math; they're a real,
  recurring cost this system's spot-based backtest does not model.
- None of the position-sizing formulas above change - `risk_dollars` is
  still based on your stop distance, not your leverage. Leverage changes
  your liquidation risk and capital efficiency; it should never be used to
  take a bigger risk-per-trade than the table above allows.

## 10. Session routine (what "sitting down for a 4-hour block" looks like)

Blocks run 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 **UTC** — set your
charting/trading platform to UTC (or do the conversion once and keep a
cheat-sheet of your local block start times) so "the block" means the same
thing on the chart, in the journal, and in the backtester.

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
   your instrument - `python/fetch_data.py` pulls this via `ccxt` (Coinbase
   by default; see its docstring for exchange-specific gotchas) - with
   realistic commission and slippage assumptions - use
   your actual exchange's taker fee (spot majors are commonly ~0.1% per
   fill, less with a fee-token discount or maker rebate; check your own
   account's tier) rather than the default. Since crypto trades every day,
   6-12 months of 5-minute bars is a genuinely large sample (roughly 50,000
   -105,000 bars) - a real advantage over a market that's only open a third
   of the week. Look for a minimum of ~100 closed trades before trusting any
   statistic from it. Read the expectancy and max-drawdown numbers, not just
   the headline win rate.
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
