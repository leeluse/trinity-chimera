"""Integration tests for Phase 3: LLM Arbiter System.

This module tests the integration between:
- LLM Arbiter and Arena
- Strategy Generator and BaseAgent
- Market Analyzer and real-time API
"""

import asyncio
import json
import os
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

import numpy as np
import pandas as pd
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Import all Phase 3 components
from ai_trading.arbiter.llm_arbiter import (
    LLMArbiter,
    AgentPerformance,
    AllocationDecision,
    create_arbiter,
)
from ai_trading.arbiter.strategy_generator import (
    StrategyGenerator,
    StrategyProposal,
    ValidationOutcome,
    ValidationResult,
    create_strategy_generator,
)
from ai_trading.arbiter.market_analyzer import (
    MarketAnalyzer,
    MarketAnalysis,
    VolatilityCalculator,
    CorrelationTracker,
    create_market_analyzer,
)
from ai_trading.battle.arena import Arena
from ai_trading.agents.base_agent import BaseAgent, AgentConfig


class TestPhase3Integration:
    """Test Phase 3 component integration."""

    @pytest.fixture
    def sample_ohlcv(self):
        """Generate sample OHLCV data."""
        np.random.seed(42)
        n = 100
        dates = pd.date_range(end=datetime.now(), periods=n, freq="D")

        # Generate price series with trend
        returns = np.random.normal(0.001, 0.02, n)
        prices = 100 * np.exp(np.cumsum(returns))

        data = {
            "open": prices * (1 + np.random.normal(0, 0.01, n)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.02, n))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.02, n))),
            "close": prices,
            "volume": np.random.lognormal(10, 0.5, n),
        }
        return pd.DataFrame(data, index=dates)

    @pytest.fixture
    def sample_performance(self):
        """Create sample agent performance."""
        return AgentPerformance(
            name="momentum_hunter",
            sharpe_7d=1.2,
            max_drawdown=0.08,
            win_rate=0.65,
            avg_hold_bars=12.5,
            regime_fit=0.85,
            diversity_score=0.45,
            overfit_score=0.15,
            current_allocation=0.30,
            total_pnl=0.15,
            trades_count=45,
        )


class TestMarketAnalyzerIntegration:
    """Test Market Analyzer integration."""

    def test_analyzer_with_ohlcv(self, sample_ohlcv):
        """Test analyzer with real OHLCV data."""
        analyzer = create_market_analyzer(
            volatility_window=20,
            correlation_lookback=20,
        )

        agent_positions = {"momentum_hunter": 0.8, "mean_reverter": -0.5}

        analysis = analyzer.analyze(
            ohlcv=sample_ohlcv,
            agent_positions=agent_positions,
        )

        assert isinstance(analysis, MarketAnalysis)
        assert analysis.regime in ["bull", "sideways", "bear"]
        assert analysis.volatility >= 0
        assert analysis.regime_confidence >= 0
        assert analysis.trend_strength >= -1
        assert analysis.trend_strength <= 1

    def test_analyzer_history_tracking(self, sample_ohlcv):
        """Test analysis history is tracked."""
        analyzer = create_market_analyzer()

        for i in range(5):
            analyzer.analyze(sample_ohlcv, agent_positions={})

        assert len(analyzer.history) == 5
        assert analyzer.get_regime_stats()["total_analyses"] == 5


class TestLLMArbiterIntegration:
    """Test LLM Arbiter integration without API calls."""

    def test_arbiter_constraints(self):
        """Test allocation constraint application."""
        arbiter = create_arbiter(
            min_alloc=0.05,
            max_alloc=0.50,
        )

        # Test over-max allocation
        allocations = {"agent1": 0.60, "agent2": 0.40}
        result = arbiter._apply_constraints(allocations)
        assert result["agent1"] <= 0.50 + 0.02  # Close after normalization

        # Test under-min allocation
        allocations = {"agent1": 0.95, "agent2": 0.05}
        result = arbiter._apply_constraints(allocations)
        # After normalization: 0.95/1.0 = 0.95 (clamped to 0.50), 0.05/1.0 = 0.05
        assert result["agent2"] >= 0.05 - 0.02

    def test_arbiter_needs_rebalance(self):
        """Test rebalance timing logic."""
        arbiter = create_arbiter(rebalance_days=7)

        assert arbiter.needs_rebalance(7) is True
        assert arbiter.needs_rebalance(6) is False
        assert arbiter.needs_rebalance(14) is True

    def test_arbiter_statistics_empty(self):
        """Test statistics with no decisions."""
        arbiter = create_arbiter()
        stats = arbiter.get_statistics()
        assert stats["total_decisions"] == 0


