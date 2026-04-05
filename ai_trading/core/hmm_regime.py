"""Hidden Markov Model (HMM) Regime Classifier for market regime detection.

This module implements a Gaussian HMM for classifying market regimes into
three states: bull, sideways, and bear markets.

Reference:
- Rabiner, L. (1989). "A tutorial on hidden Markov models and selected
  applications in speech recognition"
- Dean Fantazzini (2020), "The Recent Sell-off in US Equity Markets:
  Did Regime-Switching Models Help?"
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np
import pandas as pd
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler


@dataclass
class HMMConfig:
    """Configuration for HMM Regime Classifier.

    Attributes:
        n_components: Number of hidden states (regimes) - default 3 (bull, sideways, bear)
        n_features: Number of features for HMM training (default: 5)
        train_window: Window size for training (default: 500 bars)
        predict_window: Window size for prediction (default: 50 bars)
        volatility_window: Window for rolling volatility calculation (default: 20)
        min_samples: Minimum samples required for training (default: 100)
        random_state: Random seed for reproducibility
        n_iter: Maximum iterations for convergence (default: 100)
        tol: Convergence tolerance (default: 1e-4)
    """
    n_components: int = 3
    n_features: int = 5
    train_window: int = 500
    predict_window: int = 50
    volatility_window: int = 20
    min_samples: int = 100
    random_state: int = 42
    n_iter: int = 100
    tol: float = 1e-4


@dataclass
class RegimePrediction:
    """Prediction output from HMM Regime Classifier.

    Attributes:
        regime: Predicted regime ('bull', 'sideways', 'bear')
        regime_idx: Integer index of regime (0, 1, 2)
        probability: Probability of the predicted regime
        all_probs: Probability distribution over all regimes
        mean_return: Mean return of the predicted regime
        volatility: Volatility estimate of the predicted regime
    """
    regime: Literal["bull", "sideways", "bear"]
    regime_idx: int
    probability: float
    all_probs: np.ndarray
    mean_return: float
    volatility: float


class HMMRegimeClassifier:
    """HMM-based market regime classifier.

    Classifies market conditions into three regimes:
    - Bull: High returns, moderate volatility
    - Sideways: Near-zero returns, low volatility
    - Bear: Negative returns, high volatility

    Uses walk-forward learning with 500-bar training windows and
    50-bar prediction horizons.
    """

    REGIME_LABELS = ["bear", "sideways", "bull"]  # Will be auto-aligned

    def __init__(self, config: Optional[HMMConfig] = None):
        """Initialize HMM classifier.

        Args:
            config: HMM configuration (uses defaults if None)
        """
        self.config = config or HMMConfig()
        self.model: Optional[hmm.GaussianHMM] = None
        self.scaler = StandardScaler()
        self._regime_map: Optional[dict[int, str]] = None
        self._is_fitted = False
        self._feature_cols = [
            "log_returns",
            "realized_vol",
            "abs_returns",
            "volume_change",
            "atr"
        ]

    def _build_features(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Build HMM features from OHLCV data.

        Features:
        - log_returns: Logarithmic returns (log(close/close_prev))
        - realized_vol: Rolling volatility of log returns
        - abs_returns: Absolute value of log returns
        - volume_change: Percentage change in volume
        - atr: Average True Range as proxy for volatility

        Args:
            ohlcv: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']

        Returns:
            DataFrame with engineered features
        """
        df = ohlcv.copy()

        # Log returns
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

        # Realized volatility (annualized rolling std of log returns)
        df["realized_vol"] = (
            df["log_returns"]
            .rolling(window=self.config.volatility_window, min_periods=5)
            .std() * np.sqrt(365)
        )

        # Absolute returns
        df["abs_returns"] = df["log_returns"].abs()

        # Volume change percentage
        df["volume_change"] = df["volume"].pct_change()

        # ATR (Average True Range)
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = true_range.rolling(window=14, min_periods=5).mean()

        # Normalize ATR by price
        df["atr"] = df["atr"] / df["close"]

        return df

    def _prepare_training_data(self, features: pd.DataFrame) -> np.ndarray:
        """Prepare feature matrix for HMM training.

        Args:
            features: DataFrame with feature columns

        Returns:
            Scaled feature array [n_samples, n_features]
        """
        # Select feature columns
        feat_df = features[self._feature_cols].dropna()

        if len(feat_df) < self.config.min_samples:
            raise ValueError(
                f"Insufficient samples: {len(feat_df)} < {self.config.min_samples}"
            )

        # Scale features
        X = self.scaler.fit_transform(feat_df)

        return X

    def _prepare_inference_data(self, features: pd.DataFrame) -> np.ndarray:
        """Prepare features for inference using fitted scaler.

        Args:
            features: DataFrame with feature columns

        Returns:
            Scaled feature array
        """
        feat_df = features[self._feature_cols].values
        return self.scaler.transform(feat_df)

    def _align_regime_labels(
        self,
        returns: np.ndarray,
        hidden_states: np.ndarray
    ) -> dict[int, str]:
        """Align HMM hidden states to regime labels based on mean returns.

        The HMM's hidden states are arbitrary numbers (0, 1, 2) that don't
correspond to specific regimes. This method aligns them based on the mean
        log returns of each state: highest = bull, lowest = bear, middle = sideways.

        Args:
            returns: Array of log returns
            hidden_states: Array of hidden state assignments

        Returns:
            Mapping from state index to regime label
        """
        state_returns = {}
        for state in range(self.config.n_components):
            mask = hidden_states == state
            if mask.sum() > 0:
                state_returns[state] = returns[mask].mean()
            else:
                state_returns[state] = 0.0

        # Sort states by mean return (descending)
        sorted_states = sorted(
            state_returns.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Assign labels: highest = bull, middle = sideways, lowest = bear
        regime_map = {}
        regime_map[sorted_states[0][0]] = "bull"   # Highest returns
        regime_map[sorted_states[1][0]] = "sideways"  # Middle
        regime_map[sorted_states[2][0]] = "bear"   # Lowest returns

        return regime_map

    def fit(
        self,
        ohlcv: pd.DataFrame,
        refit: bool = False
    ) -> "HMMRegimeClassifier":
        """Train HMM model on OHLCV data.

        Args:
            ohlcv: DataFrame with OHLCV data
            refit: If True, refit even if already fitted

        Returns:
            Self for method chaining
        """
        if self._is_fitted and not refit:
            return self

        # Build features
        features = self._build_features(ohlcv)

        # Use last train_window samples for training
        if len(features) > self.config.train_window:
            features = features.iloc[-self.config.train_window:]

        # Prepare data
        X = self._prepare_training_data(features)
        log_returns = features["log_returns"].dropna().values

        # Initialize and fit HMM
        self.model = hmm.GaussianHMM(
            n_components=self.config.n_components,
            covariance_type="full",
            n_iter=self.config.n_iter,
            tol=self.config.tol,
            random_state=self.config.random_state,
            init_params="mcs" if not self._is_fitted else ""
        )

        # Fit model
        self.model.fit(X)

        # Get training predictions
        hidden_states = self.model.predict(X)

        # Align regime labels
        self._regime_map = self._align_regime_labels(
            log_returns[-len(hidden_states):],
            hidden_states
        )

        self._is_fitted = True

        return self

    def predict(
        self,
        ohlcv: pd.DataFrame,
        return_probs: bool = False
    ) -> Union[pd.Series, pd.DataFrame]:
        """Predict regime for each time point.

        Uses walk-forward prediction: generates a regime label for each
bar using the HMM state that had highest likelihood at that time.

        Args:
            ohlcv: DataFrame with OHLCV data
            return_probs: If True, return probability distribution per regime

        Returns:
            Series with regime labels if return_probs=False,
            DataFrame with regime labels and probabilities if return_probs=True
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Build features
        features = self._build_features(ohlcv)
        valid_mask = features[self._feature_cols].notna().all(axis=1)
        valid_data = features[valid_mask]

        if len(valid_data) == 0:
            empty_series = pd.Series(
                index=ohlcv.index,
                dtype="object"
            ).fillna("sideways")
            if return_probs:
                probs = pd.DataFrame(
                    1.0/3.0,
                    index=ohlcv.index,
                    columns=["bear", "sideways", "bull"]
                )
                probs["regime"] = empty_series
                return probs
            return empty_series

        # Prepare features
        X = self._prepare_inference_data(valid_data)

        # Predict hidden states
        hidden_states = self.model.predict(X)
        state_probs = self.model.predict_proba(X)

        # Map states to regime labels
        regimes = np.array([self._regime_map[s] for s in hidden_states])

        # Create result series with correct index alignment
        result = pd.Series(index=ohlcv.index, dtype="object")
        for i, idx in enumerate(valid_data.index):
            if i < len(regimes):
                result.loc[idx] = regimes[i]
        result = result.ffill().fillna("sideways")

        if not return_probs:
            return result

        # Build probability DataFrame
        prob_df = pd.DataFrame(
            index=ohlcv.index,
            columns=["bear", "sideways", "bull"],
            dtype=float
        ).fillna(1.0/3.0)

        for state_idx, regime_label in self._regime_map.items():
            prob_df.loc[valid_data.index, regime_label] = state_probs[:, state_idx]

        prob_df["regime"] = result

        return prob_df

    def predict_latest(
        self,
        ohlcv: pd.DataFrame
    ) -> RegimePrediction:
        """Predict regime for the most recent data point.

        Args:
            ohlcv: DataFrame with OHLCV data (uses latest bar)

        Returns:
            RegimePrediction with regime label, probabilities, and statistics
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Build features for all data
        features = self._build_features(ohlcv)
        valid_data = features[features[self._feature_cols].notna().all(axis=1)]

        if len(valid_data) == 0:
            return RegimePrediction(
                regime="sideways",
                regime_idx=1,
                probability=1.0/3.0,
                all_probs=np.array([1.0/3.0] * 3),
                mean_return=0.0,
                volatility=0.0
            )

        # Use latest valid data point
        latest = valid_data.iloc[[-1]]
        X = self._prepare_inference_data(latest)

        # Get probabilities
        state_probs = self.model.predict_proba(X)[0]

        # Get most likely state
        predicted_state = np.argmax(state_probs)
        regime = self._regime_map[predicted_state]

        # Get regime statistics
        means = self.model.means_[predicted_state]
        covars = self.model.covars_[predicted_state]

        # Approximate regime return and volatility from features
        # mean_return is roughly indicated by log_returns feature
        mean_return_log = means[0]  # log_returns is first feature

        # Volatility from realized_vol feature
        volatility = means[1] if self._feature_cols[1] == "realized_vol" else 0.0

        # Build probability dict
        all_probs = {
            self._regime_map[i]: state_probs[i]
            for i in range(self.config.n_components)
        }

        # Convert regime to int index
        regime_int_map = {"bear": 0, "sideways": 1, "bull": 2}

        return RegimePrediction(
            regime=regime,
            regime_idx=regime_int_map.get(regime, 1),
            probability=state_probs[predicted_state],
            all_probs=np.array([all_probs.get("bear", 0.0),
                               all_probs.get("sideways", 0.0),
                               all_probs.get("bull", 0.0)]),
            mean_return=mean_return_log,
            volatility=volatility
        )

    def walk_forward_predict(
        self,
        ohlcv: pd.DataFrame,
        train_size: int = 500,
        step_size: int = 50
    ) -> pd.DataFrame:
        """Run walk-forward regime prediction.

        Trains on initial window, predicts next step_size bars,
        then re-trains with updated data.

        Args:
            ohlcv: Full OHLCV dataset
            train_size: Initial training window size
            step_size: Prediction horizon before retraining

        Returns:
            DataFrame with regime labels and probabilities over time
        """
        regimes = pd.Series(index=ohlcv.index, dtype="object")
        probs = pd.DataFrame(
            index=ohlcv.index,
            columns=["bear", "sideways", "bull"],
            dtype=float
        )

        # Initialize
        start_idx = 0
        end_idx = train_size

        while end_idx < len(ohlcv):
            # Training window
            train_data = ohlcv.iloc[start_idx:end_idx]

            # Fit model
            self.fit(train_data, refit=True)

            # Prediction window
            pred_start = end_idx
            pred_end = min(end_idx + step_size, len(ohlcv))
            pred_data = ohlcv.iloc[pred_start:pred_end]

            # Predict
            prob_df = self.predict(pred_data, return_probs=True)

            # Store results
            regimes.iloc[pred_start:pred_end] = prob_df["regime"].values
            probs.iloc[pred_start:pred_end] = prob_df[["bear", "sideways", "bull"]].values

            # Move window
            start_idx += step_size
            end_idx += step_size

        # Fill any remaining NaN
        regimes = regimes.ffill().fillna("sideways")
        probs = probs.fillna(1.0/3.0)

        result = probs.copy()
        result["regime"] = regimes

        return result

    def get_regime_stats(self) -> dict:
        """Get statistics about learned regimes.

        Returns:
            Dictionary with regime statistics including:
            - mean_features: Feature means per regime
            - covariances: Covariance matrices per regime
            - transition_matrix: Regime transition probabilities
        """
        if not self._is_fitted:
            raise RuntimeError("Model not fitted.")

        stats = {
            "regime_map": self._regime_map,
            "feature_names": self._feature_cols,
            "mean_features": {},
            "transition_matrix": self.model.transmat_.tolist()
        }

        for state, regime in self._regime_map.items():
            stats["mean_features"][regime] = self.model.means_[state].tolist()

        return stats

    def save(self, path: Union[str, Path]) -> None:
        """Save model to file.

        Args:
            path: Path to save model (will create parent directories)
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted model.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "model": self.model,
            "scaler": self.scaler,
            "regime_map": self._regime_map,
            "config": self.config,
            "is_fitted": self._is_fitted
        }

        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load(self, path: Union[str, Path]) -> "HMMRegimeClassifier":
        """Load model from file.

        Args:
            path: Path to saved model

        Returns:
            Self with loaded state
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")

        with open(path, "rb") as f:
            state = pickle.load(f)

        self.model = state["model"]
        self.scaler = state["scaler"]
        self._regime_map = state["regime_map"]
        self.config = state["config"]
        self._is_fitted = state["is_fitted"]

        return self


def create_regime_classifier(
    n_regimes: int = 3,
    train_window: int = 500,
    volatility_window: int = 20
) -> HMMRegimeClassifier:
    """Factory function to create HMM Regime Classifier.

    Args:
        n_regimes: Number of regimes (default 3 for bull/sideways/bear)
        train_window: Training window size
        volatility_window: Window for volatility calculation

    Returns:
        Configured HMMRegimeClassifier
    """
    config = HMMConfig(
        n_components=n_regimes,
        train_window=train_window,
        volatility_window=volatility_window
    )
    return HMMRegimeClassifier(config)
