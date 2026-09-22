"""Small, dependency-light indicator helpers shared by engine.py.

Each function matches the corresponding Pine `ta.*` call used in the Pine
scripts closely enough for backtest purposes (not bit-for-bit identical -
Pine's internal smoothing has minor edge-case differences - but the same
formulas and the same lag behavior).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing (used by Pine's ta.atr / ta.rsi internals)."""
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    return rma(true_range(high, low, close), length)


def rsi(close: pd.Series, length: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100.0)
    return out


def rolling_percentrank(series: pd.Series, length: int) -> pd.Series:
    """Percent (0-100) of the trailing `length` bars (inclusive of the
    current bar) that are <= the current value. Matches Pine's
    ta.percentrank semantics closely enough for a volatility filter."""

    def _pct(window: np.ndarray) -> float:
        current = window[-1]
        return 100.0 * np.sum(window <= current) / len(window)

    return series.rolling(length + 1, min_periods=length + 1).apply(_pct, raw=True)


def pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
    """Boolean series, True at bar i if low[i] is the minimum of the
    window [i-left, i+right]. Only known to the trader `right` bars later
    - callers must shift by `right` to use it without lookahead."""
    window = left + right + 1
    roll_min = low.rolling(window, center=True, min_periods=window).min()
    return low == roll_min


def pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
    window = left + right + 1
    roll_max = high.rolling(window, center=True, min_periods=window).max()
    return high == roll_max
