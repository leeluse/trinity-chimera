import json
import re
import os
import asyncio
import logging
import httpx
from typing import Any, Dict, List, Optional, AsyncGenerator

logger = logging.getLogger(__name__)

def _safe_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context:
        return {}
    return {k: v for k, v in context.items() if v is not None}

def _timeout_seconds() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT", "120.0"))
    except:
        return 120.0

def _ollama_config() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/"),
        "model": (os.getenv("OLLAMA_MODEL") or (os.getenv("NIM_MODEL") or "deepseek-ai/deepseek-v3.2") if os.getenv("LLM_PROVIDER") == "ollama" else "gpt-oss:20b").strip(),
    }

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
        return f"죄송합니다. 현재 로컬 Ollama 연결이 원활하지 않습니다. 하지만 백테스트 결과 순이익 {profit}을 기록한 것은 확인했습니다."
    return "현재 로컬 Ollama 모델과 연결할 수 없습니다. Ollama가 실행 중인지 확인해 주세요."

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
    """Ollama API direct non-streaming call"""
    cfg = _ollama_config()
    target_model = model or cfg["model"]
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    
    url = f"{cfg['base_url']}/api/chat"
    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": float(temperature)
        }
    }

    timeout = httpx.Timeout(timeout_sec or _timeout_seconds())
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
        logger.error(f"Ollama direct error: {e}")
        return {
            "content": _local_fallback(user_message, context),
            "provider": "local",
            "model": "fallback",
            "fallback": True
        }

async def stream_chat_reply(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    history: Optional[List[Dict[str, Any]]] = None,
    system_appendix: Optional[str] = None,
    custom_system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Ollama API direct streaming call"""
    cfg = _ollama_config()
    target_model = model or cfg["model"]
    messages = _build_messages(user_message, context, history, system_appendix, custom_system_prompt)
    
    url = f"{cfg['base_url']}/api/chat"
    payload = {
        "model": target_model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": float(temperature)
        }
    }

    timeout = httpx.Timeout(_timeout_seconds())
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise RuntimeError(f"Ollama error {response.status_code}: {error_text.decode()}")
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.error(f"Ollama direct stream error: {e}")
        yield f"\n[로컬 Ollama 연결 오류: {str(e)}]"
