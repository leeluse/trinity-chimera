import logging
import traceback
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from litellm import acompletion


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
_LLM_SEMAPHORE: Optional[asyncio.Semaphore] = None
_LLM_SEMAPHORE_LIMIT: Optional[int] = None


def _openai_compat_env() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("OPENAI_BASE_URL") or "").rstrip("/"),
        "api_key": (os.getenv("OPENAI_API_KEY") or "").strip(),
        "model": (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
    }


def _anthropic_env() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("ANTHROPIC_BASE_URL") or "").rstrip("/"),
        "api_key": (os.getenv("ANTHROPIC_API_KEY") or "").strip(),
        "model": (os.getenv("ANTHROPIC_MODEL") or "claude-3-5-sonnet").strip(),
    }


def _litellm_provider() -> str:
    provider = (os.getenv("EVOLUTION_LITELLM_PROVIDER") or "openai").strip()
    return provider or "openai"


def _normalize_litellm_model(model: str) -> str:
    model = (model or "").strip()
    if not model:
        return model
    if "/" in model:
        return model
    return f"{_litellm_provider()}/{model}"


def _litellm_fallback_models(primary_model: str) -> List[str]:
    raw = (
        os.getenv("EVOLUTION_LLM_FALLBACK_MODELS")
        or "claude-haiku-4-5,claude-3-5-haiku-20241022"
    )
    items = [part.strip() for part in raw.split(",") if part.strip()]
    normalized: List[str] = []
    for item in items:
        model_name = _normalize_litellm_model(item)
        if model_name and model_name != primary_model and model_name not in normalized:
            normalized.append(model_name)
    return normalized


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


def _llm_max_concurrency() -> int:
    raw_value = (
        os.getenv("EVOLUTION_LLM_MAX_CONCURRENCY")
        or os.getenv("LLM_MAX_CONCURRENCY")
        or "1"
    )
    try:
        concurrency = int(raw_value)
    except ValueError:
        concurrency = 1
    return max(1, min(concurrency, 8))


def _get_llm_semaphore() -> asyncio.Semaphore:
    global _LLM_SEMAPHORE, _LLM_SEMAPHORE_LIMIT
    concurrency = _llm_max_concurrency()
    if _LLM_SEMAPHORE is None or _LLM_SEMAPHORE_LIMIT != concurrency:
        _LLM_SEMAPHORE = asyncio.Semaphore(concurrency)
        _LLM_SEMAPHORE_LIMIT = concurrency
    return _LLM_SEMAPHORE


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
        semaphore = _get_llm_semaphore()

        for attempt in range(1, total_attempts + 1):
            try:
                async with semaphore:
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


