from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging

from server.shared.market.provider import fetch_market_ohlcv
from server.modules.engine.runtime import (
    get_strategy_source,
    list_skill_strategies,
    run_skill_backtest,
)

router = APIRouter(tags=["Backtest"])
logger = logging.getLogger(__name__)


class LeaderboardRequest(BaseModel):
    framework: str = Field(default="backtesting-trading-strategies")
    symbol: str = Field(default="BTCUSDT")
    leverage: float = Field(default=10, ge=1, le=20)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    timeframes: List[str] = Field(default_factory=lambda: ["1m", "5m", "15m", "1h", "4h"])
    strategies: Optional[List[str]] = None


class BacktestAnalysisRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    framework: str = "backtesting-trading-strategies"
    strategy_key: Optional[str] = None
    strategy_label: str = "Unknown Strategy"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    leverage: float = 1.0
    temperature: float = 0.2
    results: Dict[str, Any] = Field(default_factory=dict)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_backtest_analysis(req: BacktestAnalysisRequest) -> str:
    r = req.results or {}
    total_return = _to_float(r.get("total_return"))
    total_pnl = _to_float(r.get("total_pnl"))
    win_rate = _to_float(r.get("win_rate"))
    max_drawdown = _to_float(r.get("max_drawdown"))
    sharpe_ratio = _to_float(r.get("sharpe_ratio"))
    profit_factor = _to_float(r.get("profit_factor"))
    total_trades = _to_int(r.get("total_trades"))
    best_trade = _to_float(r.get("best_trade"))
    worst_trade = _to_float(r.get("worst_trade"))
    win_count = _to_int(r.get("win_count"))
    loss_count = _to_int(r.get("loss_count"))

    if total_trades <= 0:
        verdict = "거래가 거의 없어 전략 유효성을 판단하기 어렵습니다."
    elif total_return > 15 and sharpe_ratio >= 1.0 and max_drawdown < 20:
        verdict = "수익/리스크 균형이 좋은 편이라 유지·소폭 개선 전략이 적합합니다."
    elif total_return > 0:
        verdict = "양(+) 수익이지만 리스크 관리와 체결 품질을 추가 개선할 여지가 큽니다."
    else:
        verdict = "현재 구간에서는 방어력이 부족해 진입 필터 강화가 필요합니다."

    return "\n".join(
        [
            f"# Backtest Analysis: {req.strategy_label}",
            "",
            "## Summary",
            f"- Symbol: `{req.symbol}`",
            f"- Timeframe: `{req.timeframe}`",
            f"- Framework: `{req.framework}`",
            f"- Date Range: `{req.start_date or '-'} ~ {req.end_date or '-'}`",
            f"- Leverage: `{req.leverage}x`",
            "",
            "## Metrics",
            f"- Total Return: `{total_return:.2f}%`",
            f"- Net PnL: `{total_pnl:.2f}`",
            f"- Win Rate: `{win_rate:.2f}%` (`{win_count}W/{loss_count}L`)",
            f"- Max Drawdown: `{max_drawdown:.2f}%`",
            f"- Sharpe Ratio: `{sharpe_ratio:.3f}`",
            f"- Profit Factor: `{profit_factor:.3f}`",
            f"- Total Trades: `{total_trades}`",
            f"- Best / Worst Trade: `{best_trade:.2f}` / `{worst_trade:.2f}`",
            "",
            "## Interpretation",
            f"- {verdict}",
            "",
            "## Next Actions",
            "1. 진입 조건을 1~2개만 유지하고 과도한 중복 필터를 제거하세요.",
            "2. 손절은 ATR 기반으로 유지하되, 트레일링 조건을 타임프레임별로 분리해보세요.",
            "3. 같은 전략으로 `1m/5m/15m/1h`를 교차 검증해 민감도 구간을 찾으세요.",
        ]
    )


# -------------------------------------------------------------------------
# [API] 백테스트 통합 실행: 심볼, 타임프레임, 전략(또는 코드)으로 테스트 수행 [GET]
# -------------------------------------------------------------------------
@router.get("/run")
async def run_backtest_endpoint(
    symbol: str = Query("BTCUSDT", description="바이낸스 심볼"),
    interval: str = Query("15m", description="타임프레임"),
    strategy: str = Query("optPredator", description="전략 키"),
    leverage: float = Query(10, description="레버리지 (1~20)", ge=1, le=20),
    start_date: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD, UTC)"),
    end_date: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD, UTC)"),
    include_candles: bool = Query(True, description="캔들 포함 여부"),
    code: Optional[str] = Query(None, description="커스텀 전략 소스 코드 (제공 시 실시간 실행)"),
):
    try:
        return run_skill_backtest(
            symbol=symbol,
            interval=interval,
            strategy=strategy,
            leverage=leverage,
            start_date=start_date,
            end_date=end_date,
            include_candles=include_candles,
            code=code,
        )
    except Exception as exc:
        logger.exception("Backtest error")
        return {"success": False, "error": str(exc)}


