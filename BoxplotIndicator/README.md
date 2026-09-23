# Boxplot Candles (TradingView / Pine Script v6)

`BoxplotCandles.pine` replaces each candlestick with a **box-and-whisker plot of where
price traded inside that bar**.

## How it works

1. Each chart bar is split into lower-timeframe (intrabar) samples with
   `request.security_lower_tf` (e.g. a 1H bar → 60 one-minute samples).
2. Those sample prices are a distribution. Each sample stands for the same slice of
   time, so price levels that come up a lot are where price *spent time*. Levels that
   come up rarely are where price only passed through.
3. The five-number summary is computed and drawn:

| Element | Meaning |
|---|---|
| Box (body) | 25th → 75th percentile (Q1 → Q3), the range holding the middle 50% of the bar's time |
| Horizontal bar | Median: price spent half the bar above it and half below it |
| Whiskers (wicks) | 2nd → 98th percentile by default. Tukey 1.5·IQR and Min/Max are also available |
| Orange dots | Outlier samples beyond the whiskers, drawn as small text dots (• · or – ticks, size adjustable) |
| Gray × | The bar's true high/low when it lies beyond a whisker (a quick wick the samples missed) |

Box color is green or red depending on whether the bar closed above or below its open.

The defaults (closes sampled from a lower timeframe; percentiles 2/25/50/75/98) match
the approach of the "Ori Candlesticks Box Plot" script on TradingView. Differences from it:
the intrabar timeframe is picked automatically (no need to enter the TF ratio), the
current bar updates live, a real median bar is drawn, and outliers, volume weighting and
Tukey whiskers are available.

## Usage

1. Open the Pine Editor in TradingView, paste in `BoxplotCandles.pine`, and click **Add to chart**.
2. Hide the normal candles: *Chart settings → Symbol*, then untick Body, Borders and Wick.

## Settings

- **Auto intrabar timeframe / Target samples**: picks the largest lower timeframe that
  still gives about N samples per bar. Turn it off to choose one yourself.
- **Sample price**: `Close` (default), `HLC3`, or `OHLC (4 points)`, which adds all four
  prices of every intrabar so intrabar wicks are included.
- **Weighting**: `Time` (where price spent time) or `Volume` (where volume traded;
  uses weighted percentiles).
- **Box percentile**: 25 gives the classic 25/75 box; lower values widen it.
- **Whisker method**: Percentile (default 2 → 2nd/98th), Tukey k×IQR (textbook boxplot), or Min/Max.
- **Median display**: the horizontal line is a drawing object, so TradingView keeps
  only the last 500. `Marker` mode shows the median on every bar.
- Outlier dots are labels and are also capped at the last 500.

## Limitations

- Lower-timeframe history is limited by your TradingView plan (about 100k intrabars on
  lower plans). Bars older than that are drawn as faded regular candles (you can turn
  this off).
- On a 1-minute chart there is nothing lower to sample unless your plan has
  seconds-based timeframes. Set the manual timeframe to e.g. `5S`, or use
  `OHLC (4 points)`.
