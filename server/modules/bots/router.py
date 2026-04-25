"""
봇 API 라우터
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from server.shared.db.supabase import SupabaseManager
from .manager import BotManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["Bots"])

# ─── Pydantic Models ───

class BotConfigRequest(BaseModel):
    name: str
    strategy_id: str
    leverage: float = 1.0
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"
    initial_capital: float = 10000
    max_position_pct: float = 10
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    risk_profile: str = "moderate"


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    strategy_id: Optional[str] = None
    leverage: Optional[float] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    initial_capital: Optional[float] = None
    max_position_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    risk_profile: Optional[str] = None


# ─── API Endpoints ───

@router.get("/trades")
async def get_all_bot_trades(limit: int = 100) -> List[Dict[str, Any]]:
    """모든 봇의 최근 거래 내역 조회"""
    db = SupabaseManager()
    bots = await db.list_bots(limit=100)
    
    all_trades = []
    for bot in bots:
        sim_state = bot.get("sim_state") or {}
        trades = sim_state.get("recent_trades", [])
        for trade in trades:
            # 보강 정보 추가
            trade_record = {
                **trade,
                "bot_id": bot.get("id"),
                "bot_name": bot.get("name"),
                "strategy_name": bot.get("strategies", {}).get("name", "Unknown"),
                "symbol": bot.get("symbol", "BTCUSDT")
            }
            all_trades.append(trade_record)
            
    # 시간순 정렬 (최신순)
    all_trades.sort(key=lambda x: x.get("close_time", ""), reverse=True)
    return all_trades[:limit]

@router.get("/")
async def list_bots() -> List[Dict[str, Any]]:
    """전체 봇 목록 조회"""
    db = SupabaseManager()
    bots = await db.list_bots(limit=100)
    return bots


@router.post("/")
async def create_bot(req: BotConfigRequest) -> Dict[str, Any]:
    """봇 생성"""
    try:
        db = SupabaseManager()
        manager = BotManager()

        bot_data = {
            "name": req.name,
            "strategy_id": req.strategy_id,
            "leverage": req.leverage,
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "initial_capital": req.initial_capital,
            "max_position_pct": req.max_position_pct,
            "stop_loss_pct": req.stop_loss_pct,
            "take_profit_pct": req.take_profit_pct,
            "risk_profile": req.risk_profile,
            "is_active": False,
            "evolution_enabled": False,
        }

        bot = await db.create_bot(bot_data)
        if not bot:
            raise HTTPException(status_code=500, detail="Failed to create bot")

        return {"success": True, "bot": bot}

    except Exception as e:
        logger.exception("Error creating bot: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}")
async def get_bot(bot_id: str) -> Dict[str, Any]:
    """단건 봇 조회"""
    try:
        db = SupabaseManager()
        bot = await db.get_bot(bot_id)

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        return {"success": True, "bot": bot}

    except Exception as e:
        logger.exception("Error getting bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{bot_id}")
async def update_bot(bot_id: str, req: BotUpdateRequest) -> Dict[str, Any]:
    """봇 설정 수정"""
    try:
        db = SupabaseManager()

        # 현재 봇 존재 여부 확인
        existing = await db.get_bot(bot_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Bot not found")

        # 업데이트 데이터 필터링 (None 값은 제외)
        update_data = {k: v for k, v in req.dict().items() if v is not None}

        bot = await db.update_bot(bot_id, update_data)
        if not bot:
            raise HTTPException(status_code=500, detail="Failed to update bot")

        return {"success": True, "bot": bot}

    except Exception as e:
        logger.exception("Error updating bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str) -> Dict[str, Any]:
    """봇 삭제"""
    try:
        db = SupabaseManager()
        manager = BotManager()

        # 활성 봇인 경우 먼저 중지
        await manager.stop_bot(bot_id)

        # DB에서 삭제
        success = await db.delete_bot(bot_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete bot")

        return {"success": True}

    except Exception as e:
        logger.exception("Error deleting bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bot_id}/start")
async def start_bot(bot_id: str) -> Dict[str, Any]:
    """봇 시작"""
    try:
        manager = BotManager()
        success = await manager.start_bot(bot_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to start bot")

        return {"success": True, "message": f"Bot {bot_id} started"}

    except Exception as e:
        logger.exception("Error starting bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{bot_id}/stop")
async def stop_bot(bot_id: str) -> Dict[str, Any]:
    """봇 중지"""
    try:
        manager = BotManager()
        success = await manager.stop_bot(bot_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to stop bot")

        return {"success": True, "message": f"Bot {bot_id} stopped"}

    except Exception as e:
        logger.exception("Error stopping bot %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{bot_id}/state")
async def get_bot_state(bot_id: str) -> Dict[str, Any]:
    """봇 실시간 상태 조회"""
    try:
        manager = BotManager()
        state = await manager.get_bot_state(bot_id)

        if state is None:
            raise HTTPException(status_code=404, detail="Bot not found or not active")

        return {"success": True, "state": state}

    except Exception as e:
        logger.exception("Error getting bot state %s: %s", bot_id, e)
        raise HTTPException(status_code=500, detail=str(e))
