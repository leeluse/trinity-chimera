from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Response
from typing import Any, Dict, List, Optional
import asyncio
import math
from pydantic import BaseModel
from postgrest import APIError

from server.api.models.agent import AgentImprovementRequest
from server.modules.evolution.constants import AGENT_IDS
from server.modules.evolution.orchestrator import get_evolution_orchestrator
from server.modules.evolution.self_improvement import SelfImprovementService

router = APIRouter(prefix="/agents", tags=["Agents"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

improvement_service = SelfImprovementService()
evolution_orchestrator = get_evolution_orchestrator()


class RunLoopRequest(BaseModel):
    agent_ids: Optional[List[str]] = None


# -------------------------------------------------------------------------
# [Helper] 순차 진화 실행: LLM 과부하 방지를 위해 순서대로 작업 수행
# -------------------------------------------------------------------------
async def _run_evolution_loop_sequential(agent_ids: List[str], force_trigger: bool = True) -> None:
    """
    LLM 과부하를 피하기 위해 루프 내 에이전트 진화를 순차 실행한다.
    """
    for agent_id in agent_ids:
        try:
            await evolution_orchestrator.run_evolution_cycle(agent_id, force_trigger=force_trigger)
        except Exception:
            # 개별 에이전트 실패가 전체 루프를 중단시키지 않도록 보호
            continue


# -------------------------------------------------------------------------
# [Helper] 차트 데이터 생성: 가짜 시계열 데이터를 생성하여 UI 테스트 지원
# -------------------------------------------------------------------------
def _build_metric_series(agent_id: str, metric: str, points: int = 96) -> List[float]:
    seed = sum(ord(char) for char in agent_id)
    values: List[float] = []

    for idx in range(points):
        phase = (idx + (seed % 11)) / 8.0

        if metric == "score":
            value = 90 + (seed % 10) * 0.6 + idx * 0.12 + math.sin(phase) * 2.5
        elif metric == "return":
            value = (4 + (seed % 7) * 0.4 + idx * 0.22 + math.sin(phase) * 1.8) / 100
        elif metric == "sharpe":
            value = 1.0 + (seed % 5) * 0.06 + math.sin(phase) * 0.22
        elif metric == "mdd":
            value = (-7 - (seed % 4) - abs(math.sin(phase)) * 4.2) / 100
        elif metric == "win":
            value = (49 + (seed % 9) + math.sin(phase) * 4) / 100
        else:
            value = 0.0

        values.append(round(value, 3))

    return values

# -------------------------------------------------------------------------
# [Helper] 에이전트 성능 요약: 특정 에이전트의 종합 성과 데이터를 구축
# -------------------------------------------------------------------------
def _build_agent_performance(agent_id: str, real_name: Optional[str] = None) -> Dict[str, Any]:
    score_series = _build_metric_series(agent_id, "score")
    return_series = _build_metric_series(agent_id, "return")
    sharpe_series = _build_metric_series(agent_id, "sharpe")
    mdd_series = _build_metric_series(agent_id, "mdd")
    win_series = _build_metric_series(agent_id, "win")
    seed = sum(ord(char) for char in agent_id)

    return {
        "agent_id": agent_id,
        "name": real_name or agent_id,
        "score": score_series,
        "return_val": return_series,
        "sharpe": sharpe_series,
        "mdd": mdd_series,
        "win": win_series,
        "current_score": score_series[-1],
        "current_return": return_series[-1],
        "current_sharpe": sharpe_series[-1],
        "current_mdd": mdd_series[-1],
        "current_win_rate": win_series[-1],
        "total_trades": 120 + (seed % 180),
        "winning_trades": 70 + (seed % 80),
        "losing_trades": 30 + (seed % 60),
        "avg_trade_duration": 28 + (seed % 25),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _pick_latest_oos_backtest(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None

    selected = rows[0]
    for row in rows:
        test_period = row.get("test_period") or {}
        if isinstance(test_period, dict) and str(test_period.get("type", "")).upper() == "OOS":
            selected = row
            break
    return selected


def _fetch_latest_backtest_row(manager: Any, strategy_id: str) -> Optional[Dict[str, Any]]:
    if not strategy_id:
        return None

    try:
        rows = (
            manager.client.table("backtest_results")
            .select("trinity_score,return_val,sharpe,mdd,win_rate,test_period,created_at")
            .eq("strategy_id", strategy_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
            .data
            or []
        )
    except APIError:
        return None
    return _pick_latest_oos_backtest(rows)


def _fallback_current_strategy_id(manager: Any, agent_row: Dict[str, Any]) -> Optional[str]:
    agent_db_id = agent_row.get("id")
    if not agent_db_id:
        return None
    try:
        rows = (
            manager.client.table("strategies")
            .select("id")
            .eq("agent_id", agent_db_id)
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except APIError:
        return None
    if not rows:
        return None
    return rows[0].get("id")


# -------------------------------------------------------------------------
# [API] 수동 루프 실행: 선택된 에이전트들에 대해 즉시 진화 시작 [POST]
# -------------------------------------------------------------------------
@router.post("/run-loop")
async def run_manual_loop(request: Optional[RunLoopRequest] = None):
    requested = request.agent_ids if request and request.agent_ids else list(AGENT_IDS)
    filtered: List[str] = []
    for agent_id in requested:
        if agent_id in AGENT_IDS and agent_id not in filtered:
            filtered.append(agent_id)

    if not filtered:
        raise HTTPException(status_code=400, detail="유효한 agent_ids가 없습니다.")

    iteration = evolution_orchestrator.start_manual_loop(filtered)
    asyncio.create_task(_run_evolution_loop_sequential(filtered, force_trigger=True))

    return {
        "success": True,
        "iteration": iteration,
        "queued_agents": filtered,
        "message": f"Manual loop #{iteration} queued for {len(filtered)} agents.",
    }


# -------------------------------------------------------------------------
# [API] 단일 에이전트 진화 트리거: 특정 에이전트만 즉시 진화 [POST]
# -------------------------------------------------------------------------
@router.post("/{agent_id}/evolve")
async def trigger_evolution(agent_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(evolution_orchestrator.run_evolution_cycle, agent_id, force_trigger=True)
    return {
        "success": True,
        "message": f"Evolution cycle started for agent {agent_id} in background."
    }

# -------------------------------------------------------------------------
# [API] 에이전트 상태 조회: 현재 진행 단계(IDLE, GENERATING 등) 확인 [GET]
# -------------------------------------------------------------------------
@router.get("/{agent_id}/status")
async def get_agent_evolution_status(agent_id: str):
    state = await evolution_orchestrator.get_state(agent_id)
    return {
        "agent_id": agent_id,
        "current_state": state.value if state else "IDLE"
    }

@router.get("/{agent_id}/performance")
async def get_agent_performance(agent_id: str):
    if agent_id not in AGENT_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown agent_id: {agent_id}")
    
    from server.shared.db.supabase import SupabaseManager
    try:
        manager = SupabaseManager()
        # Find agent by technical ID-like name or slug matching
        res = manager.client.table("agents").select("name").ilike("id", f"%{agent_id}%").execute()
        real_name = res.data[0]["name"] if res.data else None
    except:
        real_name = None

    return _build_agent_performance(agent_id, real_name)

# -------------------------------------------------------------------------
# [API] 시계열 데이터 조회: 차트 렌더링을 위한 메트릭 데이터셋 반환 [GET]
# -------------------------------------------------------------------------
@router.get("/{agent_id}/timeseries")
async def get_agent_timeseries(
    agent_id: str,
    metric: str = Query("score", description="score|return|sharpe|mdd|win"),
):
    if agent_id not in AGENT_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown agent_id: {agent_id}")

    metric = metric.lower()
    allowed = {"score", "return", "sharpe", "mdd", "win"}
    if metric not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported metric: {metric}")

    return {
        "agent_id": agent_id,
        "metric": metric,
        "data": _build_metric_series(agent_id, metric),
    }

@router.post("/{agent_id}/improve")
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

# -------------------------------------------------------------------------
# [API] 대시보드 요약 정보: 상단 개선 현황 스냅샷 조회 [GET]
# -------------------------------------------------------------------------
@dashboard_router.get("/improvement")
async def get_dashboard_improvement(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        return evolution_orchestrator.get_dashboard_snapshot()
    except Exception as e:
        logger.error(f"Dashboard snapshot error: {e}")
        return {
            "total_improvements": 0,
            "completed_improvements": 0,
            "failed_improvements": 0,
            "latest_improvements": []
        }


# -------------------------------------------------------------------------
# [API] 진화 로그 조회: 최근 발생한 모든 시스템 이벤트 목록 [GET]
# -------------------------------------------------------------------------
@dashboard_router.get("/evolution-log")
async def get_evolution_log(
    response: Response,
    limit: int = Query(120, ge=1, le=500),
    agent_id: Optional[str] = Query(None),
):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        return {
            "events": evolution_orchestrator.get_evolution_events(limit=limit, agent_id=agent_id)
        }
    except Exception as e:
        logger.error(f"Evolution log error: {e}")
        return {"events": []}

# -------------------------------------------------------------------------
# [API] 전체 지표 요약: 에이전트별 순위 및 평균 성과 데이터 [GET]
# -------------------------------------------------------------------------
@dashboard_router.get("/metrics")
async def get_dashboard_metrics():
    from server.shared.db.supabase import SupabaseManager
    try:
        manager = SupabaseManager()
    except Exception:
        manager = None

    if manager is None:
        all_perf = [_build_agent_performance(aid) for aid in AGENT_IDS]
        best = max(all_perf, key=lambda item: item["current_score"])
        agents = {
            perf["agent_id"]: {
                "name": perf["name"],
                "current_score": perf["current_score"],
                "current_return": perf["current_return"],
                "current_sharpe": perf["current_sharpe"],
                "current_mdd": perf["current_mdd"],
                "current_win_rate": perf["current_win_rate"],
            }
            for perf in all_perf
        }
        return {
            "total_agents": len(all_perf),
            "agents": agents,
            "overall_metrics": {
                "avg_trinity_score": round(
                    sum(item["current_score"] for item in all_perf) / len(all_perf),
                    3,
                ),
                "best_performer": best["agent_id"],
                "total_trades": sum(item["total_trades"] for item in all_perf),
            },
        }

    agent_metrics: Dict[str, Dict[str, Any]] = {}
    scores: List[float] = []
    best_performer = ""
    best_score = float("-inf")

    for agent_id in AGENT_IDS:
        agent_row = manager._resolve_agent_row(agent_id) or {}
        name = str(agent_row.get("name") or agent_id)
        strategy_id = agent_row.get("current_strategy_id") or _fallback_current_strategy_id(manager, agent_row)
        backtest_row = _fetch_latest_backtest_row(manager, strategy_id) if strategy_id else None

        current_score = _safe_float((backtest_row or {}).get("trinity_score"), 0.0)
        current_return = _safe_float((backtest_row or {}).get("return_val"), 0.0)
        current_sharpe = _safe_float((backtest_row or {}).get("sharpe"), 0.0)
        current_mdd = _safe_float((backtest_row or {}).get("mdd"), 0.0)
        current_win_rate = _safe_float((backtest_row or {}).get("win_rate"), 0.0)

        scores.append(current_score)
        if current_score > best_score:
            best_score = current_score
            best_performer = agent_id

        agent_metrics[agent_id] = {
            "name": name,
            "current_score": round(current_score, 4),
            "current_return": round(current_return, 6),
            "current_sharpe": round(current_sharpe, 4),
            "current_mdd": round(current_mdd, 6),
            "current_win_rate": round(current_win_rate, 6),
        }

    if not best_performer:
        best_performer = AGENT_IDS[0] if AGENT_IDS else ""

    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
    return {
        "total_agents": len(AGENT_IDS),
        "agents": agent_metrics,
        "overall_metrics": {
            "avg_trinity_score": avg_score,
            "best_performer": best_performer,
            "total_trades": 0,
        },
    }
