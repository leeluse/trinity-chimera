import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Dict, Any, List, Optional
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from server.shared.db.supabase import SupabaseManager
from server.modules.chat.handler import ChatHandler
from server.modules.chat.skills._base import format_sse

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None
    force_chat_mode: bool = False   # True → 파이프라인 라우팅 생략, 일반 대화만
    chat_model: Optional[str] = None  # 일반 채팅 모드에서 사용할 모델 오버라이드

_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}


def _progress_interval_seconds() -> float:
    try:
        interval = float(os.getenv("CHAT_PROGRESS_INTERVAL_SECONDS", "1"))
    except Exception:
        interval = 1.0
    return max(0.5, min(interval, 5.0))


def _decode_sse_payload(event: str) -> Optional[Dict[str, Any]]:
    raw = (event or "").strip()
    if not raw.startswith("data: "):
        return None
    body = raw[len("data: "):].strip()
    if not body:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


async def _with_progress_keepalive(events: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    interval = _progress_interval_seconds()
    request_started_at = time.monotonic()
    active_started_at = request_started_at
    active_stage = 0
    active_label = "요청 처리 중..."
    event_iter = events.__aiter__()

    while True:
        next_event = asyncio.create_task(event_iter.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait({next_event}, timeout=interval)
                if done:
                    break
                elapsed_sec = int(max(0, time.monotonic() - active_started_at))
                yield format_sse({
                    "type": "progress",
                    "stage": active_stage,
                    "label": active_label,
                    "elapsed_sec": elapsed_sec,
                })

            event = await next_event
        except StopAsyncIteration:
            break

        payload = _decode_sse_payload(event)
        if payload:
            event_type = str(payload.get("type") or "").strip().lower()
            if event_type == "stage":
                try:
                    active_stage = int(payload.get("stage") or 0)
                except (ValueError, TypeError):
                    active_stage = active_stage
                active_label = str(payload.get("label") or active_label).strip() or active_label
                active_started_at = time.monotonic()
            elif event_type == "status":
                content = str(payload.get("content") or "").strip()
                if content:
                    active_label = content
            elif event_type == "error":
                content = str(payload.get("content") or "").strip()
                if content:
                    active_label = content
            elif event_type == "done":
                active_stage = 0
                active_label = "완료"

        yield event

@router.get("/history")
async def get_chat_history(session_id: Optional[str] = Query(None), limit: int = 200):
    """채팅 내역 조회 (session_id 없으면 전체 세션 통합 조회)"""
    try:
        # 환경변수 CHAT_HISTORY_LIMIT으로 DB 히스토리 한도 제어 가능
        try:
            env_limit = int(os.getenv("CHAT_HISTORY_LIMIT", str(limit)))
            limit = max(20, min(env_limit, 500))
        except Exception:
            pass
        db = SupabaseManager()
        history = await db.get_chat_history(session_id, limit)
        return JSONResponse(content={"success": True, "messages": history}, headers=_NO_CACHE)
    except Exception as e:
        logger.exception(f"History fetch error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, headers=_NO_CACHE)

@router.delete("/history")
async def delete_chat_history(session_id: str = Query(...)):
    """세션 채팅 기록 전체 삭제"""
    try:
        db = SupabaseManager()
        ok = await db.delete_chat_messages(session_id)
        return JSONResponse(content={"success": ok}, headers=_NO_CACHE)
    except Exception as e:
        logger.exception(f"History delete error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, headers=_NO_CACHE)

@router.get("/sessions")
async def list_chat_sessions(limit: int = 30):
    """채팅 세션 목록 조회"""
    try:
        db = SupabaseManager()
        sessions = await db.list_chat_sessions(limit)
        return JSONResponse(content={"success": True, "sessions": sessions}, headers=_NO_CACHE)
    except Exception as e:
        logger.exception(f"Sessions fetch error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, headers=_NO_CACHE)

@router.post("/run")
async def chat_run(req: ChatRequest, handler: ChatHandler = Depends()):
    """채팅 전략 파이프라인 실행 (Streaming + progress heartbeat)"""
    return StreamingResponse(
        _with_progress_keepalive(
            handler.execute_pipeline(
                req.message,
                req.session_id or "default_session",
                req.context or {},
                req.history or [],
                force_chat_mode=req.force_chat_mode,
                chat_model=req.chat_model,
            )
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
from server.modules.backtest.chat.chat_backtester import ChatBacktester

class ChatBacktestRequest(BaseModel):
    code: str
    message: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)

@router.post("/backtest")
async def chat_backtest_run(req: ChatBacktestRequest):
    """채팅 중 생성된 전략에 대한 독립 백테스트 실행"""
    try:
        return await ChatBacktester.run(
            code=req.code,
            message=req.message,
            context=req.context
        )
    except Exception as exc:
        logger.exception("Chat backtest error")
        return {"success": False, "error": str(exc)}

class DeployRequest(BaseModel):
    code: str
    title: Optional[str] = "AI Generated Strategy"

@router.post("/deploy")
async def chat_deploy(req: DeployRequest, handler: ChatHandler = Depends()):
    """전략 라이브러리에 저장/배포"""
    return await handler.deploy_strategy(req.dict())