class LiteLLMProxyService:
    """LiteLLM SDK service with native retry + fallback support."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = _normalize_litellm_model(model)
        self.fallback_models = _litellm_fallback_models(self.model)
        self.timeout = _timeout_seconds()
        self.request_retries = _request_retries()
        self.max_tokens = _max_tokens()

    async def generate(self, prompt: str) -> str:
        kwargs: Dict[str, Any] = {}
        if self.fallback_models:
            kwargs["fallbacks"] = self.fallback_models

        response = await acompletion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=self.max_tokens,
            stream=False,
            api_base=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            num_retries=self.request_retries,
            **kwargs,
        )
        content = _extract_openai_text(response)
        if not content:
            raise RuntimeError("LiteLLM provider returned empty content.")
        return content


def build_default_llm_service() -> Optional[Any]:
    # 1. Try Anthropic/Claude proxy first (preferred by user)
    acfg = _anthropic_env()
    if acfg["base_url"] and acfg["api_key"]:
        use_litellm = (os.getenv("EVOLUTION_LITELLM_ENABLE") or "1").strip().lower() not in {"0", "false", "no"}
        if use_litellm:
            return LiteLLMProxyService(
                base_url=acfg["base_url"],
                api_key=acfg["api_key"],
                model=acfg["model"],
            )
        return OpenAICompatLLMService(
            base_url=acfg["base_url"],
            api_key=acfg["api_key"],
            model=acfg["model"],
        )

    # 2. Try generic OpenAI compatible
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
        # 진화 모드 자동 선택 (Mode 1: Parameter Tuning / Mode 2: Free Generation)
        mode = self._select_evolution_mode(evolution_package)
        evolution_package["_selected_mode"] = mode  # 로깅용
        logger.info(f"[{evolution_package.get('agent_id', '?')}] Evolution mode selected: {mode}")

        prompt = self._assemble_c_mode_context(evolution_package, mode=mode)
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

    def _select_evolution_mode(self, pkg: Dict[str, Any]) -> str:
        """
        시장 상황과 성과 지표를 기반으로 진화 모드를 자동 선택:

        Mode 1 (parameter_tuning):
          - 전략 기본 로직은 유지하고 임계값/파라미터만 조정
          - 조건: 초기 진화(count < 3) 또는 Trinity Score 개선 중(score > 70)

        Mode 2 (free_generation):
          - 새 지표/로직 구조를 자유롭게 도입
          - 조건: (1) 시장 레짐 변화 감지, (2) trinity_score < 50 & 반복 시도,
                  (3) trinity_score > 70 & count >= 5 (발전 한계 도달), (4) 명시적 환경 변수
        """
        metrics = pkg.get("metrics", {})
        trinity_score = float(metrics.get("trinity_score") or 0.0)
        market_regime = pkg.get("market_regime", "Unknown")
        evolution_count = int(pkg.get("evolution_count", 0))

        # 환경 변수로 강제 모드 오버라이드
        forced_mode = os.getenv("EVOLUTION_FORCE_MODE", "").strip().lower()
        if forced_mode in ("free_generation", "mode2", "2"):
            logger.info("Evolution mode forced to FREE_GENERATION via env var.")
            return "free_generation"
        if forced_mode in ("parameter_tuning", "mode1", "1"):
            return "parameter_tuning"

        # 조건 1: 시장 레짐 변화 → 구조 전환 필요
        last_regime = getattr(self, "_last_regime_cache", {}).get(pkg.get("agent_id", ""), "")
        if last_regime and last_regime != market_regime and market_regime not in ("Unknown", ""):
            logger.info(f"Regime shift detected ({last_regime} → {market_regime}): FREE_GENERATION triggered.")
            if not hasattr(self, "_last_regime_cache"):
                self._last_regime_cache = {}
            self._last_regime_cache[pkg.get("agent_id", "")] = market_regime
            return "free_generation"
        if not hasattr(self, "_last_regime_cache"):
            self._last_regime_cache = {}
        self._last_regime_cache[pkg.get("agent_id", "")] = market_regime

        # 조건 2: 점수가 나쁘고 여러 번 시도했지만 개선 없음
        if trinity_score < 50 and evolution_count >= 3:
            logger.info(f"Low score ({trinity_score:.1f}) + high evolution count ({evolution_count}): FREE_GENERATION triggered.")
            return "free_generation"

        # 조건 3: 점수는 좋지만 5회 이상 진화 → 파라미터 한계 도달, 구조 탐색
        if trinity_score > 70 and evolution_count >= 5:
            logger.info(f"Score plateau ({trinity_score:.1f}) after {evolution_count} evolutions: FREE_GENERATION triggered.")
            return "free_generation"

        # 기본: 파라미터 튜닝
        return "parameter_tuning"

    def _assemble_c_mode_context(self, pkg: Dict[str, Any], mode: str = "parameter_tuning") -> str:
        agent_id = pkg.get("agent_id", "unknown")
        agent_prompt = _load_agent_prompt(agent_id)

        # [최적화] STRATEGY.md 법전 로드
        strategy_doc = ""
        doc_path = Path("STRATEGY.md")
        if doc_path.exists():
            strategy_doc = doc_path.read_text(encoding="utf-8")

        current_code = pkg.get("current_strategy_code", "No code provided")
        metrics = pkg.get("metrics", {})
        loss_logs = pkg.get("loss_period_logs", "No specific loss logs available")
        history = pkg.get("evolution_history", "No history available")
        rank_info = pkg.get("competitive_rank", "Unknown")
        regime = pkg.get("market_regime", "Unknown")
        volatility = pkg.get("market_volatility", "Unknown")

        def _m(key, fmt=""):
            val = metrics.get(key)
            if val is None: return "N/A"
            try: return format(float(val), fmt) if fmt else str(val)
            except: return str(val)

        is_free_gen = (mode == "free_generation")
        mode_label = "Mode 2: FREE GENERATION" if is_free_gen else "Mode 1: PARAMETER TUNING"

        base_prompt = f"""
### [Evolution Mode: C-MODE | {mode_label}]
너는 트리니티 시스템의 핵심 퀀트 에이전트이다. 아래의 'STRATEGY.md' 규칙을 준수하여 전략을 진화시켜라.

#### 0. 공식 가이드라인 (STRATEGY.md)
{strategy_doc[:1500]}

#### 1. Current Strategy Code
```python
{current_code}
```

#### 2. Performance Metrics
- Trinity Score: {_m('trinity_score', '.2f')}
- Total Return: {_m('return', '.4f')}
- Sharpe Ratio: {_m('sharpe', '.2f')}
- Max Drawdown: {_m('mdd', '.4f')}

#### 3. Market Context
- Regime: {regime} | Volatility: {volatility}
"""

        core_instructions = """
### Technical Constraints (Non-negotiable):
1. **Inheritance**: 반드시 `Strategy` 클래스를 상속받은 `CustomStrategy`를 작성하라.
2. **Signal Object**: `generate_signals(self, data, params)` 메서드는 반드시 `Signal` 객체를 반환해야 한다.
   - 예: `return Signal(entry=True, exit=False, direction='long', ...)`
   - **주의**: 과거의 1, -1, 0 정수 반환 방식은 절대 금지한다.
3. **Fields**: 오직 `entry`, `exit`, `direction`, `stop_loss`, `take_profit` 필드만 사용하라.
4. **Code Only**: 설명 없이 오직 ```python ... ``` 코드 블록만 출력하라.
"""
        
        if is_free_gen:
            mode_instructions = f"\n### MODE 2: FREE GENERATION\n현재 시장 레짐({regime})에 최적화된 완전히 새로운 로직 구조를 설계하라. 지표와 필터를 과감하게 변경하라."
        else:
            mode_instructions = f"\n### MODE 1: PARAMETER TUNING\n기존 로직의 뼈대는 유지하되, 현재 변동성({volatility})에 맞춰 최적의 임계값과 파라미터(lookback 등)를 정교하게 튜닝하라."

        return f"{agent_prompt}\n\n{base_prompt}\n{core_instructions}\n{mode_instructions}"

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
