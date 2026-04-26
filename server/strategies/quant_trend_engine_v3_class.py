"""
Quant Trend Engine Long Only v3 - BTC/USD, 4H
Pine Script → Python 마이그레이션 (클래스 버전)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class StrategyState:
    def __init__(self):
        self.last_exit_bar = None
        self.trail_stop = None
        self.high_since_entry = None
        self.entry_bar_index = None
        self.position_size = 0.0
        self.position_avg_price = 0.0

    def reset(self):
        self.__init__()


class QuantTrendEngine:
    """
    Quant Trend Engine Long Only v3

    주요 특징:
    - Triple EMA (Fast/Mid/Slow) 기반 트렌드 추종
    - 가중 점수 시스템 (8개 요소)
    - 3가지 진입 모델 (추세 지속, 풀백 재진입, 초기 추세)
    - ATR 기반 트레일링 스탑 + 하드 스탑
    - 쿨다운 기간 적용
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = {
            'fast_len': 18,
            'mid_len': 50,
            'slow_len': 120,
            'smooth_len': 3,
            'pullback_len': 8,
            'breakout_len': 20,
            'eff_len': 18,
            'persist_len': 7,
            'mom_len': 12,
            'slope_len': 10,
            'atr_len': 14,
            'atr_base_len': 40,
            'min_score': 5.0,
            'exit_score_thresh': 2.5,
            'min_sep_perc': 0.30,
            'min_slow_slope_perc': 0.03,
            'min_eff': 0.33,
            'min_atr_regime': 0.95,
            'min_breakout_atr': 0.15,
            'pullback_atr_mult': 0.90,
            'reclaim_atr_mult': 0.15,
            'cooldown_bars': 5,
            'hard_stop_perc': 2.0,
            'trail_atr_mult': 2.8,
            'profit_lock_atr_mult': 20.8,
        }
        if params:
            self.params.update(params)
        self.state = StrategyState()

    def _dema(self, series: pd.Series, length: int, smooth: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean().ewm(span=smooth, adjust=False).mean()

    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(span=length, adjust=False).mean()

    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        close = df['close']
        high  = df['high']
        low   = df['low']
        p     = self.params

        fast = self._dema(close, p['fast_len'], p['smooth_len'])
        mid  = self._dema(close, p['mid_len'],  p['smooth_len'])
        slow = self._dema(close, p['slow_len'], p['smooth_len'])

        atr      = self._atr(high, low, close, p['atr_len'])
        atr_base = atr.rolling(p['atr_base_len']).mean()

        bull_stack = (fast > mid) & (mid > slow)

        sep_perc = (fast - slow).abs() / slow.replace(0, np.nan) * 100
        sep_ok   = sep_perc >= p['min_sep_perc']

        fast_slope = (fast - fast.shift(p['slope_len'])) / fast.shift(p['slope_len']).replace(0, np.nan) * 100
        mid_slope  = (mid  - mid.shift(p['slope_len']))  / mid.shift(p['slope_len']).replace(0, np.nan)  * 100
        slow_slope = (slow - slow.shift(p['slope_len'])) / slow.shift(p['slope_len']).replace(0, np.nan) * 100
        slope_ok   = (slow_slope >= p['min_slow_slope_perc']) & (mid_slope > 0) & (fast_slope > 0)

        net_move   = (close - close.shift(p['eff_len'])).abs()
        step_move  = sum((close - close.shift(1)).abs().shift(i) for i in range(p['eff_len']))
        efficiency = (net_move / step_move.replace(0, np.nan)).fillna(0)
        eff_ok     = efficiency >= p['min_eff']

        persist_ratio = sum(
            (close > close.shift(1)).shift(i).fillna(False).astype(float)
            for i in range(p['persist_len'])
        ) / p['persist_len']
        mom_raw = (close - close.shift(p['mom_len'])) / close.shift(p['mom_len']).replace(0, np.nan) * 100
        mom_ok  = (mom_raw > 0) & (persist_ratio >= 0.57)

        atr_regime = atr / atr_base.replace(0, np.nan)
        atr_ok     = atr_regime >= p['min_atr_regime']

        hh           = high.rolling(p['breakout_len']).max().shift(1)
        breakout_str = (close - hh) / atr.replace(0, np.nan)
        breakout_ok  = (close > hh) & (breakout_str >= p['min_breakout_atr'])

        pb_low         = low.rolling(p['pullback_len']).min()
        dist_fast_atr  = (fast - pb_low) / atr.replace(0, np.nan)
        deep_pb        = dist_fast_atr >= p['pullback_atr_mult']
        reclaim_fast   = (close > fast) & (close.shift(1) <= fast.shift(1))
        reclaim_mid    = (close > mid)  & (close.shift(1) <= mid.shift(1))
        reclaim_str    = (close - fast) / atr.replace(0, np.nan)
        reclaim_ok     = (reclaim_fast | reclaim_mid) & (reclaim_str >= p['reclaim_atr_mult'])

        score = (
            bull_stack.astype(float)  * 1.50 +
            sep_ok.astype(float)      * 0.90 +
            slope_ok.astype(float)    * 1.10 +
            eff_ok.astype(float)      * 1.00 +
            atr_ok.astype(float)      * 0.80 +
            mom_ok.astype(float)      * 1.00 +
            breakout_ok.astype(float) * 1.25 +
            reclaim_ok.astype(float)  * 1.10
        )

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
        enter       = (score >= p['min_score']) & (close > slow) & (trend_cont | pb_reentry | early_trend)

        bear_cross    = (
            ((fast < mid)  & (fast.shift(1) >= mid.shift(1))) |
            ((fast < slow) & (fast.shift(1) >= slow.shift(1)))
        )
        struct_break = (close < mid) & (fast < mid)
        score_weak   = score <= p['exit_score_thresh']
        mom_fail     = (persist_ratio < 0.40) & (mom_raw < 0)
        regime_fail  = (atr_regime < 0.80) & (efficiency < 0.25)
        exit_cond    = bear_cross | struct_break | score_weak | mom_fail | regime_fail

        return {
            'close': close, 'high': high, 'low': low,
            'fast': fast, 'mid': mid, 'slow': slow,
            'atr': atr, 'enter': enter, 'exit_cond': exit_cond,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        p    = self.params
        ind  = self.calculate_indicators(df)
        sig  = pd.Series(0, index=df.index, dtype=int)
        self.state.reset()

        close_arr = ind['close'].values
        high_arr  = ind['high'].values
        low_arr   = ind['low'].values
        atr_arr   = ind['atr'].values
        enter_arr = ind['enter'].values
        exit_arr  = ind['exit_cond'].values

        s = self.state

        for i in range(len(df)):
            c  = close_arr[i]
            h  = high_arr[i]
            av = atr_arr[i] if not np.isnan(atr_arr[i]) else 0.0

            cooldown_ok = s.last_exit_bar is None or (i - s.last_exit_bar) > p['cooldown_bars']

            # ── 포지션 보유 중 처리 ──────────────────────────
            if s.position_size > 0:
                s.high_since_entry = max(s.high_since_entry, h)

                raw_trail      = c - av * p['trail_atr_mult']
                profit_lock    = s.high_since_entry - av * p['profit_lock_atr_mult']
                combined_trail = max(raw_trail, profit_lock)
                s.trail_stop   = combined_trail if s.trail_stop is None else max(s.trail_stop, combined_trail)

                hard_stop  = s.position_avg_price * (1 - p['hard_stop_perc'] / 100)
                stop_price = max(hard_stop, s.trail_stop)
                can_exit   = s.entry_bar_index is not None and i > s.entry_bar_index

                if can_exit and (c <= stop_price or exit_arr[i]):
                    s.last_exit_bar    = i
                    s.position_size    = 0.0
                    s.position_avg_price = 0.0
                    s.trail_stop       = None
                    s.high_since_entry = None
                    s.entry_bar_index  = None

            # ── 진입 체크 ────────────────────────────────────
            if s.position_size == 0 and cooldown_ok and enter_arr[i]:
                s.position_size      = 1.0
                s.position_avg_price = c
                s.entry_bar_index    = i
                s.trail_stop         = None
                s.high_since_entry   = h

            # ── 봉 끝 신호: 포지션 보유 중이면 1, 아니면 0 ──
            sig.iloc[i] = 1 if s.position_size > 0 else 0

        return sig


def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    return QuantTrendEngine().generate_signals(test_df)
