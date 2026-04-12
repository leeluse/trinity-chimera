"""
Rolling Backtest WebSocket/SSE Routes - T-001 Integration

실시간 롤링 백테스트 결과 스트리밍 엔드포인트
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Set, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.ai_trading.core.rolling_backtest_engine import (
    RollingBacktestEngine,
    RollingMetrics,
    MetricsBuffer
)
from server.ai_trading.agents.constants import AGENT_IDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rolling-backtest", tags=["Rolling Backtest"])

# Global instance (initialized on first use)
_rolling_engine: Optional[RollingBacktestEngine] = None
_active_connections: Set[WebSocket] = set()


def get_rolling_engine() -> RollingBacktestEngine:
    """롤링 백테스트 엔진 싱글톤"""
    global _rolling_engine
    if _rolling_engine is None:
        _rolling_engine = RollingBacktestEngine(
            data_provider=None,  # TODO: Injected via dependency
            strategy_registry=None,  # TODO: Injected via dependency
            window_months=3,
            is_days=60,
            oos_days=30
        )
    return _rolling_engine


class AgentMetricsResponse(BaseModel):
    """에이전트 메트릭스 API 응답"""
    agent_id: str
    timestamp: str
    trinity_score: float
    is_score: float
    oos_score: float
    return_pct: float
    sharpe: float
    mdd: float
    profit_factor: float
    win_rate: float
    trades: int
    passed_gate: bool
    window_start: str
    window_end: str
    error: Optional[str] = None


# ==================== WebSocket Real-time Streaming ====================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 엔드포인트: 실시간 백테스트 결과 스트리밍

    연결 시 모든 에이전트의 롤링 백테스트 결과를 실시간으로 수신
    """
    await websocket.accept()
    _active_connections.add(websocket)
    logger.info(f"WebSocket client connected. Total connections: {len(_active_connections)}")

    engine = get_rolling_engine()

    # 콜백 등록
    async def on_metrics_update(results: dict):
        """새로운 백테스트 결과 브로드캐스트"""
        # Convert RollingMetrics to serializable dict
        serializable = {}
        for agent_id, metrics in results.items():
            if isinstance(metrics, RollingMetrics):
                serializable[agent_id] = {
                    "agent_id": metrics.agent_id,
                    "timestamp": metrics.timestamp.isoformat(),
                    "trinity_score_v2": metrics.trinity_score_v2,
                    "is_score": metrics.is_score,
                    "oos_score": metrics.oos_score,
                    "return_pct": metrics.return_pct,
                    "sharpe": metrics.sharpe,
                    "mdd": metrics.mdd,
                    "profit_factor": metrics.profit_factor,
                    "win_rate": metrics.win_rate,
                    "trades": metrics.trades,
                    "passed_gate": metrics.passed_gate,
                    "window_start": metrics.window_start.isoformat(),
                    "window_end": metrics.window_end.isoformat(),
                    "error": metrics.error
                }

        try:
            await websocket.send_json({
                "type": "metrics_update",
                "timestamp": datetime.now().isoformat(),
                "data": serializable
            })
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            await websocket.close()

    engine.subscribe(on_metrics_update)

    try:
        # 클라이언트에게 연결 성공 알림
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to rolling backtest stream",
            "agents": AGENT_IDS
        })

        # 연결 유지 및 명령 처리
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                # 클라이언트 명령 처리
                try:
                    cmd = json.loads(data)
                    await _handle_client_command(websocket, cmd, engine)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
            except asyncio.TimeoutError:
                # Heartbeat
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        _active_connections.discard(websocket)
        engine.unsubscribe(on_metrics_update)


async def _handle_client_command(
    websocket: WebSocket,
    cmd: dict,
    engine: RollingBacktestEngine
):
    """클라이언트 명령 처리"""
    command = cmd.get("command")

    if command == "get_status":
        status = engine.get_status()
        await websocket.send_json({
            "type": "status",
            "data": status
        })

    elif command == "force_tick":
        # 수동 틱 실행 (테스트용)
        results = await engine.run_single_tick()
        await websocket.send_json({
            "type": "force_tick_complete",
            "data": "Tick executed"
        })

    elif command == "get_buffer":
        # 버퍼 상태 조회
        agent_id = cmd.get("agent_id")
        metrics = engine.metrics_buffer.get_buffered_metrics(agent_id)
        await websocket.send_json({
            "type": "buffer_data",
            "agent_id": agent_id,
            "count": len(metrics)
        })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown command: {command}"
        })


# ==================== SSE Real-time Streaming ====================

