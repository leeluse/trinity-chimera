"""Mean Reverter Agent - Counter-trend agent.

Persona: "Buy when everyone panics. Sell at tops."
Algorithm: SAC + ATR-based dynamic barriers
"""

from typing import Any
import numpy as np

from ai_trading.agents.base_agent import BaseAgent, AgentConfig


class MeanReverter(BaseAgent):
    """Contrarian agent specialized for sideways and bear markets.

    Persona:
        - Buy when everyone panic sells
        - Sell at local tops
        - Both long and short positions

    Entry Conditions:
        - Oversold (RSI < 30)
        - Below Bollinger Band lower
        - Volume spike

    Exit Conditions:
        - RSI > 60 (mean reversion complete)
        - Stop loss hit

    Unique Features:
        - BB deviation
        - RSI divergence
        - Funding rate extremes

    Reward:
        - Sortino (penalizes only downside volatility)
    """

    PERSONA = "Contrarian. Buy panic, sell greed."
    ALGORITHM = "SAC"

    # Entry thresholds
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    BB_DEVIATION_THRESHOLD = 1.5  # Standard deviations

    def __init__(self, config: AgentConfig):
        """Initialize Mean Reverter.

        Args:
            config: Agent configuration
        """
        super().__init__(config)
        self.params = {
            "rsi_oversold": self.RSI_OVERSOLD,
            "rsi_overbought": self.RSI_OVERBOUGHT,
            "bb_threshold": self.BB_DEVIATION_THRESHOLD,
            "target_rsi": 50,  # Mean reversion target
            "atr_multiplier_sl": 2.0,  # ATR-based stop loss
        }

    def build_observation(
        self,
        market_obs: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> np.ndarray:
        """Build mean-reversion specific observation.

        Features:
            - ML signal (p_long, p_short, confidence)
            - Regime encoding
            - RSI, BB deviation, volume spike
            - Funding rate extremes
            - Portfolio state

        Args:
            market_obs: Market data dictionary
            portfolio_state: Current position and PnL

        Returns:
            Observation vector
        """
        # ML signal
        p_long = market_obs.get("p_long", 0.0)
        p_short = market_obs.get("p_short", 0.0)
        confidence = market_obs.get("confidence", 0.0)

        # Regime
        regime = market_obs.get("regime", "sideways")
        regime_enc = self._encode_regime(regime)

        # Mean reversion features
        rsi = market_obs.get("rsi", 50.0)
        bb_deviation = market_obs.get("bb_deviation", 0.0)  # Normalized deviation
        rsi_div = market_obs.get("rsi_divergence", 0.0)  # Price vs RSI divergence

        # Volume signal
        volume_spike = market_obs.get("volume_spike", 1.0)  # Volume / avg
        volume_zscore = market_obs.get("volume_zscore", 0.0)

        # Funding rate (extreme values signal reversal)
        funding_rate = market_obs.get("funding_rate", 0.0)
        funding_zscore = market_obs.get("funding_zscore", 0.0)

        # Technical
        atr = market_obs.get("atr", 0.0)
        price_vs_sma = market_obs.get("price_vs_sma", 0.0)  # Distance from SMA

        # Portfolio state
        current_position = portfolio_state.get("position", 0.0)
        unrealized_pnl = portfolio_state.get("unrealized_pnl", 0.0)
        entry_rsi = portfolio_state.get("entry_rsi", 50.0)

        obs = np.array([
            p_long,
            p_short,
            confidence,
            regime_enc,
            rsi / 100.0,  # Normalize
            bb_deviation,
            rsi_div,
            volume_spike,
            volume_zscore,
            funding_rate,
            funding_zscore,
            atr,
            price_vs_sma,
            current_position,
            unrealized_pnl,
            entry_rsi / 100.0,
        ], dtype=np.float32)

        return obs

    def _encode_regime(self, regime: str) -> float:
        """Encode regime to numeric value.

        Args:
            regime: "bull", "sideways", or "bear"

        Returns:
            Encoded value: sideways=1.0 (best for mean reversion)
        """
        mapping = {"bull": 0.0, "sideways": 1.0, "bear": 0.5}
        return mapping.get(regime, 1.0)

    def compute_reward(
        self,
        action: float,
        prev_state: dict[str, Any],
        curr_state: dict[str, Any],
    ) -> float:
        """Compute Sortino ratio based reward.

        Sortino only penalizes downside volatility.

        Args:
            action: Position taken (-1.0 to 1.0)
            prev_state: Previous state
            curr_state: Current state

        Returns:
            Sortino-style reward
        """
        pnl = curr_state.get("unrealized_pnl", 0.0) - prev_state.get("unrealized_pnl", 0.0)

        # Sortino: only penalize downside
        if pnl < 0:
            # Negative return - penalize
            reward = pnl * 2.0  # Extra penalty for losses
        else:
            # Positive return - full credit
            reward = pnl

        # Bonus for mean reversion completion
        rsi = curr_state.get("rsi", 50.0)
        entry_rsi = prev_state.get("entry_rsi", rsi)

        # Long from oversold, exiting near middle
        if action > 0 and entry_rsi < self.params["rsi_oversold"]:
            if rsi > self.params["target_rsi"]:
                reward += 0.001  # Bonus for successful mean reversion

        # Short from overbought, exiting near middle
        if action < 0 and entry_rsi > self.params["rsi_overbought"]:
            if rsi < self.params["target_rsi"]:
                reward += 0.001

        return float(reward)

    def can_enter_long(self, market_obs: dict[str, Any]) -> bool:
        """Check if long entry conditions met.

        Conditions:
            - RSI < 30 (oversold)
            - Price below BB lower band
            - Volume spike (panic selling)

        Args:
            market_obs: Market observation

        Returns:
            True if can enter long
        """
        rsi = market_obs.get("rsi", 50.0)
        bb_dev = market_obs.get("bb_deviation", 0.0)
        volume_spike = market_obs.get("volume_spike", 1.0)

        return (
            rsi < self.params["rsi_oversold"]
            and bb_dev < -self.params["bb_threshold"]
            and volume_spike > 1.5
        )

    def can_enter_short(self, market_obs: dict[str, Any]) -> bool:
        """Check if short entry conditions met.

        Conditions:
            - RSI > 70 (overbought)
            - Price above BB upper band
            - Volume spike (euphoria)

        Args:
            market_obs: Market observation

        Returns:
            True if can enter short
        """
        rsi = market_obs.get("rsi", 50.0)
        bb_dev = market_obs.get("bb_deviation", 0.0)
        volume_spike = market_obs.get("volume_spike", 1.0)

        return (
            rsi > self.params["rsi_overbought"]
            and bb_dev > self.params["bb_threshold"]
            and volume_spike > 1.5
        )

    def should_exit(self, market_obs: dict[str, Any], position: float) -> bool:
        """Check if should exit position.

        Exit on:
            - RSI crossed target (mean reversion complete)
            - RSI against position (loss prevention)

        Args:
            market_obs: Market observation
            position: Current position

        Returns:
            True if should exit
        """
        if position == 0:
            return False

        rsi = market_obs.get("rsi", 50.0)

        # Exit long when RSI reaches neutral zone
        if position > 0 and rsi > self.params["target_rsi"]:
            return True

        # Exit short when RSI reaches neutral zone
        if position < 0 and rsi < self.params["target_rsi"]:
            return True

        return False
