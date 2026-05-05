import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def atr(h, l, c, n=14):
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def adx(h, l, c, n=14):
    up = h.diff()
    down = -l.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr_v = tr.ewm(alpha=1 / n, adjust=False).mean()

    plus_di = 100 * pd.Series(plus_dm, index=c.index).ewm(alpha=1 / n, adjust=False).mean() / (atr_v + 1e-9)
    minus_di = 100 * pd.Series(minus_dm, index=c.index).ewm(alpha=1 / n, adjust=False).mean() / (atr_v + 1e-9)

    dx = 100 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9)
    adx_v = dx.ewm(alpha=1 / n, adjust=False).mean()

    return adx_v, plus_di, minus_di


def macd(c, fast=12, slow=26, signal=9):
    macd_line = ema(c, fast) - ema(c, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def prepare_ohlcv(df):
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
    BBWidth-MACD-Volume Breakout Long Only

    Return:
        1  = long / hold
        0  = no position
        -1 = explicit exit
    """

    if test_df is None or len(test_df) == 0:
        return pd.Series(dtype=int)

    train = prepare_ohlcv(train_df) if train_df is not None and len(train_df) > 0 else pd.DataFrame()
    test = prepare_ohlcv(test_df)

    if len(test) == 0:
        return pd.Series(0, index=test_df.index, dtype=int)

    required = ["open", "high", "low", "close", "volume"]

    if len(train) > 0:
        df_full = pd.concat([train[required], test[required]])
    else:
        df_full = test[required].copy()

    df_full = df_full.sort_index()
    df_full = df_full[~df_full.index.duplicated(keep="last")]

    c = df_full["close"]
    h = df_full["high"]
    l = df_full["low"]
    v = df_full["volume"]

    ema50 = ema(c, 50)
    ema200 = ema(c, 200)

    atr14 = atr(h, l, c, 14)
    adx14, plus_di, minus_di = adx(h, l, c, 14)

    _, _, macd_hist = macd(c)

    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_upper = bb_mid + bb_std * 2
    bb_lower = bb_mid - bb_std * 2

    bb_width = (bb_upper - bb_lower) / (bb_mid.abs() + 1e-9)
    bb_width_ma = bb_width.rolling(20).mean()

    # squeeze_recent leakage 방지
    bb_width_pct = bb_width.rolling(120).rank(pct=True)
    squeeze_recent = bb_width_pct.shift(1).rolling(20).min() <= 0.35

    # 완화된 expansion
    expansion = (
        (bb_width > bb_width_ma) &
        (bb_width > bb_width.shift(1))
    )

    bull_regime = (
        (ema50 > ema200) &
        (ema200 > ema200.shift(10)) &
        (adx14 >= 18) &
        (plus_di > minus_di)
    )

    high_20 = h.rolling(20).max().shift(1)

    breakout = (
        (c > high_20) &
        ((c - high_20) / (atr14 + 1e-9) >= 0.05)
    )

    # MACD 조건 완화
    macd_confirm = macd_hist > 0

    volume_ma = v.rolling(20).mean()
    volume_confirm = v > volume_ma * 1.05

    # 조건 5개 버전
    enter_full = (
        bull_regime &
        expansion &
        breakout &
        macd_confirm &
        volume_confirm
    )

    failed_breakout = c < high_20
    macd_bearish = (macd_hist < 0) & (macd_hist.shift(1) < 0)  # 2봉 연속

    exit_full = (
        failed_breakout |
        (c < ema50) |
        (plus_di < minus_di) |
        macd_bearish
    )

    if len(train) > 0:
        df_ctx = pd.concat([train[required].iloc[-1:], test[required]])
    else:
        df_ctx = test[required].copy()

    df_ctx = df_ctx.sort_index()
    df_ctx = df_ctx[~df_ctx.index.duplicated(keep="last")]

    ctx_idx = df_ctx.index

    c_ctx = df_ctx["close"]
    h_ctx = df_ctx["high"]

    atr_ctx = atr14.reindex(ctx_idx)
    enter = enter_full.reindex(ctx_idx).fillna(False)
    exit_cond = exit_full.reindex(ctx_idx).fillna(False)

    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    in_pos = False
    entry_price = None
    high_since_entry = None
    trail_stop = None
    entry_bar = None

    WARMUP = 400
    first_test_pos = df_ctx.index.get_loc(test.index[0])

    for i in range(len(df_ctx)):
        if i < first_test_pos:
            signal.iloc[i] = 0
            continue

        if i < WARMUP and len(train) == 0:
            signal.iloc[i] = 0
            continue

        price = c_ctx.iloc[i]
        high = h_ctx.iloc[i]
        atr_now = atr_ctx.iloc[i]

        if np.isnan(price) or np.isnan(atr_now):
            signal.iloc[i] = 1 if in_pos else 0
            continue

        if in_pos:
            high_since_entry = max(high_since_entry, high)

            hard_stop = entry_price * 0.965
            raw_trail = high_since_entry - atr_now * 3.8
            trail_stop = raw_trail if trail_stop is None else max(trail_stop, raw_trail)

            can_exit = entry_bar is not None and i > entry_bar

            should_exit = can_exit and (
                price <= hard_stop or
                price <= trail_stop or
                bool(exit_cond.iloc[i])
            )

            if should_exit:
                in_pos = False
                entry_price = None
                high_since_entry = None
                trail_stop = None
                entry_bar = None

                signal.iloc[i] = -1
                continue

        if not in_pos and bool(enter.iloc[i]):
            in_pos = True
            entry_price = price
            high_since_entry = high
            trail_stop = None
            entry_bar = i

            signal.iloc[i] = 1
            continue

        signal.iloc[i] = 1 if in_pos else 0

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)