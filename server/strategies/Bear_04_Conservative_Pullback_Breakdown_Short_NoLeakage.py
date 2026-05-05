import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.where(d > 0, 0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.where(d < 0, 0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / (dn + 1e-9)
    return 100 - (100 / (1 + rs))


def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()


def prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
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
        full = pd.concat([train[required], test[required]]).sort_index()
    else:
        full = test[required].copy()
    full = full[~full.index.duplicated(keep="last")]

    c_full = full["close"]
    h_full = full["high"]
    l_full = full["low"]
    v_full = full["volume"]

    # Conservative parameter set found from quick segmented OOS search
    EMA_FAST = 12
    EMA_SLOW = 30
    EMA_TREND = 180
    RSI_LEN = 10
    ATR_LEN = 14
    VOL_LEN = 20
    SLOPE_LB = 8

    PULLBACK_ATR = 0.20
    SLOPE_MIN = 0.0006
    RSI_MIN = 50
    RSI_MAX = 72
    VOL_MULT = 0.70

    SL_ATR = 1.30
    TP_ATR = 2.20
    TRAIL_ATR = 2.20
    TAKE_RSI = 24
    EXIT_ATR = 0.60
    COOLDOWN = 1
    MAX_HOLD_BARS = 72
    WARMUP = 240
    CTX_TAIL = 320

    ema_fast_full = ema(c_full, EMA_FAST)
    ema_slow_full = ema(c_full, EMA_SLOW)
    ema_trend_full = ema(c_full, EMA_TREND)
    rsi_full = rsi(c_full, RSI_LEN)
    atr_full = atr(h_full, l_full, c_full, ATR_LEN)
    vol_ma_full = v_full.rolling(VOL_LEN).mean()

    if len(train) > 0:
        ctx = pd.concat([train[required].tail(CTX_TAIL), test[required]]).sort_index()
        ctx = ctx[~ctx.index.duplicated(keep="last")]
    else:
        ctx = test[required].copy()

    idx = ctx.index
    c = ctx["close"]
    h = ctx["high"]
    l = ctx["low"]
    v = ctx["volume"]

    ema_fast = ema_fast_full.reindex(idx)
    ema_slow = ema_slow_full.reindex(idx)
    ema_trend = ema_trend_full.reindex(idx)
    r = rsi_full.reindex(idx)
    a = atr_full.reindex(idx)
    vol_ma = vol_ma_full.reindex(idx)

    downtrend = (ema_fast < ema_slow) & (ema_slow < ema_trend)
    trend_slope = (ema_trend - ema_trend.shift(SLOPE_LB)) / (ema_trend.shift(SLOPE_LB) + 1e-9)
    pullback_zone = (c > ema_fast) & (c < ema_slow + a * PULLBACK_ATR)
    breakdown = c < l.shift(1)
    rsi_ok = (r > RSI_MIN) & (r < RSI_MAX)
    vol_ok = v > vol_ma * VOL_MULT

    enter = (
        downtrend.shift(1).fillna(False)
        & (trend_slope.shift(1) < -SLOPE_MIN)
        & pullback_zone.shift(1).fillna(False)
        & breakdown
        & rsi_ok
        & vol_ok
    )

    signal = pd.Series(0, index=idx, dtype=int)
    in_pos = False
    stop = 0.0
    tp = 0.0
    cooldown = 0
    hold_bars = 0

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

        price = float(c.iloc[i]) if not np.isnan(c.iloc[i]) else np.nan
        lo = float(l.iloc[i]) if not np.isnan(l.iloc[i]) else np.nan
        hi = float(h.iloc[i]) if not np.isnan(h.iloc[i]) else np.nan
        atr_now = float(a.iloc[i]) if not np.isnan(a.iloc[i]) else np.nan

        if np.isnan(price) or np.isnan(atr_now) or atr_now <= 0:
            signal.iloc[i] = -1 if in_pos else 0
            continue

        if in_pos:
            hold_bars += 1
            stop = min(stop, price + atr_now * TRAIL_ATR)

            exit_now = (
                hi >= stop
                or lo <= tp
                or r.iloc[i] < TAKE_RSI
                or price > float(ema_slow.iloc[i] + atr_now * EXIT_ATR)
                or hold_bars >= MAX_HOLD_BARS
            )
            if exit_now:
                in_pos = False
                cooldown = COOLDOWN
                hold_bars = 0
                signal.iloc[i] = 0
            else:
                signal.iloc[i] = -1
        else:
            if cooldown == 0 and bool(enter.iloc[i]):
                in_pos = True
                hold_bars = 0
                stop = price + atr_now * SL_ATR
                tp = price - atr_now * TP_ATR
                signal.iloc[i] = -1
            else:
                signal.iloc[i] = 0

    out = signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)
    return out.clip(-1, 1)

