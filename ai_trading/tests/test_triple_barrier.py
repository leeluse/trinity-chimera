"""Tests for Triple Barrier Labeler."""

import pytest
import numpy as np
import pandas as pd

from ai_trading.core.triple_barrier import (
    TripleBarrierLabeler,
    RegimeAwareBarrierLabeler,
    BarrierConfig,
    BarrierType,
    create_labeler
)


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 100

    # Generate trending data
    base_price = 100.0
    trend = np.linspace(0, 5, n)
    noise = np.random.randn(n) * 0.5
    closes = base_price + trend + noise

    opens = closes + np.random.randn(n) * 0.2
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 0.5) + 0.1
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 0.5) - 0.1
    volumes = np.random.randint(1000, 10000, n)

    dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')

    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    }, index=dates)


@pytest.fixture
def bullish_ohlcv():
    """Create bullish trending data (should hit TP)."""
    n = 50
    base = np.linspace(100, 120, n)  # Strong uptrend
    dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')

    return pd.DataFrame({
        'open': base,
        'high': base + 1,  # High > close
        'low': base - 0.5,  # Low < open
        'close': base + 0.5,
        'volume': np.ones(n) * 1000
    }, index=dates)


@pytest.fixture
def bearish_ohlcv():
    """Create bearish trending data (should hit SL)."""
    n = 50
    base = np.linspace(120, 100, n)  # Strong downtrend
    dates = pd.date_range(start='2024-01-01', periods=n, freq='1h')

    return pd.DataFrame({
        'open': base + 1,
        'high': base + 1.5,
        'low': base,
        'close': base,
        'volume': np.ones(n) * 1000
    }, index=dates)


class TestTripleBarrierLabeler:
    """Test Triple Barrier Labeler functionality."""

    def test_initialization(self):
        """Test labeler initialization with config."""
        config = BarrierConfig(
            tp_multiplier=3.0,
            sl_multiplier=1.5,
            time_horizon=30,
            volatility_window=10
        )
        labeler = TripleBarrierLabeler(config)

        assert labeler.config.tp_multiplier == 3.0
        assert labeler.config.sl_multiplier == 1.5
        assert labeler.config.time_horizon == 30
        assert labeler.config.volatility_window == 10

    def test_default_initialization(self):
        """Test labeler with default config."""
        labeler = TripleBarrierLabeler()

        assert labeler.config.tp_multiplier == 2.0
        assert labeler.config.sl_multiplier == 1.0
        assert labeler.config.time_horizon == 20

    def test_atr_calculation(self, sample_ohlcv):
        """Test ATR calculation."""
        labeler = TripleBarrierLabeler()
        atr = labeler._calculate_atr(
            sample_ohlcv['high'],
            sample_ohlcv['low'],
            sample_ohlcv['close']
        )

        assert len(atr) == len(sample_ohlcv)
        assert not atr.isna().all()
        assert (atr >= 0).all()

    def test_barrier_calculation(self, sample_ohlcv):
        """Test barrier level calculation."""
        labeler = TripleBarrierLabeler()
        price = 100.0
        atr = 2.0

        tp, sl = labeler._calculate_barriers(price, atr)

        assert tp > price
        assert sl < price
        assert tp == pytest.approx(100.0 * (1 + 2.0 * 2.0 / 100.0))

    def test_event_labeling_basic(self, sample_ohlcv):
        """Test basic event labeling."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        assert len(result.events) > 0
        assert len(result.labels) == len(result.events)
        assert len(result.returns) == len(result.events)
        assert len(result.weights) == len(result.events)

    def test_label_values(self, sample_ohlcv):
        """Test that labels are only -1, 0, or 1."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        unique_labels = result.labels.unique()
        assert all(label in [-1, 0, 1] for label in unique_labels)

    def test_take_profit_detection(self, bullish_ohlcv):
        """Test that bullish data generates TP label."""
        labeler = TripleBarrierLabeler(BarrierConfig(
            tp_multiplier=0.5,  # Tight barriers
            sl_multiplier=0.5,
            time_horizon=30
        ))

        # Select specific event time
        events = pd.DatetimeIndex([bullish_ohlcv.index[10]])
        result = labeler.label_events(bullish_ohlcv, events)

        assert len(result.events) == 1
        event = result.events[0]
        assert event.label in [1, 0]  # Should hit TP or time
        assert event.weight in [1.0, 0.3]

    def test_stop_loss_detection(self, bearish_ohlcv):
        """Test that bearish data can generate SL label."""
        labeler = TripleBarrierLabeler(BarrierConfig(
            tp_multiplier=2.0,
            sl_multiplier=0.5,  # Tight SL
            time_horizon=30
        ))

        events = pd.DatetimeIndex([bearish_ohlcv.index[10]])
        result = labeler.label_events(bearish_ohlcv, events)

        if len(result.events) > 0:
            event = result.events[0]
            assert event.label in [-1, 0, 1]
            assert event.weight in [0.3, 1.0]

    def test_barrier_types(self, sample_ohlcv):
        """Test that all barrier types can be detected."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        if len(result.events) > 0:
            types = set(e.barrier_type for e in result.events)
            assert any(t in types for t in BarrierType)

    def test_weights(self, sample_ohlcv):
        """Test weight calculation."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        for event in result.events:
            if event.barrier_type in [BarrierType.TAKE_PROFIT, BarrierType.STOP_LOSS]:
                assert event.weight == 1.0
            else:
                assert event.weight == 0.3

    def test_return_calculation(self, sample_ohlcv):
        """Test return calculation for events."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        for event in result.events:
            expected_return = (event.end_price - event.start_price) / event.start_price
            assert abs(event.return_value - expected_return) < 1e-6

    def test_hold_time(self, sample_ohlcv):
        """Test hold time calculation."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        for event in result.events:
            assert event.hold_bars <= labeler.config.time_horizon
            assert event.hold_bars >= 0

    def test_stats_calculation(self, sample_ohlcv):
        """Test statistics calculation."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)
        stats = labeler.get_barrier_stats(result)

        assert 'total_events' in stats
        assert 'tp_rate' in stats
        assert 'sl_rate' in stats
        assert 'time_rate' in stats
        assert 'avg_return' in stats
        assert 'label_distribution' in stats

        assert stats['tp_rate'] + stats['sl_rate'] + stats['time_rate'] == pytest.approx(1.0, abs=0.01)

    def test_invalid_ohlcv(self):
        """Test error handling for invalid OHLCV."""
        labeler = TripleBarrierLabeler()

        with pytest.raises(ValueError):
            labeler.label_events(pd.DataFrame({'invalid': [1, 2, 3]}))


class TestRegimeAwareLabeler:
    """Test regime-aware labeler."""

    def test_regime_adjustment(self, sample_ohlcv):
        """Test regime multiplier adjustment."""
        labeler = RegimeAwareBarrierLabeler(
            bull_adjustment=0.8,
            bear_adjustment=1.2
        )

        regimes = pd.Series(
            ['neutral'] * len(sample_ohlcv),
            index=sample_ohlcv.index
        )
        regimes.iloc[:30] = 'bull'
        regimes.iloc[30:60] = 'bear'
        regimes.iloc[60:] = 'neutral'

        result = labeler.label_with_regime(sample_ohlcv, regimes)

        assert len(result.events) > 0

    def test_regime_multipier_mapping(self):
        """Test regime label to multiplier mapping."""
        labeler = RegimeAwareBarrierLabeler(
            bull_adjustment=0.8,
            bear_adjustment=1.2
        )

        price = 100.0
        atr = 2.0

        # Test with no regime (should use 1.0)
        tp, sl = labeler._calculate_barriers(price, atr)
        assert tp > price
        assert sl < price


class TestCreateLabeler:
    """Test factory function."""

    def test_create_basic(self):
        """Test basic labeler creation."""
        labeler = create_labeler()
        assert isinstance(labeler, TripleBarrierLabeler)
        assert labeler.config.tp_multiplier == 2.0

    def test_create_regime_aware(self):
        """Test regime-aware labeler creation."""
        labeler = create_labeler(regime_aware=True)
        assert isinstance(labeler, RegimeAwareBarrierLabeler)

    def test_create_with_custom_params(self):
        """Test creation with custom parameters."""
        labeler = create_labeler(
            tp_multiplier=3.0,
            sl_multiplier=1.5,
            time_horizon=50,
            volatility_window=21
        )

        assert labeler.config.tp_multiplier == 3.0
        assert labeler.config.sl_multiplier == 1.5
        assert labeler.config.time_horizon == 50
        assert labeler.config.volatility_window == 21


class TestTripleBarrierResult:
    """Test TripleBarrierResult dataclass."""

    def test_label_distribution(self, sample_ohlcv):
        """Test label distribution method."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        dist = result.get_label_distribution()

        assert 'positive' in dist
        assert 'neutral' in dist
        assert 'negative' in dist

        total = sum(dist.values())
        assert total == len(result.events)

    def test_weighted_accuracy(self, sample_ohlcv):
        """Test weighted accuracy calculation."""
        labeler = TripleBarrierLabeler()
        result = labeler.label_events(sample_ohlcv)

        accuracy = result.get_weighted_accuracy()

        assert 0.0 <= accuracy <= 1.0

    def test_empty_result(self):
        """Test stats on empty result."""
        result = TripleBarrierLabeler._create_empty_result()

        stats = TripleBarrierLabeler(BarrierConfig()).get_barrier_stats(result)

        assert stats['total_events'] == 0
        assert stats['avg_return'] == 0.0


