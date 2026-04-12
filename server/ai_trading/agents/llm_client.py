import logging
import traceback
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

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


def _openai_compat_env() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("OPENAI_BASE_URL") or "").rstrip("/"),
        "api_key": (os.getenv("OPENAI_API_KEY") or "").strip(),
        "model": (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
    }


def _timeout_seconds() -> Optional[float]:
    raw_value = (
        os.getenv("EVOLUTION_LLM_TIMEOUT_SECONDS")
        or os.getenv("LLM_TIMEOUT")
        or "120"
    )
    try:
        timeout = float(raw_value)
    except ValueError:
        timeout = 120.0

    # 0 이하 값은 무제한 대기(채팅 경로와 동작 일관성 유지)
    if timeout <= 0:
        return None
    return max(5.0, min(timeout, 300.0))


def _request_retries() -> int:
    try:
        retries = int(os.getenv("EVOLUTION_LLM_REQUEST_RETRIES", "2"))
    except ValueError:
        retries = 2
    return max(0, min(retries, 6))


def _retry_backoff_seconds() -> float:
    try:
        backoff = float(os.getenv("EVOLUTION_LLM_RETRY_BACKOFF_SECONDS", "2.5"))
    except ValueError:
        backoff = 2.5
    return max(0.1, min(backoff, 60.0))


def _max_tokens() -> int:
    try:
        value = int(os.getenv("EVOLUTION_LLM_MAX_TOKENS", "1400"))
    except ValueError:
        value = 1400
    return max(128, min(value, 8192))


def _is_retryable_llm_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return True
    if "connection error" in message or "temporarily unavailable" in message:
        return True
    if "upstream 429" in message:
        return True
    return any(code in message for code in ("upstream 500", "upstream 502", "upstream 503", "upstream 504"))


def _extract_openai_text(data: Dict[str, Any]) -> str:
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                part = str(item.get("text") or "")
            else:
                part = str(item)
            if part:
                parts.append(part)
        return "".join(parts).strip()
    return str(content).strip()


def _post_json_sync(url: str, payload: Dict[str, Any], timeout: Optional[float], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req = urlrequest.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            if value is not None:
                req.add_header(str(key), str(value))
    try:
        if timeout is None:
            with urlrequest.urlopen(req) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        else:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
        raise RuntimeError(f"LLM upstream {exc.code}: {body[:400]!r}")
    except TimeoutError as exc:
        raise RuntimeError(f"LLM upstream timeout: {exc}")
    except URLError as exc:
        raise RuntimeError(f"LLM upstream connection error: {exc}")

    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"LLM upstream invalid json: {text[:200]!r}")


class OpenAICompatLLMService:
    """Minimal async wrapper for OpenAI-compatible /chat/completions endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = _timeout_seconds()
        self.request_retries = _request_retries()
        self.retry_backoff_seconds = _retry_backoff_seconds()
        self.max_tokens = _max_tokens()

    async def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        total_attempts = 1 + self.request_retries
        last_error: Optional[Exception] = None

        for attempt in range(1, total_attempts + 1):
            try:
                data = await asyncio.to_thread(_post_json_sync, url, payload, self.timeout, headers)
                content = _extract_openai_text(data)
                if not content:
                    raise RuntimeError("OpenAI-compatible provider returned empty content.")
                return content
            except Exception as exc:
                last_error = exc
                if attempt >= total_attempts or not _is_retryable_llm_error(exc):
                    raise

                sleep_seconds = self.retry_backoff_seconds * attempt
                logger.warning(
                    "Evolution LLM request failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt,
                    total_attempts,
                    exc,
                    sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)

        if last_error:
            raise last_error
        raise RuntimeError("OpenAI-compatible provider returned empty content.")


def build_default_llm_service() -> Optional[Any]:
    cfg = _openai_compat_env()
    if cfg["base_url"] and cfg["api_key"]:
        return OpenAICompatLLMService(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            model=cfg["model"],
        )
    return None


class EvolutionLLMClient:
    """
    EvolutionLLMClient handles the interaction with the LLM for strategy evolution.
    It implements "C-mode" context assembly and a self-correction loop to ensure
    generated code is syntactically correct and secure.
    """

    def __init__(self, llm_service: Any = None):
        self.llm_service = llm_service

    async def generate_strategy_code(
        self,
        evolution_package: Dict[str, Any],
        max_retries: int = 3,
        initial_error_context: Optional[str] = None,
    ) -> str:
        """
        Generates improved strategy code using C-mode context and a self-correction loop.
        initial_error_context can be used to seed runtime/validation failure feedback.
        """
        prompt = self._assemble_c_mode_context(evolution_package)
        attempt = 0
        last_error = initial_error_context

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
6. Ensure every referenced variable is defined in scope (no undefined names like `curr`).
7. Ensure backtest runtime safety: guard index access and handle short data windows.
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
