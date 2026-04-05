"""Chaos Agent - Unpredictable contrarian trader.

Persona: "Unpredictability is a weapon. Other agents can't learn my patterns."
Algorithm: SAC + noise injection (epsilon probability of random perturbation)
"""

from typing import Any
import numpy as np

from ai_trading.agents.base_agent import BaseAgent, AgentConfig


class ChaosAgent(BaseAgent):
    """Contrarian agent that trades against consensus.

    Persona:
        - Unpredictability is a weapon
        - Takes positions opposite to other agents
        - Multiple small positions to confuse pattern learning

    Entry Conditions:
        - Can enter against ML signal
        - Small positions to minimize impact

    Exit Conditions:
        - RL-learned optimal exit
        - Random timing (epsilon noise)

    Unique Features:
        - Other agent positions (as observation)
        - Random action injection

    Reward:
        - PnL - correlation penalty with other agents
        - Diversity maintenance is key strategy
    """

    PERSONA = "Unpredictable contrarian. Weaponize noise."
    ALGORITHM = "SAC"

    # Parameters
    EPSILON = 0.2  # Random action probability
    CORRELATION_PENALTY = 0.1
    MAX_POSITION_SIZE = 0.3  # Small individual positions

    def __init__(self, config: AgentConfig):
        """Initialize Chaos Agent.

        Args:
            config: Agent configuration
        """
        super().__init__(config)
        self.other_agent_positions: dict[str, float] = {}
        self.random_state = np.random.RandomState(config.seed if hasattr(config, "seed") else 42)

        self.params = {
            "epsilon": self.EPSILON,
            "correlation_penalty": self.CORRELATION_PENALTY,
            "max_position": self.MAX_POSITION_SIZE,
            "contrarian_bias": 0.7,  # Tendency to go opposite
        }

    def build_observation(
        self,
        market_obs: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> np.ndarray:
        """Build chaos-specific observation.

        Features:
            - ML signal (but inverted as option)
            - Other agent positions (aggregate)
            - Consensus strength
            - Volatility
            - Portfolio state with noise

        Args:
            market_obs: Market data dictionary
            portfolio_state: Current position and PnL

        Returns:
            Observation vector
        """
        # ML signal (we may trade against it)
        p_long = market_obs.get("p_long", 0.0)
        p_short = market_obs.get("p_short", 0.0)
        confidence = market_obs.get("confidence", 0.0)

        # Consensus signal (aggregate of other agents)
        consensus = self._compute_consensus()
        consensus_strength = abs(consensus)

        # Regime
        regime = market_obs.get("regime", "sideways")
        regime_enc = {"bull": 1.0, "sideways": 0.0, "bear": -1.0}.get(regime, 0.0)

        # Volatility (chaos thrives in uncertainty)
        vol = market_obs.get("realized_vol", 0.0)
        vol_zscore = market_obs.get("vol_zscore", 0.0)

        # Random features (impossible to predict)
        random_feature1 = self.random_state.randn()
        random_feature2 = self.random_state.randn()

        # Portfolio state
        current_position = portfolio_state.get("position", 0.0)
        unrealized_pnl = portfolio_state.get("unrealized_pnl", 0.0)

        # Position count (number of small positions)
        position_count = portfolio_state.get("sub_position_count", 1)

        obs = np.array([
            p_long,
            p_short,
            1.0 - confidence,  # Uncertainty preference
            consensus,
            consensus_strength,
            regime_enc,
            vol,
            vol_zscore,
            random_feature1,
            random_feature2,
            current_position,
            unrealized_pnl,
            float(position_count),
        ], dtype=np.float32)

        return obs

    def _compute_consensus(self) -> float:
        """Compute consensus from other agent positions.

        Returns:
            Consensus value: positive = long, negative = short
        """
        if not self.other_agent_positions:
            return 0.0

        return np.mean(list(self.other_agent_positions.values()))

    def update_other_agents(self, positions: dict[str, float]) -> None:
        """Update knowledge of other agents' positions.

        Args:
            positions: Agent name -> position mapping
        """
        self.other_agent_positions = positions

    def act(self, observation: np.ndarray) -> float:
        """Take action with noise injection.

        Implements epsilon-greedy exploration. With probability epsilon,
        returns a random action to foil pattern learning.

        Args:
            observation: Observation vector

        Returns:
            Action in [-1, 1]
        """
        if self.random_state.random() < self.params["epsilon"]:
            # Random action: foil pattern learning
            return float(self.random_state.uniform(-1.0, 1.0))

        # Otherwise use normal behavior
        action = super().act(observation)

        # Add small noise
        noise = self.random_state.normal(0, 0.1)
        action = np.clip(action + noise, -1.0, 1.0)

        return float(action)

    def compute_reward(
        self,
        action: float,
        prev_state: dict[str, Any],
        curr_state: dict[str, Any],
    ) -> float:
        """Compute reward with correlation penalty.

        Args:
            action: Position taken (-1.0 to 1.0)
            prev_state: Previous state
            curr_state: Current state

        Returns:
            PnL minus correlation penalty
        """
        pnl = curr_state.get("unrealized_pnl", 0.0) - prev_state.get("unrealized_pnl", 0.0)

        # Base PnL reward
        reward = pnl

        # Correlation penalty: penalize correlation with consensus
        consensus = self._compute_consensus()
        if abs(consensus) > 0.3:  # Strong consensus exists
            # Penalize moving with consensus
            alignment = action * consensus
            if alignment > 0:
                # Penalty for herd behavior
                reward -= self.params["correlation_penalty"] * alignment

        # Bonus for contrarian success
        if abs(consensus) > 0.5 and pnl > 0:
            # Made money against strong consensus
            if action * consensus < 0:  # Opposite position
                reward += pnl * 0.5  # Contrarian bonus

        return float(reward)

    def can_enter_contrarian(self, market_obs: dict[str, Any]) -> float:
        """Decide contrarian entry direction.

        Returns:
            Direction: opposite to ML signal consensus
        """
        p_long = market_obs.get("p_long", 0.0)
        p_short = market_obs.get("p_short", 0.0)
        confidence = market_obs.get("confidence", 0.0)

        if confidence > 0.6:
            # High confidence suggests overreaction
            # Go opposite with probability
            if self.random_state.random() < self.params["contrarian_bias"]:
                # Reverse position
                if p_long > p_short:
                    return -0.3  # Small short
                else:
                    return 0.3  # Small long

        # Otherwise neutral or small random
        return float(self.random_state.uniform(-0.2, 0.2))

    def get_diversity_score(self) -> float:
        """Compute diversity score for the agent.

        Returns:
            Higher diversity score = less correlation
        """
        consensus = self._compute_consensus()
        if not self.other_agent_positions:
            return 1.0

        # Calculate correlation with others
        my_position = self.position if hasattr(self, "position") else 0.0
        if len(self.other_agent_positions) > 0:
            avg_position = np.mean(list(self.other_agent_positions.values()))
            corr = abs(my_position - avg_position) / 2.0
            return corr  # Higher = more diverse

        return 1.0