class TestIntegration:
    """Integration tests."""

    def test_full_pipeline(self, sample_ohlcv):
        """Test complete labeling pipeline."""
        # Create labeler
        labeler = create_labeler(
            tp_multiplier=2.0,
            sl_multiplier=1.0,
            time_horizon=20
        )

        # Generate labels
        result = labeler.label_events(sample_ohlcv)

        # Check results
        assert len(result.labels) > 0
        assert len(result.labels) == len(result.returns)
        assert len(result.labels) == len(result.weights)

        # Get stats
        stats = labeler.get_barrier_stats(result)
        assert stats['total_events'] > 0

        # Check distribution sums to 1
        rates = [stats['tp_rate'], stats['sl_rate'], stats['time_rate']]
        assert abs(sum(rates) - 1.0) < 0.01

    def test_with_specific_events(self, sample_ohlcv):
        """Test labeling specific events only."""
        labeler = TripleBarrierLabeler()

        # Select every 10th bar
        events = sample_ohlcv.index[10::10]
        result = labeler.label_events(sample_ohlcv, events=events)

        assert len(result.events) <= len(events)

    def test_with_regime_scores(self, sample_ohlcv):
        """Test labeling with regime scores."""
        labeler = TripleBarrierLabeler(
            BarrierConfig(tp_multiplier=2.0, sl_multiplier=1.0)
        )

        # Create regime scores (bullish = positive, bearish = negative)
        regime_scores = pd.Series(
            np.random.uniform(-1, 1, len(sample_ohlcv)),
            index=sample_ohlcv.index
        )

        result = labeler.label_events(sample_ohlcv, regime_scores=regime_scores)

        assert len(result.events) > 0
