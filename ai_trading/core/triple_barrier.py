"""Triple Barrier Labeler for financial time series labeling.

This module implements the Triple Barrier method from "Advances in Financial
Machine Learning" by Marcos Lopéz de Prado. It labels events based on which
of three barriers (Take Profit, Stop Loss, Time) is hit first.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Any
from enum import Enum

import numpy as np
import pandas as pd


class BarrierType(Enum):
    """Barrier hit types."""
    TAKE_PROFIT = 1  # TP barrier hit - positive return
    STOP_LOSS = -1   # SL barrier hit - negative return
    TIME_EXPIRY = 0  # Time barrier hit - neutral/sideways


@dataclass
class BarrierConfig:
    """Configuration for Triple Barrier labeling.

    Attributes:
        tp_multiplier: Take profit multiplier of ATR (default: 2.0)
        sl_multiplier: Stop loss multiplier of ATR (default: 1.0)
        time_horizon: Maximum holding period in bars (default: 20)
        volatility_window: Window for ATR calculation (default: 14)
        min_return_threshold: Minimum return to consider (default: 0.001)
    """
    tp_multiplier: float = 2.0
    sl_multiplier: float = 1.0
    time_horizon: int = 20
    volatility_window: int = 14
    min_return_threshold: float = 0.001


@dataclass
class LabelOutput:
    """Output from labeling an event.

    Attributes:
        label: Classification label (-1, 0, 1)
        return_value: Actual return when barrier was hit
        barrier_type: Which barrier was hit first
        hold_bars: Number of bars held
        weight: Sample weight (1.0 for TP/SL, 0.3 for time expiry)
        start_price: Price at event time
        end_price: Price at barrier hit
    """
    label: Literal[-1, 0, 1]
    return_value: float
    barrier_type: BarrierType
    hold_bars: int
    weight: float
    start_price: float
    end_price: float


@dataclass
class TripleBarrierResult:
    """Result of Triple Barrier labeling for a dataset.

    Attributes:
        labels: Series of labels indexed by event start time
        returns: Series of actual returns at barrier hit
        weights: Series of sample weights
        barrier_types: Series of which barrier was hit
        hold_times: Series of holding periods
        events: List of LabelOutput for each event
    """
    labels: "pd.Series"
    returns: "pd.Series"
    weights: "pd.Series"
    barrier_types: "pd.Series"
    hold_times: "pd.Series"
    events: list[LabelOutput]

    def get_label_distribution(self) -> dict[str, int]:
        """Get distribution of labels."""
        dist = self.labels.value_counts().to_dict()
        return {
            "positive": dist.get(1, 0),
            "neutral": dist.get(0, 0),
            "negative": dist.get(-1, 0),
        }

    def get_weighted_accuracy(self) -> float:
        """Calculate weighted accuracy of predictions."""
        positive_mask = self.labels == 1
        negative_mask = self.labels == -1

        if positive_mask.sum() == 0 and negative_mask.sum() == 0:
            return 0.0

        # Correct predictions: positive with positive return, negative with negative
        correct = (
            (positive_mask & (self.returns > 0)).sum() +
            (negative_mask & (self.returns < 0)).sum()
        )
        total = len(self.labels)

        return float(correct / total) if total > 0 else 0.0


class TripleBarrierLabeler:
    """Label events using the Triple Barrier method.

    The Triple Barrier method defines three barriers for each trading event:
    1. Take Profit (TP): Upward bound based on volatility
    2. Stop Loss (SL): Downward bound based on volatility
    3. Time Barrier: Maximum holding period limit

    Each event starts at a specific time (e.g., signal generation) and ends
    when the first barrier is hit. The label is:
    - +1 if TP is hit first (positive return target reached)
    - -1 if SL is hit first (stop loss triggered)
    - 0 if time expires first (sideways/neutral)

    Sample weights are assigned based on barrier type:
    - TP/SL hit: 1.0 (clear directional signal)
    - Time expiry: 0.3 (weak signal/uncertainty)
    """

    def __init__(self, config: Optional[BarrierConfig] = None):
        """Initialize labeler with configuration.

        Args:
            config: Barrier configuration (uses defaults if None)
        """
        self.config = config or BarrierConfig()

    def _calculate_atr(
        self,
        high: "pd.Series",
        low: "pd.Series",
        close: "pd.Series"
    ) -> "pd.Series":
        """Calculate Average True Range (ATR).

        ATR is used to set dynamic barrier distances based on volatility.

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            ATR values
        """
        # True Range components
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR is the rolling mean of True Range
        atr = true_range.rolling(
            window=self.config.volatility_window,
            min_periods=1
        ).mean()

        return atr

    def _calculate_barriers(
        self,
        price: float,
        atr: float,
        regime_multiplier: float = 1.0
    ) -> tuple[float, float]:
        """Calculate TP and SL barriers for a given price.

        Args:
            price: Current price
            atr: Current ATR value
            regime_multiplier: Adjustment based on market regime

        Returns:
            Tuple of (TP level, SL level)
        """
        # Adjust barriers based on regime
        adjusted_tp = self.config.tp_multiplier * regime_multiplier
        adjusted_sl = self.config.sl_multiplier * regime_multiplier

        # Calculate barrier levels
        tp_level = price * (1 + adjusted_tp * atr / price)
        sl_level = price * (1 - adjusted_sl * atr / price)

        return tp_level, sl_level

    def _label_event(
        self,
        start_idx: int,
        start_price: float,
        tp_level: float,
        sl_level: float,
        time_horizon: int,
        future_highs: "pd.Series",
        future_lows: "pd.Series",
        future_closes: "pd.Series"
    ) -> LabelOutput:
        """Label a single event by finding which barrier is hit first.

        Args:
            start_idx: Starting index of the event
            start_price: Price at event start
            tp_level: Take profit target level
            sl_level: Stop loss target level
            time_horizon: Maximum bars to look ahead
            future_highs: Future high prices
            future_lows: Future low prices
            future_closes: Future close prices

        Returns:
            LabelOutput with classification result
        """
        end_idx = min(start_idx + time_horizon, len(future_highs))

        # Scan forward to find first barrier hit
        for i in range(start_idx, end_idx):
            high = future_highs.iloc[i]
            low = future_lows.iloc[i]
            close = future_closes.iloc[i]

            # Check TP hit (price went above TP level)
            if high >= tp_level:
                return_label = 1
                barrier_type = BarrierType.TAKE_PROFIT
                end_price = tp_level
                weight = 1.0
                hold_bars = i - start_idx
                break

            # Check SL hit (price went below SL level)
            elif low <= sl_level:
                return_label = -1
                barrier_type = BarrierType.STOP_LOSS
                end_price = sl_level
                weight = 1.0
                hold_bars = i - start_idx
                break

        else:
            # Time barrier hit (no TP or SL within horizon)
            return_label = 0
            barrier_type = BarrierType.TIME_EXPIRY
            end_price = future_closes.iloc[end_idx - 1]
            weight = 0.3
            hold_bars = time_horizon

        # Calculate actual return
        return_value = (end_price - start_price) / start_price

        return LabelOutput(
            label=return_label,  # type: ignore
            return_value=return_value,
            barrier_type=barrier_type,
            hold_bars=hold_bars,
            weight=weight,
            start_price=start_price,
            end_price=end_price
        )

    def label_events(
        self,
        ohlcv: "pd.DataFrame",
        events: Optional["pd.DatetimeIndex"] = None,
        regime_scores: Optional["pd.Series"] = None
    ) -> TripleBarrierResult:
        """Label events using Triple Barrier method.

        Args:
            ohlcv: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
            events: Index of event times to label (default: all bars)
            regime_scores: Optional regime multipliers indexed by time
                (positive = bullish, reduce barriers / negative = bearish, widen barriers)

        Returns:
            TripleBarrierResult with labels, returns, weights, etc.
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in ohlcv.columns for col in required_cols):
            raise ValueError(f"OHLCV must contain columns: {required_cols}")

        # Calculate ATR
        atr = self._calculate_atr(ohlcv['high'], ohlcv['low'], ohlcv['close'])

        # Default events: every bar with valid data
        if events is None:
            events = ohlcv.index[
                ohlcv.index >= ohlcv.index[self.config.volatility_window]
            ]

        labels: list[int] = []
        returns: list[float] = []
        weights: list[float] = []
        barrier_types: list[BarrierType] = []
        hold_times: list[int] = []
        event_outputs: list[LabelOutput] = []

        # Get future data for lookahead
        future_highs = ohlcv['high']
        future_lows = ohlcv['low']
        future_closes = ohlcv['close']

        for event_time in events:
            if event_time not in ohlcv.index:
                continue

            start_idx = ohlcv.index.get_loc(event_time)

            # Skip if not enough future data
            if start_idx + 1 >= len(ohlcv):
                continue

            start_price = ohlcv['close'].iloc[start_idx]
            current_atr = atr.iloc[start_idx]

            if pd.isna(current_atr) or current_atr == 0:
                continue

            # Get regime multiplier if provided
            regime_mult = 1.0
            if regime_scores is not None and event_time in regime_scores.index:
                regime_val = regime_scores.loc[event_time]
                # Bullish regime: tighter barriers (more aggressive)
                # Bearish regime: wider barriers (more conservative)
                regime_mult = 1.0 - (regime_val * 0.2)  # +/- 20% adjustment
                regime_mult = max(0.5, min(1.5, regime_mult))

            # Calculate barriers
            tp_level, sl_level = self._calculate_barriers(
                start_price, current_atr, regime_mult
            )

            # Label the event
            output = self._label_event(
                start_idx=start_idx + 1,  # Start looking from next bar
                start_price=start_price,
                tp_level=tp_level,
                sl_level=sl_level,
                time_horizon=self.config.time_horizon,
                future_highs=future_highs,
                future_lows=future_lows,
                future_closes=future_closes
            )

            labels.append(output.label)
            returns.append(output.return_value)
            weights.append(output.weight)
            barrier_types.append(output.barrier_type)
            hold_times.append(output.hold_bars)
            event_outputs.append(output)

        # Create result series
        result_index = events[:len(labels)]

        return TripleBarrierResult(
            labels=pd.Series(labels, index=result_index),
            returns=pd.Series(returns, index=result_index),
            weights=pd.Series(weights, index=result_index),
            barrier_types=pd.Series(barrier_types, index=result_index),
            hold_times=pd.Series(hold_times, index=result_index),
            events=event_outputs
        )

    def get_barrier_stats(self, result: TripleBarrierResult) -> dict[str, Any]:
        """Calculate statistics about barrier distribution.

        Args:
            result: TripleBarrierResult from label_events()

        Returns:
            Dictionary of statistics
        """
        if not result.events:
            return {
                "total_events": 0,
                "tp_rate": 0.0,
                "sl_rate": 0.0,
                "time_rate": 0.0,
                "avg_return": 0.0,
                "avg_hold_time": 0.0,
                "avg_weight": 0.0
            }

        total = len(result.events)
        tp_count = sum(1 for e in result.events if e.barrier_type == BarrierType.TAKE_PROFIT)
        sl_count = sum(1 for e in result.events if e.barrier_type == BarrierType.STOP_LOSS)
        time_count = sum(1 for e in result.events if e.barrier_type == BarrierType.TIME_EXPIRY)

        avg_return = np.mean([e.return_value for e in result.events])
        avg_hold = np.mean([e.hold_bars for e in result.events])
        avg_weight = np.mean([e.weight for e in result.events])

        return {
            "total_events": total,
            "tp_rate": tp_count / total,
            "sl_rate": sl_count / total,
            "time_rate": time_count / total,
            "avg_return": float(avg_return),
            "avg_hold_time": float(avg_hold),
            "avg_weight": float(avg_weight),
            "weighted_accuracy": result.get_weighted_accuracy(),
            "label_distribution": result.get_label_distribution()
        }


