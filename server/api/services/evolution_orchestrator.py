"""
Backward-compatible wrapper for the canonical agent orchestrator.

The real implementation now lives in `server.ai_trading.agents.orchestrator`.
"""

from server.ai_trading.agents.orchestrator import (
    EvolutionOrchestrator,
    EvolutionState,
    get_evolution_orchestrator,
)

__all__ = ["EvolutionOrchestrator", "EvolutionState", "get_evolution_orchestrator"]