# -------------------------------------------------------------------------
# [API] 전략 목록 조회: 사용 가능한 백테스트 전략 리스트 반환 [GET]
# -------------------------------------------------------------------------
@router.get("/strategies")
async def get_backtest_strategies():
    try:
        return {
            "success": True,
            "framework": "backtesting-trading-strategies",
            "strategies": list_skill_strategies(),
        }
    except Exception as exc:
        logger.exception("Strategy list error")
        return {"success": False, "error": str(exc), "strategies": []}


@router.get("/strategies/{strategy_key}/code")
async def get_strategy_code(strategy_key: str):
    try:
        code = get_strategy_source(strategy_key)
        if not code:
            raise HTTPException(status_code=404, detail="Strategy not found")
        return {"success": True, "code": code}
    except Exception as exc:
        logger.exception("Get strategy code error")
        return {"success": False, "error": str(exc)}


# -------------------------------------------------------------------------
# [API] 백테스트 리더보드: 여러 전략/타임프레임 성과를 한눈에 비교 [POST]
# -------------------------------------------------------------------------
@router.post("/leaderboard")
async def run_backtest_leaderboard(req: LeaderboardRequest):
    try:
        if req.framework != "backtesting-trading-strategies":
            return {"success": False, "error": f"Unsupported framework: {req.framework}"}

        available = list_skill_strategies()
        available_by_key = {s["key"]: s for s in available}
        all_keys = list(available_by_key.keys())
        selected = req.strategies or all_keys

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        rows_all: List[Dict[str, Any]] = []

        for tf in req.timeframes:
            tf_rows: List[Dict[str, Any]] = []
            for key in selected:
                if key not in available_by_key:
                    continue

                data = run_skill_backtest(
                    symbol=req.symbol,
                    interval=tf,
                    strategy=key,
                    leverage=req.leverage,
                    start_date=req.start_date,
                    end_date=req.end_date,
                    include_candles=False,
                )
                if not data.get("success"):
                    continue

                res = data.get("results", {}) or {}
                meta = available_by_key[key]
                tf_rows.append(
                    {
                        "rank": 0,
                        "timeframe": tf,
                        "strategy": key,
                        "strategy_label": meta.get("label", key),
                        "framework": req.framework,
                        "results": {
                            "total_return": _to_float(res.get("total_return")),
                            "win_rate": _to_float(res.get("win_rate")),
                            "profit_factor": _to_float(res.get("profit_factor")),
                            "max_drawdown": _to_float(res.get("max_drawdown")),
                            "total_trades": _to_int(res.get("total_trades")),
                            "total_pnl": _to_float(res.get("total_pnl")),
                            "best_trade": _to_float(res.get("best_trade")),
                            "worst_trade": _to_float(res.get("worst_trade")),
                            "sharpe_ratio": _to_float(res.get("sharpe_ratio")),
                            "win_count": _to_int(res.get("win_count")),
                            "loss_count": _to_int(res.get("loss_count")),
                        },
                    }
                )

            tf_rows.sort(key=lambda x: x["results"]["total_return"], reverse=True)
            for idx, row in enumerate(tf_rows, start=1):
                row["rank"] = idx
            grouped[tf] = tf_rows
            rows_all.extend(tf_rows)

        overall = sorted(rows_all, key=lambda x: x["results"]["total_return"], reverse=True)
        for idx, row in enumerate(overall, start=1):
            row["overall_rank"] = idx

        return {
            "success": True,
            "framework": req.framework,
            "symbol": req.symbol,
            "range": {
                "start_date": req.start_date,
                "end_date": req.end_date,
                "leverage": req.leverage,
            },
            "grouped_by_timeframe": grouped,
            "overall": overall,
        }
    except Exception as exc:
        logger.exception("Leaderboard error")
        return {"success": False, "error": str(exc), "grouped_by_timeframe": {}, "overall": []}


# -------------------------------------------------------------------------
# [API] 마켓 데이터 조회: 차트 렌더링용 OHLCV 캔들 데이터 반환 [GET]
# -------------------------------------------------------------------------
@router.get("/market/ohlcv")
async def market_ohlcv(
    symbol: str = Query("BTCUSDT", description="마켓 심볼"),
    timeframe: str = Query("1h", description="타임프레임"),
    limit: int = Query(240, ge=50, le=1500),
):
    try:
        return fetch_market_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:
        logger.exception("Market OHLCV error")
        return {"success": False, "error": str(exc), "candles": []}


@router.post("/llm/backtest-analysis")
async def llm_backtest_analysis(req: BacktestAnalysisRequest):
    try:
        return {
            "success": True,
            "provider": "local",
            "model": "deterministic-backtest-analyzer",
            "content": _build_backtest_analysis(req),
        }
    except Exception as exc:
        logger.exception("Backtest analysis error")
        raise HTTPException(status_code=500, detail=f"분석 생성 실패: {exc}")
