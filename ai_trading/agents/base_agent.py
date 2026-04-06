"""Base agent interface for AI Trading System."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.base_class import BaseAlgorithm

__all__ = ["BaseAgent", "AgentConfig"]


@dataclass
class AgentConfig:
    """Configuration for an RL agent.

    Attributes:
        name: Agent identifier (e.g., "momentum_hunter")
        algorithm: "PPO" or "SAC"
        model_path: Path to saved model
        observation_dim: Observation space size
        action_dim: Action space size (default 1 for continuous [-1, 1])
        device: "auto", "cpu", or "cuda"
    """

    name: str
    algorithm: str  # "PPO" or "SAC"
    model_path: str | None = None
    observation_dim: int = 32
    action_dim: int = 1
    device: str = "auto"


class BaseAgent(ABC):
    """Abstract base class for AI trading agents.

    Each agent has a fixed persona that shapes its:
    - Observation space (what it sees)
    - Reward function (what it optimizes)
    - Entry/exit philosophy
    """

    PERSONA: str = ""  # Agent's trading philosophy (set by subclasses)
    ALGORITHM: str = "PPO"  # RL algorithm: PPO or SAC

    def __init__(self, config: AgentConfig):
        """Initialize agent with config.

        Args:
            config: Agent configuration
        """
        self.config = config
        self.name = config.name
        self.model: BaseAlgorithm | None = None
        self._device = config.device
        self._portfolio_history: list[dict] = []

        # Load model if path provided
        if config.model_path and os.path.exists(config.model_path):
            self.load(config.model_path)

    @abstractmethod
    def build_observation(
        self,
        market_obs: dict[str, Any],
        portfolio_state: dict[str, Any],
    ) -> np.ndarray:
        """Build agent-specific observation vector.

        Args:
            market_obs: Market data (OHLCV, ML signals, regime, etc.)
            portfolio_state: Current position, PnL, etc.

        Returns:
            Observation vector for RL model
        """
        ...

    @abstractmethod
    def compute_reward(
        self,
        action: float,
        prev_state: dict[str, Any],
        curr_state: dict[str, Any],
    ) -> float:
        """Compute reward for an action.

        Args:
            action: Position ratio in [-1, 1]
            prev_state: Previous step state
            curr_state: Current step state

        Returns:
            Scalar reward
        """
        ...

    def act(self, observation: np.ndarray) -> float:
        """Get action from policy.

        Args:
            observation: Observation vector

        Returns:
            Action in [-1, 1] (position ratio)
        """
        if self.model is None:
            return 0.0  # Neutral if no model

        # Convert to tensor and add batch dimension
        obs_tensor = torch.as_tensor(
            observation, dtype=torch.float32, device=self.model.device
        ).unsqueeze(0)

        # Get action from policy
        with torch.no_grad():
            action_tensor, _ = self.model.policy.predict(
                obs_tensor,
                deterministic=False,  # Use stochastic policy for exploration
            )

        # Convert to scalar in [-1, 1]
        action = float(action_tensor[0].item())
        return np.clip(action, -1.0, 1.0)

    def compute_metrics(self, portfolio_history: list[dict]) -> dict[str, float]:
        """Compute performance metrics.

        Metrics for Arbiter evaluation:
        - sharpe_7d: 7-day Sharpe ratio
        - max_drawdown: Maximum drawdown
        - win_rate: Win rate
        - avg_hold_bars: Average holding bars
        - regime_fit: Fit with current regime (subclass may override)
        - diversity_score: Correlation with other agents (placeholder)
        - overfit_score: Recent vs previous performance gap

        Args:
            portfolio_history: List of portfolio states with PnL

        Returns:
            Dictionary of metrics
        """
        if not portfolio_history:
            return {
                "sharpe_7d": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "avg_hold_bars": 0.0,
                "regime_fit": 0.5,
                "diversity_score": 0.5,
                "overfit_score": 0.0,
            }

        # Extract PnL series
        pnls = [p.get("pnl", 0.0) for p in portfolio_history]
        returns = np.diff(pnls) if len(pnls) > 1 else [0.0]

        # Sharpe ratio (7-day annualized, assuming daily data)
        returns_arr = np.array(returns)
        sharpe = 0.0
        if len(returns_arr) > 1 and returns_arr.std() > 1e-8:
            sharpe = (returns_arr.mean() / (returns_arr.std() + 1e-8)) * np.sqrt(365)

        # Max drawdown
        cumulative = np.maximum.accumulate(pnls)
        drawdowns = (cumulative - np.array(pnls)) / (cumulative + 1e-8)
        max_dd = float(drawdowns.max()) if len(drawdowns) > 0 else 0.0

        # Win rate
        positive_returns = sum(1 for r in returns if r > 0)
        win_rate = positive_returns / max(len(returns), 1)

        # Average holding bars (from position records)
        holds = [p.get("hold_bars", 1) for p in portfolio_history if "hold_bars" in p]
        avg_hold = float(np.mean(holds)) if holds else 0.0

        # Overfit score (last 20% vs first 80% performance)
        overfit = 0.0
        if len(returns_arr) >= 10:
            split = len(returns_arr) * 4 // 5
            recent_sharpe = (
                returns_arr[split:].mean() / (returns_arr[split:].std() + 1e-8)
                if returns_arr[split:].std() > 0
                else 0.0
            )
            prev_sharpe = (
                returns_arr[:split].mean() / (returns_arr[:split].std() + 1e-8)
                if returns_arr[:split].std() > 0
                else 0.0
            )
            overfit = recent_sharpe - prev_sharpe  # Positive = overfitting

        return {
            "sharpe_7d": float(sharpe),
            "max_drawdown": float(max_dd),
            "win_rate": float(win_rate),
            "avg_hold_bars": float(avg_hold),
            "regime_fit": 0.5,  # Subclass override
            "diversity_score": 0.5,  # Arbiter computes
            "overfit_score": float(overfit),
        }

    def save(self, path: str | None = None) -> str:
        """Save agent model.

        Args:
            path: Save path (default: config.model_path)

        Returns:
            Path where model was saved
        """
        if self.model is None:
            raise ValueError("No model to save")

        save_path = path or self.config.model_path
        if save_path is None:
            raise ValueError("No save path specified")

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save(save_path)
        return save_path

    def load(self, path: str) -> None:
        """Load agent model from path.

        Args:
            path: Model file path
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}")

        if self.config.algorithm.upper() == "PPO":
            self.model = PPO.load(path, device=self._device)
        elif self.config.algorithm.upper() == "SAC":
            self.model = SAC.load(path, device=self._device)
        else:
            raise ValueError(f"Unknown algorithm: {self.config.algorithm}")

    def train(
        self,
        total_timesteps: int = 100_000,
        save_path: str | None = None,
    ) -> None:
        """Train the agent.

        Args:
            total_timesteps: Training steps
            save_path: Where to save best model
        """
        # Subclass implements training setup
        raise NotImplementedError("Training implemented in train_rl.py")

    async def self_improve(
        self,
        recent_performance: dict[str, float],
        regime: str,
        params: dict[str, Any],
        strategy_generator: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Request parameter adjustment via LLM.

        Uses StrategyGenerator to propose new parameters based on
        recent performance and current market regime.

        Args:
            recent_performance: Recent metrics
            regime: Current market regime
            params: Current parameters
            strategy_generator: Optional StrategyGenerator instance

        Returns:
            Proposed new parameters or empty dict if no change
        """
        if strategy_generator is None:
            # No strategy generator available, skip self-improvement
            return {}

        try:
            from ai_trading.arbiter.strategy_generator import StrategyGenerator

            if not isinstance(strategy_generator, StrategyGenerator):
                logger.warning("Invalid strategy_generator provided")
                return {}

            # Get persona from class docstring
            persona = self.__class__.__doc__ or self.PERSONA or "Trading agent"

            # Generate strategy proposal
            proposal = await strategy_generator.generate_strategy(
                agent_name=self.name,
                persona=persona,
                current_params=params,
                recent_performance=recent_performance,
                current_regime=regime,
            )

            # Log the proposal
            logger.info(
                f"Strategy proposal for {self.name}: {proposal.expected_improvement}"
            )

            # Return proposed parameters
            return proposal.params

        except Exception as e:
            logger.error(f"Self-improvement failed: {e}")
            return {}

    def update_portfolio_history(self, state: dict[str, Any]) -> None:
        """Record portfolio state for metrics computation.

        Args:
            state: Portfolio state
        """
        self._portfolio_history.append(state)

        # Keep last 1000 entries
        if len(self._portfolio_history) > 1000:
            self._portfolio_history = self._portfolio_history[-1000:]
