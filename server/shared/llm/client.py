import json
import re
import os
import asyncio
import logging
import httpx
from typing import Any, Dict, List, Optional, AsyncGenerator
from litellm import acompletion
import litellm

# 디버그 모드 활성화 (LiteLLM Timeout 등의 원인을 상세히 로그로 출력하기 위함)
if os.getenv("LITELLM_DEBUG", "1") == "1":
    litellm._turn_on_debug()

logger = logging.getLogger(__name__)


async def stream_code_gen_reply(prompt: str) -> AsyncGenerator[Dict[str, str], None]:
    """Stage 3 코드 생성 전용. CODE_GEN_MODEL(코더/툴콜 역할) 사용."""
    model = (os.getenv("CODE_GEN_MODEL") or "").strip()
    max_tokens = int(os.getenv("CHAT_CODE_GEN_MAX_TOKENS", "3200"))
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(prompt)
    if cfg["provider"] == "litellm":
        try:
            request_kwargs = dict(
                model=target_model,
                messages=messages,
                api_base=cfg["base_url"],
                api_key=cfg.get("api_key"),
                temperature=0.3,
                max_tokens=max_tokens,
                num_retries=0,
                stream=True,
            )
            resolved_timeout = _code_gen_timeout_seconds()
            if resolved_timeout is not None:
                request_kwargs["timeout"] = resolved_timeout
            response = await acompletion(
                **request_kwargs,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                # LiteLLM: reasoning_content 지원 (DeepSeek R1 등)
                raw_thought = getattr(delta, "reasoning_content", None)
                if raw_thought:
                    yield {"thought": raw_thought}
                if delta.content:
                    yield {"content": delta.content}
            return
        except Exception as e:
            logger.error(f"stream_code_gen_reply error: {e}")
            yield {"content": f"\n[코드 생성 오류: {e}]"}
            return
    async for chunk in stream_chat_reply(prompt, model=model or None, temperature=0.3):
        yield chunk


async def stream_analysis_reply(prompt: str) -> AsyncGenerator[Dict[str, str], None]:
    """Stage 2 전략 설계 전용. ANALYSIS_MODEL(장문 분석 역할) 사용."""
    model = (os.getenv("ANALYSIS_MODEL") or "").strip()
    async for chunk in stream_chat_reply(prompt, model=model or None):
        yield chunk


async def stream_quick_reply(prompt: str) -> AsyncGenerator[Dict[str, str], None]:
    """빠른 응답 전용. QUICK_MODEL(빠른 응답 역할) 사용."""
    model = (os.getenv("QUICK_MODEL") or "").strip()
    async for chunk in stream_chat_reply(prompt, model=model or None):
        yield chunk

def _safe_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context:
        return {}
    return {k: v for k, v in context.items() if v is not None}

def _timeout_seconds() -> Optional[float]:
    """
    Base timeout for non-streaming / fallback calls.
    - `<= 0` means no timeout.
    """
    try:
        raw = float(os.getenv("LLM_TIMEOUT", "0"))
    except Exception:
        raw = 0.0
    if raw <= 0:
        return None
    return max(1.0, raw)


def _litellm_failover_timeout_seconds() -> Optional[float]:
    """
    Timeout for primary LiteLLM streaming calls.
    - `<= 0` disables timeout.
    """
    try:
        raw = float(os.getenv("LITELLM_FAILOVER_TIMEOUT", "0"))
    except Exception:
        raw = 0.0
    if raw <= 0:
        return None
    base_timeout = _timeout_seconds()
    timeout = max(1.0, raw)
    if base_timeout is not None:
        timeout = min(timeout, base_timeout)
    return timeout

def _code_gen_timeout_seconds() -> Optional[float]:
    """
    Timeout for Stage-3 code generation.
    - `<= 0` disables timeout.
    """
    try:
        raw = float(os.getenv("CHAT_CODE_GEN_TIMEOUT", "0"))
    except Exception:
        raw = 0.0
    if raw <= 0:
        return None
    timeout = max(1.0, raw)
    failover_timeout = _litellm_failover_timeout_seconds()
    base_timeout = _timeout_seconds()
    if failover_timeout is not None:
        timeout = max(timeout, failover_timeout)
    if base_timeout is not None:
        timeout = min(timeout, base_timeout)
    return timeout


def _ollama_fallback_enabled() -> bool:
    raw = (os.getenv("LLM_ENABLE_OLLAMA_FALLBACK") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _get_llm_config() -> Dict[str, str]:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "litellm":
        return {
            "provider": "litellm",
            "base_url": (os.getenv("LITELLM_BASE_URL") or "http://192.168.0.3:4000/v1").rstrip("/"),
            "model": (os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or "gpt-oss:120b-cloud").strip(),
            "api_key": (os.getenv("LITELLM_API_KEY") or "sk-dummy").strip(),
        }
    return {
        "provider": "ollama",
        "base_url": (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/"),
        "model": (os.getenv("OLLAMA_MODEL") or "gpt-oss:120b-cloud").strip(),
    }

def _normalize_model(model: Any, provider: str = "litellm") -> str:
    """Ensure model name is a normalized string for the configured provider."""
    if not model:
        return ""
    if isinstance(model, list):
        model = str(model[0]) if model else ""
    
    model_str = str(model).strip()
    if not model_str:
        return ""

    if provider == "ollama":
        # Ollama model ids are used as-is (e.g. gpt-oss:120b-cloud).
        return model_str
        
    known_providers = ["openai/", "ollama/", "anthropic/", "google/", "vertex_ai/", "bedrock/", "azure/", "mistral/", "replicate/", "huggingface/"]
    if any(model_str.startswith(p) for p in known_providers):
        return model_str
    
    # LiteLLM SDK는 provider prefix 없는 모델명을 거부할 수 있어 기본값을 ON으로 둔다.
    force_openai_prefix = (os.getenv("LITELLM_FORCE_OPENAI_PREFIX") or "1").strip().lower()
    if force_openai_prefix in {"1", "true", "yes", "on"}:
        return f"openai/{model_str}"
    # 필요 시 env로 비활성화 가능: LITELLM_FORCE_OPENAI_PREFIX=0
    return model_str


def _strip_provider_prefix(model_name: str) -> str:
    text = str(model_name or "").strip()
    if not text:
        return ""
    if "/" in text:
        return text.split("/", 1)[1].strip()
    return text


def _ollama_base_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")


def _ollama_model_fallback(preferred_model: str) -> str:
    preferred = _strip_provider_prefix(preferred_model)
    # If a stage-specific model points to OpenAI/other provider, fallback to local default.
    if preferred and (":" in preferred or preferred.startswith("qwen") or preferred.startswith("gpt") or preferred.startswith("glm")):
        return preferred
    return (os.getenv("OLLAMA_MODEL") or "gpt-oss:120b-cloud").strip()

def _build_messages(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    system_appendix: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    ctx_str = json.dumps(_safe_context(context), indent=2, ensure_ascii=False)
    
    system_content = custom_system_prompt or (
        "너는 실력 있는 퀀트 트레이딩 비서다. 사용자의 요청에 따라 전략 성과를 분석하거나 "
        "Python 기반 트레이딩 지표와 전략 코드를 작성하라. "
        "항상 전문적이고 명확한 조언을 제공하라."
    )
    
    if system_appendix:
        system_content += f"\n\n기술 지침:\n{system_appendix}"
        
    messages = [{"role": "system", "content": system_content}]
    
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
            
    prompt = f"현재 시장 상황 및 컨텍스트:\n{ctx_str}\n\n사용자 요청: {user_message}"
    messages.append({"role": "user", "content": prompt})
    return messages

def _local_fallback(user_message: str, context: Optional[Dict[str, Any]]) -> str:
    ctx = _safe_context(context)
    profit = ctx.get("netProfitAmt")
    if profit is not None:
        return f"죄송합니다. 현재 LLM 연결이 원활하지 않습니다. 하지만 백테스트 결과 순이익 {profit}을 기록한 것은 확인했습니다."
    return "현재 LLM 모델과 연결할 수 없습니다. 서비스 상태를 확인해 주세요."

async def generate_chat_reply(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    history: Optional[List[Dict[str, Any]]] = None,
    system_appendix: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    timeout_sec: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Unified LLM API non-streaming call"""
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    
    if cfg["provider"] == "litellm":
        try:
            resolved_timeout = timeout_sec if timeout_sec is not None else _litellm_failover_timeout_seconds()
            request_kwargs = dict(
                model=target_model,
                messages=messages,
                api_base=cfg["base_url"],
                api_key=cfg.get("api_key"),
                temperature=float(temperature),
                num_retries=0,
            )
            if resolved_timeout is not None:
                request_kwargs["timeout"] = resolved_timeout
            if max_tokens is not None and int(max_tokens) > 0:
                request_kwargs["max_tokens"] = int(max_tokens)
            response = await acompletion(
                stream=False,
                **request_kwargs,
            )
            finish_reason = None
            try:
                finish_reason = response.choices[0].finish_reason
            except Exception:
                finish_reason = None
            return {
                "content": response.choices[0].message.content,
                "thought": getattr(response.choices[0].message, "reasoning_content", None),
                "provider": "litellm",
                "model": target_model,
                "fallback": False,
                "finish_reason": finish_reason,
            }
        except Exception as e:
            if not _ollama_fallback_enabled():
                logger.error(f"LiteLLM error (Ollama fallback disabled): {e}")
                return {
                    "content": _local_fallback(user_message, context),
                    "provider": "litellm_error",
                    "model": target_model,
                    "fallback": True,
                }
            logger.error(f"LiteLLM error: {e}")
            # Automatic local fallback (Ollama) when LiteLLM proxy is unavailable.
            try:
                ollama_model = _ollama_model_fallback(target_model)
                ollama_url = f"{_ollama_base_url()}/api/chat"
                options = {"temperature": float(temperature)}
                if max_tokens is not None and int(max_tokens) > 0:
                    options["num_predict"] = int(max_tokens)
                payload = {
                    "model": ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": options,
                }
                async with httpx.AsyncClient(timeout=timeout_sec or _timeout_seconds()) as client:
                    response = await client.post(ollama_url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return {
                        "content": data["message"]["content"],
                        "provider": "ollama_fallback",
                        "model": ollama_model,
                        "fallback": True,
                        "finish_reason": None,
                    }
            except Exception as fb_err:
                logger.error(f"Ollama fallback error: {fb_err}")
                return {"content": _local_fallback(user_message, context), "fallback": True}
    
    # Ollama Fallback
    url = f"{cfg['base_url']}/api/chat"
    options = {"temperature": float(temperature)}
    if max_tokens is not None and int(max_tokens) > 0:
        options["num_predict"] = int(max_tokens)
    payload = {"model": target_model, "messages": messages, "stream": False, "options": options}
    try:
        async with httpx.AsyncClient(timeout=timeout_sec or _timeout_seconds()) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "content": data["message"]["content"],
                "provider": "ollama_direct",
                "model": target_model,
                "fallback": False,
                "finish_reason": None,
            }
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return {"content": _local_fallback(user_message, context), "fallback": True}

async def stream_chat_reply(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    history: Optional[List[Dict[str, Any]]] = None,
    system_appendix: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[Dict[str, str], None]:
    """Unified LLM API streaming call"""
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    logger.info(
        "[llm.stream] start provider=%s model=%s temp=%.2f history=%d msg_len=%d",
        cfg["provider"],
        target_model,
        float(temperature),
        len(history or []),
        len(user_message or ""),
    )
    
    if cfg["provider"] == "litellm":
        emitted_chars = 0
        try:
            request_kwargs = dict(
                model=target_model,
                messages=messages,
                api_base=cfg["base_url"],
                api_key=cfg.get("api_key"),
                temperature=float(temperature),
                num_retries=0,
            )
            resolved_timeout = _litellm_failover_timeout_seconds()
            if resolved_timeout is not None:
                request_kwargs["timeout"] = resolved_timeout
            if max_tokens is not None and int(max_tokens) > 0:
                request_kwargs["max_tokens"] = int(max_tokens)
            response = await acompletion(
                stream=True,
                **request_kwargs,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                raw_thought = getattr(delta, "reasoning_content", None)
                if raw_thought:
                    yield {"thought": raw_thought}
                if delta.content:
                    emitted_chars += len(delta.content)
                    yield {"content": delta.content}
            logger.info(
                "[llm.stream] done provider=litellm model=%s chars=%d",
                target_model,
                emitted_chars,
            )
            return
        except Exception as e:
            if not _ollama_fallback_enabled():
                logger.error(f"LiteLLM stream error (Ollama fallback disabled): {e}")
                yield {"content": f"\n[LLM 연결 오류: {str(e)}]\n"}
                return
            logger.error(f"LiteLLM stream error: {e}")
            # Automatic streaming fallback to local Ollama
            try:
                ollama_model = _ollama_model_fallback(target_model)
                ollama_url = f"{_ollama_base_url()}/api/chat"
                logger.info(
                    "[llm.stream] fallback start provider=ollama model=%s (from=%s)",
                    ollama_model,
                    target_model,
                )
                payload = {
                    "model": ollama_model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": float(temperature),
                        **({"num_predict": int(max_tokens)} if max_tokens is not None and int(max_tokens) > 0 else {}),
                    },
                }
                fb_chars = 0
                async with httpx.AsyncClient(timeout=_timeout_seconds()) as client:
                    async with client.stream("POST", ollama_url, json=payload) as response:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    content = chunk["message"]["content"]
                                    fb_chars += len(content)
                                    yield {"content": content}
                            except Exception:
                                continue
                logger.info(
                    "[llm.stream] fallback done provider=ollama model=%s chars=%d",
                    ollama_model,
                    fb_chars,
                )
                return
            except Exception as fb_err:
                logger.error(f"Ollama stream fallback error: {fb_err}")
                yield {"content": f"\n[LLM 연결 오류: {str(e)}]\n"}
                return

    # Ollama Fallback (Direct)
    url = f"{cfg['base_url']}/api/chat"
    payload = {
        "model": target_model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": float(temperature),
            **({"num_predict": int(max_tokens)} if max_tokens is not None and int(max_tokens) > 0 else {}),
        },
    }
    try:
        emitted_chars = 0
        async with httpx.AsyncClient(timeout=_timeout_seconds()) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            emitted_chars += len(content)
                            yield {"content": content}
                    except: continue
        logger.info(
            "[llm.stream] done provider=ollama model=%s chars=%d",
            target_model,
            emitted_chars,
        )
    except Exception as e:
        logger.error(f"Ollama stream error: {e}")
        yield {"content": f"\n[로컬 Ollama 연결 오류: {str(e)}]\n"}
