from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
import logging
import asyncio
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# [CRITICAL] Load .env variables BEFORE importing any services
# Prefer the project root .env, then allow api/.env to fill any local-only values.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

# Now safe to import services that rely on os.environ
from models.agent import AgentImprovementRequest, BacktestResult, LLMFeedback
from services.self_improvement import SelfImprovementService
from ai_trading.agents.constants import AGENT_IDS
from ai_trading.agents.orchestrator import get_evolution_orchestrator

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Trinity Chimery - LLM Self-Improvement API",
    description="LLM 기반 트레이딩 에이전트 자가 개선 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서비스 초기화 (load_dotenv 이후에 실행됨)
improvement_service = SelfImprovementService()
scheduler = AsyncIOScheduler()
evolution_orchestrator = get_evolution_orchestrator()

async def scheduled_evolution_poll():
    """
    Periodic job to check all agents for evolution triggers.
    """
    logger.info("Running scheduled evolution poll...")
    for agent_id in AGENT_IDS:
        asyncio.create_task(evolution_orchestrator.run_evolution_cycle(agent_id))

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(scheduled_evolution_poll, 'interval', hours=1)
    scheduler.start()
    logger.info("APScheduler started: Evolution poll scheduled every hour.")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

# API 엔드포인트
@app.post("/api/agents/{agent_id}/evolve")
async def trigger_evolution(agent_id: str, background_tasks: BackgroundTasks):
    logger.info(f"Manual evolution trigger requested for agent: {agent_id}")
    background_tasks.add_task(evolution_orchestrator.run_evolution_cycle, agent_id, force_trigger=True)
    return {
        "success": True,
        "message": f"Evolution cycle started for agent {agent_id} in background."
    }

@app.get("/api/agents/{agent_id}/status")
async def get_agent_evolution_status(agent_id: str):
    state = await evolution_orchestrator.get_state(agent_id)
    return {
        "agent_id": agent_id,
        "current_state": state.value if state else "IDLE"
    }

@app.post("/api/agents/{agent_id}/improve")
async def request_improvement(agent_id: str, request: AgentImprovementRequest):
    try:
        result = await improvement_service.request_improvement(agent_id, request.current_strategy)
        return {
            "success": True,
            "improvement_id": result["improvement_id"],
            "status": "processing",
            "message": "LLM 개선 요청이 시작되었습니다"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"개선 요청 실패: {str(e)}")

# 정적 파일 서빙
frontend_build_path = Path(__file__).parent.parent / "front" / "out"
if frontend_build_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="frontend")

@app.get("/")
async def serve_frontend():
    index_path = frontend_build_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Trinity Chimery API 서버 실행 중"}

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
