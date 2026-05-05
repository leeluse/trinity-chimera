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


def rsi(c, n=14):
    delta = c.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def adx(h, l, c, n=14):
    up = h.diff()
    down = -l.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = pd.concat(
        [
            h - l,
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_v = tr.ewm(alpha=1 / n, adjust=False).mean()

    plus_di = (
        100
        * pd.Series(plus_dm, index=c.index)
        .ewm(alpha=1 / n, adjust=False)
        .mean()
        / (atr_v + 1e-9)
    )

    minus_di = (
        100
        * pd.Series(minus_dm, index=c.index)
        .ewm(alpha=1 / n, adjust=False)
        .mean()
        / (atr_v + 1e-9)
    )

    dx = 100 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9)
    adx_v = dx.ewm(alpha=1 / n, adjust=False).mean()

    return adx_v, plus_di, minus_di


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
    Range Strategy 01
    RSI Mean Reversion Long/Short

    Return:
        1  = long
       -1 = short
        0  = flat
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
    # Indicator full context
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

    ema50_full = ema(c_full, 50)
    ema200_full = ema(c_full, 200)

    rsi14_full = rsi(c_full, 14)
    atr14_full = atr(h_full, l_full, c_full, 14)
    adx14_full, plus_di_full, minus_di_full = adx(h_full, l_full, c_full, 14)

    # =========================
    # Shift context
    # =========================
    if len(train) > 0:
        df_ctx = pd.concat([train[required].iloc[-1:], test[required]])
    else:
        df_ctx = test[required].copy()

    df_ctx = df_ctx.sort_index()
    df_ctx = df_ctx[~df_ctx.index.duplicated(keep="last")]

    idx = df_ctx.index

    c = df_ctx["close"]

    ema50 = ema50_full.reindex(idx)
    ema200 = ema200_full.reindex(idx)

    rsi14 = rsi14_full.reindex(idx)
    atr14 = atr14_full.reindex(idx)
    adx14 = adx14_full.reindex(idx)

    # =========================
    # Range regime filter
    # =========================
    low_trend = (
        (adx14 < 22) &                                           # 완화: BTC 고변동성 환경 적합
        (abs(ema50 - ema200) / (ema200.abs() + 1e-9) < 0.05)    # 5%로 완화 + 분모 abs로 방어
    )

    # =========================
    # Entry
    # =========================
    long_entry = (
        low_trend &
        (rsi14 < 30) &
        (rsi14 > rsi14.shift(1)) &
        (rsi14 > rsi14.shift(2))   # 2봉 연속 반등 확인 — 노이즈 진입 방지
    )

    short_entry = (
        low_trend &
        (rsi14 > 70) &
        (rsi14 < rsi14.shift(1)) &
        (rsi14 < rsi14.shift(2))   # 2봉 연속 하락 확인 — 노이즈 진입 방지
    )

    # =========================
    # Exit
    # =========================
    long_exit = (
        (rsi14 > 55) |
        (c < ema50 - atr14 * 0.3)
    )

    short_exit = (
        (rsi14 < 45) |
        (c > ema50 + atr14 * 0.3)
    )

    # =========================
    # Simulation
    # =========================
    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    pos = 0  # 1 long, -1 short
    entry_bar = None

    WARMUP = 400
    first_test_pos = df_ctx.index.get_loc(test.index[0])

    for i in range(len(df_ctx)):
        if i < first_test_pos:
            continue

        if i < WARMUP and len(train) == 0:
            continue

        if pos == 1:
            if entry_bar is not None and i > entry_bar and bool(long_exit.iloc[i]):
                pos = 0
                signal.iloc[i] = 0
                continue

        elif pos == -1:
            if entry_bar is not None and i > entry_bar and bool(short_exit.iloc[i]):
                pos = 0
                signal.iloc[i] = 0
                continue

        if pos == 0:
            if bool(long_entry.iloc[i]):
                pos = 1
                entry_bar = i
                signal.iloc[i] = 1
                continue

            elif bool(short_entry.iloc[i]):
                pos = -1
                entry_bar = i
                signal.iloc[i] = -1
                continue

        signal.iloc[i] = pos

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)