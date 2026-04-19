"""
NIM Proxy Server for Claude Code

Minimal proxy that translates between Anthropic API format and
OpenAI-compatible format for NVIDIA NIM.

Usage:
    python server.py

Then launch Claude Code with:
    ANTHROPIC_BASE_URL=http://localhost:8082 ANTHROPIC_API_KEY=dummy claude
"""

import os
import json
import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from openai import AsyncOpenAI
from dotenv import load_dotenv
import httpx

from proxy import convert_request, stream_response

load_dotenv()

# ── Config ────────────────────────────────────────────────

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NIM_BASE_URL = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", os.getenv("NIM_MODEL", "qwen/qwen3.5-397b-a17b"))
MODEL_MAP: dict = json.loads(os.getenv("MODEL_MAP", "{}"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8082"))
TIMEOUT = int(os.getenv("TIMEOUT", "600"))  # seconds, generous for slow models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("nim-proxy")

# ── OpenAI Client (for NIM) ──────────────────────────────

client = AsyncOpenAI(
    base_url=NIM_BASE_URL,
    api_key=NVIDIA_API_KEY,
    timeout=httpx.Timeout(TIMEOUT, connect=10),
)


# ── Model Resolution ─────────────────────────────────────


def resolve_model(model: str) -> str:
    """Map Claude model name to NIM model."""
    if model in MODEL_MAP:
        return MODEL_MAP[model]
    return DEFAULT_MODEL


# ── FastAPI App ───────────────────────────────────────────

app = FastAPI(title="NIM Proxy for Claude Code")


@app.post("/v1/messages")
async def create_message(request: Request):
    """
    Anthropic 호환 /v1/messages 엔드포인트.
    Claude Code가 이 경로로 요청을 보내면 NIM(OpenAI 호환)으로 변환해 스트리밍합니다.
    """
    body = await request.json()
    original_model = body.get("model", "")
    target_model = resolve_model(original_model)

    log.info(f"{original_model} -> {target_model}")

    openai_request, name_map = convert_request(body, target_model)

    if name_map:
        log.info(f"Shortened {len(name_map)} tool name(s): {list(name_map.values())}")

    return StreamingResponse(
        content=stream_response(client, openai_request, original_model, name_map),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI 호환 /v1/chat/completions 프록시.

    - 대시보드 백엔드(`/api/llm/chat`)는 NIM을 OpenAI 호환 엔드포인트로 기대합니다.
    - 이 경로에서 동일한 포맷을 받아 NIM(API 게이트웨이)로 그대로 전달하고,
      응답을 스트리밍/비스트리밍 모드에 맞게 그대로 되돌려줍니다.
    - NVIDIA_API_KEY와 NIM_BASE_URL은 이 프록시의 .env에서만 관리합니다.
    """
    body = await request.json()
    stream = bool(body.get("stream", False))

    upstream_url = f"{NIM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}"} if NVIDIA_API_KEY else {}

    if stream:
        async def proxy_stream():
            async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT, connect=10)) as client_http:
                async with client_http.stream("POST", upstream_url, headers=headers, json=body) as resp:
                    # 에러 발생 시 그대로 끊고 에러 메시지를 한 번 흘려보냄
                    if resp.status_code >= 400:
                        text = await resp.aread()
                        err_payload = {
                            "error": f"upstream error {resp.status_code}: {text[:200]!r}",
                            "done": True,
                        }
                        yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n".encode("utf-8")
                        return

                    async for chunk in resp.aiter_bytes():
                        # NIM(OpenAI 호환)의 SSE 바이트 스트림을 그대로 전달
                        if not chunk:
                            continue
                        yield chunk

        return StreamingResponse(
            proxy_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 비스트리밍 모드: 전체 JSON을 그대로 반환
    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT, connect=10)) as client_http:
        resp = await client_http.post(upstream_url, headers=headers, json=body)
        content_type = resp.headers.get("content-type", "")
        # NIM은 일반적으로 application/json 을 반환하므로 그대로 파싱
        if "application/json" in content_type:
            data = resp.json()
            return JSONResponse(status_code=resp.status_code, content=data)
        # 혹시 모를 텍스트 응답은 래핑
        text = resp.text
        return JSONResponse(
            status_code=resp.status_code,
            content={"raw": text},
        )


@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    body = await request.json()
    text = json.dumps(body.get("messages", []))
    return JSONResponse({"input_tokens": len(text) // 4})


@app.get("/health")
async def health():
    return {"status": "ok", "model": DEFAULT_MODEL}


# ── Entry Point ───────────────────────────────────────────

if __name__ == "__main__":
    if not NVIDIA_API_KEY:
        log.error("NVIDIA_API_KEY is not set!")
        log.error("Get a free key at https://build.nvidia.com")
        exit(1)
    log.info(f"Starting NIM proxy on {HOST}:{PORT}")
    log.info(f"Default model: {DEFAULT_MODEL}")
    uvicorn.run(app, host=HOST, port=PORT, timeout_keep_alive=TIMEOUT)
