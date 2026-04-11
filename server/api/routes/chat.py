import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.api.services.backtest_skill_docs import get_backtesting_skill_system_appendix
from server.api.services.llm import generate_chat_reply, run_strategy_chat_backtest


router = APIRouter(prefix="/api", tags=["Chat"])
logger = logging.getLogger(__name__)


class BacktestChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    history: Optional[List[Dict[str, str]]] = None


class BacktestChatRunRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None


@router.post("/backtest/chat")
async def backtest_chat_with_llm(req: BacktestChatRequest):
    """General chat endpoint for backtest context Q&A."""
    try:
        skill_appendix = get_backtesting_skill_system_appendix()
        result = await generate_chat_reply(
            user_message=req.message,
            context=req.context or {},
            model=req.model,
            temperature=req.temperature,
            history=req.history or [],
            system_appendix=skill_appendix,
        )
        return {
            "role": "assistant",
            "content": result["content"],
            "type": "text",
            "provider": result["provider"],
            "model": result["model"],
            "fallback": result["fallback"],
        }
    except Exception as exc:
        logger.exception("Backtest Chat API error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/backtest/chat-run")
async def backtest_chat_run(req: BacktestChatRunRequest):
    """Prompt -> strategy design -> backtest -> summary."""
    try:
        skill_appendix = get_backtesting_skill_system_appendix()
        result = await asyncio.to_thread(
            run_strategy_chat_backtest,
            req.message,
            req.context or {},
            req.history or [],
        )
        try:
            llm_ctx = {
                "symbol": (req.context or {}).get("symbol"),
                "timeframe": (req.context or {}).get("timeframe"),
                "strategy": result.get("strategy_card", {}).get("title"),
                "netProfitAmt": result.get("backtest_payload", {}).get("results", {}).get("total_pnl"),
                "winRate": result.get("backtest_payload", {}).get("results", {}).get("win_rate"),
                "maxDrawdown": result.get("backtest_payload", {}).get("results", {}).get("max_drawdown"),
                "sharpe": result.get("backtest_payload", {}).get("results", {}).get("sharpe_ratio"),
                "profitFactor": result.get("backtest_payload", {}).get("results", {}).get("profit_factor"),
                "trades": result.get("backtest_payload", {}).get("results", {}).get("total_trades"),
            }
            llm_summary_prompt = (
                "다음 백테스트 결과를 한국어로 설명해줘. "
                "섹션은 핵심 지표, 전략 설계 요약, 진단 인사이트 순서로 작성하고 숫자는 그대로 유지해.\n\n"
                f"{result.get('analysis', '')}"
            )
            llm_resp = await generate_chat_reply(
                user_message=llm_summary_prompt,
                context=llm_ctx,
                history=req.history or [],
                system_appendix=skill_appendix,
            )
            if llm_resp.get("content"):
                result["analysis"] = llm_resp["content"]
        except Exception as llm_exc:
            logger.warning("chat-run LLM summary skipped: %s", llm_exc)
        return result
    except Exception as exc:
        logger.exception("Backtest chat-run error")
        raise HTTPException(status_code=500, detail=f"chat-run failed: {exc}")
