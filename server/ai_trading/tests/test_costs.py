"""
Unit tests for Conservative Cost Model
Tests the apply_trading_costs method in BacktestManager
"""

import unittest
import numpy as np
import pandas as pd
from server.ai_trading.core.backtest_manager import BacktestManager


class TestTradingCosts(unittest.TestCase):
    """Test cases for trading cost application."""

    def setUp(self):
        """Set up BacktestManager with fixed costs for deterministic testing."""
        self.bm = BacktestManager(
            fee=0.0005,  # 0.05% as per spec
            slippage_min=0.0001,  # 0.01%
            slippage_max=0.0001   # Fixed at 0.01% for testability
        )

    def test_apply_trading_costs_buy(self):
        """Verify buy price is correctly increased by fee + slippage."""
        price = 100.0
        expected = price * (1 + 0.0005 + 0.0001)  # 100 * 1.0006 = 100.06
        result = self.bm.apply_trading_costs(price, 1)
        self.assertAlmostEqual(result, 100.06, places=5)

    def test_apply_trading_costs_sell(self):
        """Verify sell price is correctly decreased by fee + slippage."""
        price = 100.0
        expected = price * (1 - (0.0005 + 0.0001))  # 100 * 0.9994 = 99.94
        result = self.bm.apply_trading_costs(price, -1)
        self.assertAlmostEqual(result, 99.94, places=5)

    def test_apply_trading_costs_with_slippage_range(self):
        """Verify random slippage stays within bounds."""
        bm = BacktestManager(
            fee=0.0005,
            slippage_min=0.0001,
            slippage_max=0.0003
        )
        price = 100.0

        # Run multiple times to cover slippage range
        for _ in range(20):
            buy_result = bm.apply_trading_costs(price, 1)
            sell_result = bm.apply_trading_costs(price, -1)

            # Buy: price * 1.0006 to 1.0008
            assert 100.06 <= buy_result <= 100.08
            # Sell: price * 0.9994 to 0.9992
            assert 99.92 <= sell_result <= 99.94

    def test_multiple_trades_compound_costs(self):
        """Verify costs compound correctly across multiple trades."""
        initial_price = 100.0
        num_round_trips = 20  # 20 buy + 20 sell

        total_value = initial_price
        for _ in range(num_round_trips):
            # Buy with costs
            buy_price = self.bm.apply_trading_costs(total_value, 1)
            # Sell with costs
            total_value = self.bm.apply_trading_costs(buy_price, -1)

        # Each round trip loses ~(1.0006 * 0.9994 - 1) = ~0.12% per round
        expected_decay = (1.0006 * 0.9994) ** num_round_trips
        expected_value = initial_price * expected_decay
        self.assertAlmostEqual(total_value, expected_value, delta=0.01)


class ZeroReturnStrategy:
    """Mock strategy that buys at index 0 and sells at index 1 with same price."""

    def generate_signal(self, data):
        idx = len(data) - 1
        if idx == 0:
            return 1  # Buy
        if idx == 1:
            return -1  # Sell
        return 0

    def get_params(self):
        return {"name": "ZeroReturnStrategy"}


class TestCostImpactOnReturns(unittest.TestCase):
    """Test that costs negatively impact strategy returns."""

    def test_zero_return_strategy_becomes_loss_with_costs(self):
        """A strategy with zero theoretical return should show loss after costs."""
        bm = BacktestManager(fee=0.0005, slippage_min=0.0001, slippage_max=0.0001)

        # Create data with flat prices (no price change)
        data = pd.DataFrame({
            'close': [100.0, 100.0],
        }, index=pd.date_range('2024-01-01', periods=2, freq='D'))

        strategy = ZeroReturnStrategy()
        results = bm.run_backtest(strategy, data)

        # Should be negative due to fees/slippage
        assert results['return'] < 0
        # Trade count = number of round-trips (1 buy + 1 sell = 1 round-trip = 1 trade recorded)
        assert results['trades'] == 1

    def test_costs_reduce_positive_return(self):
        """Verify that positive strategic returns are reduced by costs."""
        bm = BacktestManager(fee=0.0005, slippage_min=0.0001, slippage_max=0.0001)

        # Rising prices (10% gain without costs)
        data = pd.DataFrame({
            'close': [100.0, 110.0],
        }, index=pd.date_range('2024-01-01', periods=2, freq='D'))

        strategy = ZeroReturnStrategy()
        results = bm.run_backtest(strategy, data)

        # Return should be less than 10% due to costs
        assert results['return'] < 0.10


if __name__ == '__main__':
    unittest.main()
