import numpy as np
import pandas as pd


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """
    Quant Trend Engine Long Only v3 — BTC/USD 4H
    멀티팩터 추세 점수 기반 롱 온리 전략.
    train_df 기반 파라미터 적응은 없고 고정 파라미터 사용.
    """
    df = test_df.copy()

    # ── 파라미터 ──────────────────────────────────────────
    fast_len       = 18
    mid_len        = 50
    slow_len       = 120
    smooth_len     = 3
    pullback_len   = 8
    breakout_len   = 20
    eff_len        = 18
    persist_len    = 7
    mom_len        = 12
    slope_len      = 10
    atr_len        = 14
    atr_base_len   = 40

    min_score          = 5.0
    exit_score_thresh  = 2.5
    min_sep_perc       = 0.30
    min_slow_slope     = 0.03
    min_eff            = 0.33
    min_atr_regime     = 0.95
    min_breakout_atr   = 0.15
    pullback_atr_mult  = 0.90
    reclaim_atr_mult   = 0.15
    cooldown_bars      = 5
    hard_stop_perc     = 2.0
    trail_atr_mult     = 2.8
    profit_lock_mult   = 20.8

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # ── Double EMA (EMA의 EMA) ─────────────────────────────
    def dema(series, period, smooth):
        return series.ewm(span=period, adjust=False).mean().ewm(span=smooth, adjust=False).mean()

    fast = dema(close, fast_len, smooth_len)
    mid  = dema(close, mid_len,  smooth_len)
    slow = dema(close, slow_len, smooth_len)

    # ── ATR ───────────────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr      = tr.ewm(span=atr_len, adjust=False).mean()
    atr_base = atr.rolling(atr_base_len).mean()

    # ── Bull stack ────────────────────────────────────────
    bull_stack = (fast > mid) & (mid > slow)

    # ── EMA 분리도 ────────────────────────────────────────
    sep_perc = (fast - slow).abs() / slow.replace(0, np.nan) * 100
    sep_ok   = sep_perc >= min_sep_perc

    # ── 기울기 ───────────────────────────────────────────
    fast_slope = (fast - fast.shift(slope_len)) / fast.shift(slope_len).replace(0, np.nan) * 100
    mid_slope  = (mid  - mid.shift(slope_len))  / mid.shift(slope_len).replace(0, np.nan)  * 100
    slow_slope = (slow - slow.shift(slope_len)) / slow.shift(slope_len).replace(0, np.nan) * 100
    slope_ok   = (slow_slope >= min_slow_slope) & (mid_slope > 0) & (fast_slope > 0)

    # ── Path efficiency ───────────────────────────────────
    net_move  = (close - close.shift(eff_len)).abs()
    step_move = sum((close - close.shift(1)).abs().shift(i) for i in range(eff_len))
    efficiency = (net_move / step_move.replace(0, np.nan)).fillna(0)
    eff_ok     = efficiency >= min_eff

    # ── 모멘텀 지속성 ─────────────────────────────────────
    persist_ratio = sum(
        (close > close.shift(1)).shift(i).fillna(False).astype(float)
        for i in range(persist_len)
    ) / persist_len
    mom_raw = (close - close.shift(mom_len)) / close.shift(mom_len).replace(0, np.nan) * 100
    mom_ok  = (mom_raw > 0) & (persist_ratio >= 0.57)

    # ── 변동성 레짐 ───────────────────────────────────────
    atr_regime = atr / atr_base.replace(0, np.nan)
    atr_ok     = atr_regime >= min_atr_regime

    # ── 브레이크아웃 ─────────────────────────────────────
    hh               = high.rolling(breakout_len).max().shift(1)
    breakout_str     = (close - hh) / atr.replace(0, np.nan)
    breakout_ok      = (close > hh) & (breakout_str >= min_breakout_atr)

    # ── 풀백 / 리클레임 ──────────────────────────────────
    pb_low           = low.rolling(pullback_len).min()
    dist_fast_atr    = (fast - pb_low) / atr.replace(0, np.nan)
    deep_pb          = dist_fast_atr >= pullback_atr_mult

    reclaim_fast     = (close > fast) & (close.shift(1) <= fast.shift(1))
    reclaim_mid      = (close > mid)  & (close.shift(1) <= mid.shift(1))
    reclaim_str      = (close - fast) / atr.replace(0, np.nan)
    reclaim_ok       = (reclaim_fast | reclaim_mid) & (reclaim_str >= reclaim_atr_mult)

    # ── 트렌드 점수 ──────────────────────────────────────
    score = (
        bull_stack.astype(float) * 1.50 +
        sep_ok.astype(float)     * 0.90 +
        slope_ok.astype(float)   * 1.10 +
        eff_ok.astype(float)     * 1.00 +
        atr_ok.astype(float)     * 0.80 +
        mom_ok.astype(float)     * 1.00 +
        breakout_ok.astype(float)* 1.25 +
        reclaim_ok.astype(float) * 1.10
    )

    # ── 진입 모델 ────────────────────────────────────────
    bull_cross = (
        ((fast > mid)  & (fast.shift(1) <= mid.shift(1)))  |
        ((fast > slow) & (fast.shift(1) <= slow.shift(1))) |
        ((mid  > slow) & (mid.shift(1)  <= slow.shift(1)))
    )
    bars_since = pd.Series(np.inf, index=df.index)
    cnt = np.inf
    for i in range(len(df)):
        cnt = 0 if bull_cross.iloc[i] else (cnt + 1 if not np.isinf(cnt) else np.inf)
        bars_since.iloc[i] = cnt
    recent_birth = bars_since <= 14

    trend_cont  = bull_stack & breakout_ok & slope_ok & eff_ok & mom_ok
    pb_reentry  = bull_stack & sep_ok & slope_ok & deep_pb & reclaim_ok & eff_ok
    early_trend = recent_birth & bull_stack & sep_ok & slope_ok & atr_ok & mom_ok

    enter = (score >= min_score) & (close > slow) & (trend_cont | pb_reentry | early_trend)

    # ── 청산 조건 ────────────────────────────────────────
    bear_cross = (
        ((fast < mid)  & (fast.shift(1) >= mid.shift(1)))  |
        ((fast < slow) & (fast.shift(1) >= slow.shift(1)))
    )
    struct_break  = (close < mid) & (fast < mid)
    score_weak    = score <= exit_score_thresh
    mom_fail      = (persist_ratio < 0.40) & (mom_raw < 0)
    regime_fail   = (atr_regime < 0.80) & (efficiency < 0.25)
    exit_cond     = bear_cross | struct_break | score_weak | mom_fail | regime_fail

    # ── 상태 기계 (롱 온리) ───────────────────────────────
    sig            = pd.Series(0, index=df.index, dtype=int)
    in_pos         = False
    entry_price    = 0.0
    trail_stop_val = None
    high_since     = None
    last_exit      = None
    entry_bar      = None

    atr_arr  = atr.values
    close_arr= close.values
    high_arr = high.values

    for i in range(len(df)):
        c  = close_arr[i]
        h  = high_arr[i]
        av = atr_arr[i] if not np.isnan(atr_arr[i]) else 0.0

        cooldown_ok = last_exit is None or (i - last_exit) > cooldown_bars

        if not in_pos:
            if enter.iloc[i] and cooldown_ok:
                sig.iloc[i]    = 1
                in_pos         = True
                entry_price    = c
                trail_stop_val = None
                high_since     = h
                entry_bar      = i
        else:
            high_since     = max(high_since, h)
            raw_trail      = c - av * trail_atr_mult
            profit_lock    = high_since - av * profit_lock_mult
            combined_trail = max(raw_trail, profit_lock)
            trail_stop_val = combined_trail if trail_stop_val is None else max(trail_stop_val, combined_trail)

            hard_stop  = entry_price * (1 - hard_stop_perc / 100)
            stop_price = max(hard_stop, trail_stop_val)
            can_exit   = entry_bar is not None and i > entry_bar

            if can_exit and (c <= stop_price or exit_cond.iloc[i]):
                sig.iloc[i]    = 0
                in_pos         = False
                last_exit      = i
                trail_stop_val = None
                high_since     = None
            else:
                sig.iloc[i]    = 1

    return sig.fillna(0).astype(int)
