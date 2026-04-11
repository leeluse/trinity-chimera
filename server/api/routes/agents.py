from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Any, Dict, List, Optional
import math
from datetime import datetime, timezone

from server.api.models.agent import AgentImprovementRequest
from server.ai_trading.agents.constants import AGENT_IDS
from server.ai_trading.agents.orchestrator import get_evolution_orchestrator
from server.api.services.self_improvement import SelfImprovementService

router = APIRouter(prefix="/api/agents", tags=["Agents"])
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

improvement_service = SelfImprovementService()
evolution_orchestrator = get_evolution_orchestrator()

def _build_metric_series(agent_id: str, metric: str, points: int = 96) -> List[float]:
    seed = sum(ord(char) for char in agent_id)
    values: List[float] = []

    for idx in range(points):
        phase = (idx + (seed % 11)) / 8.0

        if metric == "score":
            value = 90 + (seed % 10) * 0.6 + idx * 0.12 + math.sin(phase) * 2.5
        elif metric == "return":
            value = 4 + (seed % 7) * 0.4 + idx * 0.22 + math.sin(phase) * 1.8
        elif metric == "sharpe":
            value = 1.0 + (seed % 5) * 0.06 + math.sin(phase) * 0.22
        elif metric == "mdd":
            value = -7 - (seed % 4) - abs(math.sin(phase)) * 4.2
        elif metric == "win":
            value = 49 + (seed % 9) + math.sin(phase) * 4
        else:
            value = 0.0

        values.append(round(value, 3))

    return values

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

@router.post("/{agent_id}/evolve")
async def trigger_evolution(agent_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(evolution_orchestrator.run_evolution_cycle, agent_id, force_trigger=True)
    return {
        "success": True,
        "message": f"Evolution cycle started for agent {agent_id} in background."
    }

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
    
    from server.api.services.supabase_client import SupabaseManager
    try:
        manager = SupabaseManager()
        # Find agent by technical ID-like name or slug matching
        res = manager.client.table("agents").select("name").ilike("id", f"%{agent_id}%").execute()
        real_name = res.data[0]["name"] if res.data else None
    except:
        real_name = None

    return _build_agent_performance(agent_id, real_name)

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

@dashboard_router.get("/improvement")
async def get_dashboard_improvement():
    now = datetime.now(timezone.utc).isoformat()
    latest = [
        {
            "agent_id": agent_id,
            "status": "idle",
            "progress": 0,
            "created_at": now,
        }
        for agent_id in AGENT_IDS
    ]
    return {
        "active_improvements": 0,
        "completed_improvements": 0,
        "failed_improvements": 0,
        "total_improvements": 0,
        "agents": list(AGENT_IDS),
        "latest_improvements": latest,
    }

@dashboard_router.get("/metrics")
async def get_dashboard_metrics():
    from server.api.services.supabase_client import SupabaseManager
    agent_name_map = {}
    try:
        manager = SupabaseManager()
        res = manager.client.table("agents").select("id, name").execute()
        # Create a mapping for AGENT_IDS
        # Since technical IDs in DB might be UUIDs, we match names if they contain the technical ID or similar
        for row in res.data:
            db_name = row.get("name", "")
            # Simple heuristic mapping
            if "momentum" in db_name.lower(): agent_name_map["momentum_hunter"] = db_name
            elif "revert" in db_name.lower(): agent_name_map["mean_reverter"] = db_name
            elif "macro" in db_name.lower(): agent_name_map["macro_trader"] = db_name
            elif "chaos" in db_name.lower(): agent_name_map["chaos_agent"] = db_name
    except:
        pass

    all_perf = [_build_agent_performance(aid, agent_name_map.get(aid)) for aid in AGENT_IDS]
    
    if not all_perf:
        return {
            "total_agents": 0,
            "agents": {},
            "overall_metrics": {
                "avg_trinity_score": 0,
                "best_performer": "",
                "total_trades": 0,
            },
        }

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
