"""
Backward-compatible wrapper for the canonical agent LLM client.

The real implementation now lives in `ai_trading.agents.llm_client`.
"""

from ai_trading.agents.llm_client import EvolutionLLMClient

__all__ = ["EvolutionLLMClient"]