class RegimeAwareBarrierLabeler(TripleBarrierLabeler):
    """Triple Barrier Labeler with regime-aware barrier adjustment.

    Adjusts barrier levels based on HMM regime classification:
    - Bull regime: Tighter barriers (aggressive profit taking)
    - Bear regime: Wider barriers (conservative stop loss)
    """

    def __init__(
        self,
        config: Optional[BarrierConfig] = None,
        bull_adjustment: float = 0.8,
        bear_adjustment: float = 1.2
    ):
        """Initialize with regime adjustments.

        Args:
            config: Base barrier configuration
            bull_adjustment: Multiplier for bull regime (< 1 = tighter)
            bear_adjustment: Multiplier for bear regime (> 1 = wider)
        """
        super().__init__(config)
        self.bull_adjustment = bull_adjustment
        self.bear_adjustment = bear_adjustment

    def label_with_regime(
        self,
        ohlcv: "pd.DataFrame",
        regimes: "pd.Series",
        events: Optional["pd.DatetimeIndex"] = None
    ) -> TripleBarrierResult:
        """Label events with regime-based barrier adjustment.

        Args:
            ohlcv: OHLCV data
            regimes: Series with regime labels ('bull', 'bear', 'neutral')
            events: Optional event times

        Returns:
            TripleBarrierResult
        """
        # Convert regime labels to multipliers
        regime_map = {
            'bull': self.bull_adjustment,
            'bear': self.bear_adjustment,
            'neutral': 1.0
        }

        regime_scores = regimes.map(
            lambda x: regime_map.get(x, 1.0)
        )

        return self.label_events(ohlcv, events, regime_scores)


def create_labeler(
    tp_multiplier: float = 2.0,
    sl_multiplier: float = 1.0,
    time_horizon: int = 20,
    volatility_window: int = 14,
    regime_aware: bool = False
) -> TripleBarrierLabeler:
    """Factory function to create TripleBarrierLabeler.

    Args:
        tp_multiplier: Take profit ATR multiplier
        sl_multiplier: Stop loss ATR multiplier
        time_horizon: Maximum holding period
        volatility_window: ATR calculation window
        regime_aware: Whether to use RegimeAwareBarrierLabeler

    Returns:
        TripleBarrierLabeler instance
    """
    config = BarrierConfig(
        tp_multiplier=tp_multiplier,
        sl_multiplier=sl_multiplier,
        time_horizon=time_horizon,
        volatility_window=volatility_window
    )

    if regime_aware:
        return RegimeAwareBarrierLabeler(config)
    return TripleBarrierLabeler(config)
