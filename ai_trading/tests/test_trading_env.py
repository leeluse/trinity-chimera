"""Tests for RL Trading Environment."""

import numpy as np
import pandas as pd
import pytest

from ai_trading.rl.trading_env import (
    CryptoTradingEnv,
    PositionType,
    RewardType,
    TradingConfig,
    create_trading_env,
)


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data."""
    np.random.seed(42)
    n = 100

    prices = [100.0]
    for _ in range(n - 1):
        ret = np.random.normal(0.0001, 0.01)
        prices.append(prices[-1] * (1 + ret))

    df = pd.DataFrame({
        "open": prices,
        "high": [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
        "low": [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
        "close": prices,
        "volume": np.random.uniform(1000, 5000, n)
    }, index=pd.date_range("2024-01-01", periods=n, freq="1h"))

    return df


@pytest.fixture
def sample_ml_signals():
    """Generate sample ML signals."""
    n = 100
    return pd.DataFrame({
        "p_long": np.random.uniform(0, 1, n),
        "p_short": np.random.uniform(0, 1, n),
        "confidence": np.random.uniform(0, 1, n)
    }, index=pd.date_range("2024-01-01", periods=n, freq="1h"))


@pytest.fixture
def sample_regimes():
    """Generate sample regime labels."""
    n = 100
    regimes = np.random.choice(["bull", "bear", "sideways"], n, p=[0.3, 0.2, 0.5])
    return pd.Series(regimes, index=pd.date_range("2024-01-01", periods=n, freq="1h"))


class TestCryptoTradingEnv:
    """Test suite for CryptoTradingEnv."""

    def test_initialization(self, sample_ohlcv):
        """Test basic initialization."""
        env = CryptoTradingEnv(sample_ohlcv)
        assert env.config.initial_capital == 10000.0
        assert env.config.commission_rate == 0.001
        assert env.action_space.shape == (1,)

    def test_custom_config(self, sample_ohlcv):
        """Test initialization with custom config."""
        config = TradingConfig(
            initial_capital=50000.0,
            commission_rate=0.002,
            reward_type=RewardType.SORTINO
        )
        env = CryptoTradingEnv(sample_ohlcv, config=config)
        assert env.config.initial_capital == 50000.0
        assert env.config.commission_rate == 0.002
        assert env.config.reward_type == RewardType.SORTINO

    def test_observation_space(self, sample_ohlcv):
        """Test observation space dimensions."""
        env = CryptoTradingEnv(sample_ohlcv)
        obs, info = env.reset()

        assert obs.shape == (env.observation_size,)
        assert isinstance(obs, np.ndarray)
        assert obs.dtype == np.float32

    def test_action_space(self, sample_ohlcv):
        """Test action space."""
        env = CryptoTradingEnv(sample_ohlcv)
        obs, info = env.reset()

        # Test valid actions
        for action in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            obs, reward, terminated, truncated, info = env.step(np.array([action]))
            assert -1.0 <= info["position"] <= 1.0

    def test_reset(self, sample_ohlcv):
        """Test environment reset."""
        env = CryptoTradingEnv(sample_ohlcv)
        obs, info = env.reset(seed=42)

        assert env.current_step == 0
        assert env.position == 0.0
        assert env.cash == env.config.initial_capital
        assert env.portfolio_value == env.config.initial_capital
        assert "portfolio_value" in info

    def test_step_updates_state(self, sample_ohlcv):
        """Test step updates environment state."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(np.array([0.5]))

        assert env.current_step == 1
        assert env.position == 0.5
        assert "portfolio_value" in info
        assert "cash" in info

    def test_long_position(self, sample_ohlcv):
        """Test taking long position."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Enter long
        obs, reward, terminated, truncated, info = env.step(np.array([1.0]))
        assert env.position > 0
        assert len(env.trades) == 1

    def test_short_position(self, sample_ohlcv):
        """Test taking short position."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Enter short
        obs, reward, terminated, truncated, info = env.step(np.array([-1.0]))
        assert env.position < 0

    def test_position_change(self, sample_ohlcv):
        """Test changing position."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Long to neutral
        env.step(np.array([1.0]))
        assert env.position == 1.0

        env.step(np.array([0.0]))
        assert env.position == 0.0

        # Neutral to short
        env.step(np.array([-1.0]))
        assert env.position == -1.0

    def test_returns_calculated(self, sample_ohlcv):
        """Test that returns are calculated."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Take a position and run several steps
        env.step(np.array([1.0]))
        for _ in range(5):
            env.step(np.array([1.0]))

        assert len(env.portfolio_history) > 1
        returns = np.diff(env.portfolio_history)
        assert len(returns) > 0

    def test_reward_types(self, sample_ohlcv):
        """Test different reward types."""
        for reward_type in RewardType:
            config = TradingConfig(reward_type=reward_type)
            env = CryptoTradingEnv(sample_ohlcv, config=config)
            env.reset()

            # Run a few steps
            total_reward = 0
            for _ in range(10):
                obs, reward, terminated, truncated, info = env.step(np.array([0.5]))
                total_reward += reward
                assert isinstance(reward, float)

            assert not np.isnan(total_reward)

    def test_trading_costs(self, sample_ohlcv):
        """Test trading costs are applied."""
        config = TradingConfig(commission_rate=0.01)  # High commission
        env = CryptoTradingEnv(sample_ohlcv, config=config)
        env.reset()

        # Enter position
        obs, reward, terminated, truncated, info = env.step(np.array([1.0]))
        assert info["transaction_cost"] > 0
        assert len(env.trades) > 0
        assert env.trades[0]["commission"] > 0

    def test_max_hold_bars(self, sample_ohlcv):
        """Test max hold bars constraint."""
        config = TradingConfig(max_hold_bars=5)
        env = CryptoTradingEnv(sample_ohlcv, config=config)
        env.reset()

        # Take position and hold
        env.step(np.array([1.0]))
        for _ in range(6):
            obs, reward, terminated, truncated, info = env.step(np.array([1.0]))

        # Should be truncated after max_hold_bars
        assert env.hold_bars >= 5

    def test_portfolio_drawdown(self, sample_ohlcv):
        """Test drawdown calculation."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Run episode
        for _ in range(20):
            env.step(np.array([1.0]))

        dd = env._calculate_max_drawdown()
        assert isinstance(dd, float)
        assert dd >= 0

    def test_metrics(self, sample_ohlcv):
        """Test metrics calculation."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Run a few steps
        for _ in range(20):
            env.step(np.array([0.5]))

        metrics = env.get_metrics()
        assert "total_return" in metrics
        assert "final_portfolio" in metrics
        assert "num_trades" in metrics

    def test_episode_termination(self, sample_ohlcv):
        """Test episode termination."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Run until end of data
        terminated = False
        steps = 0
        while not terminated and steps < 200:
            obs, reward, terminated, truncated, info = env.step(np.array([0.5]))
            steps += 1

        assert terminated or steps >= len(sample_ohlcv) - 1

    def test_with_ml_signals(self, sample_ohlcv, sample_ml_signals):
        """Test environment with ML signals."""
        env = CryptoTradingEnv(sample_ohlcv, ml_signals=sample_ml_signals)
        obs, info = env.reset()

        assert obs.shape == (env.observation_size,)

    def test_with_regimes(self, sample_ohlcv, sample_regimes):
        """Test environment with regime labels."""
        env = CryptoTradingEnv(sample_ohlcv, regimes=sample_regimes)
        obs, info = env.reset()

        # First few regimes should be accessible
        assert env._get_current_regime() in ["bull", "bear", "sideways"]

    def test_factory_function(self, sample_ohlcv):
        """Test factory function."""
        env = create_trading_env(
            sample_ohlcv,
            reward_type="sharpe",
            commission=0.002,
            slippage=0.001,
            initial_capital=50000.0
        )

        assert env.config.initial_capital == 50000.0
        assert env.config.commission_rate == 0.002
        assert env.config.slippage_rate == 0.001


class TestPositionManagement:
    """Tests for position management functionality."""

    def test_position_updates_correctly(self, sample_ohlcv):
        """Test position tracks correctly."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        env.step(np.array([0.5]))
        assert env.position == 0.5

        env.step(np.array([0.5]))
        assert env.position == 0.5  # No change

        env.step(np.array([-0.3]))
        assert env.position == -0.3

    def test_position_clipping(self, sample_ohlcv):
        """Test position values are clipped."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        env.step(np.array([1.5]))
        assert env.position == 1.0

        env.step(np.array([-2.0]))
        assert env.position == -1.0


class TestRewardCalculation:
    """Tests for reward function calculation."""

    def test_pnl_reward(self, sample_ohlcv):
        """Test PnL reward."""
        config = TradingConfig(reward_type=RewardType.PNL)
        env = CryptoTradingEnv(sample_ohlcv, config=config)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(np.array([1.0]))
        assert isinstance(reward, float)

    def test_sharpe_reward(self, sample_ohlcv):
        """Test Sharpe ratio reward."""
        config = TradingConfig(reward_type=RewardType.SHARPE, window_size=10)
        env = CryptoTradingEnv(sample_ohlcv, config=config)
        env.reset()

        # Need several steps for Sharpe
        for _ in range(15):
            obs, reward, terminated, truncated, info = env.step(np.array([0.5]))
            assert isinstance(reward, float)
            assert not np.isnan(reward)


class TestTechnicalFeatures:
    """Tests for technical indicator features."""

    def test_technical_features_calculated(self, sample_ohlcv):
        """Test technical features are calculated."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        # Move forward to have window data
        for _ in range(25):
            env.step(np.array([0.5]))

        tech = env._calculate_technical_features()
        assert "returns" in tech
        assert "volatility" in tech
        assert "rsi" in tech
        assert "atr" in tech

        assert all(isinstance(v, float) for v in tech.values())


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_data(self):
        """Test with minimal data."""
        df = pd.DataFrame({
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000]
        })

        env = CryptoTradingEnv(df)
        obs, info = env.reset()

        # Should still work with minimal data
        assert isinstance(obs, np.ndarray)

    def test_single_step(self, sample_ohlcv):
        """Test single step episode."""
        env = CryptoTradingEnv(sample_ohlcv)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(np.array([1.0]))

        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
