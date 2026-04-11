import json
import logging
import os
import asyncio
from typing import Any, Dict, List, Optional

from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "너는 백테스트 결과를 상세히 분석해주는 전문 퀀트 어시스턴트다. "
    "사용자가 백테스트 결과를 물어보면 반드시 다음 형식을 지켜서 답변하라:\n\n"
    "요약은 다음과 같습니다 :\n"
    "---\n"
    "### **전략 이름 — 백테스트 결과**\n\n"
    "**전략:** [전략명] | **종목:** [심볼] | **타임프레임:** [주기] | **기간:** [시작일] → [종료일]\n\n"
    "#### **핵심 지표**\n"
    "*   **순수익:** [기호]$[금액] ([수익률])\n"
    "*   **최대 낙폭:** [MDD%]\n"
    "*   **샤프 비율:** [값]\n"
    "*   **손익 배수:** [값]\n\n"
    "#### **방향별 분석**\n"
    "*   **롱:** [건수]건, 승률 [승률]%, [기호]$[수익]\n"
    "*   **숏:** [건수]건, 승률 [승률]%, [기호]$[수익]\n\n"
    "#### **전략 설계**\n"
    "*   [사용한 채널/지표 및 파라미터 상세]\n"
    "*   [필터링 로직 및 ATR 손절/익절 배수]\n"
    "*   [레버리지 및 자산 배분 방식]\n\n"
    "#### **진단 인사이트**\n"
    "*   [청산 원인 분석: 반전 신호 vs 손익절 발동 비중]\n"
    "*   [개선 제안: 트레일링 스탑, 보유 시간 필터 등 구체적 제안]\n\n"
    "실제 데이터(context)를 바탕으로 위 항목들을 전문적이고 실무적인 톤으로 작성하라."
)


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "local").strip().lower()


def _timeout_seconds() -> Optional[float]:
    try:
        timeout = float(os.getenv("LLM_TIMEOUT", "8"))
    except ValueError:
        timeout = 8.0
    if timeout <= 0:
        return None
    return max(3.0, min(timeout, 120.0))


def _nim_config() -> Dict[str, str]:
    api_key = (os.getenv("NVIDIA_API_KEY") or os.getenv("NVIDIA_NIM_API_KEY") or "").strip()
    return {
        "base_url": (os.getenv("NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/"),
        "api_key": api_key,
        "model": (os.getenv("NIM_MODEL") or "qwen/qwen3.5-397b-a17b").strip(),
    }


def _openai_compat_config() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("OPENAI_BASE_URL") or "").rstrip("/"),
        "api_key": (os.getenv("OPENAI_API_KEY") or "").strip(),
        "model": (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip(),
    }


def _ollama_config() -> Dict[str, str]:
    return {
        "base_url": (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/"),
        "model": (os.getenv("OLLAMA_MODEL") or "llama3.1").strip(),
    }


def _safe_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context:
        return {}

    allowed = {
        "symbol",
        "timeframe",
        "strategy",
        "netProfitAmt",
        "winRate",
        "maxDrawdown",
        "sharpe",
        "profitFactor",
        "trades",
    }
    return {key: value for key, value in context.items() if key in allowed}


def _build_messages(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    system_appendix: Optional[str] = None,
) -> List[Dict[str, str]]:
    context_payload = _safe_context(context)
    system_text = _SYSTEM_PROMPT
    if system_appendix:
        system_text += "\n\n추가 가이드:\n" + str(system_appendix).strip()
    if context_payload:
        system_text += "\n\n참고 백테스트 컨텍스트:\n" + json.dumps(context_payload, ensure_ascii=False)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_text}]

    if history:
        for item in history[-8:]:
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role in {"system", "user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages


async def _post_json(
    url: str,
    payload: Dict[str, Any],
    timeout: Optional[float],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _post_json_sync,
        url,
        payload,
        timeout,
        headers,
    )


def _post_json_sync(
    url: str,
    payload: Dict[str, Any],
    timeout: Optional[float],
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, method="POST")
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
        raise RuntimeError(f"upstream {exc.code}: {body[:400]!r}")
    except URLError as exc:
        raise RuntimeError(f"upstream connection error: {exc}")

    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"invalid json response: {text[:200]!r}")


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


