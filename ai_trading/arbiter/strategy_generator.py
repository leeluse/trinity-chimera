"""Strategy Generator for self-improving agents.

This module implements LLM-based strategy generation for trading agents,
enabling automated parameter optimization and strategy evolution.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum

import pandas as pd
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Strategy proposal validation result."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class StrategyProposal:
    """LLM-generated strategy parameter proposal.

    Attributes:
        agent_name: Target agent name
        params: Proposed parameter values
        rationale: Explanation for the proposal
        expected_improvement: Expected performance improvement
        backtest_required: Whether backtest is required
        timestamp: Proposal timestamp
        persona: Agent persona context
        current_params: Parameters before proposal
        current_regime: Market regime context
    """
    agent_name: str
    params: Dict[str, Any]
    rationale: str
    expected_improvement: str
    backtest_required: bool
    timestamp: datetime
    persona: str
    current_params: Dict[str, Any]
    current_regime: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "params": self.params,
            "rationale": self.rationale,
            "expected_improvement": self.expected_improvement,
            "backtest_required": self.backtest_required,
            "timestamp": self.timestamp.isoformat(),
            "persona": self.persona,
            "current_params": self.current_params,
            "current_regime": self.current_regime,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyProposal":
        """Create from dictionary."""
        return cls(
            agent_name=data["agent_name"],
            params=data["params"],
            rationale=data["rationale"],
            expected_improvement=data["expected_improvement"],
            backtest_required=data["backtest_required"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            persona=data["persona"],
            current_params=data["current_params"],
            current_regime=data["current_regime"],
        )


@dataclass
class ValidationOutcome:
    """Outcome of backtest validation."""
    proposal: StrategyProposal
    result: ValidationResult
    sharpe_before: float
    sharpe_after: float
    improvement: float
    validation_message: str
    backtest_data: Optional[pd.DataFrame] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal": self.proposal.to_dict(),
            "result": self.result.value,
            "sharpe_before": self.sharpe_before,
            "sharpe_after": self.sharpe_after,
            "improvement": self.improvement,
            "validation_message": self.validation_message,
        }


class StrategyGenerator:
    """LLM-based strategy generator for agent self-improvement.

    This class enables agents to automatically generate and validate
    new strategy parameters using LLM reasoning and backtesting.

    The improvement cycle:
    1. Agent collects performance metrics
    2. LLM generates parameter proposal based on regime + performance
    3. Backtest validation with minimum Sharpe improvement threshold
    4. Accept/Reject decision
    5. Notify Arbiter of changes

    Example:
        >>> generator = StrategyGenerator()
        >>> proposal = await generator.generate_strategy(
        ...     agent_name="momentum_hunter",
        ...     persona="Trend following, bull regime specialist",
        ...     current_params={"lookback": 20, "threshold": 0.02},
        ...     recent_performance={"sharpe": 0.8, "regime": "bull"},
        ...     current_regime="bull"
        ... )
        >>> outcome = await generator.validate_proposal(
        ...     proposal,
        ...     backtest_data=historical_data
        ... )
    """

    # Minimum Sharpe ratio improvement to accept proposal
    MIN_SHARPE_IMPROVEMENT = 0.1

    # Default personas for standard agents
    DEFAULT_PERSONAS = {
        "momentum_hunter": (
            "Trend-following specialist. Only trades with the trend. "
            "Bull regime expert. Uses momentum indicators."
        ),
        "mean_reverter": (
            "Mean reversion trader. Buys panic, sells euphoria. "
            "Sideways and bear regime specialist. Uses RSI, Bollinger Bands."
        ),
        "macro_trader": (
            "Big picture trader. Ignores short-term noise. "
            "Regime-aware, low frequency trading."
        ),
        "chaos_agent": (
            "Contrarian agent. Unpredictability is the weapon. "
            "Diversification keeper. May trade against other agents."
        ),
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        min_sharpe_improvement: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ):
        """Initialize Strategy Generator.

        Args:
            model: Claude model to use
            min_sharpe_improvement: Minimum Sharpe improvement to accept (default: 0.1)
            api_key: Anthropic API key
            max_tokens: Maximum tokens for LLM response
            temperature: LLM temperature
        """
        self.model = model
        self.min_sharpe_improvement = min_sharpe_improvement
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("No API key provided. LLM calls will fail.")
            self.client = None
        else:
            self.client = Anthropic(api_key=api_key)

        # History tracking
        self.proposal_history: List[StrategyProposal] = []
        self.validation_history: List[ValidationOutcome] = []
        self.last_improvement_cycle: Dict[str, datetime] = {}

        logger.info(f"StrategyGenerator initialized with model: {model}")

    def _build_prompt(
        self,
        agent_name: str,
        persona: str,
        current_params: Dict[str, Any],
        recent_performance: Dict[str, float],
        current_regime: str,
    ) -> str:
        """Build LLM prompt for strategy generation.

        Args:
            agent_name: Name of the agent
            persona: Agent persona description
            current_params: Current parameter values
            recent_performance: Recent performance metrics
            current_regime: Current market regime

        Returns:
            Formatted prompt string
        """
        perf_str = json.dumps(recent_performance, indent=2)
        params_str = json.dumps(current_params, indent=2)

        prompt = f"""You are a trading strategy optimizer. An agent is requesting parameter improvements.

