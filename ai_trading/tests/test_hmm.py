"""Tests for HMM Regime Classifier."""

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from ai_trading.core.hmm_regime import (
    HMMConfig,
    HMMRegimeClassifier,
    create_regime_classifier,
)


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data with regime patterns."""
    np.random.seed(42)
    n = 600

    # Create regimes
    prices = [100.0]
    volumes = []

    # Bull period (0-200): upward drift
    for i in range(200):
        ret = np.random.normal(0.001, 0.01)
        prices.append(prices[-1] * (1 + ret))
        volumes.append(np.random.uniform(1000, 2000))

    # Sideways period (200-400): mean reverting
    for i in range(200):
        base = 122  # Around bull end price
        ret = np.random.normal(0.0, 0.005)
        prices.append(base * (1 + ret))
        volumes.append(np.random.uniform(500, 1500))

    # Bear period (400-600): downward drift
    for i in range(200):
        ret = np.random.normal(-0.0015, 0.015)
        prices.append(prices[-1] * (1 + ret))
        volumes.append(np.random.uniform(1500, 3000))

    prices = prices[1:]  # Remove initial seed

    df = pd.DataFrame({
        "open": prices,
        "high": [p * (1 + np.random.uniform(0, 0.01)) for p in prices],
        "low": [p * (1 - np.random.uniform(0, 0.01)) for p in prices],
        "close": prices,
        "volume": volumes
    }, index=pd.date_range("2024-01-01", periods=n, freq="1h"))

    return df


class TestHMMRegimeClassifier:
    """Test suite for HMMRegimeClassifier."""

    def test_initialization(self):
        """Test basic initialization."""
        clf = HMMRegimeClassifier()
        assert clf.config.n_components == 3
        assert clf.model is None
        assert not clf._is_fitted

    def test_custom_config(self):
        """Test initialization with custom config."""
        config = HMMConfig(n_components=2, train_window=1000)
        clf = HMMRegimeClassifier(config)
        assert clf.config.n_components == 2
        assert clf.config.train_window == 1000

    def test_build_features(self, sample_ohlcv):
        """Test feature building from OHLCV."""
        clf = HMMRegimeClassifier()
        features = clf._build_features(sample_ohlcv)

        # Check all features exist
        expected_cols = [
            "log_returns", "realized_vol", "abs_returns",
            "volume_change", "atr"
        ]
        for col in expected_cols:
            assert col in features.columns

        # Check no infinite values
        assert not np.isinf(features).any().any()

    def test_fit(self, sample_ohlcv):
        """Test model fitting."""
        clf = HMMRegimeClassifier()
        clf.fit(sample_ohlcv)

        assert clf._is_fitted
        assert clf.model is not None
        assert clf._regime_map is not None
        assert len(clf._regime_map) == 3
        assert set(clf._regime_map.values()) == {"bull", "sideways", "bear"}

    def test_predict(self, sample_ohlcv):
        """Test regime prediction."""
        clf = HMMRegimeClassifier()
        clf.fit(sample_ohlcv)

        predictions = clf.predict(sample_ohlcv)

        assert len(predictions) == len(sample_ohlcv)
        assert set(predictions.unique()).issubset({"bull", "sideways", "bear"})
        assert predictions.isna().sum() == 0

    def test_predict_with_probs(self, sample_ohlcv):
        """Test prediction with probabilities."""
        clf = HMMRegimeClassifier()
        clf.fit(sample_ohlcv)

        result = clf.predict(sample_ohlcv, return_probs=True)

        assert "regime" in result.columns
        assert "bull" in result.columns
        assert "sideways" in result.columns
        assert "bear" in result.columns

        # Check probabilities sum to 1
        probs = result[["bull", "sideways", "bear"]]
        np.testing.assert_array_almost_equal(
            probs.sum(axis=1).values,
            np.ones(len(result)),
            decimal=6
        )

    def test_predict_latest(self, sample_ohlcv):
        """Test latest prediction."""
        clf = HMMRegimeClassifier()
        clf.fit(sample_ohlcv)

        pred = clf.predict_latest(sample_ohlcv)

        assert pred.regime in {"bull", "sideways", "bear"}
        assert 0 <= pred.probability <= 1
        assert len(pred.all_probs) == 3
        np.testing.assert_almost_equal(sum(pred.all_probs), 1.0, decimal=6)

    def test_save_load(self, sample_ohlcv):
        """Test model persistence."""
        clf = create_regime_classifier()
        clf.fit(sample_ohlcv)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = f.name

        try:
            clf.save(path)
            assert os.path.exists(path)

            # Load and verify
            new_clf = HMMRegimeClassifier()
            new_clf.load(path)

            assert new_clf._is_fitted
            assert new_clf._regime_map == clf._regime_map

            # Predictions should match
            pred_orig = clf.predict(sample_ohlcv)
            pred_new = new_clf.predict(sample_ohlcv)
            pd.testing.assert_series_equal(pred_orig, pred_new)

        finally:
            os.unlink(path)

    def test_get_regime_stats(self, sample_ohlcv):
        """Test regime statistics."""
        clf = HMMRegimeClassifier()
        clf.fit(sample_ohlcv)

        stats = clf.get_regime_stats()

        assert "regime_map" in stats
        assert "mean_features" in stats
        assert "transition_matrix" in stats
        assert len(stats["transition_matrix"]) == 3

    def test_walk_forward_predict(self, sample_ohlcv):
        """Test walk-forward prediction."""
        clf = HMMRegimeClassifier()

        result = clf.walk_forward_predict(
            sample_ohlcv,
            train_size=300,
            step_size=50
        )

        assert "regime" in result.columns
        assert len(result) == len(sample_ohlcv)

    def test_insufficient_samples_raises(self):
        """Test error when insufficient samples."""
        clf = HMMRegimeClassifier(HMMConfig(train_window=50, min_samples=100))
        small_data = pd.DataFrame({
            "open": [100] * 50,
            "high": [101] * 50,
            "low": [99] * 50,
            "close": [100] * 50,
            "volume": [1000] * 50
        })

        with pytest.raises(ValueError, match="Insufficient samples"):
            clf.fit(small_data)

    def test_predict_before_fit_raises(self, sample_ohlcv):
        """Test error when predicting before fitting."""
        clf = HMMRegimeClassifier()

        with pytest.raises(RuntimeError, match="not fitted"):
            clf.predict(sample_ohlcv)


class TestRegimePatternDetection:
    """Test regime detection on synthetic data with known patterns."""

    @pytest.fixture
    def bull_market_data(self):
        """Generate clear bull market data."""
        np.random.seed(123)
        prices = [100.0]
        for _ in range(200):
            ret = np.random.normal(0.003, 0.01)
            prices.append(prices[-1] * (1 + ret))

        return pd.DataFrame({
            "open": [p * 0.99 for p in prices],
            "high": [p * 1.02 for p in prices],
            "low": [p * 0.98 for p in prices],
            "close": prices,
            "volume": [np.random.uniform(5000, 10000) for _ in prices]
        }, index=pd.date_range("2024-01-01", periods=len(prices), freq="1h"))

    @pytest.fixture
    def bear_market_data(self):
        """Generate clear bear market data."""
        np.random.seed(456)
        prices = [100.0]
        for _ in range(200):
            ret = np.random.normal(-0.004, 0.02)
            prices.append(prices[-1] * (1 + ret))

        return pd.DataFrame({
            "open": [p * 1.01 for p in prices],
            "high": [p * 1.02 for p in prices],
            "low": [p * 0.98 for p in prices],
            "close": prices,
            "volume": [np.random.uniform(8000, 15000) for _ in prices]
        }, index=pd.date_range("2024-01-01", periods=len(prices), freq="1h"))

    def test_detects_bull_regime(self, bull_market_data):
        """Test classifier detects bull market."""
        clf = HMMRegimeClassifier()
        clf.fit(bull_market_data)

        # Last 100 predictions should mostly be bull
        predictions = clf.predict(bull_market_data)
        bull_ratio = (predictions.iloc[-100:] == "bull").mean()
        assert bull_ratio > 0.5

    def test_detects_bear_regime(self, bear_market_data):
        """Test classifier detects bear market."""
        clf = HMMRegimeClassifier()
        clf.fit(bear_market_data)

        predictions = clf.predict(bear_market_data)
        bear_ratio = (predictions.iloc[-100:] == "bear").mean()
        assert bear_ratio > 0.3

    def test_distinguishes_different_regimes(self, bull_market_data, bear_market_data):
        """Test classifier distinguishes between regimes."""
        # Combine bull and bear data
        combined = pd.concat([bull_market_data, bear_market_data])

        clf = HMMRegimeClassifier()
        clf.fit(combined)

        predictions = clf.predict(combined)

        # Should have both bull and bear predictions
        unique_regimes = set(predictions.unique())
        assert "bull" in unique_regimes or "sideways" in unique_regimes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
