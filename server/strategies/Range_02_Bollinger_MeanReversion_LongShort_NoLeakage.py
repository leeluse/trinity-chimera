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
    Range Strategy 02
    Bollinger Band Mean Reversion Long/Short

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

    bb_mid_full = c_full.rolling(20).mean()
    bb_std_full = c_full.rolling(20).std()
    bb_upper_full = bb_mid_full + bb_std_full * 2
    bb_lower_full = bb_mid_full - bb_std_full * 2
    bb_width_full = (bb_upper_full - bb_lower_full) / (bb_mid_full.abs() + 1e-9)
    bb_width_pct_full = bb_width_full.rolling(120).rank(pct=True)

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

    bb_mid = bb_mid_full.reindex(idx)
    bb_upper = bb_upper_full.reindex(idx)
    bb_lower = bb_lower_full.reindex(idx)
    bb_width_pct = bb_width_pct_full.reindex(idx)

    # =========================
    # Range regime filter
    # =========================
    low_trend = (
        (adx14 < 22) &                                          # Range_01과 통일: ADX 기준 22
        (abs(ema50 - ema200) / (ema200.abs() + 1e-9) < 0.05)   # Range_01과 통일: EMA 간격 5%
    )

    band_not_too_wide = (
        bb_width_pct < 0.75
    )

    range_regime = low_trend & band_not_too_wide

    # =========================
    # Entry
    # =========================
    lower_band_reclaim = (
        (c.shift(1) < bb_lower.shift(1)) &
        (c > bb_lower) &
        (rsi14 < 38)   # 과매도 확인 엄격화 (42 → 38)
    )

    upper_band_reclaim = (
        (c.shift(1) > bb_upper.shift(1)) &
        (c < bb_upper) &
        (rsi14 > 62)   # 과매수 확인 엄격화 + 대칭 (58 → 62)
    )

    long_entry = range_regime & lower_band_reclaim
    short_entry = range_regime & upper_band_reclaim

    # =========================
    # Exit
    # =========================
    long_exit = (
        (c >= bb_mid + atr14 * 0.10) |   # 중심선 약간 위에서 청산 — 슬리피지 보수
        (rsi14 > 55) |
        (c < bb_lower - atr14 * 0.50)
    )

    short_exit = (
        (c <= bb_mid - atr14 * 0.10) |   # 중심선 약간 아래에서 청산 (long과 대칭)
        (rsi14 < 45) |
        (c > bb_upper + atr14 * 0.50)
    )

    # =========================
    # Simulation
    # =========================
    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    pos = 0
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

            if bool(short_entry.iloc[i]):
                pos = -1
                entry_bar = i
                signal.iloc[i] = -1
                continue

        signal.iloc[i] = pos

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)