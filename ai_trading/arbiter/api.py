"""Real-time API for Market Analyzer.

This module provides async REST API endpoints for real-time market analysis,
agegent correlation tracking, and LLM Arbiter integration.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pandas as pd
from aiohttp import web

from ai_trading.arbiter.llm_arbiter import LLMArbiter, AgentPerformance
from ai_trading.arbiter.market_analyzer import MarketAnalyzer, MarketAnalysis
from ai_trading.arbiter.strategy_generator import StrategyGenerator

logger = logging.getLogger(__name__)


class AnalysisState:
    """Shared state for analysis API."""

    def __init__(self):
        self.market_analyzer: Optional[MarketAnalyzer] = None
        self.llm_arbiter: Optional[LLMArbiter] = None
        self.strategy_generator: Optional[StrategyGenerator] = None
        self.agent_positions: Dict[str, float] = {}
        self.agent_metrics: Dict[str, Dict[str, float]] = {}
        self.analysis_history: List[Dict[str, Any]] = []
        self.subscribers: Set[web.WebSocketResponse] = set()
        self.running = False


state = AnalysisState()


async def initialize_analyzers(
    enable_llm: bool = True,
    api_key: Optional[str] = None,
) -> None:
    """Initialize all analyzer components.

    Args:
        enable_llm: Whether to enable LLM-based arbiter
        api_key: Anthropic API key for LLM
    """
    from ai_trading.core.hmm_regime import create_regime_classifier

    # Initialize Market Analyzer
    state.market_analyzer = MarketAnalyzer(
        volatility_window=20,
        correlation_lookback=20,
    )

    # Initialize LLM Arbiter if enabled
    if enable_llm:
        state.llm_arbiter = LLMArbiter(
            model="claude-sonnet-4-6",
            min_allocation=0.05,
            max_allocation=0.50,
            rebalance_interval=7,
            api_key=api_key,
        )
        logger.info("LLM Arbiter initialized")

    # Initialize Strategy Generator
    state.strategy_generator = StrategyGenerator(
        model="claude-sonnet-4-6",
        api_key=api_key,
    )

    state.running = True
    logger.info("Analysis API state initialized")


async def cleanup_analyzers() -> None:
    """Cleanup analyzer resources."""
    state.running = False
    for ws in list(state.subscribers):
        await ws.close()
    state.subscribers.clear()
    logger.info("Analysis API cleanup complete")


async def api_lifespan(app: web.Application):
    """Application lifespan handler for cleanup_ctx.

    Usage: app.cleanup_ctx.append(api_lifespan)
    """
    # Startup
    await initialize_analyzers()
    yield
    # Shutdown
    await cleanup_analyzers()


async def analyze_market(request: web.Request) -> web.Response:
    """POST /api/v1/market/analyze - Run market analysis.

    Request body:
        {
            "ohlcv": DataFrame data,
            "agent_positions": {"agent_name": position}
        }

    Returns:
        MarketAnalysis as JSON
    """
    if not state.market_analyzer:
        return web.json_response(
            {"error": "Market analyzer not initialized"},
            status=503
        )

    try:
        data = await request.json()

        # Parse OHLCV data
        ohlcv = pd.DataFrame(data.get("ohlcv", {}))
        agent_positions = data.get("agent_positions", {})

        if ohlcv.empty:
            return web.json_response(
                {"error": "OHLCV data required"},
                status=400
            )

        # Update agent positions
        state.agent_positions.update(agent_positions)

        # Run analysis
        analysis = state.market_analyzer.analyze(
            ohlcv=ohlcv,
            agent_positions=state.agent_positions,
        )

        # Convert to dict
        result = analysis.to_dict()
        result["timestamp"] = datetime.now().isoformat()

        # Store in history
        state.analysis_history.append(result)
        if len(state.analysis_history) > 100:
            state.analysis_history = state.analysis_history[-100:]

        # Broadcast to subscribers
        await broadcast_analysis(result)

        return web.json_response(result)

    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def get_market_state(request: web.Request) -> web.Response:
    """GET /api/v1/market/state - Get current market state.

    Returns:
        Current market analysis summary
    """
    if not state.market_analyzer:
        return web.json_response(
            {"error": "Market analyzer not initialized"},
            status=503
        )

    if not state.analysis_history:
        return web.json_response(
            {"status": "no_data", "message": "No analysis run yet"}
        )

    latest = state.analysis_history[-1]

    # Calculate regime stats
    regime_stats = state.market_analyzer.get_regime_stats()
    diversification = state.market_analyzer.get_diversification_metrics()

    return web.json_response({
        "current_state": latest,
        "regime_stats": regime_stats,
        "diversification": diversification,
        "agent_positions": state.agent_positions,
        "history_count": len(state.analysis_history),
    })


async def run_rebalance(request: web.Request) -> web.Response:
    """POST /api/v1/arbiter/rebalance - Run LLM rebalance.

    Request body:
        {
            "current_regime": "bull",
            "force": false
        }

    Returns:
        AllocationDecision as JSON
    """
    if not state.llm_arbiter:
        return web.json_response(
            {"error": "LLM Arbiter not enabled"},
            status=503
        )

    try:
        data = await request.json()
        current_regime = data.get("current_regime", "sideways")
        force_rebalance = data.get("force", False)

        # Check if rebalance needed
        if not force_rebalance:
            days_since = data.get("days_since_last", 0)
            if not state.llm_arbiter.needs_rebalance(days_since):
                return web.json_response({
                    "status": "skipped",
                    "message": f"Rebalance not needed (last: {days_since}d ago)",
                    "next_rebalance_in": state.llm_arbiter.rebalance_interval - days_since,
                })

        # Build AgentPerformance list
        performances = []
        for agent_name, metrics in state.agent_metrics.items():
            perf = AgentPerformance(
                name=agent_name,
                sharpe_7d=metrics.get("sharpe_7d", 0.0),
                max_drawdown=metrics.get("max_drawdown", 0.0),
                win_rate=metrics.get("win_rate", 0.0),
                avg_hold_bars=metrics.get("avg_hold_bars", 0.0),
                regime_fit=metrics.get("regime_fit", 0.5),
                diversity_score=metrics.get("diversity_score", 0.5),
                overfit_score=metrics.get("overfit_score", 0.0),
                current_allocation=metrics.get("allocation", 0.25),
                total_pnl=metrics.get("total_pnl", 0.0),
                trades_count=metrics.get("trades_count", 0),
            )
            performances.append(perf)

        # Get market context
        market_context = {}
        if state.analysis_history:
            latest = state.analysis_history[-1]
            market_context["volatility"] = latest.get("volatility", 0.0)
            market_context["regime_confidence"] = latest.get("regime_confidence", 0.0)

        # Run LLM rebalance
        decision = await state.llm_arbiter.analyze_performance(
            performances,
            current_regime,
            market_context,
        )

        return web.json_response({
            "status": "success",
            "allocations": decision.allocations,
            "reasoning": decision.reasoning,
            "warnings": decision.warnings,
            "confidence": decision.confidence,
            "regime_recommendation": decision.regime_recommendation,
            "timestamp": decision.timestamp.isoformat(),
        })

    except Exception as e:
        logger.error(f"Rebalance failed: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def generate_strategy(request: web.Request) -> web.Response:
    """POST /api/v1/strategy/generate - Generate strategy parameters.

    Request body:
        {
            "agent_name": "momentum_hunter",
            "current_params": {...},
            "recent_performance": {...},
            "current_regime": "bull"
        }

    Returns:
        StrategyProposal as JSON
    """
    if not state.strategy_generator:
        return web.json_response(
            {"error": "Strategy generator not initialized"},
            status=503
        )

    try:
        data = await request.json()

        agent_name = data.get("agent_name")
        current_params = data.get("current_params", {})
        recent_performance = data.get("recent_performance", {})
        current_regime = data.get("current_regime", "sideways")

        if not agent_name:
            return web.json_response(
                {"error": "agent_name required"},
                status=400
            )

        # Get persona from default personas
        from ai_trading.arbiter.strategy_generator import StrategyGenerator
        persona = StrategyGenerator.DEFAULT_PERSONAS.get(
            agent_name,
            "Trading agent"
        )

        # Generate strategy
        proposal = await state.strategy_generator.generate_strategy(
            agent_name=agent_name,
            persona=persona,
            current_params=current_params,
            recent_performance=recent_performance,
            current_regime=current_regime,
        )

        return web.json_response({
            "status": "success",
            "proposal": proposal.to_dict(),
        })

    except Exception as e:
        logger.error(f"Strategy generation failed: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """WebSocket endpoint for real-time updates.

    Streams market analysis updates to connected clients.
    """
    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    state.subscribers.add(ws)
    logger.info(f"WebSocket client connected. Total: {len(state.subscribers)}")

    try:
        # Send current state
        if state.analysis_history:
            await ws.send_json({
                "type": "initial",
                "data": state.analysis_history[-1],
            })

        # Listen for messages (mostly for ping/pong)
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get("action") == "subscribe":
                        await ws.send_json({
                            "type": "subscribed",
                            "message": "Subscribed to real-time updates",
                        })
                except json.JSONDecodeError:
                    pass
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")

    finally:
        state.subscribers.discard(ws)
        logger.info(f"WebSocket client disconnected. Total: {len(state.subscribers)}")

    return ws


async def broadcast_analysis(analysis: Dict[str, Any]):
    """Broadcast analysis to all connected WebSocket clients.

    Args:
        analysis: Market analysis to broadcast
    """
    if not state.subscribers:
        return

    message = json.dumps({
        "type": "analysis_update",
        "timestamp": datetime.now().isoformat(),
        "data": analysis,
    })

    # Send to all subscribers
    closed = set()
    for ws in state.subscribers:
        try:
            await ws.send_str(message)
        except Exception:
            closed.add(ws)

    # Remove closed connections
    for ws in closed:
        state.subscribers.discard(ws)


async def update_agent_metrics(request: web.Request) -> web.Response:
    """POST /api/v1/agents/metrics - Update agent metrics.

    Used by Arena to report agent performance.

    Request body:
        {
            "agent_name": {
                "sharpe_7d": 1.2,
                "max_drawdown": 0.08,
                ...
            }
        }
    """
    try:
        data = await request.json()

        for agent_name, metrics in data.items():
            state.agent_metrics[agent_name] = metrics

        # Update positions if provided
        positions = data.get("_positions", {})
        if positions:
            state.agent_positions.update(positions)

        return web.json_response({
            "status": "updated",
            "agents_count": len(state.agent_metrics),
        })

    except Exception as e:
        logger.error(f"Metrics update failed: {e}")
        return web.json_response(
            {"error": str(e)},
            status=400
        )


async def get_arbiter_stats(request: web.Request) -> web.Response:
    """GET /api/v1/arbiter/stats - Get LLM Arbiter statistics."""
    if not state.llm_arbiter:
        return web.json_response(
            {"error": "LLM Arbiter not enabled"},
            status=503
        )

    stats = state.llm_arbiter.get_statistics()
    return web.json_response(stats)


async def get_strategy_stats(request: web.Request) -> web.Response:
    """GET /api/v1/strategy/stats - Get strategy generator statistics."""
    if not state.strategy_generator:
        return web.json_response(
            {"error": "Strategy generator not initialized"},
            status=503
        )

    stats = state.strategy_generator.get_improvement_statistics()
    return web.json_response(stats)


def create_app() -> web.Application:
    """Create aiohttp application with all routes.

    Returns:
        Configured web Application
    """
    app = web.Application()
    app.cleanup_ctx.append(api_lifespan)

    # Routes
    app.router.add_post("/api/v1/market/analyze", analyze_market)
    app.router.add_get("/api/v1/market/state", get_market_state)
    app.router.add_post("/api/v1/arbiter/rebalance", run_rebalance)
    app.router.add_get("/api/v1/arbiter/stats", get_arbiter_stats)
    app.router.add_post("/api/v1/strategy/generate", generate_strategy)
    app.router.add_get("/api/v1/strategy/stats", get_strategy_stats)
    app.router.add_post("/api/v1/agents/metrics", update_agent_metrics)
    app.router.add_get("/ws", websocket_handler)

    return app


async def start_server(host: str = "localhost", port: int = 8080):
    """Start API server.

    Args:
        host: Server host
        port: Server port
    """
    from aiohttp import web

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"API server started on http://{host}:{port}")

    return runner
