import json
import re
import os
import asyncio
import logging
import httpx
from typing import Any, Dict, List, Optional, AsyncGenerator
from litellm import acompletion
import litellm

# 디버그 모드 활성화 (필요할 때만 켜기: LITELLM_DEBUG=1)
if os.getenv("LITELLM_DEBUG", "0") == "1":
    litellm._turn_on_debug()

logger = logging.getLogger(__name__)


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _code_gen_stream_retries() -> int:
    try:
        raw = int(os.getenv("CHAT_CODE_GEN_STREAM_RETRIES", "1"))
    except Exception:
        raw = 1
    return max(0, min(raw, 3))


def _code_gen_fallback_timeout_seconds(stream_timeout: Optional[float]) -> Optional[float]:
    try:
        raw = float(os.getenv("CHAT_CODE_GEN_FALLBACK_TIMEOUT", "60"))
    except Exception:
        raw = 60.0
    if raw <= 0:
        return None
    fallback_timeout = max(5.0, raw)
    if stream_timeout is not None:
        fallback_timeout = min(fallback_timeout, max(5.0, stream_timeout))
    return fallback_timeout


def _code_gen_hard_timeout_seconds(stream_timeout: Optional[float]) -> Optional[float]:
    try:
        raw = float(os.getenv("CHAT_CODE_GEN_HARD_TIMEOUT", "75"))
    except Exception:
        raw = 75.0
    if raw <= 0:
        return None
    hard_timeout = max(5.0, raw)
    if stream_timeout is not None:
        # SDK timeout보다 약간 큰 절대 상한으로 벽시계 시간 보장
        hard_timeout = min(hard_timeout, max(5.0, stream_timeout + 5.0))
    return hard_timeout


