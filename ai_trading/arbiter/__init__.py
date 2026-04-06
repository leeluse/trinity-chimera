"""LLM Arbiter module for intelligent agent capital allocation.

This module provides LLM-based decision making for:
- Capital reallocation based on agent performance
- Market regime analysis and agent fit evaluation
- Portfolio risk and diversity management

Example:
    >>> from ai_trading.arbiter import LLMArbiter, AgentPerformance
    >>> arbiter = LLMArbiter(model="claude-sonnet-4-6")
    >>> performances = [
    ...     AgentPerformance(
    ...         name="momentum_hunter",
    ...         sharpe_7d=1.2,
    ...         max_drawdown=0.08,
    ...         current_allocation=0.30,
    ...         ...
    ...     )
    ... ]
    >>> decision = await arbiter.analyze_performance(performances, "bull")
"""

from .llm_arbiter import LLMArbiter, AgentPerformance, AllocationDecision
from .strategy_generator import StrategyGenerator, StrategyProposal
from .market_analyzer import MarketAnalyzer, MarketAnalysis

__all__ = [
    "LLMArbiter",
    "AgentPerformance",
    "AllocationDecision",
    "StrategyGenerator",
    "StrategyProposal",
    "MarketAnalyzer",
    "MarketAnalysis",
]