@router.get("/sse")
async def sse_endpoint():
    """
    Server-Sent Events 엔드포인트: 백테스트 결과 스트리밍

    WebSocket 대안으로, HTTP 기반 실시간 스트리밍
    """
    engine = get_rolling_engine()
    results_queue = asyncio.Queue()

    def on_metrics(results: dict):
        """백테스트 결과 콜백"""
        asyncio.create_task(results_queue.put(results))

    engine.subscribe(on_metrics)

    async def event_generator():
        try:
            while True:
                results = await results_queue.get()

                # Serialize RollingMetrics
                serializable = {}
                for agent_id, metrics in results.items():
                    if isinstance(metrics, RollingMetrics):
                        serializable[agent_id] = {
                            "agent_id": metrics.agent_id,
                            "timestamp": metrics.timestamp.isoformat(),
                            "trinity_score_v2": metrics.trinity_score_v2,
                            "is_score": metrics.is_score,
                            "oos_score": metrics.oos_score,
                            "return_pct": metrics.return_pct,
                            "sharpe": metrics.sharpe,
                            "mdd": metrics.mdd,
                            "profit_factor": metrics.profit_factor,
                            "win_rate": metrics.win_rate,
                            "trades": metrics.trades,
                            "passed_gate": metrics.passed_gate,
                        }

                data = json.dumps({
                    "type": "metrics_update",
                    "timestamp": datetime.now().isoformat(),
                    "data": serializable
                })

                yield f"data: {data}\n\n"

        except asyncio.CancelledError:
            engine.unsubscribe(on_metrics)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ==================== REST API Endpoints ====================

@router.get("/agents/{agent_id}/latest")
async def get_latest_metrics(agent_id: str) -> AgentMetricsResponse:
    """
    특정 에이전트의 최신 롤링 백테스트 결과 조회
    """
    if agent_id not in AGENT_IDS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    engine = get_rolling_engine()
    buffered = engine.metrics_buffer.get_buffered_metrics(agent_id)

    if not buffered:
        raise HTTPException(status_code=404, detail="No metrics available yet")

    latest = buffered[-1]

    return AgentMetricsResponse(
        agent_id=latest.agent_id,
        timestamp=latest.timestamp.isoformat(),
        trinity_score=latest.trinity_score_v2,
        is_score=latest.is_score,
        oos_score=latest.oos_score,
        return_pct=latest.return_pct,
        sharpe=latest.sharpe,
        mdd=latest.mdd,
        profit_factor=latest.profit_factor,
        win_rate=latest.win_rate,
        trades=latest.trades,
        passed_gate=latest.passed_gate,
        window_start=latest.window_start.isoformat(),
        window_end=latest.window_end.isoformat(),
        error=latest.error
    )


@router.get("/agents/{agent_id}/history")
async def get_metrics_history(
    agent_id: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """
    특정 에이전트의 백테스트 이력 조회
    """
    if agent_id not in AGENT_IDS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    engine = get_rolling_engine()
    buffered = engine.metrics_buffer.get_buffered_metrics(agent_id)

    history = buffered[-limit:]

    return {
        "agent_id": agent_id,
        "count": len(history),
        "history": [
            {
                "timestamp": m.timestamp.isoformat(),
                "trinity_score": m.trinity_score_v2,
                "is_score": m.is_score,
                "oos_score": m.oos_score,
                "return_pct": m.return_pct,
                "sharpe": m.sharpe,
                "mdd": m.mdd,
                "profit_factor": m.profit_factor,
                "win_rate": m.win_rate,
                "trades": m.trades,
                "passed_gate": m.passed_gate,
            }
            for m in history
        ]
    }


@router.post("/force-tick")
async def force_tick():
    """
    수동 틱 실행 (테스트용)
    """
    engine = get_rolling_engine()
    results = await engine.run_single_tick()

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "agents_count": len(results)
    }


@router.get("/status")
async def get_engine_status():
    """
    롤링 백테스트 엔진 상태 조회
    """
    engine = get_rolling_engine()
    return engine.get_status()


# ==================== Initialization ====================

async def initialize_rolling_engine(
    data_provider=None,
    strategy_registry=None
):
    """
    엔진 초기화 (startup 이벤트에서 호출)
    """
    global _rolling_engine
    _rolling_engine = RollingBacktestEngine(
        data_provider=data_provider,
        strategy_registry=strategy_registry,
        window_months=3,
        is_days=60,
        oos_days=30
    )

    # 백그라운드에서 롤링 백테스트 시작
    asyncio.create_task(_rolling_engine.start(interval_seconds=60))
    logger.info("RollingBacktestEngine initialized and started")
