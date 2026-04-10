"""
Backward-compatible wrapper for the canonical agent orchestrator.

The real implementation now lives in `ai_trading.agents.orchestrator`.
"""

from ai_trading.agents.orchestrator import (
    EvolutionOrchestrator,
    EvolutionState,
    get_evolution_orchestrator,
)

__all__ = ["EvolutionOrchestrator", "EvolutionState", "get_evolution_orchestrator"]