def _is_timeout_error(exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    text = str(exc or "").lower()
    if not text:
        return False
    return (
        "timeout" in text
        or "timed out" in text
        or "apitimeouterror" in text
        or "connecttimeout" in text
        or "readtimeout" in text
    )


def _exc_text(exc: Optional[Exception]) -> str:
    if exc is None:
        return "unknown error"
    text = str(exc).strip()
    if text:
        return text
    name = exc.__class__.__name__ if hasattr(exc, "__class__") else "Exception"
    return name


def _iter_text_chunks(text: str, chunk_size: int = 1200) -> List[str]:
    body = str(text or "")
    if not body:
        return []
    size = max(200, chunk_size)
    return [body[i:i + size] for i in range(0, len(body), size)]


async def stream_code_gen_reply(prompt: str, max_tokens: Optional[int] = None) -> AsyncGenerator[Dict[str, str], None]:
    """Stage 3 코드 생성 전용. CODE_GEN_MODEL(코더/툴콜 역할) 사용."""
    model = (os.getenv("CODE_GEN_MODEL") or "").strip()
    max_tokens = max_tokens or int(os.getenv("CHAT_CODE_GEN_MAX_TOKENS", "4000"))
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(prompt)
    if cfg["provider"] == "litellm":
        request_kwargs = dict(
            model=target_model,
            messages=messages,
            api_base=cfg["base_url"],
            api_key=cfg.get("api_key"),
            temperature=0.3,
            max_tokens=max_tokens,
            num_retries=0,
        )
        resolved_timeout = _code_gen_timeout_seconds()
        if resolved_timeout is not None:
            request_kwargs["timeout"] = resolved_timeout
        _apply_litellm_provider_hint(target_model, request_kwargs)

        max_attempts = _code_gen_stream_retries() + 1
        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            try:
                hard_timeout = _code_gen_hard_timeout_seconds(resolved_timeout)
                emitted_chars = 0
                if hard_timeout is not None:
                    async with asyncio.timeout(hard_timeout):
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
                else:
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
                if emitted_chars == 0:
                    raise RuntimeError("empty streaming response")
                return
            except Exception as e:
                last_error = e
                is_timeout = _is_timeout_error(e)
                logger.error(
                    "[codegen.stream] attempt %d/%d failed model=%s timeout=%s err=%s",
                    attempt,
                    max_attempts,
                    target_model,
                    is_timeout,
                    _exc_text(e),
                )
                if attempt < max_attempts:
                    await asyncio.sleep(min(3.0, 0.8 * attempt))
                    continue

        # Streaming 실패 시 non-stream 폴백으로 완료 코드 확보 시도
        if _env_enabled("CHAT_CODE_GEN_NON_STREAM_FALLBACK", True):
            try:
                fallback_timeout = _code_gen_fallback_timeout_seconds(resolved_timeout)
                fallback_kwargs = dict(request_kwargs)
                if fallback_timeout is not None:
                    fallback_kwargs["timeout"] = fallback_timeout
                if fallback_timeout is not None:
                    async with asyncio.timeout(max(5.0, fallback_timeout + 5.0)):
                        response = await acompletion(
                            stream=False,
                            **fallback_kwargs,
                        )
                else:
                    response = await acompletion(
                        stream=False,
                        **fallback_kwargs,
                    )
                fallback_thought = getattr(response.choices[0].message, "reasoning_content", None)
                fallback_content = str(response.choices[0].message.content or "")
                if fallback_thought:
                    yield {"thought": fallback_thought}
                if fallback_content.strip():
                    for part in _iter_text_chunks(fallback_content):
                        yield {"content": part}
                    logger.info(
                        "[codegen.stream] non-stream fallback success model=%s chars=%d",
                        target_model,
                        len(fallback_content),
                    )
                    return
                raise RuntimeError("empty non-stream fallback response")
            except Exception as fb_err:
                logger.error("[codegen.stream] non-stream fallback failed model=%s err=%s", target_model, _exc_text(fb_err))
                if last_error is None:
                    last_error = fb_err

        # 모델 폴백: CODE_GEN_FALLBACK_MODEL로 재시도
        fallback_code_model = (os.getenv("CODE_GEN_FALLBACK_MODEL") or "").strip()
        if fallback_code_model and fallback_code_model != model:
            logger.warning(
                "[codegen.stream] primary model=%s failed, trying CODE_GEN_FALLBACK_MODEL=%s",
                target_model,
                fallback_code_model,
            )
            fb_target = _normalize_model(fallback_code_model, provider=cfg["provider"])
            fb_kwargs = dict(request_kwargs)
            fb_kwargs["model"] = fb_target
            _apply_litellm_provider_hint(fb_target, fb_kwargs)
            try:
                fb_hard = resolved_timeout + 10.0 if resolved_timeout else None
                fb_chars = 0
                if fb_hard is not None:
                    async with asyncio.timeout(fb_hard):
                        fb_resp = await acompletion(stream=True, **fb_kwargs)
                        async for chunk in fb_resp:
                            delta = chunk.choices[0].delta
                            raw_thought = getattr(delta, "reasoning_content", None)
                            if raw_thought:
                                yield {"thought": raw_thought}
                            if delta.content:
                                fb_chars += len(delta.content)
                                yield {"content": delta.content}
                else:
                    fb_resp = await acompletion(stream=True, **fb_kwargs)
                    async for chunk in fb_resp:
                        delta = chunk.choices[0].delta
                        raw_thought = getattr(delta, "reasoning_content", None)
                        if raw_thought:
                            yield {"thought": raw_thought}
                        if delta.content:
                            fb_chars += len(delta.content)
                            yield {"content": delta.content}
                if fb_chars > 0:
                    logger.info("[codegen.stream] fallback model success model=%s chars=%d", fb_target, fb_chars)
                    return
                last_error = RuntimeError(f"empty response from fallback model {fallback_code_model}")
            except Exception as fb_model_err:
                logger.error("[codegen.stream] fallback model failed model=%s err=%s", fb_target, _exc_text(fb_model_err))
                if last_error is None:
                    last_error = fb_model_err

        final_err = last_error or RuntimeError("unknown code generation error")
        err_text = _exc_text(final_err)
        logger.error(f"stream_code_gen_reply error: {err_text}")
        yield {"content": f"\n[코드 생성 오류: {err_text}]"}
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


def _litellm_provider_hint() -> str:
    # bare model 이름(minimax-m2.5 등) 사용 시 LiteLLM SDK가 provider 힌트를 요구할 수 있다.
    return (
        os.getenv("LITELLM_CUSTOM_PROVIDER")
        or os.getenv("EVOLUTION_LITELLM_PROVIDER")
        or "openai"
    ).strip()


def _apply_litellm_provider_hint(model_name: str, request_kwargs: Dict[str, Any]) -> None:
    text = str(model_name or "").strip()
    if not text:
        return
    # provider prefix가 이미 있으면 추가 힌트 불필요
    if "/" in text:
        return
    hint = _litellm_provider_hint()
    if hint:
        request_kwargs.setdefault("custom_llm_provider", hint)


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
            _apply_litellm_provider_hint(target_model, request_kwargs)
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
            _apply_litellm_provider_hint(target_model, request_kwargs)
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
