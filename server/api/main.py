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

# [CRITICAL] Load root .env variables BEFORE importing any services
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Routes - New Modular Structure
from server.modules.chat.router import router as chat_router
from server.modules.evolution.router import router as evolution_router, dashboard_router
from server.modules.engine.router import router as engine_router
from server.modules.settings.router import router as settings_router
from server.modules.evolution.orchestrator import get_evolution_orchestrator
from server.modules.evolution.constants import AGENT_IDS, ACTIVE_AGENT_IDS
from server.shared.market.metrics_buffer import get_metrics_buffer

# Logging setup
from logging.handlers import TimedRotatingFileHandler


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_log_level(name: str, default: str = "WARNING") -> str:
    value = (os.getenv(name) or default).strip().upper()
    if value not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
        return default
    return value


TRINITY_LOG_LEVEL = _env_log_level("TRINITY_LOG_LEVEL", "WARNING")
CHAT_REQUEST_LOG_ENABLED = _env_flag("CHAT_REQUEST_LOG_ENABLED", True)

# 1. 기본 콘솔 로그
logging.basicConfig(
    level=getattr(logging, TRINITY_LOG_LEVEL, logging.WARNING),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 채팅 요청 처리 추적 로그는 기본 ON (필요 시 CHAT_REQUEST_LOG_ENABLED=0)
if CHAT_REQUEST_LOG_ENABLED:
    logging.getLogger("server.modules.chat").setLevel(logging.INFO)
    logging.getLogger("server.shared.llm.client").setLevel(logging.INFO)
else:
    logging.getLogger("server.modules.chat").setLevel(getattr(logging, TRINITY_LOG_LEVEL, logging.WARNING))
    logging.getLogger("server.shared.llm.client").setLevel(getattr(logging, TRINITY_LOG_LEVEL, logging.WARNING))

# 터미널 잡음을 줄이기 위해 기본적으로 uvicorn access 로그 비활성화
if not _env_flag("UVICORN_ACCESS_LOG", False):
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers = []
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.disabled = True

logging.getLogger("uvicorn.error").setLevel(getattr(logging, TRINITY_LOG_LEVEL, logging.WARNING))

# 2. 진화 루프 및 LLM 관련 파일 로그 설정 (기본 OFF)
if _env_flag("EVOLUTION_FILE_LOG_ENABLED", False):
    logs_dir = PROJECT_ROOT / "server" / "logs" / "evolution"
    os.makedirs(logs_dir, exist_ok=True)
    try:
        backup_count = int(os.getenv("EVOLUTION_FILE_LOG_BACKUP_DAYS", "3"))
    except ValueError:
        backup_count = 3
    backup_count = max(1, min(backup_count, 30))

    log_subjects = ["server.modules.evolution", "server.shared.llm"]
    evo_file_handler = TimedRotatingFileHandler(
        filename=logs_dir / "loop.log",
        when="midnight",
        interval=1,
        backupCount=backup_count,
        encoding="utf-8",
    )
    evo_file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

    for subject in log_subjects:
        sub_logger = logging.getLogger(subject)
        sub_logger.addHandler(evo_file_handler)
        sub_logger.propagate = True

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
app.include_router(chat_router, prefix="/api")
app.include_router(evolution_router, prefix="/api")  # /api/agents ...
app.include_router(dashboard_router, prefix="/api")  # /api/dashboard ...
app.include_router(engine_router, prefix="/api/backtest")
app.include_router(settings_router, prefix="/api/system")

# Scheduler setup
scheduler = AsyncIOScheduler()
evolution_orchestrator = get_evolution_orchestrator()

async def scheduled_evolution_poll():
    """Periodic job to check all agents for evolution triggers."""
    logger.debug("Running scheduled evolution poll...")
    if hasattr(evolution_orchestrator, "start_scheduled_loop"):
        evolution_orchestrator.start_scheduled_loop(list(ACTIVE_AGENT_IDS))
    for agent_id in ACTIVE_AGENT_IDS:
        await evolution_orchestrator.run_evolution_cycle(agent_id)

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
        id="evolution_poll",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=poll_minutes * 60,
    )
    # 기본적으로 일시정지 상태로 시작하여 사용자의 명시적 'RUN' 요청 시 작동하게 함
    job = scheduler.get_job("evolution_poll")
    if job:
        job.pause()
        
    scheduler.start()
    logger.info(
        "APScheduler started: Evolution poll added (PAUSED by default). active_agents=%s",
        ACTIVE_AGENT_IDS,
    )

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
    metrics_buffer = get_metrics_buffer()

    status = {
        "agents": {},
        "metrics_buffer": {},
        "evolution_states": {},
        "active_agents": list(ACTIVE_AGENT_IDS),
    }

    for agent_id in AGENT_IDS:
        buffer_stats = metrics_buffer.get_buffer_status(agent_id)
        evolution_state = orchestrator.agent_manager.get_state(agent_id).value

        status["agents"][agent_id] = {
            "buffer": buffer_stats,
            "evolution_state": evolution_state
        }

    return status


@app.get("/api/system/automation")
async def get_automation_status():
    """자동화 루프(스케줄러) 상태 조회"""
    job = scheduler.get_job("evolution_poll")
    if not job:
        return {"enabled": False, "status": "not_found"}

    # next_run_time이 None이면 일시정지 상태임
    enabled = job.next_run_time is not None
    return {
        "enabled": enabled,
        "status": "running" if enabled else "paused",
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
    }


@app.post("/api/system/automation")
async def set_automation_status(data: dict):
    """자동화 루프(스케줄러) 끄기/켜기"""
    enabled = data.get("enabled", True)
    job = scheduler.get_job("evolution_poll")
    if not job:
        return {"success": False, "error": "job_not_found"}

    if enabled:
        job.resume()
        # 재개 시 즉시 실행되도록 다음 실행 시간을 지금으로 설정
        job.modify(next_run_time=datetime.now())
        logger.info("Evolution automation RESUMED and triggered immediately.")
    else:
        job.pause()
        logger.info("Evolution automation PAUSED.")

    return {"success": True, "enabled": enabled}

if __name__ == "__main__":
    uvicorn_log_level = (os.getenv("UVICORN_LOG_LEVEL") or TRINITY_LOG_LEVEL).strip().lower()
    if uvicorn_log_level not in {"critical", "error", "warning", "info", "debug", "trace"}:
        uvicorn_log_level = "warning"

    uvicorn.run(
        "server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=_env_flag("UVICORN_RELOAD", False),
        log_level=uvicorn_log_level,
        access_log=_env_flag("UVICORN_ACCESS_LOG", False),
    )
