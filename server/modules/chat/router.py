import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse

from server.shared.db.supabase import SupabaseManager
from server.modules.chat.handler import ChatHandler

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, Any]]] = None

@router.get("/history")
async def get_chat_history(session_id: str = Query("default_session"), limit: int = 50):
    """과거 대화 기록 조회"""
    try:
        db = SupabaseManager()
        history = await db.get_chat_history(session_id, limit)
        return {"success": True, "messages": history}
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        return {"success": False, "error": str(e)}

@router.post("/run")
async def chat_run(req: ChatRequest, handler: ChatHandler = Depends()):
    """4단계 전략 생성 파이프라인 실행 (Streaming)"""
    return StreamingResponse(
        handler.execute_pipeline(
            req.message, 
            req.session_id or "default_session", 
            req.context or {}, 
            req.history or []
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
