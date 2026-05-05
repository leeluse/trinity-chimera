import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def atr(h, l, c, n=14):
    pc = c.shift(1)
    tr = pd.concat(
        [h - l, (h - pc).abs(), (l - pc).abs()],
        axis=1
    ).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def macd(c, fast=12, slow=26, signal=9):
    macd_line = ema(c, fast) - ema(c, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def obv(c, v):
    direction = np.sign(c.diff()).fillna(0)
    return (direction * v).cumsum()


def prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    required = ["open", "high", "low", "close", "volume"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=required)


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """
    Bull Strategy 02
    BBWidth-MACD-OBV Breakout Long Only

    Return:
        1  = long / hold
        0  = no position
        -1 = explicit exit
    """

    if test_df is None or len(test_df) == 0:
        return pd.Series(dtype=int)

    train = (
        prepare_ohlcv(train_df)
        if train_df is not None and len(train_df) > 0
        else pd.DataFrame()
    )
    test = prepare_ohlcv(test_df)

    if len(test) == 0:
        return pd.Series(0, index=test_df.index, dtype=int)

    required = ["open", "high", "low", "close", "volume"]

    # =========================
    # 1. Indicator full context
    # =========================
    if len(train) > 0:
        df_full = pd.concat([train[required], test[required]])
    else:
        df_full = test[required].copy()

    df_full = df_full.sort_index()
    df_full = df_full[~df_full.index.duplicated(keep="last")]

    c_full = df_full["close"]
    h_full = df_full["high"]
    l_full = df_full["low"]
    v_full = df_full["volume"]

    ema20_full = ema(c_full, 20)
    ema50_full = ema(c_full, 50)
    ema200_full = ema(c_full, 200)

    atr14_full = atr(h_full, l_full, c_full, 14)

    macd_line_full, macd_signal_full, macd_hist_full = macd(c_full)

    obv_full = obv(c_full, v_full)
    obv_ema_full = ema(obv_full, 20)

    bb_mid_full = c_full.rolling(20).mean()
    bb_std_full = c_full.rolling(20).std()

    bb_upper_full = bb_mid_full + bb_std_full * 2
    bb_lower_full = bb_mid_full - bb_std_full * 2

    bb_width_full = (
        (bb_upper_full - bb_lower_full)
        / (bb_mid_full.abs() + 1e-9)
    )

    # 현재 봉 기준 과거 120봉 내 percentile
    bb_width_pct_full = bb_width_full.rolling(120).rank(pct=True)

    hh20_full = h_full.rolling(20).max().shift(1)
    vol_ma20_full = v_full.rolling(20).mean()

    # =========================
    # 2. Shift context
    # =========================
    if len(train) > 0:
        df_ctx = pd.concat([train[required].iloc[-1:], test[required]])
    else:
        df_ctx = test[required].copy()

    df_ctx = df_ctx.sort_index()
    df_ctx = df_ctx[~df_ctx.index.duplicated(keep="last")]

    idx = df_ctx.index

    c = df_ctx["close"]
    h = df_ctx["high"]
    v = df_ctx["volume"]

    ema20 = ema20_full.reindex(idx)
    ema50 = ema50_full.reindex(idx)
    ema200 = ema200_full.reindex(idx)

    atr14 = atr14_full.reindex(idx)

    macd_line = macd_line_full.reindex(idx)
    macd_signal = macd_signal_full.reindex(idx)
    macd_hist = macd_hist_full.reindex(idx)

    obv_val = obv_full.reindex(idx)
    obv_ema = obv_ema_full.reindex(idx)

    bb_width = bb_width_full.reindex(idx)
    bb_width_pct = bb_width_pct_full.reindex(idx)

    hh20 = hh20_full.reindex(idx)
    vol_ma20 = vol_ma20_full.reindex(idx)

    # =========================
    # 3. Bull regime
    # =========================
    bull_regime = (
        (ema50 > ema200) &
        (ema200 > ema200.shift(10))
    )

    # =========================
    # 4. Squeeze + expansion
    # =========================
    squeeze_recent = (
        bb_width_pct.shift(1).rolling(20).min() <= 0.35
    )

    expansion = (
        (bb_width > bb_width.shift(1)) &
        (bb_width > bb_width.rolling(20).mean())
    )

    # =========================
    # 5. Breakout trigger
    # =========================
    breakout = (
        (c > hh20) &
        ((c - hh20) / (atr14 + 1e-9) >= 0.15)
    )

    # =========================
    # 6. Confirmation score
    # =========================
    macd_confirm = (
        (macd_line > macd_signal) &
        (macd_hist > 0)
    )

    obv_confirm = (
        (obv_val > obv_ema) &
        (obv_val > obv_val.shift(3))
    )

    volume_confirm = (
        v > vol_ma20 * 1.20
    )

    confirm_score = (
        macd_confirm.astype(int) +
        obv_confirm.astype(int) +
        volume_confirm.astype(int)
    )

    enter = (
        bull_regime &
        squeeze_recent &
        expansion &
        breakout &
        (confirm_score >= 2)
    )

    # =========================
    # 7. Exit conditions
    # =========================
    failed_breakout = (
        (c < hh20 - atr14 * 0.50) &
        (c.shift(1) < hh20.shift(1) - atr14.shift(1) * 0.50)
    )

    trend_failure = (
        (c < ema50) |
        ((macd_hist < 0) & (macd_line < macd_signal))
    )

    exit_cond = failed_breakout | trend_failure

    # =========================
    # 8. Simulation
    # =========================
    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    in_pos = False
    entry_price = None
    high_since_entry = None
    trail_stop = None
    entry_bar = None
    last_exit_bar = None

    WARMUP = 400
    COOLDOWN = 5

    first_test_pos = df_ctx.index.get_loc(test.index[0])

    for i in range(len(df_ctx)):
        if i < first_test_pos:
            signal.iloc[i] = 0
            continue

        if i < WARMUP and len(train) == 0:
            signal.iloc[i] = 0
            continue

        price = c.iloc[i]
        high = h.iloc[i]
        atr_now = atr14.iloc[i]

        if np.isnan(price) or np.isnan(atr_now):
            signal.iloc[i] = 1 if in_pos else 0
            continue

        # ===== Manage position =====
        if in_pos:
            high_since_entry = max(high_since_entry, high)

            # ATR stop clipping
            stop_dist = np.clip(
                atr_now * 3.0,
                entry_price * 0.025,
                entry_price * 0.070
            )

            raw_trail = high_since_entry - stop_dist
            trail_stop = raw_trail if trail_stop is None else max(trail_stop, raw_trail)

            hard_stop = entry_price * 0.965
            stop_price = max(hard_stop, trail_stop)

            can_exit = entry_bar is not None and i > entry_bar

            should_exit = can_exit and (
                price <= stop_price or
                bool(exit_cond.iloc[i])
            )

            if should_exit:
                in_pos = False
                entry_price = None
                high_since_entry = None
                trail_stop = None
                entry_bar = None
                last_exit_bar = i

                signal.iloc[i] = -1
                continue

        # ===== Entry =====
        cooldown_ok = (
            last_exit_bar is None or
            (i - last_exit_bar) > COOLDOWN
        )

        if not in_pos and cooldown_ok and bool(enter.iloc[i]):
            in_pos = True
            entry_price = price
            high_since_entry = high
            trail_stop = None
            entry_bar = i

            signal.iloc[i] = 1
            continue

        signal.iloc[i] = 1 if in_pos else 0

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)