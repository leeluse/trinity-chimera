"""LLM Arbiter for intelligent capital allocation.

This module implements an LLM-based portfolio manager that analyzes agent
performance and makes capital reallocation decisions using Claude API.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
from anthropic import Anthropic

logger = logging.getLogger(__name__)


@dataclass
class AgentPerformance:
    """Agent performance metrics for Arbiter evaluation.

    Attributes:
        name: Agent identifier (e.g., "momentum_hunter")
        sharpe_7d: 7-day Sharpe ratio
        max_drawdown: Maximum drawdown percentage
        win_rate: Percentage of positive returns
        avg_hold_bars: Average holding period in bars
        regime_fit: Fit with current market regime (0-1)
        diversity_score: Correlation with other agents (0-1)
        overfit_score: Recent vs previous performance gap
        current_allocation: Current capital allocation ratio
        total_pnl: Total profit and loss
        trades_count: Number of trades executed
    """
    name: str
    sharpe_7d: float
    max_drawdown: float
    win_rate: float
    avg_hold_bars: float
    regime_fit: float
    diversity_score: float
    overfit_score: float
    current_allocation: float
    total_pnl: float = 0.0
    trades_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "sharpe_7d": round(self.sharpe_7d, 3),
            "max_drawdown": round(self.max_drawdown, 4),
            "win_rate": round(self.win_rate, 3),
            "avg_hold_bars": round(self.avg_hold_bars, 1),
            "regime_fit": round(self.regime_fit, 3),
            "diversity_score": round(self.diversity_score, 3),
            "overfit_score": round(self.overfit_score, 3),
            "current_allocation": round(self.current_allocation, 3),
            "total_pnl": round(self.total_pnl, 4),
            "trades_count": self.trades_count,
        }


@dataclass
class AllocationDecision:
    """Capital allocation decision from LLM Arbiter.

    Attributes:
        allocations: Agent name to allocation ratio mapping (sum = 1.0)
        reasoning: Detailed explanation of the decision
        warnings: List of warnings about agent performance
        confidence: Confidence score of the decision (0-1)
        regime_recommendation: Recommended action for current regime
        timestamp: Decision timestamp
    """
    allocations: Dict[str, float]
    reasoning: str
    warnings: List[str]
    confidence: float
    regime_recommendation: str
    timestamp: datetime

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate allocation decision.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check allocations sum to approximately 1.0
        total = sum(self.allocations.values())
        if not 0.99 <= total <= 1.01:
            errors.append(f"Allocations sum to {total:.4f}, expected ~1.0")

        # Check all allocations are non-negative
        for name, alloc in self.allocations.items():
            if alloc < 0:
                errors.append(f"Negative allocation for {name}: {alloc}")

        return len(errors) == 0, errors


class LLMArbiter:
    """LLM-based portfolio manager for agent capital allocation.

    The Arbiter analyzes agent performance using Claude API and makes
    capital reallocation decisions based on:
    - Regime fit: Which agents suit current market conditions
    - Overfitting detection: Agents showing signs of performance degradation
    - Portfolio diversity: Maintaining correlation balance
    - Risk management: Min/max allocation constraints
    """

    # Recommended agent personas and their default allocations
    DEFAULT_AGENTS = {
        "momentum_hunter": 0.30,
        "mean_reverter": 0.30,
        "macro_trader": 0.25,
        "chaos_agent": 0.15,
    }

    # Allocation constraints
    MIN_ALLOCATION = 0.05  # Minimum 5% per agent
    MAX_ALLOCATION = 0.50  # Maximum 50% per agent

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        min_allocation: float = 0.05,
        max_allocation: float = 0.50,
        rebalance_interval: int = 7,
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ):
        """Initialize LLM Arbiter.

        Args:
            model: Claude model to use
            min_allocation: Minimum allocation per agent (default: 5%)
            max_allocation: Maximum allocation per agent (default: 50%)
            rebalance_interval: Days between rebalancing
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env)
            max_tokens: Maximum tokens for LLM response
            temperature: LLM temperature (lower = more deterministic)
        """
        self.model = model
        self.min_allocation = min_allocation
        self.max_allocation = max_allocation
        self.rebalance_interval = rebalance_interval
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.decision_history: List[AllocationDecision] = []

        # Initialize Anthropic client
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("No API key provided. LLM calls will fail.")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)

        logger.info(f"LLMArbiter initialized with model: {model}")

    def _build_prompt(
        self,
        performances: List[AgentPerformance],
        current_regime: str,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build LLM prompt for allocation decision.

        Args:
            performances: List of agent performance metrics
            current_regime: Current market regime
            market_context: Additional market context

        Returns:
            Formatted prompt string
        """
        # Convert performances to JSON
        metrics_json = json.dumps([p.to_dict() for p in performances], indent=2)

        # Market volatility if available
        volatility = market_context.get("volatility", 0.0) if market_context else 0.0

        prompt = f"""You are a high-performance quantitative portfolio manager.

## Current Market Situation
- Regime: {current_regime}
- Timestamp: {datetime.now().isoformat()}
- 7-day Market Volatility: {volatility:.2%}

## Agent Performance Metrics
{metrics_json}

## Allocation Constraints
- Minimum allocation per agent: {self.min_allocation:.0%}
- Maximum allocation per agent: {self.max_allocation:.0%}
- Total allocations must sum to 100%

## Evaluation Guidelines

1. **Regime Fit (regime_fit)**:
   - Which agents are best suited for {current_regime} conditions?
   - Score each agent's fit with their persona and current regime

2. **Overfitting Detection (overfit_score)**:
   - overfit_score > 0.3 indicates potential overfitting
   - Consider recent vs historical performance consistency
   - Flag agents with suspicious performance gaps

3. **Portfolio Diversity (diversity_score)**:
   - Ensure low correlation between agents
   - Chaos Agent should maintain minimum allocation for diversity

4. **Risk Management**:
   - Sharpe ratio < -0.5: Consider reducing allocation
   - Max drawdown > 15%: Warning flag
   - Balance risk-adjusted returns across portfolio

## Agent Personas Reference
- **momentum_hunter**: Trend-following, bull regime specialist
- **mean_reverter**: Mean reversion, sideways/bear regime
- **macro_trader**: Regime-aware, low frequency trading
- **chaos_agent**: Contrarian, ensures diversity

## Output Format
Respond with a JSON object only:

```json
{{
  "allocations": {{
    "momentum_hunter": 0.30,
    "mean_reverter": 0.25,
    "macro_trader": 0.30,
    "chaos_agent": 0.15
  }},
  "reasoning": "Detailed explanation of allocation decisions...",
  "warnings": [
    "agent_name: specific warning message",
    "..."
  ],
  "confidence": 0.85,
  "regime_recommendation": "Specific recommendation for {current_regime} regime"
}}
```

IMPORTANT:
- Ensure allocations sum to exactly 1.0
- Provide specific, actionable reasoning
- Include warnings for any concerning metrics
- Confidence should reflect uncertainty in decision
"""
        return prompt

    async def analyze_performance(
        self,
        performances: List[AgentPerformance],
        current_regime: str,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> AllocationDecision:
        """Analyze agent performance and make allocation decision.

        Args:
            performances: List of agent performance metrics
            current_regime: Current market regime (bull/sideways/bear)
            market_context: Additional market context

        Returns:
            AllocationDecision with new allocations

        Raises:
            RuntimeError: If LLM client not initialized or API fails
        """
        if not self.client:
            raise RuntimeError("LLM client not initialized. Set ANTHROPIC_API_KEY.")

        # Build prompt
        prompt = self._build_prompt(performances, current_regime, market_context)

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract content
            content = response.content[0].text if response.content else ""

            # Parse JSON response
            decision = self._parse_response(content)

            # Apply allocation constraints
            decision.allocations = self._apply_constraints(decision.allocations)

            # Validate decision
            is_valid, errors = decision.validate()
            if not is_valid:
                logger.warning(f"Invalid allocation decision: {errors}")
                # Fall back to current allocations
                decision.allocations = {p.name: p.current_allocation for p in performances}

            # Store in history
            self.decision_history.append(decision)

            logger.info(
                f"Allocation decision made: {json.dumps(decision.allocations)}, "
                f"confidence={decision.confidence:.2f}"
            )

            return decision

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            # Fallback: return equal allocations
            n_agents = len(performances)
            equal_alloc = {p.name: 1.0 / n_agents for p in performances}
            return AllocationDecision(
                allocations=equal_alloc,
                reasoning=f"LLM API failed: {e}. Using equal allocation fallback.",
                warnings=["API failure - using fallback allocation"],
                confidence=0.0,
                regime_recommendation="manual review required",
                timestamp=datetime.now(),
            )

    def _parse_response(self, content: str) -> AllocationDecision:
        """Parse LLM response into AllocationDecision.

        Args:
            content: Raw LLM response text

        Returns:
            AllocationDecision

        Raises:
            ValueError: If JSON parsing fails
        """
        # Extract JSON from markdown code block if present
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        try:
            data = json.loads(content)

            return AllocationDecision(
                allocations=data.get("allocations", {}),
                reasoning=data.get("reasoning", "No reasoning provided"),
                warnings=data.get("warnings", []),
                confidence=data.get("confidence", 0.5),
                regime_recommendation=data.get("regime_recommendation", ""),
                timestamp=datetime.now(),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw content: {content}")
            raise ValueError(f"Invalid JSON response: {e}")

    def _apply_constraints(
        self,
        allocations: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply allocation constraints (min/max) and normalize.

        Args:
            allocations: Proposed allocations from LLM

        Returns:
            Constrained and normalized allocations
        """
        # Apply min/max constraints
        constrained = {}
        for name, alloc in allocations.items():
            constrained[name] = np.clip(alloc, self.min_allocation, self.max_allocation)

        # Normalize to sum to 1.0
        total = sum(constrained.values())
        if total > 0:
            constrained = {k: v / total for k, v in constrained.items()}
        else:
            # Fallback to default allocations
            constrained = self.DEFAULT_AGENTS.copy()

        logger.debug(f"Applied constraints: {allocations} -> {constrained}")
        return constrained

    def needs_rebalance(self, days_since_last: int) -> bool:
        """Check if rebalance is needed.

        Args:
            days_since_last: Days since last reallocation

        Returns:
            True if rebalance needed
        """
        return days_since_last >= self.rebalance_interval

    def get_decision_for_agent(
        self,
        agent_name: str,
        decision: Optional[AllocationDecision] = None,
    ) -> Tuple[float, str]:
        """Get allocation and reasoning for specific agent.

        Args:
            agent_name: Name of the agent
            decision: Specific decision (or latest)

        Returns:
            Tuple of (allocation_ratio, reasoning_snippet)
        """
        if decision is None:
            if not self.decision_history:
                return 0.0, "No decision history"
            decision = self.decision_history[-1]

        allocation = decision.allocations.get(agent_name, 0.0)

        # Extract agent-specific reasoning if present
        reasoning = decision.reasoning

        return allocation, reasoning

    def get_statistics(self) -> Dict[str, Any]:
        """Get Arbiter operation statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.decision_history:
            return {
                "total_decisions": 0,
                "avg_confidence": 0.0,
                "recent_allocations": {},
            }

        avg_confidence = sum(d.confidence for d in self.decision_history) / len(
            self.decision_history
        )

        return {
            "total_decisions": len(self.decision_history),
            "avg_confidence": round(avg_confidence, 3),
            "recent_allocations": self.decision_history[-1].allocations if self.decision_history else {},
            "recent_warnings": self.decision_history[-1].warnings if self.decision_history else [],
        }


def create_arbiter(
    model: str = "claude-sonnet-4-6",
    min_alloc: float = 0.05,
    max_alloc: float = 0.50,
    rebalance_days: int = 7,
) -> LLMArbiter:
    """Factory function to create LLMArbiter.

    Args:
        model: Claude model name
        min_alloc: Minimum allocation per agent
        max_alloc: Maximum allocation per agent
        rebalance_days: Days between rebalancing

    Returns:
        Configured LLMArbiter
    """
    return LLMArbiter(
        model=model,
        min_allocation=min_alloc,
        max_allocation=max_alloc,
        rebalance_interval=rebalance_days,
    )
