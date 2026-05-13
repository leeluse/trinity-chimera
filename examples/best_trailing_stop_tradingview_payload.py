# [Title: BEST Trailing Stop Strategy TV Payload]
import numpy as np
import pandas as pd

TV_INITIAL_CAPITAL = 100000
TV_QTY_TYPE = "fixed"
TV_FIXED_QTY = 100
TV_COMMISSION_PCT = 0.075


def _compute_features(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([train_df, test_df], axis=0)
    df = df[~df.index.duplicated(keep="last")].sort_index().copy()

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

    df["fast_sma"] = df["close"].rolling(15, min_periods=15).mean()
    df["slow_sma"] = df["close"].rolling(45, min_periods=45).mean()
    df["enter_long"] = (df["fast_sma"] > df["slow_sma"]) & (
        df["fast_sma"].shift(1) <= df["slow_sma"].shift(1)
    )
    df["enter_short"] = (df["fast_sma"] < df["slow_sma"]) & (
        df["fast_sma"].shift(1) >= df["slow_sma"].shift(1)
    )
    return df


def _build_raw_signal(df: pd.DataFrame) -> pd.Series:
    signal = pd.Series(0, index=df.index, dtype=int)
    signal[df["enter_long"].fillna(False)] = 1
    signal[df["enter_short"].fillna(False)] = -1
    return signal


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    df = _compute_features(train_df.copy(), test_df.copy())
    _ = _build_raw_signal(df)

    stop_trail_perc = 0.03
    stop_trigger_perc = 0.02
    use_stop_trigger = True
    fixed_qty = float(TV_FIXED_QTY)

    signal = pd.Series(0, index=df.index, dtype=int)
    entry_price = pd.Series(np.nan, index=df.index, dtype=float)
    exit_price = pd.Series(np.nan, index=df.index, dtype=float)
    position_size = pd.Series(np.nan, index=df.index, dtype=float)
    trade_direction = pd.Series(np.nan, index=df.index, dtype=float)
    exit_reason = pd.Series("", index=df.index, dtype=object)

    trend = 0
    position = 0
    pending_entry = 0
    anchor_price = np.nan
    long_stop = np.nan
    short_stop = np.nan
    long_trigger_hit = False
    short_trigger_hit = False

    for i in range(len(df)):
        open_i = float(df["open"].iloc[i]) if pd.notna(df["open"].iloc[i]) else np.nan
        high_i = float(df["high"].iloc[i]) if pd.notna(df["high"].iloc[i]) else np.nan
        low_i = float(df["low"].iloc[i]) if pd.notna(df["low"].iloc[i]) else np.nan
        close_i = float(df["close"].iloc[i]) if pd.notna(df["close"].iloc[i]) else np.nan

        if pending_entry != 0 and pd.notna(open_i):
            if position != pending_entry:
                if position != 0:
                    exit_price.iloc[i] = open_i
                    exit_reason.iloc[i] = "reverse"
                entry_price.iloc[i] = open_i
                position_size.iloc[i] = fixed_qty
                position = pending_entry
                trade_direction.iloc[i] = float(position)
            pending_entry = 0

        if position != 0:
            signal.iloc[i] = position
            position_size.iloc[i] = fixed_qty

        prev_long_stop = long_stop
        prev_short_stop = short_stop

        if trend == 1:
            trigger_price = (
                anchor_price * (1.0 + stop_trigger_perc)
                if use_stop_trigger and pd.notna(anchor_price)
                else np.nan
            )
            if use_stop_trigger and pd.notna(trigger_price) and pd.notna(high_i) and high_i >= trigger_price:
                long_trigger_hit = True

            if pd.notna(low_i):
                stop_candidate = low_i * (1.0 - stop_trail_perc)
                long_stop = stop_candidate if pd.isna(long_stop) else max(long_stop, stop_candidate)

            can_exit = (not use_stop_trigger) or long_trigger_hit
            if position == 1 and can_exit and pd.notna(prev_long_stop) and pd.notna(low_i) and low_i <= prev_long_stop:
                signal.iloc[i] = 0
                exit_price.iloc[i] = prev_long_stop
                position_size.iloc[i] = fixed_qty
                trade_direction.iloc[i] = 1.0
                exit_reason.iloc[i] = "trail_stop"
                position = 0

        elif trend == -1:
            trigger_price = (
                anchor_price * (1.0 - stop_trigger_perc)
                if use_stop_trigger and pd.notna(anchor_price)
                else np.nan
            )
            if use_stop_trigger and pd.notna(trigger_price) and pd.notna(low_i) and low_i <= trigger_price:
                short_trigger_hit = True

            if pd.notna(high_i):
                stop_candidate = high_i * (1.0 + stop_trail_perc)
                short_stop = stop_candidate if pd.isna(short_stop) else min(short_stop, stop_candidate)

            can_exit = (not use_stop_trigger) or short_trigger_hit
            if position == -1 and can_exit and pd.notna(prev_short_stop) and pd.notna(high_i) and high_i >= prev_short_stop:
                signal.iloc[i] = 0
                exit_price.iloc[i] = prev_short_stop
                position_size.iloc[i] = fixed_qty
                trade_direction.iloc[i] = -1.0
                exit_reason.iloc[i] = "trail_stop"
                position = 0

        enter_long = bool(df["enter_long"].iloc[i])
        enter_short = bool(df["enter_short"].iloc[i])

        if enter_long and pd.notna(close_i):
            trend = 1
            pending_entry = 1
            anchor_price = close_i
            long_stop = np.nan
            short_stop = np.nan
            long_trigger_hit = False
            short_trigger_hit = False
        elif enter_short and pd.notna(close_i):
            trend = -1
            pending_entry = -1
            anchor_price = close_i
            long_stop = np.nan
            short_stop = np.nan
            long_trigger_hit = False
            short_trigger_hit = False

    signal = signal.reindex(test_df.index).fillna(0).astype(int)
    return {
        "signal": signal,
        "entry_price": entry_price.reindex(test_df.index),
        "exit_price": exit_price.reindex(test_df.index),
        "position_size": position_size.reindex(test_df.index),
        "trade_direction": trade_direction.reindex(test_df.index),
        "exit_reason": exit_reason.reindex(test_df.index).fillna(""),
        "meta": {
            "tradingview": {
                "initial_capital": float(TV_INITIAL_CAPITAL),
                "qty_type": str(TV_QTY_TYPE),
                "fixed_qty": float(TV_FIXED_QTY),
                "commission_pct": float(TV_COMMISSION_PCT),
            }
        },
    }