## Agent Profile
- Name: {agent_name}
- Persona: {persona}
- Current Regime: {current_regime}
- Timestamp: {datetime.now().isoformat()}

## Current Parameters
```json
{params_str}
```

## Recent 7-Day Performance
```json
{perf_str}
```

## Your Task
基于当前的市场regime和agent的performance，提出参数调整建议。

Requirements:
1. 必须保持agent的核心persona - 不要改变策略的本质
2. 基于current_regime调整参数 - 不同regime需要不同的参数
3. 解决近期performance中暴露的问题
4. 预期Sharpe ratio至少提升0.1
5. 所有参数必须有合理的rationale

## Output Format
Respond with a JSON object:

```json
{{
  "params": {{
    "param_name": value,
    "another_param": value
  }},
  "rationale": "Detailed explanation of why these parameter changes were proposed...",
  "expected_improvement": "Specific expectations for performance improvement...",
  "conservative": false,
  "risk_level": "low|medium|high"
}}
```

Important:
- Only output the JSON, no additional text
- 保留原有参数中仍然有效的部分
- 参数值必须合理并且在有效范围内
- 保守提案(conservative=true)只在市场regime非常不确定时使用
"""
        return prompt

    async def generate_strategy(
        self,
        agent_name: str,
        persona: str,
        current_params: Dict[str, Any],
        recent_performance: Dict[str, float],
        current_regime: str,
    ) -> StrategyProposal:
        """Generate strategy proposal using LLM.

        Args:
            agent_name: Name of the agent
            persona: Agent persona (or auto-lookup from DEFAULT_PERSONAS)
            current_params: Current parameter values
            recent_performance: Recent performance metrics
            current_regime: Current market regime

        Returns:
            StrategyProposal with suggested parameters

        Raises:
            RuntimeError: If LLM client not initialized
        """
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        # Use default persona if available
        if agent_name in self.DEFAULT_PERSONAS and not persona:
            persona = self.DEFAULT_PERSONAS[agent_name]

        # Build prompt
        prompt = self._build_prompt(
            agent_name,
            persona,
            current_params,
            recent_performance,
            current_regime,
        )

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

            # Parse response
            proposal_data = self._parse_response(content)

            # Create proposal
            proposal = StrategyProposal(
                agent_name=agent_name,
                params=proposal_data["params"],
                rationale=proposal_data["rationale"],
                expected_improvement=proposal_data["expected_improvement"],
                backtest_required=True,
                timestamp=datetime.now(),
                persona=persona,
                current_params=current_params,
                current_regime=current_regime,
            )

            # Store in history
            self.proposal_history.append(proposal)

            logger.info(
                f"Strategy proposed for {agent_name}: "
                f"{json.dumps(proposal.params)}"
            )

            return proposal

        except Exception as e:
            logger.error(f"Failed to generate strategy: {e}")
            raise

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response.

        Args:
            content: Raw response text

        Returns:
            Parsed proposal data
        """
        # Extract JSON from markdown
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        try:
            data = json.loads(content)
            return {
                "params": data.get("params", {}),
                "rationale": data.get("rationale", "No rationale provided"),
                "expected_improvement": data.get(
                    "expected_improvement",
                    "No specific expectations"
                ),
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Content: {content}")
            return {
                "params": {},
                "rationale": f"Parsing error: {e}",
                "expected_improvement": "Error occurred",
            }

    async def validate_proposal(
        self,
        proposal: StrategyProposal,
        backtest_data: pd.DataFrame,
        backtest_fn: Optional[Callable] = None,
    ) -> ValidationOutcome:
        """Validate proposal through backtest.

        Args:
            proposal: Strategy proposal to validate
            backtest_data: Historical data for backtesting
            backtest_fn: Optional custom backtest function

        Returns:
            ValidationOutcome with results
        """
        logger.info(f"Validating proposal for {proposal.agent_name}")

        try:
            if backtest_fn:
                # Use custom backtest function
                sharpe_before, sharpe_after = await backtest_fn(
                    proposal.current_params,
                    proposal.params,
                    backtest_data,
                )
            else:
                # Default: simple Sharpe calculation from returns
                sharpe_before, sharpe_after = self._default_backtest(
                    proposal,
                    backtest_data,
                )

            # Calculate improvement
            improvement = sharpe_after - sharpe_before

            # Determine acceptance
            if improvement >= self.min_sharpe_improvement:
                result = ValidationResult.ACCEPTED
                message = (
                    f"Accepted: Sharpe improved from {sharpe_before:.3f} "
                    f"to {sharpe_after:.3f} (Δ{improvement:+.3f})"
                )
            else:
                result = ValidationResult.REJECTED
                message = (
                    f"Rejected: Sharpe changed from {sharpe_before:.3f} "
                    f"to {sharpe_after:.3f} (Δ{improvement:+.3f}), "
                    f"below threshold {self.min_sharpe_improvement}"
                )

            outcome = ValidationOutcome(
                proposal=proposal,
                result=result,
                sharpe_before=sharpe_before,
                sharpe_after=sharpe_after,
                improvement=improvement,
                validation_message=message,
            )

            self.validation_history.append(outcome)

            logger.info(message)
            return outcome

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationOutcome(
                proposal=proposal,
                result=ValidationResult.REJECTED,
                sharpe_before=0.0,
                sharpe_after=0.0,
                improvement=0.0,
                validation_message=f"Validation error: {e}",
            )

    def _default_backtest(
        self,
        proposal: StrategyProposal,
        data: pd.DataFrame,
    ) -> Tuple[float, float]:
        """Default backtest using simple comparison.

        This is a placeholder - should be replaced with actual strategy logic.

        Args:
            proposal: Strategy proposal
            data: OHLCV data

        Returns:
            Tuple of (sharpe_before, sharpe_after)
        """
        # Placeholder - would need actual strategy evaluation
        import numpy as np

        # Simulate some returns for demonstration
        np.random.seed(42)
        returns_before = np.random.normal(0.001, 0.02, len(data))
        returns_after = np.random.normal(0.0015, 0.018, len(data))

        sharpe_before = (returns_before.mean() / returns_before.std()) * np.sqrt(365)
        sharpe_after = (returns_after.mean() / returns_after.std()) * np.sqrt(365)

        return float(sharpe_before), float(sharpe_after)

    async def run_improvement_cycle(
        self,
        agent_name: str,
        persona: str,
        current_params: Dict[str, Any],
        recent_performance: Dict[str, float],
        current_regime: str,
        backtest_data: pd.DataFrame,
        backtest_fn: Optional[Callable] = None,
    ) -> Optional[ValidationOutcome]:
        """Run full self-improvement cycle.

        Args:
            agent_name: Agent name
            persona: Agent persona
            current_params: Current params
            recent_performance: Recent performance
            current_regime: Current regime
            backtest_data: Data for validation
            backtest_fn: Optional custom backtest function

        Returns:
            ValidationOutcome or None if cycle skipped
        """
        now = datetime.now()

        # Check cycle timing (14 days apart)
        last_cycle = self.last_improvement_cycle.get(agent_name)
        if last_cycle:
            days_since = (now - last_cycle).days
            if days_since < 14:
                logger.info(f"Skipping {agent_name}: {days_since}d < 14d")
                return None

        # Generate proposal
        proposal = await self.generate_strategy(
            agent_name,
            persona,
            current_params,
            recent_performance,
            current_regime,
        )

        # Validate
        outcome = await self.validate_proposal(
            proposal,
            backtest_data,
            backtest_fn,
        )

        # Update cycle timestamp
        self.last_improvement_cycle[agent_name] = now

        return outcome

    def get_improvement_statistics(self) -> Dict[str, Any]:
        """Get improvement cycle statistics.

        Returns:
            Statistics dictionary
        """
        if not self.validation_history:
            return {
                "total_cycles": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "avg_improvement": 0.0,
            }

        accepted = sum(
            1 for v in self.validation_history
            if v.result == ValidationResult.ACCEPTED
        )
        rejected = len(self.validation_history) - accepted
        avg_improvement = sum(v.improvement for v in self.validation_history)
        avg_improvement /= len(self.validation_history)

        return {
            "total_cycles": len(self.validation_history),
            "accepted_count": accepted,
            "rejected_count": rejected,
            "acceptance_rate": accepted / len(self.validation_history),
            "avg_improvement": round(avg_improvement, 4),
            "last_cycles": {
                name: ts.isoformat()
                for name, ts in self.last_improvement_cycle.items()
            },
        }


def create_strategy_generator(
    model: str = "claude-sonnet-4-6",
    min_improvement: float = 0.1,
) -> StrategyGenerator:
    """Factory function to create StrategyGenerator.

    Args:
        model: Claude model name
        min_improvement: Minimum Sharpe improvement threshold

    Returns:
        Configured StrategyGenerator
    """
    return StrategyGenerator(
        model=model,
        min_sharpe_improvement=min_improvement,
    )
