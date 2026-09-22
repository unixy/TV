"""Session Pullback System - feature computation + event-driven backtest.

This mirrors day-trading-system/pine/Session_Pullback_5m_Strategy.pine bar
by bar (see PLAYBOOK.md for the rules in prose). Two deliberate,
documented simplifications versus the live Pine script:

1. Entries and the hard time-stop fill at the *signal bar's own close*
   (matching `process_orders_on_close = true` in the Pine strategy), not
   the next bar's open. Resting stop/target orders are still checked
   against subsequent bars' intrabar high/low, same as TradingView's
   broker emulator.
2. Daily/weekly loss limits are evaluated against *realized* equity only
   (closed trades), not floating/unrealized P&L. This is simpler, fully
   deterministic, and arguably more standard for a hard "stop trading"
   rule - but it means the Python and Pine equity curves can diverge
   slightly intraday even when every trade matches. The equity curve this
   engine reports is *marked-to-market* (realized + open position),
   the loss-limit checks are on realized equity only.

Feed it 5-minute OHLCV bars indexed by a tz-naive DatetimeIndex already in
your intended session timezone (see python/README.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from . import indicators as ind


@dataclass
class SPSParams:
    # Bias (4H)
    bias_tf: str = "4h"
    bias_ema_fast: int = 20
    bias_ema_slow: int = 50
    bias_atr_len: int = 14
    min_sep_atr_mult: float = 0.15

    # Setup
    pivot_len: int = 3
    fib_near: float = 0.382
    fib_far: float = 0.618
    zone_touch_window: int = 6
    confluence_ema_len: int = 21
    confluence_atr_mult: float = 0.5

    # Trigger
    rsi_len: int = 14
    rsi_trigger: float = 45.0
    vol_ma_len: int = 20

    # Session block
    session_anchor_hour: int = 9
    session_anchor_min: int = 30
    block_len_min: int = 240
    no_trade_open_min: int = 10
    no_trade_close_min: int = 20
    max_trades_per_block: int = 2

    # Volatility filter
    atr_len: int = 14
    pct_lookback: int = 1000
    low_pctile: float = 10.0
    high_pctile: float = 97.5

    # Risk management
    allow_shorts: bool = True
    risk_pct_per_trade: float = 0.4
    allow_fractional: bool = False
    min_rr: float = 1.5
    target_r_multiple: float = 2.0
    be_trigger_r: float = 1.0
    partial_at_be: bool = True
    partial_pct: float = 50.0
    daily_loss_limit_pct: float = 1.2
    weekly_loss_limit_pct: float = 3.0
    consec_loss_breaker: int = 2

    # Costs / execution
    initial_capital: float = 25_000.0
    commission_per_order: float = 1.0
    slippage_ticks: int = 2
    tick_size: float = 0.01


def build_features(df: pd.DataFrame, p: SPSParams) -> pd.DataFrame:
    """Add every indicator/session column the backtest loop needs.
    `df` must have columns open/high/low/close/volume and a tz-naive
    DatetimeIndex already in the intended session timezone."""
    out = df.copy()
    out["hlc3"] = (out["high"] + out["low"] + out["close"]) / 3.0

    # ---- 5m indicators ----
    out["ema21"] = ind.ema(out["close"], p.confluence_ema_len)
    out["atr5"] = ind.atr(out["high"], out["low"], out["close"], p.atr_len)
    out["atr_pct"] = out["atr5"] / out["close"] * 100.0
    out["vol_percentile"] = ind.rolling_percentrank(out["atr_pct"], p.pct_lookback)
    out["vol_ok"] = (out["vol_percentile"] >= p.low_pctile) & (out["vol_percentile"] <= p.high_pctile)
    out["vol_ok"] = out["vol_ok"].fillna(False)
    out["rsi"] = ind.rsi(out["close"], p.rsi_len)
    out["vol_ma"] = ind.sma(out["volume"], p.vol_ma_len)

    # ---- 4H bias, computed on closed higher-tf bars only (no lookahead) ----
    htf = out[["close", "high", "low"]].resample(p.bias_tf, label="right", closed="right").agg(
        {"close": "last", "high": "max", "low": "min"}
    ).dropna()
    htf_close_shift = htf["close"].shift(1)
    htf_tr = pd.concat(
        [(htf["high"] - htf["low"]), (htf["high"] - htf_close_shift).abs(), (htf["low"] - htf_close_shift).abs()],
        axis=1,
    ).max(axis=1)
    htf_atr = ind.rma(htf_tr, p.bias_atr_len)
    htf_ema_fast = ind.ema(htf["close"], p.bias_ema_fast)
    htf_ema_slow = ind.ema(htf["close"], p.bias_ema_slow)
    htf_feat = pd.DataFrame(
        {"biasEmaFast": htf_ema_fast, "biasEmaSlow": htf_ema_slow, "biasAtr": htf_atr, "biasClose": htf["close"]}
    )
    left = out.reset_index()
    left = left.rename(columns={left.columns[0]: "ts"})
    right = htf_feat.reset_index()
    right = right.rename(columns={right.columns[0]: "ts"})
    merged = pd.merge_asof(left, right, on="ts", direction="backward").set_index("ts")
    out["biasEmaFast"], out["biasEmaSlow"], out["biasAtr"], out["biasClose"] = (
        merged["biasEmaFast"],
        merged["biasEmaSlow"],
        merged["biasAtr"],
        merged["biasClose"],
    )
    ema_sep_atr = (out["biasEmaFast"] - out["biasEmaSlow"]) / out["biasAtr"].replace(0.0, np.nan)
    out["bias_bullish"] = (
        (out["biasEmaFast"] > out["biasEmaSlow"]) & (out["biasClose"] > out["biasEmaFast"]) & (ema_sep_atr > p.min_sep_atr_mult)
    ).fillna(False)
    out["bias_bearish"] = (
        (out["biasEmaFast"] < out["biasEmaSlow"]) & (out["biasClose"] < out["biasEmaFast"]) & (ema_sep_atr < -p.min_sep_atr_mult)
    ).fillna(False)

    # ---- session block bookkeeping (index assumed already in session tz) ----
    minutes_of_day = out.index.hour * 60 + out.index.minute
    anchor = p.session_anchor_hour * 60 + p.session_anchor_min
    minutes_since_anchor = (minutes_of_day - anchor) % 1440
    pos_in_block = minutes_since_anchor % p.block_len_min
    new_block = pos_in_block == 0
    if len(new_block) > 0:
        new_block[0] = True  # force a block start at the beginning of the data
    out["pos_in_block"] = pos_in_block
    out["new_block"] = new_block
    out["no_trade_window"] = (pos_in_block < p.no_trade_open_min) | (pos_in_block >= (p.block_len_min - p.no_trade_close_min))

    block_id = pd.Series(new_block, index=out.index).cumsum()
    cum_pv = (out["hlc3"] * out["volume"]).groupby(block_id).cumsum()
    cum_vol = out["volume"].groupby(block_id).cumsum()
    out["vwap_session"] = cum_pv / cum_vol.replace(0.0, np.nan)

    out["new_day"] = out.index.normalize() != pd.Series(out.index, index=out.index).shift(1).dt.normalize()
    iso = out.index.isocalendar()
    week_key = iso["year"].astype(str) + "-W" + iso["week"].astype(str)
    out["new_week"] = week_key.values != np.roll(week_key.values, 1)
    out.loc[out.index[0], "new_week"] = True

    # ---- confirmed pivots (available `pivot_len` bars after they occur) ----
    raw_piv_low = ind.pivot_low(out["low"], p.pivot_len, p.pivot_len)
    raw_piv_high = ind.pivot_high(out["high"], p.pivot_len, p.pivot_len)
    out["confirmed_piv_low"] = raw_piv_low.shift(p.pivot_len).fillna(False).astype(bool)
    out["confirmed_piv_high"] = raw_piv_high.shift(p.pivot_len).fillna(False).astype(bool)
    out["confirmed_piv_low_price"] = out["low"].shift(p.pivot_len)
    out["confirmed_piv_high_price"] = out["high"].shift(p.pivot_len)

    return out


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp = None
    exit_price: float = None
    qty: float = 0.0
    stop_price: float = None
    target_price: float = None
    r_dist: float = None
    exit_reason: str = None
    pnl: float = 0.0
    r_multiple: float = None
    partial_pnl: float = 0.0
    breakeven_moved: bool = False


def run_backtest(feat: pd.DataFrame, p: SPSParams) -> tuple[pd.DataFrame, pd.Series, dict]:
    n = len(feat)
    idx = feat.index
    o, h, l, c, v = (feat[col].to_numpy() for col in ["open", "high", "low", "close", "volume"])
    bias_bull = feat["bias_bullish"].to_numpy()
    bias_bear = feat["bias_bearish"].to_numpy()
    vwap = feat["vwap_session"].to_numpy()
    ema21 = feat["ema21"].to_numpy()
    atr5 = feat["atr5"].to_numpy()
    vol_ok = feat["vol_ok"].to_numpy()
    rsi = feat["rsi"].to_numpy()
    vol_ma = feat["vol_ma"].to_numpy()
    new_block = feat["new_block"].to_numpy()
    no_trade_window = feat["no_trade_window"].to_numpy()
    new_day = feat["new_day"].to_numpy()
    new_week = feat["new_week"].to_numpy()
    cpl_flag = feat["confirmed_piv_low"].to_numpy()
    cph_flag = feat["confirmed_piv_high"].to_numpy()
    cpl_price = feat["confirmed_piv_low_price"].to_numpy()
    cph_price = feat["confirmed_piv_high_price"].to_numpy()

    tick = p.tick_size
    equity = p.initial_capital
    day_start_equity = None
    week_start_equity = None
    trades_this_block = 0
    consec_losses_this_block = 0

    last_piv_low_price = np.nan
    last_piv_high_price = np.nan
    run_up_high = np.nan
    run_down_low = np.nan
    bars_since_long_touch = None
    bars_since_short_touch = None

    position_side = 0  # 0 flat, 1 long, -1 short
    entry_bar = -1
    entry_price = stop_price = target_price = r_dist = qty_open = np.nan
    be_done = partial_done = False
    current_trade: Trade | None = None

    trades: list[Trade] = []
    equity_curve = np.empty(n)

    for i in range(n):
        if new_block[i]:
            trades_this_block = 0
            consec_losses_this_block = 0

        if new_day[i] or day_start_equity is None:
            day_start_equity = equity
        if new_week[i] or week_start_equity is None:
            week_start_equity = equity
        daily_loss_pct = (equity - day_start_equity) / day_start_equity * 100.0 if day_start_equity else 0.0
        weekly_loss_pct = (equity - week_start_equity) / week_start_equity * 100.0 if week_start_equity else 0.0
        daily_loss_hit = daily_loss_pct <= -p.daily_loss_limit_pct
        weekly_loss_hit = weekly_loss_pct <= -p.weekly_loss_limit_pct

        # ---- 1. resting stop/target check (only for bars after entry bar) ----
        if position_side != 0 and entry_bar < i:
            exit_price = None
            reason = None
            if position_side == 1:
                hit_stop = l[i] <= stop_price
                hit_target = h[i] >= target_price
                if hit_stop:
                    exit_price = stop_price if o[i] >= stop_price else o[i]
                    reason = "stop"
                elif hit_target:
                    exit_price = target_price if o[i] <= target_price else o[i]
                    reason = "target"
            else:
                hit_stop = h[i] >= stop_price
                hit_target = l[i] <= target_price
                if hit_stop:
                    exit_price = stop_price if o[i] <= stop_price else o[i]
                    reason = "stop"
                elif hit_target:
                    exit_price = target_price if o[i] >= target_price else o[i]
                    reason = "target"

            if exit_price is not None:
                fill = exit_price - p.slippage_ticks * tick if position_side == 1 else exit_price + p.slippage_ticks * tick
                pnl = (fill - entry_price) * qty_open if position_side == 1 else (entry_price - fill) * qty_open
                pnl -= p.commission_per_order
                equity += pnl
                current_trade.exit_time = idx[i]
                current_trade.exit_price = fill
                current_trade.exit_reason = reason
                current_trade.pnl += pnl
                current_trade.r_multiple = current_trade.pnl / (r_dist * current_trade.qty) if r_dist else np.nan
                trades.append(current_trade)
                if pnl < 0:
                    consec_losses_this_block += 1
                else:
                    consec_losses_this_block = 0
                position_side = 0
                current_trade = None

        # ---- 2. breakeven + partial (bar-close based, only if still open) ----
        if position_side != 0:
            r_now = (c[i] - entry_price) / r_dist if position_side == 1 else (entry_price - c[i]) / r_dist
            if r_now >= p.be_trigger_r and not be_done:
                if p.partial_at_be and not partial_done:
                    part_qty = qty_open * p.partial_pct / 100.0
                    if not p.allow_fractional:
                        part_qty = float(np.floor(part_qty))
                    if part_qty > 0:
                        fill = c[i] - p.slippage_ticks * tick if position_side == 1 else c[i] + p.slippage_ticks * tick
                        pnl = (fill - entry_price) * part_qty if position_side == 1 else (entry_price - fill) * part_qty
                        pnl -= p.commission_per_order
                        equity += pnl
                        current_trade.partial_pnl += pnl
                        current_trade.pnl += pnl
                        qty_open -= part_qty
                    partial_done = True
                stop_price = entry_price
                be_done = True
                current_trade.breakeven_moved = True

        # ---- 3. hard time-stop: flat at block end, no exceptions ----
        if new_block[i] and position_side != 0:
            fill = c[i] - p.slippage_ticks * tick if position_side == 1 else c[i] + p.slippage_ticks * tick
            pnl = (fill - entry_price) * qty_open if position_side == 1 else (entry_price - fill) * qty_open
            pnl -= p.commission_per_order
            equity += pnl
            current_trade.exit_time = idx[i]
            current_trade.exit_price = fill
            current_trade.exit_reason = "session_end"
            current_trade.pnl += pnl
            current_trade.r_multiple = current_trade.pnl / (r_dist * current_trade.qty) if r_dist else np.nan
            trades.append(current_trade)
            if pnl < 0:
                consec_losses_this_block += 1
            else:
                consec_losses_this_block = 0
            position_side = 0
            current_trade = None

        # ---- 4. leg tracking (always updates, mirrors the Pine script) ----
        if cpl_flag[i]:
            last_piv_low_price = cpl_price[i]
            lo = max(0, i - p.pivot_len)
            run_up_high = np.max(h[lo : i + 1])
        elif not np.isnan(run_up_high):
            run_up_high = max(run_up_high, h[i])

        if cph_flag[i]:
            last_piv_high_price = cph_price[i]
            lo = max(0, i - p.pivot_len)
            run_down_low = np.min(l[lo : i + 1])
        elif not np.isnan(run_down_low):
            run_down_low = min(run_down_low, l[i])

        leg_up_valid = not np.isnan(last_piv_low_price) and not np.isnan(run_up_high) and run_up_high > last_piv_low_price
        leg_down_valid = not np.isnan(last_piv_high_price) and not np.isnan(run_down_low) and last_piv_high_price > run_down_low

        if leg_up_valid:
            fib_hi_l = run_up_high - (run_up_high - last_piv_low_price) * p.fib_near
            fib_lo_l = run_up_high - (run_up_high - last_piv_low_price) * p.fib_far
            touched_long = fib_lo_l <= l[i] <= fib_hi_l
        else:
            fib_hi_l = fib_lo_l = np.nan
            touched_long = False
        bars_since_long_touch = 0 if touched_long else (None if bars_since_long_touch is None else bars_since_long_touch + 1)
        long_zone_fresh = bars_since_long_touch is not None and bars_since_long_touch <= p.zone_touch_window

        if leg_down_valid:
            fib_lo_s = run_down_low + (last_piv_high_price - run_down_low) * p.fib_near
            fib_hi_s = run_down_low + (last_piv_high_price - run_down_low) * p.fib_far
            touched_short = fib_lo_s <= h[i] <= fib_hi_s
        else:
            fib_lo_s = fib_hi_s = np.nan
            touched_short = False
        bars_since_short_touch = 0 if touched_short else (None if bars_since_short_touch is None else bars_since_short_touch + 1)
        short_zone_fresh = bars_since_short_touch is not None and bars_since_short_touch <= p.zone_touch_window

        confluence_ok = not np.isnan(vwap[i]) and (
            abs(c[i] - vwap[i]) <= atr5[i] * p.confluence_atr_mult or abs(c[i] - ema21[i]) <= atr5[i] * p.confluence_atr_mult
        )

        rsi_reclaim_up = i > 0 and not np.isnan(rsi[i - 1]) and rsi[i - 1] < p.rsi_trigger <= rsi[i]
        rsi_reclaim_down = i > 0 and not np.isnan(rsi[i - 1]) and rsi[i - 1] > (100 - p.rsi_trigger) >= rsi[i]
        vol_ok_bar = v[i] >= vol_ma[i] if not np.isnan(vol_ma[i]) else False

        long_trigger = (
            bias_bull[i] and leg_up_valid and long_zone_fresh and confluence_ok and not no_trade_window[i] and vol_ok[i]
            and c[i] > fib_lo_l and c[i] > o[i] and rsi_reclaim_up and vol_ok_bar
        )
        short_trigger = (
            p.allow_shorts and bias_bear[i] and leg_down_valid and short_zone_fresh and confluence_ok and not no_trade_window[i]
            and vol_ok[i] and c[i] < fib_hi_s and c[i] < o[i] and rsi_reclaim_down and vol_ok_bar
        )

        struct_stop_long = last_piv_low_price - atr5[i] * 0.1 if leg_up_valid else np.nan
        stop_long = min(max(struct_stop_long, c[i] - atr5[i] * 1.5), c[i] - atr5[i] * 1.0)
        stop_dist_long = c[i] - stop_long

        struct_stop_short = last_piv_high_price + atr5[i] * 0.1 if leg_down_valid else np.nan
        stop_short = max(min(struct_stop_short, c[i] + atr5[i] * 1.5), c[i] + atr5[i] * 1.0)
        stop_dist_short = stop_short - c[i]

        # ---- 5. entries (flat only) ----
        can_enter = (
            position_side == 0 and trades_this_block < p.max_trades_per_block
            and consec_losses_this_block < p.consec_loss_breaker and not daily_loss_hit and not weekly_loss_hit
        )

        if can_enter and long_trigger and stop_dist_long > 0 and p.target_r_multiple >= p.min_rr:
            risk_dollars = equity * p.risk_pct_per_trade / 100.0
            size = risk_dollars / stop_dist_long
            if not p.allow_fractional:
                size = float(np.floor(size))
            if size > 0:
                fill = c[i] + p.slippage_ticks * tick
                equity -= p.commission_per_order
                position_side = 1
                entry_bar = i
                entry_price = fill
                stop_price = stop_long
                r_dist = max(entry_price - stop_price, tick)
                target_price = entry_price + r_dist * p.target_r_multiple
                qty_open = size
                be_done = partial_done = False
                trades_this_block += 1
                current_trade = Trade(
                    side="long", entry_time=idx[i], entry_price=entry_price, qty=size,
                    stop_price=stop_price, target_price=target_price, r_dist=r_dist,
                )
        elif can_enter and short_trigger and stop_dist_short > 0 and p.target_r_multiple >= p.min_rr:
            risk_dollars = equity * p.risk_pct_per_trade / 100.0
            size = risk_dollars / stop_dist_short
            if not p.allow_fractional:
                size = float(np.floor(size))
            if size > 0:
                fill = c[i] - p.slippage_ticks * tick
                equity -= p.commission_per_order
                position_side = -1
                entry_bar = i
                entry_price = fill
                stop_price = stop_short
                r_dist = max(stop_price - entry_price, tick)
                target_price = entry_price - r_dist * p.target_r_multiple
                qty_open = size
                be_done = partial_done = False
                trades_this_block += 1
                current_trade = Trade(
                    side="short", entry_time=idx[i], entry_price=entry_price, qty=size,
                    stop_price=stop_price, target_price=target_price, r_dist=r_dist,
                )

        # ---- 6. mark-to-market equity curve ----
        if position_side != 0:
            unreal = (c[i] - entry_price) * qty_open if position_side == 1 else (entry_price - c[i]) * qty_open
            equity_curve[i] = equity + unreal
        else:
            equity_curve[i] = equity

    # If a position is still open at the end of the data, close it at the last price.
    if position_side != 0 and current_trade is not None:
        fill = c[-1]
        pnl = (fill - entry_price) * qty_open if position_side == 1 else (entry_price - fill) * qty_open
        pnl -= p.commission_per_order
        equity += pnl
        current_trade.exit_time = idx[-1]
        current_trade.exit_price = fill
        current_trade.exit_reason = "end_of_data"
        current_trade.pnl += pnl
        current_trade.r_multiple = current_trade.pnl / (r_dist * current_trade.qty) if r_dist else np.nan
        trades.append(current_trade)
        equity_curve[-1] = equity

    trades_df = pd.DataFrame([t.__dict__ for t in trades])
    equity_series = pd.Series(equity_curve, index=idx, name="equity")
    metrics = compute_metrics(trades_df, equity_series, p.initial_capital)
    return trades_df, equity_series, metrics


def compute_metrics(trades_df: pd.DataFrame, equity: pd.Series, initial_capital: float) -> dict:
    if trades_df.empty:
        return {"n_trades": 0}

    wins = trades_df[trades_df["pnl"] > 0]
    losses = trades_df[trades_df["pnl"] <= 0]
    gross_profit = wins["pnl"].sum()
    gross_loss = losses["pnl"].sum()  # negative
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max * 100.0

    return {
        "n_trades": len(trades_df),
        "win_rate_pct": 100.0 * len(wins) / len(trades_df),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_profit": gross_profit + gross_loss,
        "profit_factor": (gross_profit / abs(gross_loss)) if gross_loss != 0 else np.nan,
        "avg_r_multiple": trades_df["r_multiple"].mean(),
        "expectancy_r": trades_df["r_multiple"].mean(),
        "avg_win": wins["pnl"].mean() if len(wins) else 0.0,
        "avg_loss": losses["pnl"].mean() if len(losses) else 0.0,
        "max_drawdown_pct": drawdown.min(),
        "final_equity": equity.iloc[-1],
        "total_return_pct": (equity.iloc[-1] / initial_capital - 1) * 100.0,
        "breakeven_saves": int(trades_df["breakeven_moved"].sum()),
        "exit_reason_counts": trades_df["exit_reason"].value_counts().to_dict(),
    }
