import json
import re
import os
import asyncio
import logging
import httpx
from typing import Any, Dict, List, Optional, AsyncGenerator
from litellm import acompletion

logger = logging.getLogger(__name__)


async def stream_code_gen_reply(prompt: str) -> AsyncGenerator[str, None]:
    """Stage 3 코드 생성 전용. CODE_GEN_MODEL(코더/툴콜 역할) 사용."""
    model = (os.getenv("CODE_GEN_MODEL") or "").strip()
    async for chunk in stream_chat_reply(prompt, model=model or None):
        yield chunk


async def stream_analysis_reply(prompt: str) -> AsyncGenerator[str, None]:
    """Stage 2 전략 설계 전용. ANALYSIS_MODEL(장문 분석 역할) 사용."""
    model = (os.getenv("ANALYSIS_MODEL") or "").strip()
    async for chunk in stream_chat_reply(prompt, model=model or None):
        yield chunk


async def stream_quick_reply(prompt: str) -> AsyncGenerator[str, None]:
    """빠른 응답 전용. QUICK_MODEL(빠른 응답 역할) 사용."""
    model = (os.getenv("QUICK_MODEL") or "").strip()
    async for chunk in stream_chat_reply(prompt, model=model or None):
        yield chunk

def _safe_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context:
        return {}
    return {k: v for k, v in context.items() if v is not None}

def _timeout_seconds() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT", "120.0"))
    except:
        return 120.0


def _litellm_failover_timeout_seconds() -> float:
    """Short timeout for primary LiteLLM call before local fallback."""
    try:
        raw = float(os.getenv("LITELLM_FAILOVER_TIMEOUT", "12.0"))
    except Exception:
        raw = 12.0
    return max(3.0, min(raw, _timeout_seconds()))

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
    """Ensure model name is a string and prepend provider if missing (litellm only)."""
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
    
    # 만약 환경변수에서 이미 복잡한 이름을 사용 중이라면 (예: minimax-m2.5) 
    # LiteLLM이 자체적으로 추론하게 두거나 기본값인 openai/를 명시함.
    # 하지만 litellm 프록시 연동 시에는 openai/ 접두사가 가장 범용적임.
    return f"openai/{model_str}"


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
) -> Dict[str, Any]:
    """Unified LLM API non-streaming call"""
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    
    if cfg["provider"] == "litellm":
        try:
            response = await acompletion(
                model=target_model,
                messages=messages,
                api_base=cfg["base_url"],
                api_key=cfg.get("api_key"),
                temperature=float(temperature),
                timeout=timeout_sec or _litellm_failover_timeout_seconds(),
                num_retries=0,
                stream=False
            )
            return {
                "content": response.choices[0].message.content,
                "provider": "litellm",
                "model": target_model,
                "fallback": False
            }
        except Exception as e:
            logger.error(f"LiteLLM error: {e}")
            # Automatic local fallback (Ollama) when LiteLLM proxy is unavailable.
            try:
                ollama_model = _ollama_model_fallback(target_model)
                ollama_url = f"{_ollama_base_url()}/api/chat"
                payload = {
                    "model": ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": float(temperature)},
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
                    }
            except Exception as fb_err:
                logger.error(f"Ollama fallback error: {fb_err}")
                return {"content": _local_fallback(user_message, context), "fallback": True}
    
    # Ollama Fallback
    url = f"{cfg['base_url']}/api/chat"
    payload = {"model": target_model, "messages": messages, "stream": False, "options": {"temperature": float(temperature)}}
    try:
        async with httpx.AsyncClient(timeout=timeout_sec or _timeout_seconds()) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "content": data["message"]["content"],
                "provider": "ollama_direct",
                "model": target_model,
                "fallback": False
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
) -> AsyncGenerator[str, None]:
    """Unified LLM API streaming call"""
    cfg = _get_llm_config()
    target_model = _normalize_model(model or cfg["model"], provider=cfg["provider"])
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    
    if cfg["provider"] == "litellm":
        try:
            response = await acompletion(
                model=target_model,
                messages=messages,
                api_base=cfg["base_url"],
                api_key=cfg.get("api_key"),
                temperature=float(temperature),
                timeout=_litellm_failover_timeout_seconds(),
                num_retries=0,
                stream=True
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return
        except Exception as e:
            logger.error(f"LiteLLM stream error: {e}")
            # Automatic streaming fallback to local Ollama
            try:
                ollama_model = _ollama_model_fallback(target_model)
                ollama_url = f"{_ollama_base_url()}/api/chat"
                payload = {
                    "model": ollama_model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": float(temperature)},
                }
                async with httpx.AsyncClient(timeout=_timeout_seconds()) as client:
                    async with client.stream("POST", ollama_url, json=payload) as response:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                if "message" in chunk and "content" in chunk["message"]:
                                    yield chunk["message"]["content"]
                            except Exception:
                                continue
                return
            except Exception as fb_err:
                logger.error(f"Ollama stream fallback error: {fb_err}")
                yield f"\n[LLM 연결 오류: {str(e)}]"
                return

    # Ollama Fallback
    url = f"{cfg['base_url']}/api/chat"
    payload = {"model": target_model, "messages": messages, "stream": True, "options": {"temperature": float(temperature)}}
    try:
        async with httpx.AsyncClient(timeout=_timeout_seconds()) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                    except: continue
    except Exception as e:
        logger.error(f"Ollama stream error: {e}")
        yield f"\n[로컬 Ollama 연결 오류: {str(e)}]"