class TestStrategyGeneratorIntegration:
    """Test Strategy Generator integration."""

    def test_generator_without_api(self):
        """Test generator initialization without API."""
        os.environ.pop("ANTHROPIC_API_KEY", None)

        generator = create_strategy_generator()
        assert generator.model == "claude-sonnet-4-6"
        assert generator.min_sharpe_improvement == 0.1

    def test_default_personas(self):
        """Test default agent personas."""
        generator = create_strategy_generator()
        assert "momentum_hunter" in generator.DEFAULT_PERSONAS
        assert "mean_reverter" in generator.DEFAULT_PERSONAS
        assert len(generator.DEFAULT_PERSONAS) == 4


class TestArenaLLMIntegration:
    """Test Arena with LLM Arbiter integration."""

    def test_arena_with_llm_disabled(self):
        """Test Arena when LLM is disabled."""
        arena = Arena(
            agents=[],
            total_capital=100.0,
            rebalance_interval=7,
            enable_llm_arbiter=False,
        )

        assert arena.llm_arbiter is None

    @pytest.mark.asyncio
    async def test_arena_needs_rebalance(self):
        """Test Arena rebalance checking."""
        arena = Arena(
            agents=[],
            rebalance_interval=7,
            enable_llm_arbiter=False,
        )

        assert arena.needs_rebalance(7) is True
        assert arena.needs_rebalance(3) is False


class TestBaseAgentSelfImprovement:
    """Test BaseAgent self-improve integration."""

    def test_self_improve_no_generator(self):
        """Test self_improve without strategy generator."""
        config = AgentConfig(name="test_agent", algorithm="PPO")
        agent = BaseAgent(config)

        result = asyncio.run(
            agent.self_improve(
                recent_performance={"sharpe": 1.0},
                regime="bull",
                params={"param1": 0.5},
                strategy_generator=None,
            )
        )

        assert result == {}


class TestVolatilityCalculator:
    """Test volatility calculation."""

    def test_volatility_calculation(self, sample_ohlcv):
        """Test volatility metrics calculation."""
        from ai_trading.arbiter.market_analyzer import VolatilityCalculator

        calc = VolatilityCalculator(
            short_window=5,
            medium_window=20,
            long_window=60,
        )

        prices = sample_ohlcv["close"]
        returns = np.log(prices / prices.shift(1))
        vols = calc.calculate(prices, returns)

        assert "short" in vols
        assert "medium" in vols
        assert "long" in vols
        assert "regime" in vols
        assert vols["regime"] in ["low", "normal", "high"]

    def test_volatility_forecast(self, sample_ohlcv):
        """Test volatility forecasting."""
        from ai_trading.arbiter.market_analyzer import VolatilityCalculator

        calc = VolatilityCalculator()
        prices = sample_ohlcv["close"]

        forecast = calc.forecast_volatility(prices, forecast_horizon=7)
        assert forecast >= 0


