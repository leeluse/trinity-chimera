"""Gymnasium-based RL Trading Environment.

Implements a standard Gymnasium interface for training trading agents.
Supports multiple reward functions and realistic trading costs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces


class RewardType(Enum):
    """Available reward function types."""
    PNL = "pnl"                  # Raw PnL
    SHARPE = "sharpe"            # Sharpe ratio (risk-adjusted return)
    SORTINO = "sortino"          # Sortino ratio (downside risk only)
    CALMAR = "calmar"            # Calmar ratio (return / max drawdown)


class PositionType(Enum):
    """Trading position types."""
    LONG = 1.0
    NEUTRAL = 0.0
    SHORT = -1.0


@dataclass
class TradingConfig:
    """Configuration for trading environment.

    Attributes:
        initial_capital: Starting capital (default: 10000)
        commission_rate: Trading commission (default: 0.001 = 0.1%)
        slippage_rate: Slippage on execution (default: 0.0005 = 0.05%)
        max_position_size: Maximum position size (default: 1.0 = 100%)
        reward_type: Type of reward function (default: sharpe)
        window_size: Observation window size (default: 20)
        risk_free_rate: Annual risk-free rate for Sharpe (default: 0.02)
        max_hold_bars: Maximum bars to hold position (default: 100)
        penalty_factor: Penalty for excessive trading (default: 0.001)
    """
    initial_capital: float = 10000.0
    commission_rate: float = 0.001
    slippage_rate: float = 0.0005
    max_position_size: float = 1.0
    reward_type: RewardType = RewardType.SHARPE
    window_size: int = 20
    risk_free_rate: float = 0.02
    max_hold_bars: int = 100
    penalty_factor: float = 0.001


class CryptoTradingEnv(gym.Env):
    """Gymnasium environment for cryptocurrency trading.

    Observation Space:
    - Market features: returns, volatility, price position
    - ML signals: p_long, p_short, confidence
    - Regime: encoded market regime
    - Portfolio state: position, unrealized_pnl, cash_ratio
    - Technical indicators: moving averages, RSI, etc.

    Action Space:
    - Continuous [-1, 1]: Position ratio
      -1.0 = 100% short
       0.0 = neutral/cash
      +1.0 = 100% long

    Reward:
    - Sharpe, Sortino, Calmar, or raw PnL based on config

    Costs:
    - Commission: applied on trade execution
    - Slippage: price impact on entry/exit
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 1}

    def __init__(
        self,
        ohlcv: pd.DataFrame,
        ml_signals: Optional[pd.DataFrame] = None,
        regimes: Optional[pd.Series] = None,
        config: Optional[TradingConfig] = None,
        render_mode: Optional[str] = None
    ):
        """Initialize trading environment.

        Args:
            ohlcv: OHLCV data with columns ['open', 'high', 'low', 'close', 'volume']
            ml_signals: Optional DataFrame with ['p_long', 'p_short', 'confidence']
            regimes: Optional Series with regime labels ('bull', 'bear', 'sideways')
            config: Trading configuration
            render_mode: Rendering mode
        """
        super().__init__()

        self.ohlcv = ohlcv.reset_index(drop=True)
        self.ml_signals = ml_signals
        self.regimes = regimes.reset_index(drop=True) if regimes is not None else None
        self.config = config or TradingConfig()
        self.render_mode = render_mode

        # State tracking
        self.current_step = 0
        self.position = 0.0  # Current position ratio [-1, 1]
        self.cash = self.config.initial_capital
        self.portfolio_value = self.config.initial_capital
        self.unrealized_pnl = 0.0
        self.hold_bars = 0
        self.entry_price = 0.0

        # History for metrics calculation
        self.portfolio_history: list[float] = []
        self.position_history: list[float] = []
        self.returns_history: list[float] = []
        self.trades: list[dict] = []

        # Define spaces
        self._setup_observation_space()
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(1,),
            dtype=np.float32
        )

        # Observation window cache
        self._observation_window: list[np.ndarray] = []

    def _setup_observation_space(self) -> None:
        """Setup observation space dimensions."""
        # Calculate expected observation size
        # Price features (5) + ML signals (3) + Regime (1) + Portfolio (3) + Tech (5) = ~17
        obs_dim = 17
        self.observation_size = obs_dim

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32
        )

    def _get_current_price(self) -> float:
        """Get current bar's close price."""
        return float(self.ohlcv["close"].iloc[self.current_step])

    def _get_current_regime(self) -> str:
        """Get current market regime."""
        if self.regimes is not None and self.current_step < len(self.regimes):
            return str(self.regimes.iloc[self.current_step])
        return "sideways"

    def _encode_regime(self, regime: str) -> float:
        """Encode regime to numeric."""
        mapping = {"bull": 1.0, "sideways": 0.0, "bear": -1.0}
        return mapping.get(regime, 0.0)

    def _get_ml_signals(self) -> tuple[float, float, float]:
        """Get ML signals for current step."""
        if self.ml_signals is None or self.current_step >= len(self.ml_signals):
            return 0.0, 0.0, 0.0

        row = self.ml_signals.iloc[self.current_step]
        return (
            float(row.get("p_long", 0.0)),
            float(row.get("p_short", 0.0)),
            float(row.get("confidence", 0.0))
        )

    def _calculate_technical_features(self) -> dict[str, float]:
        """Calculate technical indicators for observation."""
        idx = self.current_step
        window = min(self.config.window_size, idx + 1)

        if window < 2:
            return {
                "returns": 0.0,
                "volatility": 0.0,
                "price_vs_sma": 0.0,
                "rsi": 50.0,
                "atr": 0.0
            }

        prices = self.ohlcv["close"].iloc[idx - window + 1:idx + 1]

        # Returns
        returns = np.diff(prices.values) / (prices.values[:-1] + 1e-8)

        # Volatility (annualized)
        volatility = float(np.std(returns) * np.sqrt(365 * 24)) if len(returns) > 1 else 0.0

        # Price vs moving average
        sma = prices.mean()
        current_price = prices.iloc[-1]
        price_vs_sma = (current_price / sma - 1.0) if sma > 0 else 0.0

        # Simple RSI approximation
        if len(returns) >= 2:
            gains = np.sum(returns[returns > 0])
            losses = abs(np.sum(returns[returns < 0]))
            rsi = 50.0
            if losses > 0:
                rs = gains / losses
                rsi = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi = 50.0

        # ATR approximation
        highs = self.ohlcv["high"].iloc[idx - window + 1:idx + 1]
        lows = self.ohlcv["low"].iloc[idx - window + 1:idx + 1]
        tr = highs.max() - lows.min()
        atr = tr / window if window > 0 else 0.0

        return {
            "returns": float(returns[-1]) if len(returns) > 0 else 0.0,
            "volatility": volatility,
            "price_vs_sma": float(price_vs_sma),
            "rsi": float(rsi),
            "atr": float(atr) / current_price  # Normalized ATR
        }

    def _get_observation(self) -> np.ndarray:
        """Build observation vector."""
        # Market features
        tech = self._calculate_technical_features()

        # ML signals
        p_long, p_short, confidence = self._get_ml_signals()

        # Regime
        regime = self._encode_regime(self._get_current_regime())

        # Portfolio state
        cash_ratio = self.cash / (self.portfolio_value + 1e-8)
        position_normalized = self.position  # Already [-1, 1]
        unrealized_normalized = self.unrealized_pnl / (self.portfolio_value + 1e-8)

        obs = np.array([
            # Market features (5)
            tech["returns"],
            tech["volatility"],
            tech["price_vs_sma"],
            tech["rsi"] / 100.0 - 0.5,  # Normalize to [-0.5, 0.5]
            tech["atr"],
            # ML signals (3)
            p_long,
            p_short,
            confidence,
            # Regime (1)
            regime,
            # Portfolio state (3)
            cash_ratio,
            position_normalized,
            unrealized_normalized,
            # Position timing (1)
            min(self.hold_bars / self.config.max_hold_bars, 1.0),
            # Current price level (1) - for context
            0.0,  # Placeholder
            # Historical returns (3x window stats)
            0.0, 0.0, 0.0  # Placeholders
        ], dtype=np.float32)

        return obs

    def _execute_trade(self, target_position: float) -> float:
        """Execute trade to reach target position.

        Args:
            target_position: Desired position [-1, 1]

        Returns:
            Transaction cost incurred
        """
        current_price = self._get_current_price()
        position_change = target_position - self.position

        if abs(position_change) < 1e-6:
            return 0.0

        # Calculate trade value
        trade_value = abs(position_change) * self.portfolio_value

        # Commission
        commission = trade_value * self.config.commission_rate

        # Slippage (proportional to position change magnitude)
        slippage = trade_value * self.config.slippage_rate * abs(position_change)

        # Update state
        self.cash -= commission + slippage

        # Track entry price for PnL calculation
        if self.position == 0.0 and target_position != 0.0:
            self.entry_price = current_price * (1 + self.config.slippage_rate * np.sign(position_change))

        # Record trade
        if abs(position_change) > 0.01:
            self.trades.append({
                "step": self.current_step,
                "price": current_price,
                "position_before": self.position,
                "position_after": target_position,
                "change": position_change,
                "commission": commission,
                "slippage": slippage
            })

        self.position = np.clip(target_position, -1.0, 1.0)

        return commission + slippage

    def _update_portfolio(self) -> None:
        """Update portfolio value based on current position and price."""
        if self.current_step == 0:
            return

        current_price = self._get_current_price()
        prev_price = float(self.ohlcv["close"].iloc[self.current_step - 1])

        # Calculate price return
        price_return = (current_price - prev_price) / (prev_price + 1e-8)

        # Update unrealized PnL
        if self.position != 0:
            self.unrealized_pnl = self.position * price_return * self.portfolio_value

        # Update portfolio value
        self.portfolio_value = self.cash + self.position * self.portfolio_value * (1 + price_return)

    def _compute_reward(self, action: float) -> float:
        """Compute reward based on configured reward type.

        Args:
            action: The action taken

        Returns:
            Scalar reward value
        """
        if len(self.portfolio_history) < 2:
            return 0.0

        # Current portfolio return
        prev_value = self.portfolio_history[-2] if len(self.portfolio_history) >= 2 else self.config.initial_capital
        curr_value = self.portfolio_value
        portfolio_return = (curr_value - prev_value) / (prev_value + 1e-8)

        if self.config.reward_type == RewardType.PNL:
            return portfolio_return * 100  # Scale for visibility

        # Update returns history for ratio calculations
        self.returns_history.append(portfolio_return)
        window = min(len(self.returns_history), self.config.window_size)
        recent_returns = np.array(self.returns_history[-window:])

        if self.config.reward_type == RewardType.SHARPE:
            if len(recent_returns) < 2 or recent_returns.std() == 0:
                return portfolio_return * 10
            excess_return = recent_returns.mean()
            volatility = recent_returns.std()
            sharpe = excess_return / (volatility + 1e-8)
            return float(sharpe)

        elif self.config.reward_type == RewardType.SORTINO:
            if len(recent_returns) < 2:
                return portfolio_return * 10
            excess_return = recent_returns.mean()
            downside = recent_returns[recent_returns < 0]
            downside_std = downside.std() if len(downside) > 0 else 1e-8
            sortino = excess_return / (downside_std + 1e-8)
            return float(sortino)

        elif self.config.reward_type == RewardType.CALMAR:
            if len(self.returns_history) < 10:
                return portfolio_return * 10
            cumulative = np.maximum.accumulate(self.portfolio_history)
            drawdowns = (cumulative - np.array(self.portfolio_history)) / (cumulative + 1e-8)
            max_dd = drawdowns.max()
            if max_dd == 0:
                return portfolio_return * 100
            total_return = (curr_value - self.config.initial_capital) / self.config.initial_capital
            calmar = total_return / (max_dd + 1e-8)
            return float(calmar)

        return portfolio_return * 100

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None
    ) -> tuple[np.ndarray, dict]:
        """Reset environment to initial state.

        Args:
            seed: Random seed
            options: Additional options

        Returns:
            Initial observation and info dict
        """
        super().reset(seed=seed)

        self.current_step = 0
        self.position = 0.0
        self.cash = self.config.initial_capital
        self.portfolio_value = self.config.initial_capital
        self.unrealized_pnl = 0.0
        self.hold_bars = 0
        self.entry_price = 0.0

        self.portfolio_history = [self.config.initial_capital]
        self.position_history = [0.0]
        self.returns_history = []
        self.trades = []
        self._observation_window = []

        obs = self._get_observation()
        info = {
            "portfolio_value": self.portfolio_value,
            "position": self.position,
            "cash": self.cash
        }

        return obs, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Take a step in the environment.

        Args:
            action: Position target [-1, 1]

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Convert action to target position
        target_position = float(np.clip(action[0], -1.0, 1.0))

        # Execute trade
        transaction_cost = self._execute_trade(target_position)

        # Move to next step
        self.current_step += 1

        # Update portfolio
        self._update_portfolio()

        # Track history
        self.portfolio_history.append(self.portfolio_value)
        self.position_history.append(self.position)

        # Update hold bars
        if self.position != 0:
            self.hold_bars += 1
        else:
            self.hold_bars = 0

        # Compute reward
        reward = self._compute_reward(target_position)

        # Trading penalty
        if abs(target_position - self.position_history[-2]) > 0.01:
            reward -= self.config.penalty_factor

        # Check termination
        terminated = self.current_step >= len(self.ohlcv) - 1
        truncated = (
            self.portfolio_value <= self.config.initial_capital * 0.1  # 90% loss
            or (self.hold_bars >= self.config.max_hold_bars and self.position != 0)
        )

        # Get observation
        obs = self._get_observation()

        info = {
            "portfolio_value": self.portfolio_value,
            "position": self.position,
            "cash": self.cash,
            "unrealized_pnl": self.unrealized_pnl,
            "transaction_cost": transaction_cost,
            "hold_bars": self.hold_bars,
            "regime": self._get_current_regime()
        }

        return obs, float(reward), terminated, truncated, info

    def render(self) -> Optional[np.ndarray]:
        """Render current state."""
        if self.render_mode == "human":
            print(
                f"Step {self.current_step}: "
                f"Price={self._get_current_price():.2f}, "
                f"Position={self.position:.2f}, "
                f"Portfolio={self.portfolio_value:.2f}, "
                f"Regime={self._get_current_regime()}"
            )
        return None

    def get_metrics(self) -> dict[str, float]:
        """Calculate episode metrics.

        Returns:
            Dictionary of performance metrics
        """
        if not self.portfolio_history:
            return {}

        returns = np.diff(self.portfolio_history) / (np.array(self.portfolio_history[:-1]) + 1e-8)

        metrics = {
            "total_return": (self.portfolio_value - self.config.initial_capital) / self.config.initial_capital,
            "final_portfolio": self.portfolio_value,
            "num_trades": len(self.trades),
            "num_bars": self.current_step
        }

        if len(returns) > 1 and returns.std() > 0:
            metrics["sharpe"] = (returns.mean() / returns.std()) * np.sqrt(365 * 24)
            metrics["volatility"] = returns.std() * np.sqrt(365 * 24)
            metrics["max_drawdown"] = self._calculate_max_drawdown()

        return metrics

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        portfolio = np.array(self.portfolio_history)
        peak = np.maximum.accumulate(portfolio)
        drawdown = (peak - portfolio) / (peak + 1e-8)
        return float(drawdown.max())


def create_trading_env(
    ohlcv: pd.DataFrame,
    ml_signals: Optional[pd.DataFrame] = None,
    regimes: Optional[pd.Series] = None,
    reward_type: str = "sharpe",
    commission: float = 0.001,
    slippage: float = 0.0005,
    initial_capital: float = 10000.0
) -> CryptoTradingEnv:
    """Factory function to create trading environment.

    Args:
        ohlcv: OHLCV data
        ml_signals: Optional ML model predictions
        regimes: Optional regime labels
        reward_type: Type of reward function
        commission: Trading commission rate
        slippage: Slippage rate
        initial_capital: Starting capital

    Returns:
        Configured CryptoTradingEnv
    """
    reward_type_enum = RewardType(reward_type.lower())

    config = TradingConfig(
        initial_capital=initial_capital,
        commission_rate=commission,
        slippage_rate=slippage,
        reward_type=reward_type_enum
    )

    return CryptoTradingEnv(ohlcv, ml_signals, regimes, config)
