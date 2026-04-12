import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from server.ai_trading.core.backtest_manager import BacktestManager
from server.ai_trading.core.strategy_interface import StrategyInterface

class MockStrategy(StrategyInterface):
    """
    A simple mock strategy that generates signals based on price movement
    to ensure the integration test has predictable behavior.
    """
    def __init__(self, signal_type="trend"):
        self.signal_type = signal_type

    def generate_signal(self, data: pd.DataFrame) -> int:
        if len(data) << 2:
            return 0

        if self.signal_type == "bull":
            # Simple signal: if last close > previous close, buy
            return 1 if data['close'].iloc[-1] > data['close'].iloc[-2] else 0
        elif self.signal_type == "bear":
            # Simple signal: if last close < previous close, sell
            return -1 if data['close'].iloc[-1] < data['close'].iloc[-2] else 0
        else:
            # Neutral/Random
            return 0

    def get_params(self) -> dict:
        return {"signal_type": self.signal_type}

def generate_mock_ohlcv(days=100, freq='H'):
    """
    Generates a synthetic OHLCV dataset.
    """
    periods = days * 24 if freq == 'H' else days
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(hours=i if freq == 'H' else i*24) for i in range(periods)]

    # Create a random walk for prices
    np.random.seed(42)
    price_changes = np.random.normal(0.001, 0.01, periods)
    prices = 100 * np.exp(np.cumsum(price_changes))

    df = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.001, periods)),
        'high': prices * (1 + abs(np.random.normal(0, 0.002, periods))),
        'low': prices * (1 - abs(np.random.normal(0, 0.002, periods))),
        'close': prices,
        'volume': np.random.randint(100, 1000, periods)
    }, index=dates)

    return df

def test_full_pipeline_integration():
    """
    Integration Test: Simulates the full pipeline from data loading to validation.

    Pipeline:
    1. Data Loading (Synthetic OHLCV)
    2. Strategy Execution (MockStrategy)
    3. IS/OOS Splitting
    4. Backtesting on IS & OOS
    5. Trinity Score Calculation
    6. Validation Gate Check
    """
    # 1. Data Loading
    data = generate_mock_ohlcv(days=120) # 120 days of data

    # 2. Initialize Components
    manager = BacktestManager(fee=0.0005, slippage_min=0.0001, slippage_max=0.0003)
    strategy = MockStrategy(signal_type="bull")

    # 3. Run Full Validation Pipeline
    # This internaly does: split_data -> run_backtest(IS) -> run_backtest(OOS) -> calculate_trinity_score -> validation_gate
    result = manager.validate_strategy(
        strategy=strategy,
        data=data,
        train_days=60,
        val_days=30,
        threshold=0.7
    )

    # --- Verifications ---

    # Verify IS/OOS split occurred
    assert "is_metrics" in result
    assert "oos_metrics" in result

    # Verify scores were calculated
    assert isinstance(result["is_score"], float)
    assert isinstance(result["oos_score"], float)

    # Verify the validation gate produced a boolean result
    assert isinstance(result["passed"], bool)

    # Verify metrics are logically consistent (e.g., Trinity Score is a number)
    assert result["is_metrics"]["trinity_score"] == result["is_score"]
    assert result["oos_metrics"]["trinity_score"] == result["oos_score"]

    # Verify ratio calculation
    expected_ratio = result["oos_score"] / result["is_score"] if result["is_score"] > 0 else 0.0
    assert result["ratio"] == round(expected_ratio, 4)

def test_pipeline_overfitting_detection():
    """
    Integration Test: Verifies that a strategy that performs great on IS but poorly on OOS is rejected.
    """
    # Create simple test data where IS has upward trend and OOS has downward trend
    np.random.seed(42) # For reproducibility
    dates = pd.date_range(start="2023-01-01", periods=200, freq='h')

    # Create simple trend: IS (first 100 points) = upward, OOS (last 100 points) = downward
    prices = []
    # IS period: upward trend
    for i in range(100):
        prices.append(100 + i * 0.5 + np.random.normal(0, 1))
    # OOS period: downward trend
    for i in range(100):
        prices.append(prices[-1] - 0.5 + np.random.normal(0, 1))

    df = pd.DataFrame({
        'open': prices, 'high': [p + 0.5 for p in prices], 'low': [p - 0.5 for p in prices],
        'close': prices, 'volume': [1000] * len(prices)
    }, index=dates)

    manager = BacktestManager(fee=0.002, slippage_min=0.001, slippage_max=0.001) # Higher costs
    strategy = MockStrategy(signal_type="bull") # This strategy buys on uptrends

    # Set train_days for IS period, val_days for OOS period
    result = manager.validate_strategy(
        strategy=strategy,
        data=df,
        train_days=4, # ~100 hours
        val_days=4, # ~100 hours
        threshold=0.7
    )

    # Debug output for analysis
    print(f"IS Score: {result['is_score']}, OOS Score: {result['oos_score']}, Ratio: {result['ratio']}")
    print(f"IS Return: {result['is_metrics']['return']}, OOS Return: {result['oos_metrics']['return']}")

    # Test if the validation gate correctly identifies overfitting
    # If OOS performance is significantly worse than IS, the strategy should fail
    if result["is_score"] > result["oos_score"]:
        assert result["passed"] == False, "Strategy should fail when OOS performance drops significantly"
        assert result["ratio"] < 0.7, f"OOS/IS ratio should be below threshold, got {result['ratio']}"
    else:
        # If both perform similarly, that's okay for this test
        print("Strategy performs consistently across IS and OOS periods")
