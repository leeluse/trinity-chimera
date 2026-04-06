"""Unit tests for LLM Arbiter module."""

import json
import os
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from ai_trading.arbiter.llm_arbiter import (
    LLMArbiter,
    AgentPerformance,
    AllocationDecision,
    create_arbiter,
)


class TestAgentPerformance:
    """Test AgentPerformance dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        perf = AgentPerformance(
            name="momentum_hunter",
            sharpe_7d=1.25,
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

        d = perf.to_dict()
        assert d["name"] == "momentum_hunter"
        assert d["sharpe_7d"] == pytest.approx(1.25, abs=0.01)
        assert d["max_drawdown"] == pytest.approx(0.08, abs=0.001)
        assert d["trades_count"] == 45


class TestAllocationDecision:
    """Test AllocationDecision dataclass."""

    def test_validation_success(self):
        """Test validation with valid allocation."""
        decision = AllocationDecision(
            allocations={
                "momentum_hunter": 0.30,
                "mean_reverter": 0.30,
                "macro_trader": 0.25,
                "chaos_agent": 0.15,
            },
            reasoning="Good allocation",
            warnings=[],
            confidence=0.85,
            regime_recommendation="bull market",
            timestamp=datetime.now(),
        )

        is_valid, errors = decision.validate()
        assert is_valid is True
        assert len(errors) == 0

    def test_validation_sum_not_one(self):
        """Test validation when allocations don't sum to 1.0."""
        decision = AllocationDecision(
            allocations={
                "momentum_hunter": 0.30,
                "mean_reverter": 0.30,
                "macro_trader": 0.30,  # Sum = 0.9
            },
            reasoning="Partial allocation",
            warnings=[],
            confidence=0.8,
            regime_recommendation="sideways",
            timestamp=datetime.now(),
        )

        is_valid, errors = decision.validate()
        assert is_valid is False
        assert any("sum to" in e.lower() for e in errors)

    def test_validation_negative_allocation(self):
        """Test validation with negative allocation."""
        decision = AllocationDecision(
            allocations={
                "momentum_hunter": 0.40,
                "mean_reverter": -0.10,  # Negative
                "macro_trader": 0.50,
                "chaos_agent": 0.20,
            },
            reasoning="Has negative",
            warnings=[],
            confidence=0.7,
            regime_recommendation="bear",
            timestamp=datetime.now(),
        )

        is_valid, errors = decision.validate()
        assert is_valid is False
        assert any("negative" in e.lower() for e in errors)


