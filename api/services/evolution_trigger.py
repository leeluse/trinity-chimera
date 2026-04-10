"""
Backward-compatible wrapper for the canonical agent trigger logic.

The real implementation now lives in `ai_trading.agents.trigger`.
"""

from ai_trading.agents.trigger import EvolutionTrigger

__all__ = ["EvolutionTrigger"]
