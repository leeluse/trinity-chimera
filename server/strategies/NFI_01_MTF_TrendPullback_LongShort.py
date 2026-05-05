"""
NFI-inspired trend pullback strategy for Trinity native backtest engine.
"""

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1 / length, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(span=length, adjust=False).mean()


def prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(col).lower() for col in out.columns]
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]

    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in out.columns:
            raise ValueError(f"Missing required column: {col}")
        out[col] = pd.to_numeric(out[col], errors="coerce")

    return out.dropna(subset=required)


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    if test_df is None or len(test_df) == 0:
        return pd.Series(dtype=int)

    train = prepare_ohlcv(train_df) if train_df is not None and len(train_df) > 0 else pd.DataFrame()
    test = prepare_ohlcv(test_df)

    if len(test) == 0:
        return pd.Series(0, index=test_df.index, dtype=int)

    required = ["open", "high", "low", "close", "volume"]
    if len(train) > 0:
        full = pd.concat([train[required], test[required]])
    else:
        full = test[required].copy()

    full = full.sort_index()
    full = full[~full.index.duplicated(keep="last")]

    close_full = full["close"]
    high_full = full["high"]
    low_full = full["low"]
    volume_full = full["volume"]

    EMA_FAST = 20
    EMA_MID = 50
    EMA_SLOW = 200
    RSI_LEN = 14
    ATR_LEN = 14
    ROC_LEN = 6
    VOL_LEN = 20

    PULLBACK_ATR = 0.45
    MOMENTUM_MIN = 0.0005
    RSI_LONG_MIN = 46
    RSI_LONG_MAX = 74
    RSI_SHORT_MIN = 26
    RSI_SHORT_MAX = 56
    VOL_MULT = 0.75

    SL_ATR = 1.30
    TP_ATR = 2.40
    TRAIL_ATR = 1.80
    EXIT_ATR = 0.65
    MAX_HOLD_BARS = 120
    COOLDOWN_BARS = 2
    WARMUP = 240
    CTX_TAIL = 400

    ema_fast_full = ema(close_full, EMA_FAST)
    ema_mid_full = ema(close_full, EMA_MID)
    ema_slow_full = ema(close_full, EMA_SLOW)
    rsi_full = rsi(close_full, RSI_LEN)
    atr_full = atr(high_full, low_full, close_full, ATR_LEN)
    roc_full = close_full.pct_change(ROC_LEN)
    vol_ma_full = volume_full.rolling(VOL_LEN).mean()

    if len(train) > 0:
        ctx = pd.concat([train[required].tail(CTX_TAIL), test[required]])
    else:
        ctx = test[required].copy()

    ctx = ctx.sort_index()
    ctx = ctx[~ctx.index.duplicated(keep="last")]

    idx = ctx.index
    close = ctx["close"]
    high = ctx["high"]
    low = ctx["low"]
    volume = ctx["volume"]

    ema_fast = ema_fast_full.reindex(idx)
    ema_mid = ema_mid_full.reindex(idx)
    ema_slow = ema_slow_full.reindex(idx)
    rsi_now = rsi_full.reindex(idx)
    atr_now = atr_full.reindex(idx)
    roc = roc_full.reindex(idx)
    vol_ma = vol_ma_full.reindex(idx)

    trend_up = (ema_mid > ema_slow) & (ema_fast > ema_mid)
    trend_down = (ema_mid < ema_slow) & (ema_fast < ema_mid)

    long_pullback = (close < ema_fast) & (close > ema_mid - atr_now * PULLBACK_ATR)
    short_pullback = (close > ema_fast) & (close < ema_mid + atr_now * PULLBACK_ATR)

    long_break = close > high.shift(1)
    short_break = close < low.shift(1)

    long_rsi_ok = (rsi_now > RSI_LONG_MIN) & (rsi_now < RSI_LONG_MAX) & (rsi_now > rsi_now.shift(1))
    short_rsi_ok = (rsi_now > RSI_SHORT_MIN) & (rsi_now < RSI_SHORT_MAX) & (rsi_now < rsi_now.shift(1))

    volume_ok = volume > vol_ma * VOL_MULT

    enter_long = (
        trend_up.shift(1).fillna(False)
        & long_pullback.shift(1).fillna(False)
        & long_break
        & (roc > MOMENTUM_MIN)
        & long_rsi_ok
        & volume_ok
    ).fillna(False)

    enter_short = (
        trend_down.shift(1).fillna(False)
        & short_pullback.shift(1).fillna(False)
        & short_break
        & (roc < -MOMENTUM_MIN)
        & short_rsi_ok
        & volume_ok
    ).fillna(False)

    signal = pd.Series(0, index=idx, dtype=int)

    position = 0
    stop = 0.0
    target = 0.0
    hold_bars = 0
    cooldown = 0

    first_test_pos = idx.get_loc(test.index[0])

    for i in range(len(idx)):
        if i < first_test_pos:
            signal.iloc[i] = 0
            continue

        if i < WARMUP and len(train) == 0:
            signal.iloc[i] = 0
            continue

        if cooldown > 0:
            cooldown -= 1

        px = float(close.iloc[i]) if not np.isnan(close.iloc[i]) else np.nan
        hi = float(high.iloc[i]) if not np.isnan(high.iloc[i]) else np.nan
        lo = float(low.iloc[i]) if not np.isnan(low.iloc[i]) else np.nan
        atr_v = float(atr_now.iloc[i]) if not np.isnan(atr_now.iloc[i]) else np.nan

        if np.isnan(px) or np.isnan(atr_v) or atr_v <= 0:
            signal.iloc[i] = position
            continue

        if position == 1:
            hold_bars += 1
            stop = max(stop, px - atr_v * TRAIL_ATR)

            rsi_value = float(rsi_now.iloc[i]) if not np.isnan(rsi_now.iloc[i]) else 50.0
            exit_long = (
                lo <= stop
                or hi >= target
                or rsi_value > 80
                or px < float(ema_mid.iloc[i] - atr_v * EXIT_ATR)
                or hold_bars >= MAX_HOLD_BARS
            )
            if exit_long:
                position = 0
                hold_bars = 0
                cooldown = COOLDOWN_BARS
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = 1
            continue

        if position == -1:
            hold_bars += 1
            stop = min(stop, px + atr_v * TRAIL_ATR)

            rsi_value = float(rsi_now.iloc[i]) if not np.isnan(rsi_now.iloc[i]) else 50.0
            exit_short = (
                hi >= stop
                or lo <= target
                or rsi_value < 20
                or px > float(ema_mid.iloc[i] + atr_v * EXIT_ATR)
                or hold_bars >= MAX_HOLD_BARS
            )
            if exit_short:
                position = 0
                hold_bars = 0
                cooldown = COOLDOWN_BARS
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = -1
            continue

        if cooldown == 0:
            if bool(enter_long.iloc[i]):
                position = 1
                hold_bars = 0
                stop = px - atr_v * SL_ATR
                target = px + atr_v * TP_ATR
                signal.iloc[i] = 1
                continue

            if bool(enter_short.iloc[i]):
                position = -1
                hold_bars = 0
                stop = px + atr_v * SL_ATR
                target = px - atr_v * TP_ATR
                signal.iloc[i] = -1
                continue

        signal.iloc[i] = 0

    out = signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)
    return out.clip(-1, 1)
