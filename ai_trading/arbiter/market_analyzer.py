"""Market Analyzer for real-time market analysis and agent correlation tracking.

This module provides comprehensive market state analysis integrating with
HMM regime classification, volatility tracking, and agent correlation monitoring.
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from ai_trading.core.hmm_regime import HMMRegimeClassifier, create_regime_classifier

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    """Comprehensive market analysis result.

    Attributes:
        timestamp: Analysis timestamp
        regime: Detected market regime (bull/sideways/bear)
        regime_confidence: Confidence in regime prediction
        volatility: Current market volatility (annualized)
        volatility_regime: Volatility regime (low/normal/high)
        correlations: Agent correlation matrix
        risk_signals: Detected risk signals
        trend_strength: Trend strength indicator
        forecast: Volatility forecast
    """
    timestamp: datetime
    regime: str
    regime_confidence: float
    volatility: float
    volatility_regime: str
    correlations: pd.DataFrame
    risk_signals: List[str]
    trend_strength: float
    volatility_forecast: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime,
            "regime_confidence": round(self.regime_confidence, 3),
            "volatility": round(self.volatility, 4),
            "volatility_regime": self.volatility_regime,
            "correlations": self.correlations.to_dict() if hasattr(self.correlations, 'to_dict') else {},
            "risk_signals": self.risk_signals,
            "trend_strength": round(self.trend_strength, 3),
            "volatility_forecast": round(self.volatility_forecast, 4),
        }


class VolatilityCalculator:
    """Realized volatility calculator with regime detection."""

    def __init__(
        self,
        short_window: int = 5,
        medium_window: int = 20,
        long_window: int = 60,
        annualization_factor: int = 365,
    ):
        """Initialize calculator.

        Args:
            short_window: Short-term volatility window
            medium_window: Medium-term volatility window
            long_window: Long-term volatility window
            annualization_factor: Days per year for annualization
        """
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window
        self.annualization_factor = annualization_factor

    def calculate(
        self,
        prices: pd.Series,
        returns: Optional[pd.Series] = None,
    ) -> Dict[str, float]:
        """Calculate volatility metrics.

        Args:
            prices: Price series
            returns: Pre-calculated returns (optional)

        Returns:
            Dictionary of volatility metrics
        """
        if returns is None:
            returns = np.log(prices / prices.shift(1))

        vols = {}

        # Realized volatilities
        vols["short"] = returns.rolling(self.short_window).std().iloc[-1] * np.sqrt(self.annualization_factor)
        vols["medium"] = returns.rolling(self.medium_window).std().iloc[-1] * np.sqrt(self.annualization_factor)
        vols["long"] = returns.rolling(self.long_window).std().iloc[-1] * np.sqrt(self.annualization_factor)

        # Volatility of volatility
        vol_returns = returns.rolling(self.medium_window).std()
        vols["vol_of_vol"] = vol_returns.std() if len(vol_returns) > 1 else 0.0

        # Volatility regime (based on medium-term)
        current_vol = vols["medium"]
        vol_percentile = returns.rolling(self.long_window).std().rank(pct=True).iloc[-1]

        if vol_percentile < 0.33:
            vols["regime"] = "low"
        elif vol_percentile > 0.67:
            vols["regime"] = "high"
        else:
            vols["regime"] = "normal"

        vols["percentile"] = vol_percentile
        vols["current"] = current_vol

        return vols

    def forecast_volatility(
        self,
        prices: pd.Series,
        forecast_horizon: int = 7,
    ) -> float:
        """Forecast volatility using EWMA-like mean reversion.

        Args:
            prices: Price series
            forecast_horizon: Days to forecast ahead

        Returns:
            Forecasted volatility
        """
        returns = np.log(prices / prices.shift(1))

        vols = self.calculate(prices, returns)
        current = vols["current"]

        # Mean reversion forecast
        long_term = vols["long"]
        reversion_rate = 0.1

        forecast = current + (long_term - current) * reversion_rate * forecast_horizon
        return max(0.0, forecast)


class CorrelationTracker:
    """Track agent position correlations over time."""

    def __init__(self, lookback_window: int = 20):
        """Initialize tracker.

        Args:
            lookback_window: Window for correlation calculation
        """
        self.lookback_window = lookback_window
        self.position_history: Dict[str, List[float]] = {}
        self.names: List[str] = []

    def update(
        self,
        agent_positions: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ):
        """Update with new position data.

        Args:
            agent_positions: Agent name to position mapping
            timestamp: Optional timestamp
        """
        for name, position in agent_positions.items():
            if name not in self.position_history:
                self.position_history[name] = []
            self.position_history[name].append(position)

            # Maintain fixed window
            if len(self.position_history[name]) > self.lookback_window * 2:
                self.position_history[name] = self.position_history[name][-self.lookback_window:]

        self.names = sorted(self.position_history.keys())

    def get_correlation_matrix(self) -> pd.DataFrame:
        """Calculate correlation matrix.

        Returns:
            DataFrame with agent correlations
        """
        if len(self.names) < 2:
            return pd.DataFrame()

        # Build position matrix
        min_len = min(len(self.position_history.get(n, [])) for n in self.names)
        if min_len < 5:
            return pd.DataFrame()

        data = {}
        for name in self.names:
            data[name] = self.position_history[name][-min_len:]

        df = pd.DataFrame(data)
        return df.corr()

    def get_diversification_score(self) -> float:
        """Calculate portfolio diversification score.

        Returns:
            Diversification score (0-1, higher is better)
        """
        corr_matrix = self.get_correlation_matrix()
        if corr_matrix.empty or len(corr_matrix) < 2:
            return 0.5  # Default

        # Average absolute correlation (excluding diagonal)
        abs_corr = corr_matrix.abs()
        np.fill_diagonal(abs_corr.values, 0)
        avg_corr = abs_corr.values.mean()

        # Convert to diversification score
        diversification = 1 - avg_corr
        return float(np.clip(diversification, 0, 1))

    def get_agent_pairwise_correlations(
        self,
        agent_name: str,
    ) -> Dict[str, float]:
        """Get correlations of one agent with all others.

        Args:
            agent_name: Agent to analyze

        Returns:
            Dictionary of correlations
        """
        corr_matrix = self.get_correlation_matrix()
        if corr_matrix.empty or agent_name not in corr_matrix:
            return {}

        return corr_matrix[agent_name].to_dict()


class MarketAnalyzer:
    """Comprehensive market analyzer.

    Integrates HMM regime classification, volatility analysis, and
    agent correlation tracking for complete market picture.

    Example:
        >>> analyzer = MarketAnalyzer()
        >>> analysis = analyzer.analyze(
        ...     ohlcv=data,
        ...     agent_positions={"momentum": 0.8, "reverter": -0.5}
        ... )
        >>> print(f"Current regime: {analysis.regime}")
    """

    def __init__(
        self,
        volatility_window: int = 20,
        correlation_lookback: int = 20,
    ):
        """Initialize analyzer.

        Args:
            volatility_window: Window for volatility calculation
            correlation_lookback: Lookback for agent correlations
        """
        self.volatility_calc = VolatilityCalculator(
            medium_window=volatility_window
        )
        self.corr_tracker = CorrelationTracker(
            lookback_window=correlation_lookback
        )
        self.regime_classifier: Optional[HMMRegimeClassifier] = None
        self.history: List[MarketAnalysis] = []

    def _init_classifier(self) -> HMMRegimeClassifier:
        """Initialize regime classifier.

        Returns:
            Initialized classifier
        """
        self.regime_classifier = create_regime_classifier()
        return self.regime_classifier

    def analyze(
        self,
        ohlcv: pd.DataFrame,
        agent_positions: Optional[Dict[str, float]] = None,
        force_retrain: bool = False,
    ) -> MarketAnalysis:
        """Run comprehensive market analysis.

        Args:
            ohlcv: OHLCV DataFrame with required columns
            agent_positions: Current agent positions (optional)
            force_retrain: Force retraining of HMM

        Returns:
            MarketAnalysis with all metrics
        """
        # Calculate log returns
        returns = np.log(ohlcv['close'] / ohlcv['close'].shift(1))

        # Volatility analysis
        vols = self.volatility_calc.calculate(ohlcv['close'], returns)

        # Regime classification
        if self.regime_classifier is None:
            self._init_classifier()

        try:
            self.regime_classifier.fit(ohlcv, refit=force_retrain)
            regime_pred = self.regime_classifier.predict_latest(ohlcv)
            regime = regime_pred.regime
            regime_conf = regime_pred.probability
        except Exception as e:
            logger.warning(f"Regime classification failed: {e}")
            regime = "sideways"
            regime_conf = 0.5

        # Trend strength
        trend_strength = self._calculate_trend_strength(ohlcv, returns)

        # Volatility forecast
        vol_forecast = self.volatility_calc.forecast_volatility(ohlcv['close'])

        # Agent correlations
        if agent_positions:
            self.corr_tracker.update(agent_positions)
        correlations = self.corr_tracker.get_correlation_matrix()

        # Risk signals
        risk_signals = self._detect_risk_signals(ohlcv, vols, trend_strength)

        analysis = MarketAnalysis(
            timestamp=datetime.now(),
            regime=regime,
            regime_confidence=regime_conf,
            volatility=vols["current"],
            volatility_regime=vols["regime"],
            correlations=correlations,
            risk_signals=risk_signals,
            trend_strength=trend_strength,
            volatility_forecast=vol_forecast,
        )

        # Store in history
        self.history.append(analysis)
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return analysis

    def _calculate_trend_strength(
        self,
        ohlcv: pd.DataFrame,
        returns: pd.Series,
        window: int = 20,
    ) -> float:
        """Calculate trend strength using return autocorrelation.

        Args:
            ohlcv: Price data
            returns: Log returns series
            window: Calculation window

        Returns:
            Trend strength (-1 to 1)
        """
        if len(returns) < window * 2:
            return 0.0

        recent_returns = returns.tail(window).dropna()
        if len(recent_returns) < 5:
            return 0.0

        # Linear trend slope
        x = np.arange(len(recent_returns))
        y = recent_returns.values

        slope = np.polyfit(x, y, 1)[0] if len(x) > 1 else 0

        # Normalize by volatility
        vol = recent_returns.std() + 1e-8
        trend_strength = np.clip(slope / vol, -1, 1)

        # Moving average alignment
        ma_short = ohlcv['close'].rolling(window // 2).mean().iloc[-1]
        ma_long = ohlcv['close'].rolling(window).mean().iloc[-1]

        ma_alignment = 1 if ma_short > ma_long else -1

        return float(np.clip(trend_strength * 0.5 + ma_alignment * 0.5, -1, 1))

    def _detect_risk_signals(
        self,
        ohlcv: pd.DataFrame,
        vols: Dict[str, float],
        trend_strength: float,
    ) -> List[str]:
        """Detect potential risk signals.

        Args:
            ohlcv: Price data
            vols: Volatility metrics
            trend_strength: Current trend strength

        Returns:
            List of risk signal descriptions
        """
        signals = []

        # Volatility spike
        if vols["regime"] == "high":
            signals.append(f"High volatility: {vols['current']:.1%}")

        # Trend exhaustion
        if abs(trend_strength) > 0.7:
            prices = ohlcv['close']
            returns = np.log(prices / prices.shift(1))
            direction = np.sign(trend_strength)
            recent_returns = returns.tail(20).dropna()
            consecutive = 0
            for r in recent_returns:
                if np.sign(r) == direction:
                    consecutive += 1
                else:
                    consecutive = 0

            if consecutive > 7:
                signals.append(f"Trend exhaustion: {consecutive} consecutive {direction}")

        # Volatility of volatility
        if vols.get("vol_of_vol", 0) > 0.5:
            signals.append("Rapid volatility changes")

        # Price gap
        gaps = (ohlcv['open'] / ohlcv['close'].shift(1) - 1).abs()
        recent_gap = gaps.iloc[-1]
        if recent_gap > 0.02:
            signals.append(f"Large gap: {recent_gap:.1%}")

        return signals

    def get_regime_stats(self) -> Dict[str, Any]:
        """Get statistics on regime transitions.

        Returns:
            Dictionary with regime statistics
        """
        if not self.history:
            return {"regime_counts": {}, "regime_changes": 0}

        regimes = [h.regime for h in self.history]
        regime_counts = {}
        for r in regimes:
            regime_counts[r] = regime_counts.get(r, 0) + 1

        transitions = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i-1])

        return {
            "regime_counts": regime_counts,
            "regime_changes": transitions,
            "current_regime": regimes[-1] if regimes else None,
            "regime_duration": self._calculate_regime_duration(regimes),
        }

    def _calculate_regime_duration(
        self,
        regimes: List[str],
    ) -> Dict[str, int]:
        """Calculate average duration per regime.

        Args:
            regimes: List of sequential regimes

        Returns:
            Average durations
        """
        if not regimes:
            return {}

        durations: Dict[str, List[int]] = {}
        current = regimes[0]
        count = 1

        for r in regimes[1:]:
            if r == current:
                count += 1
            else:
                if current not in durations:
                    durations[current] = []
                durations[current].append(count)
                current = r
                count = 1

        if current not in durations:
            durations[current] = []
        durations[current].append(count)

        return {r: sum(d) // len(d) for r, d in durations.items()}

    def get_diversification_metrics(self) -> Dict[str, Any]:
        """Get current diversification status.

        Returns:
            Diversification metrics
        """
        div_score = self.corr_tracker.get_diversification_score()
        corr_matrix = self.corr_tracker.get_correlation_matrix()

        pair_corrs = {}
        if not corr_matrix.empty:
            names = list(corr_matrix.columns)
            for i, name1 in enumerate(names):
                for name2 in names[i+1:]:
                    pair_corrs[f"{name1}-{name2}"] = corr_matrix.loc[name1, name2]

        sorted_pairs = sorted(pair_corrs.items(), key=lambda x: abs(x[1]), reverse=True)
        highest_corr = sorted_pairs[:3] if sorted_pairs else []

        return {
            "diversification_score": div_score,
            "average_correlation": 1 - div_score,
            "highest_correlations": [
                {"pair": p[0], "correlation": round(p[1], 3)}
                for p in highest_corr
            ],
        }


def create_market_analyzer(
    volatility_window: int = 20,
    correlation_lookback: int = 20,
) -> MarketAnalyzer:
    """Factory function to create MarketAnalyzer.

    Args:
        volatility_window: Window for volatility calc
        correlation_lookback: Lookback for correlations

    Returns:
        Configured MarketAnalyzer
    """
    return MarketAnalyzer(
        volatility_window=volatility_window,
        correlation_lookback=correlation_lookback,
    )