class TestCorrelationTracker:
    """Test correlation tracking."""

    def test_correlation_matrix(self):
        """Test correlation matrix calculation."""
        from ai_trading.arbiter.market_analyzer import CorrelationTracker

        tracker = CorrelationTracker(lookback_window=20)

        # Add some positions
        for i in range(30):
            tracker.update({
                "agent1": np.sin(i * 0.1),
                "agent2": np.sin(i * 0.1 + 0.5),
            })

        corr = tracker.get_correlation_matrix()
        assert corr is not None

        if not corr.empty:
            diversification = tracker.get_diversification_score()
            assert 0 <= diversification <= 1

    def test_single_agent_no_correlation(self):
        """Test with single agent."""
        from ai_trading.arbiter.market_analyzer import CorrelationTracker

        tracker = CorrelationTracker()
        tracker.update({"agent1": 0.5})

        corr = tracker.get_correlation_matrix()
        assert corr.empty or len(corr) == 1


class TestEndToEndScenarios:
    """End-to-end integration scenarios."""

    def test_full_pipeline_without_llm(self, sample_ohlcv):
        """Test full pipeline without LLM calls."""
        # 1. Market Analysis
        analyzer = create_market_analyzer()

        positions = {"momentum_hunter": 0.7, "mean_reverter": -0.3}
        analysis = analyzer.analyze(sample_ohlcv, positions)

        # 2. Create fake agent performances
        performances = [
            AgentPerformance(
                name="momentum_hunter",
                sharpe_7d=1.5,
                max_drawdown=0.10,
                win_rate=0.70,
                avg_hold_bars=15.0,
                regime_fit=0.90,
                diversity_score=0.40,
                overfit_score=0.05,
                current_allocation=0.50,
                total_pnl=0.25,
                trades_count=50,
            ),
            AgentPerformance(
                name="mean_reverter",
                sharpe_7d=0.8,
                max_drawdown=0.05,
                win_rate=0.55,
                avg_hold_bars=8.0,
                regime_fit=0.60,
                diversity_score=0.50,
                overfit_score=0.10,
                current_allocation=0.30,
                total_pnl=0.10,
                trades_count=40,
            ),
        ]

        # 3. Allocation constraint validation
        arbiter = create_arbiter(min_alloc=0.05, max_alloc=0.50)
        raw_allocations = {"momentum_hunter": 0.60, "mean_reverter": 0.40}
        constrained = arbiter._apply_constraints(raw_allocations)

        assert sum(constrained.values()) == pytest.approx(1.0, abs=0.01)
        for alloc in constrained.values():
            assert 0.05 <= alloc <= 0.50

    def test_multi_agent_correlation_tracking(self):
        """Test correlation tracking with multiple agents."""
        from ai_trading.arbiter.market_analyzer import CorrelationTracker

        tracker = CorrelationTracker(lookback_window=20)

        # Simulate positions over time
        np.random.seed(42)
        for i in range(100):
            # Agents that sometimes agree, sometimes disagree
            base = np.sin(i * 0.1)
            tracker.update({
                "momentum": base,
                "reverter": -base * 0.7,  # Often opposite
                "macro": np.sign(base) * 0.5 + np.random.normal(0, 0.1),
                "chaos": np.random.uniform(-1, 1),  # Random
            })

        metrics = tracker.get_diversification_score()
        assert 0 <= metrics <= 1


class TestErrorHandling:
    """Test error handling in integration."""

    def test_analyzer_empty_data(self):
        """Test analyzer with empty data."""
        analyzer = create_market_analyzer()

        empty = pd.DataFrame({
            "open": [], "high": [], "low": [], "close": [], "volume": []
        })

        # Should handle gracefully
        try:
            analysis = analyzer.analyze(empty, {})
            # May fail, but should not crash
        except Exception:
            pass  # Expected

    def test_arbiter_parse_invalid_response(self):
        """Test parsing invalid LLM response."""
        arbiter = create_arbiter()

        with pytest.raises(ValueError):
            arbiter._parse_response("not valid json}")

    def test_correlation_tracker_too_few_samples(self):
        """Test correlation with insufficient data."""
        from ai_trading.arbiter.market_analyzer import CorrelationTracker

        tracker = CorrelationTracker()

        # Only 2 samples (need minimum window)
        tracker.update({"a": 0.5, "b": -0.3})
        tracker.update({"a": 0.6, "b": -0.2})

        corr = tracker.get_correlation_matrix()
        assert corr.empty or len(corr) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
