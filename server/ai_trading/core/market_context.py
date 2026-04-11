import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class MarketContext:
    regime: str
    volatility_percentile: float
    trend_strength: float
    is_trending: bool
    volatility_level: str
    liquidity_score: float = 1.0 # 0.0 to 1.0, where 1.0 is high liquidity
    orderflow_imbalance: float = 0.0 # -1.0 (Sell heavy) to 1.0 (Buy heavy)
    funding_annualized: float = 0.0 # Annualized funding rate

    def to_rag_key(self) -> str:
        """Generates a unique fingerprint key for RAG retrieval."""
        liq_bin = int(self.liquidity_score * 5) # Bin into 5 levels
        return f"{self.regime}_{self.volatility_level}_liq{liq_bin}"

class MarketContextProvider:
    """
    Provides structural and statistical context about the current market state
    to guide the LLM's strategy evolution.
    """
    def __init__(self, data_provider):
        self.data_provider = data_provider

    async def get_context(self, symbol: str, timeframe: str) -> MarketContext:
        # Fetch recent OHLCV data
        df = await self.data_provider.get_recent_data(symbol, timeframe)
        if df is None or df.empty:
            return MarketContext("Unknown", 0.0, 0.0, False, "Unknown")

        # 1. Calculate Volatility Percentile (relative to historical)
        vol = df['close'].pct_change().std()
        vol_percentile = self._calculate_vol_percentile(vol, symbol)

        # 2. Determine Trend Strength (Simplified ADX/Momentum)
        trend_strength = self._calculate_trend_strength(df)
        is_trending = trend_strength > 25 # Standard ADX threshold

        # 3. Define Market Regime
        regime = self._determine_regime(df, vol_percentile, is_trending)

        vol_level = "High" if vol_percentile > 70 else "Low" if vol_percentile <  30 else "Medium"

        return MarketContext(
            regime=regime,
            volatility_percentile=vol_percentile,
            trend_strength=trend_strength,
            is_trending=is_trending,
            volatility_level=vol_level
        )

    def _calculate_vol_percentile(self, current_vol: float, symbol: str) -> float:
        # Analyst Recommended: Symbol-specific distributions for Z-score calculation
        distributions = {
            "BTC": {"mean": 0.025, "std": 0.015},
            "ETH": {"mean": 0.030, "std": 0.020},
        }
        dist = distributions.get(symbol, {"mean": 0.02, "std": 0.015})

        # Z-score normalization
        z_score = (current_vol - dist["mean"]) / dist["std"]

        # Simple approximation of CDF for normal distribution
        # (In production, use scipy.stats.norm.cdf)
        percentile = 0.5 * (1 + np.tanh(z_score / np.sqrt(2))) * 100
        return np.clip(percentile, 0, 100)

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        # Simplified trend strength using price change over the window
        returns = df['close'].pct_change().dropna()
        if len(returns) <  2: return 0.0
        # Relative strength of trend (CUMSUM of returns)
        return abs(returns.sum()) * 100

    def _determine_regime(self, df: pd.DataFrame, vol_perc: float, is_trending: bool) -> str:
        last_return = df['close'].pct_change().iloc[-1]

        if is_trending:
            direction = "Bull" if last_return > 0 else "Bear"
            vol_type = "Volatile" if vol_perc > 60 else "Stable"
            return f"{vol_type} {direction}"
        else:
            vol_type = "High-Vol" if vol_perc > 60 else "Low-Vol"
            return f"{vol_type} Ranging"
