"""
LLM 기반 자가 개선 시스템 API 서버

핵심 흐름: 에이전트 전략 제안 → 백테스팅 → LLM 피드백 → 개선
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
from pathlib import Path

from .models.agent import AgentImprovementRequest, BacktestResult, LLMFeedback
from .services.self_improvement import SelfImprovementService

# FastAPI 앱 생성
app = FastAPI(
    title="Trinity Chimery - LLM Self-Improvement API",
    description="LLM 기반 트레이딩 에이전트 자가 개선 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 프론트엔드 주소
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서비스 초기화
improvement_service = SelfImprovementService()

# API 엔드포인트
@app.post("/api/agents/{agent_id}/improve")
async def request_improvement(agent_id: str, request: AgentImprovementRequest):
    """LLM 자가 개선 요청"""
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

@app.get("/api/agents/{agent_id}/backtest")
async def get_backtest_result(agent_id: str):
    """최근 백테스팅 결과 조회"""
    try:
        result = await improvement_service.get_latest_backtest(agent_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"백테스팅 결과 없음: {str(e)}")

@app.get("/api/agents/{agent_id}/feedback")
async def get_feedback_history(agent_id: str):
    """LLM 피드백 이력 조회"""
    try:
        feedback = await improvement_service.get_feedback_history(agent_id)
        return feedback
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"피드백 이력 없음: {str(e)}")

@app.get("/api/dashboard/improvement")
async def get_improvement_progress():
    """개선 진행 상황 대시보드"""
    try:
        progress = await improvement_service.get_improvement_progress()
        return progress
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"진행 상황 조회 실패: {str(e)}")

@app.get("/api/agents/{agent_id}/performance")
async def get_agent_performance(agent_id: str):
    """에이전트별 성과 데이터 제공"""
    try:
        # 에이전트 성과 데이터 초기화 (없는 경우)
        if agent_id not in improvement_service.agent_performance:
            agent_names = {
                "momentum_hunter": "MINARA V2",
                "mean_reverter": "ARBITER V1",
                "macro_trader": "NIM-ALPHA",
                "chaos_agent": "CHIMERA-β"
            }
            improvement_service.initialize_agent_performance(
                agent_id,
                agent_names.get(agent_id, agent_id)
            )

        performance = improvement_service.agent_performance[agent_id]
        return performance
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"에이전트 성과 데이터 없음: {str(e)}")

@app.get("/api/agents/{agent_id}/timeseries")
async def get_agent_timeseries(agent_id: str, metric: str):
    """에이전트별 시계열 데이터 제공"""
    try:
        # 지원되는 메트릭 확인
        valid_metrics = ["score", "return", "sharpe", "mdd", "win"]
        if metric not in valid_metrics:
            raise HTTPException(status_code=400, detail=f"지원되지 않는 메트릭: {metric}")

        # 에이전트 성과 데이터가 없는 경우 초기화
        if agent_id not in improvement_service.agent_performance:
            agent_names = {
                "momentum_hunter": "MINARA V2",
                "mean_reverter": "ARBITER V1",
                "macro_trader": "NIM-ALPHA",
                "chaos_agent": "CHIMERA-β"
            }
            improvement_service.initialize_agent_performance(
                agent_id,
                agent_names.get(agent_id, agent_id)
            )

        performance = improvement_service.agent_performance[agent_id]

        # 요청된 메트릭의 시계열 데이터 반환
        timeseries_data = getattr(performance, metric, [])
        return {
            "agent_id": agent_id,
            "metric": metric,
            "data": timeseries_data,
            "labels": list(range(len(timeseries_data)))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시계열 데이터 조회 실패: {str(e)}")

@app.get("/api/dashboard/metrics")
async def get_dashboard_metrics():
    """대시보드용 통합 메트릭 제공"""
    try:
        # 모든 에이전트의 성과 데이터 수집
        agent_ids = ["momentum_hunter", "mean_reverter", "macro_trader", "chaos_agent"]
        agent_performances = {}

        for agent_id in agent_ids:
            if agent_id in improvement_service.agent_performance:
                agent_performances[agent_id] = improvement_service.agent_performance[agent_id]

        return {
            "total_agents": len(agent_performances),
            "agents": agent_performances,
            "overall_metrics": {
                "avg_trinity_score": sum(p.current_score for p in agent_performances.values()) / len(agent_performances),
                "best_performer": max(agent_performances.values(), key=lambda x: x.current_score).name if agent_performances else "없음"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"대시보드 메트릭 조회 실패: {str(e)}")

# 정적 파일 서빙 (프론트엔드 빌드 파일)
frontend_build_path = Path(__file__).parent.parent / "front" / "out"
if frontend_build_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="frontend")

@app.get("/")
async def serve_frontend():
    """프론트엔드 서빙"""
    index_path = frontend_build_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Trinity Chimery API 서버 실행 중"}

# 서버 실행
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )