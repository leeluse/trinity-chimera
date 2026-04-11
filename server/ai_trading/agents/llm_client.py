import logging
import traceback
import os
from pathlib import Path
from typing import Dict, Any, Optional

from server.ai_trading.core.strategy_loader import StrategyLoader, SecurityError


class LLMUnavailableError(Exception):
    """Raised when LLM service is unavailable"""
    pass


def _load_agent_prompt(agent_id: str) -> str:
    """Load agent-specific prompt template"""
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / f"{agent_id}.txt"

    if prompt_file.exists():
        with open(prompt_file, 'r') as f:
            return f.read()
    else:
        # Fallback to default prompt structure
        return f"[Evolution Mode: C-MODE - {agent_id.upper()}]\n\nYou are a {agent_id.replace('_', ' ').title()} strategy expert."

logger = logging.getLogger(__name__)


class EvolutionLLMClient:
    """
    EvolutionLLMClient handles the interaction with the LLM for strategy evolution.
    It implements "C-mode" context assembly and a self-correction loop to ensure
    generated code is syntactically correct and secure.
    """

    def __init__(self, llm_service: Any = None):
        self.llm_service = llm_service

    async def generate_strategy_code(self, evolution_package: Dict[str, Any], max_retries: int = 3) -> str:
        """
        Generates improved strategy code using C-mode context and a self-correction loop.
        """
        prompt = self._assemble_c_mode_context(evolution_package)
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                code = await self._call_llm(prompt, last_error)
                code = self._clean_code(code)
                StrategyLoader.validate_code(code)
                logger.info(f"Strategy code generated and validated successfully on attempt {attempt + 1}")
                return code
            except (SecurityError, SyntaxError) as e:
                attempt += 1
                last_error = traceback.format_exc()
                logger.warning(f"Strategy validation failed (attempt {attempt}/{max_retries}): {e}")
                if attempt >= max_retries:
                    logger.error(f"Failed to generate valid strategy code after {max_retries} attempts.")
                    raise e
            except Exception as e:
                logger.error(f"Unexpected error during code generation: {e}")
                raise e

    def _assemble_c_mode_context(self, pkg: Dict[str, Any]) -> str:
        agent_id = pkg.get("agent_id", "unknown")
        agent_prompt = _load_agent_prompt(agent_id)

        current_code = pkg.get("current_strategy_code", "No code provided")
        metrics = pkg.get("metrics", {})
        loss_logs = pkg.get("loss_period_logs", "No specific loss logs available")
        history = pkg.get("evolution_history", "No history available")
        rank_info = pkg.get("competitive_rank", "Unknown")
        top_agent_traits = pkg.get("top_agent_traits", "Not provided")
        regime = pkg.get("market_regime", "Unknown")
        volatility = pkg.get("market_volatility", "Unknown")

        base_prompt = f"""
### [Evolution Mode: C-MODE]
You are an expert Quantitative Strategy Evolver. Your goal is to evolve the current trading strategy to improve its Trinity Score and robustness.

#### 1. Current Strategy Code
```python
{current_code}
```

#### 2. Performance Metrics
- Trinity Score: {metrics.get('trinity_score', 'N/A')}
- Total Return: {metrics.get('return', 'N/A')}
- Sharpe Ratio: {metrics.get('sharpe', 'N/A')}
- Max Drawdown (MDD): {metrics.get('mdd', 'N/A')}

#### 3. Vulnerability Analysis (Loss-Period Logs)
{loss_logs}

#### 4. Evolution History (S-Curve)
{history}

#### 5. Competitive Context
- Relative Rank: {rank_info}
- Top-Agent Characteristics: {top_agent_traits}

#### 6. Market Environment
- Current Regime: {regime}
- Volatility Level: {volatility}

### Instructions:
1. Analyze the current code and the vulnerabilities in the loss-period logs.
2. Adapt the strategy to the current market regime ({regime}) and volatility.
3. Incorporate the successful characteristics of top-performing agents.
4. Ensure the code strictly adheres to the `StrategyInterface` and contains no forbidden imports or functions (os, sys, subprocess, etc.).
5. Output ONLY the valid Python code for the strategy class. Do not include explanations outside the code block.
"""
        return f"{agent_prompt}\n\n{base_prompt}"

    async def _call_llm(self, prompt: str, error_context: Optional[str] = None) -> str:
        if error_context:
            prompt += f"\n\n### SELF-CORRECTION REQUIRED\nYour previous attempt failed with:\n```\n{error_context}\n```\nPlease fix the code."

        if not self.llm_service:
            raise LLMUnavailableError("LLM service not configured")

        try:
            return await self.llm_service.generate(prompt)
        except Exception as e:
            raise LLMUnavailableError(f"LLM call failed: {str(e)}")

    def _clean_code(self, text: str) -> str:
        if "```python" in text:
            text = text.split("```python")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return text.strip()
