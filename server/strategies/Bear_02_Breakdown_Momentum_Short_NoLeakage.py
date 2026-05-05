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
    Bear Strategy 02
    Breakdown Momentum Short

    Return:
        -1 = short / hold
         0 = no position
         1 = explicit short exit
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

    rsi14_full = rsi(c_full, 14)
    atr14_full = atr(h_full, l_full, c_full, 14)
    adx14_full, plus_di_full, minus_di_full = adx(h_full, l_full, c_full, 14)

    ll20_full = l_full.rolling(20).min().shift(1)
    ll40_full = l_full.rolling(40).min().shift(1)

    roc10_full = (c_full - c_full.shift(10)) / (c_full.shift(10) + 1e-9) * 100
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
    l = df_ctx["low"]
    v = df_ctx["volume"]

    ema20 = ema20_full.reindex(idx)
    ema50 = ema50_full.reindex(idx)
    ema200 = ema200_full.reindex(idx)

    rsi14 = rsi14_full.reindex(idx)
    atr14 = atr14_full.reindex(idx)
    adx14 = adx14_full.reindex(idx)
    plus_di = plus_di_full.reindex(idx)
    minus_di = minus_di_full.reindex(idx)

    ll20 = ll20_full.reindex(idx)
    ll40 = ll40_full.reindex(idx)
    roc10 = roc10_full.reindex(idx)
    vol_ma20 = vol_ma20_full.reindex(idx)

    # =========================
    # 3. Bear regime
    # =========================
    bear_regime = (
        (ema50 < ema200) &
        (ema200 < ema200.shift(10)) &
        (adx14 >= 16) &
        (minus_di > plus_di)
    )

    downtrend_stack = (
        (ema20 < ema50) &
        (ema50 < ema200)
    )

    # =========================
    # 4. Breakdown entry
    # =========================
    breakdown_20 = (
        (c < ll20) &
        ((ll20 - c) / (atr14 + 1e-9) >= 0.15)
    )

    breakdown_40 = (
        (c < ll40) &
        ((ll40 - c) / (atr14 + 1e-9) >= 0.10)   # 20봉 0.15와 정합성 확보
    )

    rsi_momentum = (
        (rsi14 < 48) &
        (rsi14 > 24) &
        (rsi14 < rsi14.shift(3))
    )

    roc_down = (
        (roc10 < 0) &
        (roc10 < roc10.shift(3))
    )

    volume_ok = (
        v >= vol_ma20 * 0.80
    )

    enter = (
        bear_regime.shift(1).fillna(False) &        # 전봉 regime 확인으로 Lookahead 제거
        downtrend_stack.shift(1).fillna(False) &    # 전봉 EMA 스택 확인
        (breakdown_20 | breakdown_40) &
        rsi_momentum &
        roc_down &
        volume_ok
    )

    # =========================
    # 5. Exit conditions
    # =========================
    breakdown_reclaim = (
        (c > ll20 + atr14 * 0.25) &
        (c > c.shift(1))   # 반등 중인지 확인 (2봉 연속 상승)
    )

    momentum_failure = (
        (rsi14 > 52) |
        (roc10 > 0)
    )

    ema20_reclaim = (
        c > ema20 + atr14 * 0.20
    )

    di_failure = (
        (plus_di > minus_di) &
        (adx14 > 18)
    )

    profit_take_zone = (
        rsi14 < 28
    )

    exit_cond = (
        breakdown_reclaim |
        momentum_failure |
        ema20_reclaim |
        di_failure |
        profit_take_zone
    )

    # =========================
    # 6. Position simulation
    # =========================
    signal = pd.Series(0, index=df_ctx.index, dtype=int)

    in_pos = False
    entry_price = None
    low_since_entry = None
    trail_stop = None
    entry_bar = None
    last_exit_bar = None

    WARMUP = 400
    COOLDOWN = 3

    first_test_pos = df_ctx.index.get_loc(test.index[0])

    for i in range(len(df_ctx)):
        if i < first_test_pos:
            signal.iloc[i] = 0
            continue

        if i < WARMUP and len(train) == 0:
            signal.iloc[i] = 0
            continue

        price = c.iloc[i]
        low = l.iloc[i]
        atr_now = atr14.iloc[i]

        if np.isnan(price) or np.isnan(atr_now):
            signal.iloc[i] = -1 if in_pos else 0
            continue

        # ===== Manage short position =====
        if in_pos:
            low_since_entry = min(low_since_entry, low)

            # Breakdown은 Bear 01보다 약간 넓게,
            # 단 급반등 대응을 위해 max 6.5% 제한
            stop_dist = np.clip(
                atr_now * 2.4,
                entry_price * 0.020,
                entry_price * 0.065
            )

            raw_trail = low_since_entry + stop_dist
            trail_stop = raw_trail if trail_stop is None else min(trail_stop, raw_trail)

            hard_stop = entry_price * 1.030
            stop_price = max(hard_stop, trail_stop)  # 숏: 더 높은 값이 더 타이트한 손절

            can_exit = entry_bar is not None and i > entry_bar

            should_exit = can_exit and (
                price >= stop_price or
                bool(exit_cond.iloc[i])
            )

            if should_exit:
                in_pos = False
                entry_price = None
                low_since_entry = None
                trail_stop = None
                entry_bar = None
                last_exit_bar = i

                signal.iloc[i] = 1
                continue

        # ===== Entry =====
        cooldown_ok = (
            last_exit_bar is None or
            (i - last_exit_bar) > COOLDOWN
        )

        if not in_pos and cooldown_ok and bool(enter.iloc[i]):
            in_pos = True
            entry_price = price
            low_since_entry = low
            trail_stop = None
            entry_bar = i

            signal.iloc[i] = -1
            continue

        signal.iloc[i] = -1 if in_pos else 0

    return signal.loc[test.index].reindex(test_df.index).fillna(0).astype(int)