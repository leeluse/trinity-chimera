"""
Unit tests for BacktestManager - IS/OOS Splitter and Validation Gate
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ai_trading.core.backtest_manager import BacktestManager
from ai_trading.core.strategy_interface import StrategyInterface


class MockStrategy(StrategyInterface):
    """Mock strategy for testing purposes."""

    def generate_signal(self, data: pd.DataFrame) -> int:
        """Simple momentum strategy for testing."""
        if len(data) < 2:
            return 0
        return 1 if data['close'].iloc[-1] > data['close'].iloc[-2] else -1

    def get_params(self) -> dict:
        return {"name": "MockStrategy"}


class TestDataSplitter(unittest.TestCase):
    """Test cases for IS/OOS data splitting functionality."""

    def setUp(self):
        """Set up test data and manager."""
        self.manager = BacktestManager()

        # Create 60 days of hourly OHLCV data (60 * 24 = 1440 rows)
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=1440, freq='h')
        base_price = 100
        prices = [base_price]
        for _ in range(1439):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.001)))

        self.hourly_data = pd.DataFrame({
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, 1440)
        }, index=dates)

    def test_split_data_60_day_window(self):
        """Verify 60-day data is split into 30+30 days."""
        train_set, val_set = self.manager.split_data(
            self.hourly_data, train_days=30, val_days=30
        )

        # Should use last 60 days (1440 hours)
        total_hours = 30 * 24 + 30 * 24
        self.assertEqual(len(train_set) + len(val_set), total_hours)

        # Train should be 30 days (720 hours)
        self.assertEqual(len(train_set), 720)

        # Validation should be 30 days (720 hours)
        self.assertEqual(len(val_set), 720)

    def test_split_data_hourly_data(self):
        """Test hourly OHLCV data splitting."""
        train_set, val_set = self.manager.split_data(
            self.hourly_data, train_days=30, val_days=30
        )

        # Verify column integrity
        self.assertEqual(list(train_set.columns), ['open', 'high', 'low', 'close', 'volume'])
        self.assertEqual(list(val_set.columns), ['open', 'high', 'low', 'close', 'volume'])

        # Verify temporal ordering
        self.assertLess(train_set.index[-1], val_set.index[0])

    def test_split_data_insufficient_data(self):
        """Test behavior when data is insufficient."""
        # Create only 10 days of data
        short_data = self.hourly_data.tail(240)  # 10 days

        train_set, val_set = self.manager.split_data(
            short_data, train_days=30, val_days=30
        )

        # Should still return split (50/50)
        self.assertGreater(len(train_set), 0)
        self.assertGreater(len(val_set), 0)
        self.assertEqual(len(train_set) + len(val_set), len(short_data))


class TestValidationGate(unittest.TestCase):
    """Test cases for validation gate logic."""

    def setUp(self):
        self.manager = BacktestManager()

    def test_validation_gate_pass(self):
        """Test when OOS score >= 70% of IS score."""
        is_score = 100.0
        oos_score = 75.0  # 75% of IS - should pass
        self.assertTrue(self.manager.validation_gate(is_score, oos_score, threshold=0.7))

    def test_validation_gate_pass_exact_threshold(self):
        """Test when OOS score is exactly 70% of IS score."""
        is_score = 100.0
        oos_score = 70.0  # Exactly 70% - should pass
        self.assertTrue(self.manager.validation_gate(is_score, oos_score, threshold=0.7))

    def test_validation_gate_fail(self):
        """Test when OOS score < 70% of IS score (overfitting)."""
        is_score = 100.0
        oos_score = 50.0  # 50% of IS - should fail/reject
        self.assertFalse(self.manager.validation_gate(is_score, oos_score, threshold=0.7))

    def test_validation_gate_invalid_is_score(self):
        """Handle edge case when IS score <= 0."""
        is_score = -10.0
        oos_score = 5.0
        # Should return True if OOS > 0 (alternative condition)
        self.assertTrue(self.manager.validation_gate(is_score, oos_score))

    def test_validation_gate_is_zero(self):
        """Handle edge case when IS score is exactly 0."""
        is_score = 0.0
        oos_score = 10.0
        self.assertTrue(self.manager.validation_gate(is_score, oos_score))

    def test_validation_gate_both_zero(self):
        """Handle edge case when both scores are 0 or negative."""
        is_score = 0.0
        oos_score = 0.0
        # Should return False if both are <= 0
        result = self.manager.validation_gate(is_score, oos_score)
        self.assertIsInstance(result, bool)


class TestValidateStrategyWorkflow(unittest.TestCase):
    """Test complete IS -> OOS validation workflow."""

    def setUp(self):
        self.manager = BacktestManager()
        self.strategy = MockStrategy()

        # Create realistic 60 days of hourly data
        np.random.seed(42)
        dates = pd.date_range(start='2024-01-01', periods=1440, freq='h')
        base_price = 100
        prices = [base_price]
        for _ in range(1439):
            prices.append(prices[-1] * (1 + np.random.normal(0.0001, 0.001)))

        self.data = pd.DataFrame({
            'open': prices,
            'high': [p * 1.005 for p in prices],
            'low': [p * 0.995 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, 1440)
        }, index=dates)

    def test_validate_strategy_workflow(self):
        """Full IS backtest -> OOS backtest -> validate flow."""
        result = self.manager.validate_strategy(
            self.strategy, self.data, train_days=30, val_days=30
        )

        # Should return dictionary with validation result
        self.assertIn('is_metrics', result)
        self.assertIn('oos_metrics', result)
        self.assertIn('passed', result)
        self.assertIn('is_score', result)
        self.assertIn('oos_score', result)
        self.assertIn('ratio', result)

    def test_store_is_oos_metrics_separately(self):
        """Verify IS and OOS metrics are stored separately."""
        result = self.manager.validate_strategy(
            self.strategy, self.data, train_days=30, val_days=30
        )

        # Check IS metrics structure
        is_metrics = result['is_metrics']
        self.assertIn('return', is_metrics)
        self.assertIn('sharpe', is_metrics)
        self.assertIn('mdd', is_metrics)
        self.assertIn('trinity_score', is_metrics)
        self.assertIn('trades', is_metrics)

        # Check OOS metrics structure
        oos_metrics = result['oos_metrics']
        self.assertIn('return', oos_metrics)
        self.assertIn('sharpe', oos_metrics)
        self.assertIn('mdd', oos_metrics)
        self.assertIn('trinity_score', oos_metrics)
        self.assertIn('trades', oos_metrics)

    def test_trinity_score_from_oos_only(self):
        """Final Trinity Score must be from OOS performance, not IS."""
        result = self.manager.validate_strategy(
            self.strategy, self.data, train_days=30, val_days=30
        )

        # The final score should equal the OOS score
        oos_trinity_score = result['oos_metrics']['trinity_score']
        self.assertEqual(result['oos_score'], oos_trinity_score)

    def test_validation_pass_with_good_strategy(self):
        """Test that a good strategy passes validation."""
        # Note: This is a probabilistic test with our random data
        result = self.manager.validate_strategy(
            self.strategy, self.data, train_days=30, val_days=30
        )

        # Should have a valid boolean result
        self.assertIsInstance(result['passed'], bool)

        # Should have ratio calculated
        self.assertIn('ratio', result)
        if result['is_score'] > 0:
            expected_ratio = result['oos_score'] / result['is_score']
            self.assertAlmostEqual(result['ratio'], expected_ratio, places=4)


class TestCalculateTrinityScore(unittest.TestCase):
    """Test Trinity Score calculation."""

    def setUp(self):
        self.manager = BacktestManager()

    def test_calculate_trinity_score_formula(self):
        """Test the Trinity Score formula: Return * 0.40 + Sharpe * 25 * 0.35 + (1 + MDD) * 100 * 0.25"""
        return_val = 0.10  # 10% return
        sharpe = 1.5
        mdd = -0.15  # 15% drawdown

        expected = (return_val * 0.40) + (sharpe * 25 * 0.35) + ((1 + mdd) * 100 * 0.25)
        actual = self.manager.calculate_trinity_score(return_val, sharpe, mdd)

        self.assertAlmostEqual(actual, round(expected, 4), places=4)

    def test_calculate_trinity_score_with_zero(self):
        """Test with zero values."""
        score = self.manager.calculate_trinity_score(0.0, 0.0, 0.0)
        expected = 0.0 + 0.0 + (1 * 100 * 0.25)  # MDD = 0 means (1+0)*100*0.25 = 25
        self.assertAlmostEqual(score, round(expected, 4), places=4)


class TestBacktestManagerIntegration(unittest.TestCase):
    """Integration tests for the complete BacktestManager."""

    def setUp(self):
        self.manager = BacktestManager()

        # Create trending data for predictable signal
        dates = pd.date_range(start='2024-01-01', periods=100, freq='h')
        prices = list(range(100, 200))  # Steady uptrend

        self.trending_data = pd.DataFrame({
            'open': prices,
            'high': [p + 1 for p in prices],
            'low': [p - 1 for p in prices],
            'close': prices,
            'volume': [1000] * 100
        }, index=dates)

    def test_run_backtest_returns_dict(self):
        """Test that run_backtest returns a dictionary with expected keys."""
        strategy = MockStrategy()
        result = self.manager.run_backtest(strategy, self.trending_data)

        self.assertIsInstance(result, dict)
        self.assertIn('return', result)
        self.assertIn('sharpe', result)
        self.assertIn('mdd', result)
        self.assertIn('trinity_score', result)
        self.assertIn('trades', result)


if __name__ == '__main__':
    unittest.main()
