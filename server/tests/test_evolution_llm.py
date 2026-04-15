import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from server.core.evolution.llm_client import EvolutionLLMClient
from server.shared.market.strategy_loader import SecurityError

def run_async(coro):
    return asyncio.run(coro)

def test_generate_strategy_code_success_first_try():
    """Test successful strategy generation on the first attempt."""
    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "```python\nclass evolved_strategy:\n    def generate_signal(self, data): return 1\n```"

    client = EvolutionLLMClient(llm_service=mock_llm)
    evolution_package = {
        "current_strategy_code": "class old_strategy: pass",
        "metrics": {"trinity_score": 100},
        "market_regime": "Bull"
    }

    code = run_async(client.generate_strategy_code(evolution_package))

    assert "class evolved_strategy" in code
    assert mock_llm.generate.call_count == 1

def test_generate_strategy_code_self_correction():
    """Test self-correction loop: fail once with SyntaxError, then succeed."""
    mock_llm = AsyncMock()
    # First call returns invalid code (missing colon), second call returns valid code
    mock_llm.generate.side_effect = [
        "```python\nclass evolved_strategy\n    def generate_signal(self, data): return 1\n```",
        "```python\nclass evolved_strategy:\n    def generate_signal(self, data): return 1\n```"
    ]

    client = EvolutionLLMClient(llm_service=mock_llm)
    evolution_package = {
        "current_strategy_code": "class old_strategy: pass",
        "metrics": {"trinity_score": 100},
        "market_regime": "Bull"
    }

    code = run_async(client.generate_strategy_code(evolution_package))

    assert "class evolved_strategy" in code
    assert mock_llm.generate.call_count == 2

def test_generate_strategy_code_max_retries_exceeded():
    """Test that the client raises an exception after max_retries failures."""
    mock_llm = AsyncMock()
    # Always return invalid code
    mock_llm.generate.return_value = "```python\nclass invalid_strategy\n```"

    client = EvolutionLLMClient(llm_service=mock_llm)
    evolution_package = {
        "current_strategy_code": "class old_strategy: pass",
        "metrics": {"trinity_score": 100},
        "market_regime": "Bull"
    }

    with pytest.raises((SecurityError, SyntaxError)):
        run_async(client.generate_strategy_code(evolution_package, max_retries=3))

    assert mock_llm.generate.call_count == 3

def test_assemble_c_mode_context():
    """Test if the C-mode context is correctly assembled in the prompt."""
    client = EvolutionLLMClient()
    evolution_package = {
        "current_strategy_code": "CODE_SAMP",
        "metrics": {"trinity_score": 150, "return": 20.0, "sharpe": 2.1, "mdd": -5.0},
        "loss_period_logs": "LOSS_LOGS",
        "evolution_history": "S_CURVE_TEXT",
        "competitive_rank": "Rank 3",
        "top_agent_traits": "Trend Following",
        "market_regime": "Bear",
        "market_volatility": "High"
    }

    prompt = client._assemble_c_mode_context(evolution_package)

    assert "CODE_SAMP" in prompt
    assert "Trinity Score: 150" in prompt
    assert "LOSS_LOGS" in prompt
    assert "S_CURVE_TEXT" in prompt
    assert "Rank 3" in prompt
    assert "Trend Following" in prompt
    assert "Current Regime: Bear" in prompt
    assert "Volatility Level: High" in prompt