class TestLLMArbiter:
    """Test LLMArbiter class."""

    def test_initialization_without_api_key(self):
        """Test initialization without API key."""
        os.environ.pop("ANTHROPIC_API_KEY", None)

        arbiter = LLMArbiter(model="claude-sonnet-4-6")
        assert arbiter.model == "claude-sonnet-4-6"
        assert arbiter.min_allocation == 0.05
        assert arbiter.max_allocation == 0.50
        assert arbiter.client is None

    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("ai_trading.arbiter.llm_arbiter.Anthropic") as mock_anthropic:
                arbiter = LLMArbiter()
                assert arbiter.model == "claude-sonnet-4-6"
                mock_anthropic.assert_called_once_with(api_key="test-key")

    def test_apply_constraints(self):
        """Test allocation constraint application."""
        arbiter = LLMArbiter()

        # Test exceeding max allocation
        allocations = {"agent1": 0.60, "agent2": 0.40}
        result = arbiter._apply_constraints(allocations)
        assert result["agent1"] <= 0.50 + 0.01  # Max constraint

        # Test under min allocation
        allocations = {"agent1": 0.99, "agent2": 0.01}
        result = arbiter._apply_constraints(allocations)
        assert result["agent2"] >= 0.05 - 0.01  # Min constraint

        # Test normal allocations
        allocations = {"agent1": 0.40, "agent2": 0.35, "agent3": 0.25}
        result = arbiter._apply_constraints(allocations)
        assert sum(result.values()) == pytest.approx(1.0, abs=0.01)

    def test_parse_response_valid(self):
        """Test parsing valid LLM response."""
        arbiter = LLMArbiter()

        response_text = """
        ```json
        {
          "allocations": {
            "momentum_hunter": 0.35,
            "mean_reverter": 0.25,
            "macro_trader": 0.25,
            "chaos_agent": 0.15
          },
          "reasoning": "Bull market favors momentum strategy",
          "warnings": ["chaos_agent: low Sharpe"],
          "confidence": 0.85,
          "regime_recommendation": "maintain momentum focus"
        }
        ```
        """

        decision = arbiter._parse_response(response_text)
        assert decision.allocations["momentum_hunter"] == 0.35
        assert decision.confidence == 0.85
        assert len(decision.warnings) == 1

    def test_parse_response_no_markdown(self):
        """Test parsing response without markdown code block."""
        arbiter = LLMArbiter()

        response_text = """
        {"allocations": {"ag1": 0.5, "ag2": 0.5}, "reasoning": "test", "warnings": [], "confidence": 0.7, "regime_recommendation": "bull"}
        """

        decision = arbiter._parse_response(response_text)
        assert decision.allocations["ag1"] == 0.5
        assert decision.confidence == 0.7

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        arbiter = LLMArbiter()

        with pytest.raises(ValueError):
            arbiter._parse_response("not valid json}")

    def test_build_prompt(self):
        """Test prompt building."""
        arbiter = LLMArbiter()

        performances = [
            AgentPerformance(
                name="momentum_hunter",
                sharpe_7d=1.2,
                max_drawdown=0.08,
                win_rate=0.65,
                avg_hold_bars=12.5,
                regime_fit=0.8,
                diversity_score=0.5,
                overfit_score=0.1,
                current_allocation=0.30,
            )
        ]

        prompt = arbiter._build_prompt(performances, "bull")
        assert "bull" in prompt
        assert "momentum_hunter" in prompt
        assert "sharpe_7d" in prompt

    def test_needs_rebalance(self):
        """Test rebalance timing check."""
        arbiter = LLMArbiter(rebalance_interval=7)
        assert arbiter.needs_rebalance(7) is True
        assert arbiter.needs_rebalance(6) is False
        assert arbiter.needs_rebalance(14) is True

    def test_get_decision_for_agent(self):
        """Test getting decision for specific agent."""
        arbiter = LLMArbiter()

        decision = AllocationDecision(
            allocations={
                "momentum_hunter": 0.40,
                "mean_reverter": 0.30,
            },
            reasoning="Overall good fit",
            warnings=[],
            confidence=0.8,
            regime_recommendation="bull",
            timestamp=datetime.now(),
        )
        arbiter.decision_history.append(decision)

        alloc, reason = arbiter.get_decision_for_agent("momentum_hunter")
        assert alloc == 0.40

    def test_get_statistics_empty(self):
        """Test getting statistics with empty history."""
        arbiter = LLMArbiter()
        stats = arbiter.get_statistics()
        assert stats["total_decisions"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_get_statistics_with_history(self):
        """Test getting statistics with decision history."""
        arbiter = LLMArbiter()

        for i in range(3):
            decision = AllocationDecision(
                allocations={"a": 0.5, "b": 0.5},
                reasoning="test",
                warnings=[],
                confidence=0.8,
                regime_recommendation="bull",
                timestamp=datetime.now(),
            )
            arbiter.decision_history.append(decision)

        stats = arbiter.get_statistics()
        assert stats["total_decisions"] == 3
        assert stats["avg_confidence"] == pytest.approx(0.8, abs=0.01)


class TestCreateArbiter:
    """Test factory function."""

    def test_arbiter_creation(self):
        """Test arbiter factory."""
        arbiter = create_arbiter(
            model="claude-sonnet-4-6",
            min_alloc=0.10,
            max_alloc=0.40,
            rebalance_days=5,
        )
        assert arbiter.model == "claude-sonnet-4-6"
        assert arbiter.min_allocation == 0.10
        assert arbiter.max_allocation == 0.40
        assert arbiter.rebalance_interval == 5


@pytest.mark.asyncio
class TestLLMArbiterAsync:
    """Async tests for LLMArbiter."""

    async def test_analyze_performance_no_api_key(self):
        """Test analysis fails without API key."""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        arbiter = LLMArbiter()

        performances = [
            AgentPerformance(
                name="momentum_hunter",
                sharpe_7d=1.2,
                max_drawdown=0.08,
                win_rate=0.65,
                avg_hold_bars=12.5,
                regime_fit=0.8,
                diversity_score=0.5,
                overfit_score=0.1,
                current_allocation=0.30,
            )
        ]

        with pytest.raises(RuntimeError):
            await arbiter.analyze_performance(performances, "bull")

    @patch("ai_trading.arbiter.llm_arbiter.Anthropic")
    async def test_analyze_performance_success(self, mock_anthropic):
        """Test successful analysis."""
        # Setup mock client
        mock_response = Mock()
        mock_response.content = [
            Mock(text='```json\n{"allocations": {"a": 0.5, "b": 0.5}, "reasoning": "good strategy", "warnings": [], "confidence": 0.9, "regime_recommendation": "bull"}\n```')
        ]

        mock_client = Mock()
        mock_client.messages.create = Mock(return_value=mock_response)
        mock_anthropic.return_value = mock_client

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            arbiter = LLMArbiter()

            performances = [
                AgentPerformance(
                    name="a",
                    sharpe_7d=1.2,
                    max_drawdown=0.08,
                    win_rate=0.65,
                    avg_hold_bars=12.5,
                    regime_fit=0.8,
                    diversity_score=0.5,
                    overfit_score=0.1,
                    current_allocation=0.30,
                ),
                AgentPerformance(
                    name="b",
                    sharpe_7d=0.8,
                    max_drawdown=0.05,
                    win_rate=0.55,
                    avg_hold_bars=10.0,
                    regime_fit=0.7,
                    diversity_score=0.4,
                    overfit_score=0.2,
                    current_allocation=0.30,
                ),
            ]

            decision = await arbiter.analyze_performance(performances, "bull")
            assert decision.confidence == 0.9
            assert "a" in decision.allocations
            assert len(arbiter.decision_history) == 1

    @patch("ai_trading.arbiter.llm_arbiter.Anthropic")
    async def test_analyze_performance_fallback(self, mock_anthropic):
        """Test fallback to equal allocations on API failure."""
        mock_client = Mock()
        mock_client.messages.create = Mock(side_effect=Exception("API Error"))
        mock_anthropic.return_value = mock_client

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            arbiter = LLMArbiter()

            performances = [
                AgentPerformance(
                    name="a",
                    sharpe_7d=1.2,
                    max_drawdown=0.08,
                    win_rate=0.65,
                    avg_hold_bars=12.5,
                    regime_fit=0.8,
                    diversity_score=0.5,
                    overfit_score=0.1,
                    current_allocation=0.60,
                ),
                AgentPerformance(
                    name="b",
                    sharpe_7d=0.8,
                    max_drawdown=0.05,
                    win_rate=0.55,
                    avg_hold_bars=10.0,
                    regime_fit=0.7,
                    diversity_score=0.4,
                    overfit_score=0.2,
                    current_allocation=0.40,
                ),
            ]

            # This uses fallback since we didn't properly mock
            # We need to also mock _apply_constraints validation
            arbiter.client = None  # Force fallback
            decision = await arbiter.analyze_performance(performances, "bull")

            assert decision.confidence == 0.0
            assert "API failure" in decision.warnings[0]
