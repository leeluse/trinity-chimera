"""Momentum Hunter Agent - Trend-following agent.

Persona: "Only trades trends. Sideways doesn't exist."
Algorithm: PPO + LSTM (temporal memory)
"""

from typing import Any
import numpy as np

from ai_trading.agents.base_agent import BaseAgent, AgentConfig


class MomentumHunter(BaseAgent):
    """Trend-following agent specialized for bull markets.

    Persona:
        - Only trades trends. Sideways doesn't exist.
        - Long-only in bull markets
        - Enters on regime=bull + ML confidence >= 0.55 + momentum strong
        - Exits on momentum reversal or regime change

    Unique Features:
        - ROC (Rate of Change)
        - ADX (Trend strength)
        - 52-week high relative position

    Reward:
        - PnL-based (no Sharpe penalty - aggressive in trends)
    """

    PERSONA = "Trend trader. Only trends exist. Sideways is illusion."
    ALGORITHM = "PPO"

    # Entry/exit thresholds
    MIN_CONFIDENCE = 0.55
    MIN_ADX = 25  # Trend strength threshold

    def __init__(self, config: AgentConfig):
        """Initialize Momentum Hunter.

        Args:
            config: Agent configuration
        """
        super().__init__(config)
        self.params = {
            "min_confidence": self.MIN_CONFIDENCE,
            "min_adx": self.MIN_ADX,
            "roc_lookback": 10,
            "long_only": True,  # No short positions in bear market
        }

    def build_observation(
        self,
        market_obs: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> np.ndarray:
        """Build momentum-specific observation.

        Features:
            - ML signal (p_long, p_short, confidence)
            - Regime (bull/sideways/bear encoded)
            - Momentum features: ROC, ADX, position vs 52w high
            - Portfolio state: current position, unrealized PnL

        Args:
            market_obs: Market data dictionary
            portfolio_state: Current position and PnL

        Returns:
            Observation vector
        """
        # ML signal features
        p_long = market_obs.get("p_long", 0.0)
        p_short = market_obs.get("p_short", 0.0)
        confidence = market_obs.get("confidence", 0.0)

        # Regime encoding
        regime = market_obs.get("regime", "sideways")
        regime_enc = self._encode_regime(regime)

        # Momentum features
        roc = market_obs.get("roc_10", 0.0)  # Rate of change
        adx = market_obs.get("adx", 0.0)  # Trend strength
        price_vs_high = market_obs.get("price_vs_52w_high", 0.5)  # 0-1 normalized

        # Technical momentum
        ema_fast = market_obs.get("ema_fast", 0.0)
        ema_slow = market_obs.get("ema_slow", 0.0)
        ema_ratio = ema_fast / (ema_slow + 1e-8) - 1.0 if ema_slow > 0 else 0.0

        # Portfolio state
        current_position = portfolio_state.get("position", 0.0)
        unrealized_pnl = portfolio_state.get("unrealized_pnl", 0.0)
        cash_ratio = portfolio_state.get("cash_ratio", 1.0)

        obs = np.array([
            p_long,
            p_short,
            confidence,
            regime_enc,
            roc,
            adx,
            price_vs_high,
            ema_ratio,
            current_position,
            unrealized_pnl,
            cash_ratio,
        ], dtype=np.float32)

        return obs

    def _encode_regime(self, regime: str) -> float:
        """Encode regime to numeric value.

        Args:
            regime: "bull", "sideways", or "bear"

        Returns:
            Encoded value: bull=1.0, sideways=0.0, bear=-1.0
        """
        mapping = {"bull": 1.0, "sideways": 0.0, "bear": -1.0}
        return mapping.get(regime, 0.0)

    def compute_reward(
        self,
        action: float,
        prev_state: dict[str, Any],
        curr_state: dict[str, Any],
    ) -> float:
        """Compute PnL-based reward.

        Args:
            action: Position taken (-1.0 to 1.0)
            prev_state: Previous state
            curr_state: Current state

        Returns:
            PnL reward (no Sharpe penalty - aggressive in trends)
        """
        pnl = curr_state.get("unrealized_pnl", 0.0) - prev_state.get("unrealized_pnl", 0.0)

        # Scale by position size to encourage full position in strong trends
        position_size = abs(action)

        # No mean-reversion penalty - pure PnL focus
        reward = pnl * (1.0 + position_size * 0.1)

        # Penalty for holding through regime change to bear
        curr_regime = curr_state.get("regime", "sideways")
        if curr_regime == "bear" and action > 0:
            # Shouldn't be long in bear market
            reward -= 0.01 * abs(action)

        return float(reward)

    def can_enter(self, market_obs: dict[str, Any]) -> bool:
        """Check if entry conditions are met.

        Entry conditions:
            - regime = bull
            - ML confidence >= 0.55
            - ADX >= 25 (strong trend)
            - ROC > 0 (positive momentum)

        Args:
            market_obs: Market observation

        Returns:
            True if can enter position
        """
        regime = market_obs.get("regime", "")
        confidence = market_obs.get("confidence", 0.0)
        adx = market_obs.get("adx", 0.0)
        roc = market_obs.get("roc_10", 0.0)

        return (
            regime == "bull"
            and confidence >= self.params["min_confidence"]
            and adx >= self.params["min_adx"]
            and roc > 0
        )

    def should_exit(self, market_obs: dict[str, Any], position: float) -> bool:
        """Check if should exit position.

        Exit conditions:
            - regime changed from bull
            - momentum reversal (ROC < 0)
            - ADX dropped below threshold

        Args:
            market_obs: Market observation
            position: Current position

        Returns:
            True if should exit
        """
        if position == 0:
            return False

        regime = market_obs.get("regime", "")
        roc = market_obs.get("roc_10", 0.0)
        adx = market_obs.get("adx", 0.0)

        # Exit if regime not bull anymore
        if regime != "bull":
            return True

        # Exit on momentum reversal
        if roc < 0:
            return True

        # Exit if trend weakens
        if adx < self.params["min_adx"] * 0.8:
            return True

        return False
