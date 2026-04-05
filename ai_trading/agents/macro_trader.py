"""Macro Trader Agent - Regime-based strategic trader.

Persona: "Sees the big picture. Ignores short-term noise."
Algorithm: PPO + HMM regime as first-order filter
"""

from typing import Any
import numpy as np

from ai_trading.agents.base_agent import BaseAgent, AgentConfig


class MacroTrader(BaseAgent):
    """Regime-based trader with low-frequency, high-conviction trades.

    Persona:
        - Sees the big picture, ignores short-term noise
        - Trades 1-3 times per week
        - Enters on regime transition detected

    Entry Conditions:
        - Regime change detected
        - HMM state probability > 0.7

    Exit Conditions:
        - Regime changes again
        - Maximum hold period reached

    Unique Features:
        - Open interest change
        - Fear & Greed index
        - Multi-timeframe (4h, 1d) aggregation

    Reward:
        - Sharpe ratio (long-term risk-adjusted returns)
    """

    PERSONA = "Macro view. Low frequency, high conviction."
    ALGORITHM = "PPO"

    # Parameters
    REGIME_CONFIDENCE_THRESHOLD = 0.7
    MAX_HOLD_BARS = 7 * 24  # 7 days of hourly bars

    def __init__(self, config: AgentConfig):
        """Initialize Macro Trader.

        Args:
            config: Agent configuration
        """
        super().__init__(config)
        self.prev_regime = "sideways"
        self.entry_bar = 0
        self.current_bar = 0

        self.params = {
            "regime_threshold": self.REGIME_CONFIDENCE_THRESHOLD,
            "max_hold_bars": self.MAX_HOLD_BARS,
            "min_hold_bars": 24,  # Hold at least 1 day
        }

    def build_observation(
        self,
        market_obs: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> np.ndarray:
        """Build macro-specific observation.

        Features:
            - HMM regime probability
            - Regime transition signals
            - Open interest changes
            - Fear & Greed index
            - Multi-timeframe features

        Args:
            market_obs: Market data dictionary
            portfolio_state: Current position and PnL

        Returns:
            Observation vector
        """
        # Regime with confidence
        regime = market_obs.get("regime", "sideways")
        regime_enc = self._encode_regime_with_confidence(
            regime, market_obs.get("regime_prob", 0.5)
        )

        # Regime change detection
        regime_changed = 1.0 if regime != self.prev_regime else 0.0
        self.prev_regime = regime

        # ML signal (used as secondary confirmation)
        p_long = market_obs.get("p_long", 0.0)
        p_short = market_obs.get("p_short", 0.0)
        confidence = market_obs.get("confidence", 0.0)

        # Macro features
        oi_change = market_obs.get("open_interest_change", 0.0)
        fear_greed = market_obs.get("fear_greed_index", 50.0) / 100.0

        # Multi-timeframe
        trend_4h = market_obs.get("trend_4h", 0.0)  # -1 to 1
        trend_1d = market_obs.get("trend_1d", 0.0)
        trend_1w = market_obs.get("trend_1w", 0.0)

        # Volatility
        vol_regime = market_obs.get("realized_vol", 0.0)

        # Portfolio state
        current_position = portfolio_state.get("position", 0.0)
        hold_bars = portfolio_state.get("hold_bars", 0)
        normalized_hold = min(hold_bars / self.params["max_hold_bars"], 1.0)

        obs = np.array([
            regime_enc,
            regime_changed,
            p_long,
            p_short,
            confidence,
            oi_change,
            fear_greed,
            trend_4h,
            trend_1d,
            trend_1w,
            vol_regime,
            current_position,
            normalized_hold,
        ], dtype=np.float32)

        return obs

    def _encode_regime_with_confidence(self, regime: str, prob: float) -> float:
        """Encode regime weighted by HMM confidence.

        Args:
            regime: Current regime
            prob: HMM confidence (0.0 to 1.0)

        Returns:
            Encoded value weighted by confidence
        """
        base_value = {"bull": 1.0, "sideways": 0.0, "bear": -1.0}.get(regime, 0.0)
        return base_value * prob

    def compute_reward(
        self,
        action: float,
        prev_state: dict[str, Any],
        curr_state: dict[str, Any],
    ) -> float:
        """Compute Sharpe ratio based reward.

        Long-term risk-adjusted returns maximization.

        Args:
            action: Position taken (-1.0 to 1.0)
            prev_state: Previous state
            curr_state: Current state

        Returns:
            Sharpe-style reward
        """
        pnl = curr_state.get("unrealized_pnl", 0.0) - prev_state.get("unrealized_pnl", 0.0)

        # Get returns history for Sharpe computation
        returns_hist = curr_state.get("returns_history", [])
        if len(returns_hist) < 10:
            # Not enough history: use simple PnL
            return pnl

        returns_arr = np.array(returns_hist[-100:])  # Last 100 periods

        # Sharpe = mean / std (annualized assuming hourly bars)
        mean_ret = returns_arr.mean()
        std_ret = returns_arr.std()

        if std_ret > 1e-8:
            sharpe = mean_ret / std_ret * np.sqrt(8760)  # Annualized
        else:
            sharpe = 0.0

        # Base reward is Sharpe ratio
        reward = sharpe * 0.1  # Scale to reasonable magnitude

        # PnL bonus
        reward += pnl

        # Penalty for holding too long
        hold_bars = curr_state.get("hold_bars", 0)
        if hold_bars > self.params["max_hold_bars"] * 0.8:
            reward -= 0.001  # Gentle nudge to exit

        return float(reward)

    def can_enter(self, market_obs: dict[str, Any]) -> tuple[bool, float]:
        """Check if macro entry conditions met.

        Conditions:
            - Regime change detected
            - HMM confidence >= 0.7

        Returns:
            (enter, direction) tuple
        """
        regime = market_obs.get("regime", "sideways")
        prob = market_obs.get("regime_prob", 0.5)

        if prob < self.params["regime_threshold"]:
            return False, 0.0

        if regime == "bull":
            return True, 1.0
        elif regime == "bear":
            return True, -1.0

        return False, 0.0

    def should_exit(self, market_obs: dict[str, Any], hold_bars: int) -> bool:
        """Check if should exit position.

        Exit on:
            - Regime changed
            - Max hold period reached

        Args:
            market_obs: Market observation
            hold_bars: Bars held

        Returns:
            True if should exit
        """
        # Hold minimum period
        if hold_bars < self.params["min_hold_bars"]:
            return False

        # Normal exit check
        return hold_bars >= self.params["max_hold_bars"]
