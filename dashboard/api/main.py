"""
Dashboard API - FastAPI 기반 웹 대시보드 서버
"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import json

from dashboard.api.models import (
    AgentPnL, PortfolioAllocation, BattleEvent, DashboardState
)
from dashboard.api.data_store import DataStore

app = FastAPI(title="AI Trading Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_store = DataStore()


@app.get("/api/agents/pnl")
def get_agents_pnl(timeframe: str = "24h") -> Dict[str, List[AgentPnL]]:
    """에이전트별 PnL 히스토리"""
    return data_store.get_agent_pnl_history(timeframe)


@app.get("/api/portfolio/allocation")
def get_portfolio_allocation() -> PortfolioAllocation:
    """현재 포트폴리오 배분"""
    return data_store.get_current_allocation()


@app.get("/api/portfolio/allocation/history")
def get_allocation_history(days: int = 30) -> List[PortfolioAllocation]:
    """포트폴리오 배분 히스토리"""
    return data_store.get_allocation_history(days)


@app.get("/api/battle/history")
def get_battle_history(
    limit: int = 100,
    agent_filter: Optional[str] = None
) -> List[BattleEvent]:
    """배틀 이벤트 히스토리"""
    return data_store.get_battle_events(limit, agent_filter)


@app.get("/api/dashboard/state")
def get_dashboard_state() -> DashboardState:
    """대시보드 전체 상태"""
    return data_store.get_current_state()


@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    """실시간 대시보드 웹소켓"""
    await websocket.accept()
    try:
        while True:
            state = data_store.get_current_state()
            await websocket.send_json(state.dict())
            await asyncio.sleep(1)
    except Exception:
        await websocket.close()


@app.post("/api/freqtrade/webhook")
def freqtrade_webhook(payload: dict):
    """Freqtrade에서 호출하는 실시간 업데이트"""
    data_store.handle_freqtrade_update(payload)
    return {"status": "received"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
