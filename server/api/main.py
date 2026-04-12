from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# [CRITICAL] Load .env variables BEFORE importing any services
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

# Routes
from server.api.routes import agents, backtest, chat
from server.ai_trading.agents.constants import AGENT_IDS
from server.ai_trading.agents.orchestrator import get_evolution_orchestrator

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Trinity Chimery API",
    description="LLM 기반 트레이딩 에이전트 및 백테스트 관리 시스템",
    version="1.1.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router 등록
app.include_router(agents.router)
app.include_router(agents.dashboard_router)
app.include_router(backtest.router)
app.include_router(chat.router)

# Scheduler setup
scheduler = AsyncIOScheduler()
evolution_orchestrator = get_evolution_orchestrator()

async def scheduled_evolution_poll():
    """Periodic job to check all agents for evolution triggers."""
    logger.info("Running scheduled evolution poll...")
    if hasattr(evolution_orchestrator, "start_scheduled_loop"):
        evolution_orchestrator.start_scheduled_loop(list(AGENT_IDS))
    for agent_id in AGENT_IDS:
        asyncio.create_task(evolution_orchestrator.run_evolution_cycle(agent_id))

@app.on_event("startup")
async def startup_event():
    try:
        poll_minutes = int(os.getenv("EVOLUTION_POLL_MINUTES", "60"))
    except ValueError:
        poll_minutes = 60
    poll_minutes = max(1, min(poll_minutes, 24 * 60))

    scheduler.add_job(
        scheduled_evolution_poll,
        "interval",
        minutes=poll_minutes,
        next_run_time=datetime.now(),
        coalesce=True,
        max_instances=1,
        misfire_grace_time=poll_minutes * 60,
    )
    scheduler.start()
    logger.info("APScheduler started: Evolution poll scheduled every %s minute(s).", poll_minutes)

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

# 정적 파일 서빙 (React/Next.js Build)
client_build_path = PROJECT_ROOT / "client" / "out"
if client_build_path.exists():
    app.mount("/", StaticFiles(directory=str(client_build_path), html=True), name="client")

@app.get("/")
async def serve_client():
    index_path = client_build_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Trinity Chimery API 서버 실행 중"}

@app.get("/api/system/status")
async def get_system_status():
    """시스템 상태 정보 반환"""
    orchestrator = get_evolution_orchestrator()

    status = {
        "agents": {},
        "metrics_buffer": {},
        "evolution_states": {}
    }

    for agent_id in AGENT_IDS:
        buffer_stats = orchestrator.metrics_buffer.get_buffer_stats(agent_id)
        evolution_state = orchestrator.states.get(agent_id, "IDLE")

        status["agents"][agent_id] = {
            "buffer": buffer_stats,
            "evolution_state": evolution_state
        }

    return status

if __name__ == "__main__":
    uvicorn.run(
        "server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