def _extract_ollama_text(data: Dict[str, Any]) -> str:
    content = ((data.get("message") or {}).get("content")) or ""
    return str(content).strip()


def _local_fallback(user_message: str, context: Optional[Dict[str, Any]]) -> str:
    ctx = _safe_context(context)
    profit = ctx.get("netProfitAmt")
    win_rate = ctx.get("winRate")
    drawdown = ctx.get("maxDrawdown")

    if any(value is not None for value in (profit, win_rate, drawdown)):
        return (
            f"손익={profit if profit is not None else 'N/A'}, "
            f"승률={win_rate if win_rate is not None else 'N/A'}, "
            f"MDD={drawdown if drawdown is not None else 'N/A'} 기준으로 보면 "
            "수익성은 유지되고 있고, 다음 단계는 진입 조건 단순화와 손절 규칙 고정으로 과최적화를 줄이는 것입니다."
        )

    return (
        f"질문하신 내용은 '{user_message}'로 이해했습니다. "
        "백테스트 관점에서 핵심 지표(수익률, MDD, 승률, PF)를 같이 보내주시면 더 구체적으로 코멘트할 수 있습니다."
    )


async def generate_chat_reply(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    history: Optional[List[Dict[str, str]]] = None,
    system_appendix: Optional[str] = None,
) -> Dict[str, Any]:
    provider = _provider()
    timeout = _timeout_seconds()
    messages = _build_messages(
        user_message=user_message,
        context=context,
        history=history,
        system_appendix=system_appendix,
    )

    if provider == "nim":
        cfg = _nim_config()
        if not cfg["api_key"]:
            raise RuntimeError("NIM API key is missing (NVIDIA_NIM_API_KEY/NVIDIA_API_KEY).")
        chosen_model = (model or cfg["model"]).strip()
        url = f"{cfg['base_url']}/chat/completions"
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": float(temperature),
            "stream": False,
        }
        data = await _post_json(url, payload, timeout, headers={"Authorization": f"Bearer {cfg['api_key']}"})
        content = _extract_openai_text(data)
        if not content:
            raise RuntimeError("NIM returned empty content.")
        return {"content": content, "provider": provider, "model": chosen_model, "fallback": False}

    if provider in {"openai", "openai-compatible", "openai_compatible"}:
        cfg = _openai_compat_config()
        if not cfg["base_url"] or not cfg["api_key"]:
            raise RuntimeError("OPENAI_BASE_URL/OPENAI_API_KEY is missing.")
        chosen_model = (model or cfg["model"]).strip()
        url = f"{cfg['base_url']}/chat/completions"
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": float(temperature),
            "stream": False,
        }
        data = await _post_json(url, payload, timeout, headers={"Authorization": f"Bearer {cfg['api_key']}"})
        content = _extract_openai_text(data)
        if not content:
            raise RuntimeError("OpenAI-compatible provider returned empty content.")
        return {"content": content, "provider": provider, "model": chosen_model, "fallback": False}

    if provider == "ollama":
        cfg = _ollama_config()
        chosen_model = (model or cfg["model"]).strip()
        url = f"{cfg['base_url']}/api/chat"
        payload = {
            "model": chosen_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": float(temperature)},
        }
        data = await _post_json(url, payload, timeout)
        content = _extract_ollama_text(data)
        if not content:
            raise RuntimeError("Ollama returned empty content.")
        return {"content": content, "provider": provider, "model": chosen_model, "fallback": False}

    local_answer = _local_fallback(user_message, context)
    return {"content": local_answer, "provider": "local", "model": "local-fallback", "fallback": True}
