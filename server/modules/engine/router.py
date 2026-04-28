from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import json
import logging
import math
import random
import re
from itertools import product
from pathlib import Path

from server.shared.market.provider import fetch_market_ohlcv
from server.modules.engine.runtime import (
    get_strategy_source,
    list_skill_strategies,
    run_skill_backtest,
)
from server.modules.evolution.scoring import calculate_trinity_score
from server.modules.regime.labeler import (
    ARTIFACT_MAP,
    DEFAULT_VALIDATION_END,
    DEFAULT_VALIDATION_START,
    run_regime_labeler,
    resolve_out_root,
)

router = APIRouter(tags=["Backtest"])
logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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


class BacktestOptimizeRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    strategy: Optional[str] = None
    code: Optional[str] = None
    leverage: float = Field(default=10.0, ge=1, le=20)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    param_count: int = Field(default=4, ge=1, le=12)
    max_combos: int = Field(default=50, ge=1, le=300)
    method: str = Field(default="grid")
    objective: str = Field(default="trinity")
    top_k: int = Field(default=5, ge=1, le=20)
    score_weights: Optional[Dict[str, float]] = None


class BacktestRegimeRunRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    start_date: str = DEFAULT_VALIDATION_START
    end_date: str = DEFAULT_VALIDATION_END
    out_dir: Optional[str] = None


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


def _scan_numeric_params_from_code(code: str) -> Dict[str, float]:
    found: Dict[str, float] = {}

    for m in re.finditer(r"^\s*([a-zA-Z_]\w*)\s*=\s*(-?\d+\.?\d*)\s*(?:#.*)?$", code, re.MULTILINE):
        name, val_str = m.group(1), m.group(2)
        v = float(val_str)
        found[name] = int(v) if v == int(v) else v

    for m in re.finditer(r"[\"']([a-zA-Z_]\w*)[\"']\s*:\s*(-?\d+\.?\d*)", code):
        name, val_str = m.group(1), m.group(2)
        v = float(val_str)
        found[name] = int(v) if v == int(v) else v

    return found


def _build_param_ranges(found: Dict[str, float]) -> List[Dict[str, Any]]:
    priority_keywords = ("len", "period", "window", "lookback", "atr", "rsi", "stoch", "ema", "mult", "thresh", "pivot", "slope")

    def rank(name: str, value: float) -> float:
        score = 0.0
        low_name = name.lower()
        if any(k in low_name for k in priority_keywords):
            score += 10.0
        score += min(5.0, abs(float(value)))
        if abs(float(value)) <= 1:
            score -= 0.5
        return score

    sorted_items = sorted(found.items(), key=lambda item: rank(item[0], item[1]), reverse=True)
    ranges: List[Dict[str, Any]] = []

    for name, value in sorted_items:
        if isinstance(value, bool):
            continue

        v = float(value)
        is_int_like = float(v).is_integer()

        if is_int_like:
            base = int(v)
            if base <= 0:
                min_v, max_v, step = 0, max(3, abs(base) + 3), 1
            elif base <= 3:
                min_v, max_v, step = max(1, base - 1), base + 2, 1
            else:
                span = max(1, int(round(abs(base) * 0.5)))
                min_v = max(1, base - span)
                max_v = base + span
                step = max(1, int(round(abs(base) * 0.1)))
        else:
            if abs(v) < 1e-9:
                min_v, max_v, step = 0.0, 0.5, 0.1
            else:
                span = max(0.01, abs(v) * 0.5)
                min_v = max(0.0, v - span) if v > 0 else v - span
                max_v = v + span
                step = max(0.01, abs(v) * 0.1)
            min_v = round(float(min_v), 8)
            max_v = round(float(max_v), 8)
            step = round(float(step), 8)

        if max_v <= min_v:
            continue

        ranges.append(
            {
                "name": name,
                "current": int(v) if is_int_like else v,
                "min": min_v,
                "max": max_v,
                "step": step,
            }
        )

    return ranges


def _float_range(min_v: float, max_v: float, step: float) -> List[float]:
    values: List[float] = []
    v = min_v
    while v <= max_v + 1e-9:
        values.append(round(v, 10))
        v = round(v + step, 10)
    return values


def _build_param_combos(param_ranges: List[Dict[str, Any]], max_limit: int, method: str) -> List[Dict[str, Any]]:
    if not param_ranges:
        return []

    names: List[str] = []
    values_list: List[List[float]] = []
    for p in param_ranges:
        current = p.get("current")
        # Preserve integer-typed params (e.g., rolling windows) to avoid runtime failures
        # such as "window must be an integer 0 or greater".
        if isinstance(current, int) and not isinstance(current, bool):
            min_i = int(round(float(p["min"])))
            max_i = int(round(float(p["max"])))
            step_i = max(1, int(round(float(p["step"]))))
            values = list(range(min_i, max_i + 1, step_i))
        else:
            values = _float_range(float(p["min"]), float(p["max"]), float(p["step"]))

        if len(values) > 7:
            picks = [0, len(values) // 4, len(values) // 2, (len(values) * 3) // 4, len(values) - 1]
            values = sorted(set(values[i] for i in picks))
        names.append(str(p["name"]))
        values_list.append(values)

    total = 1
    for vals in values_list:
        total *= len(vals)

    method_lower = method.lower()
    if method_lower == "random":
        size = [len(v) for v in values_list]
        sampled: set = set()
        combos: List[Dict[str, Any]] = []
        for _ in range(max_limit * 30):
            if len(combos) >= max_limit:
                break
            idx_tuple = tuple(random.randrange(n) for n in size)
            if idx_tuple in sampled:
                continue
            sampled.add(idx_tuple)
            combos.append(dict(zip(names, [values_list[i][j] for i, j in enumerate(idx_tuple)])))
        return combos

    if total <= max_limit:
        return [dict(zip(names, combo)) for combo in product(*values_list)]

    sampled_idx: set = set()
    combos: List[Dict[str, Any]] = []
    size = [len(v) for v in values_list]
    for _ in range(max_limit * 30):
        if len(combos) >= max_limit:
            break
        idx_tuple = tuple(random.randrange(n) for n in size)
        if idx_tuple in sampled_idx:
            continue
        sampled_idx.add(idx_tuple)
        combos.append(dict(zip(names, [values_list[i][j] for i, j in enumerate(idx_tuple)])))
    return combos


def _apply_param_values_to_code(code: str, param_values: Dict[str, Any]) -> str:
    modified = code
    for param_name, param_value in param_values.items():
        pattern_var = rf"(?<![a-zA-Z0-9_])({re.escape(param_name)}\s*=\s*)(-?\d+\.?\d*)"
        modified = re.sub(pattern_var, rf"\g<1>{param_value}", modified)

        pattern_dict = rf"([\"']{re.escape(param_name)}[\"']\s*:\s*)(-?\d+\.?\d*)"
        modified = re.sub(pattern_dict, rf"\g<1>{param_value}", modified)
    return modified


def _extract_metrics(payload: Dict[str, Any]) -> Dict[str, float]:
    res = (payload or {}).get("results", {}) or {}
    return {
        "total_return": _to_float(res.get("total_return")),
        "max_drawdown": _to_float(res.get("max_drawdown")),
        "sharpe_ratio": _to_float(res.get("sharpe_ratio")),
        "win_rate": _to_float(res.get("win_rate")),
        "profit_factor": _to_float(res.get("profit_factor")),
        "total_trades": _to_float(res.get("total_trades")),
    }


def _default_score_weights() -> Dict[str, float]:
    return {
        "total_return": 0.45,
        "sharpe_ratio": 0.30,
        "win_rate": 0.05,
        "profit_factor": 0.05,
        "trades": 0.05,
        "max_drawdown": 0.10,  # penalty
    }


def _normalize_score_weights(raw_weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    merged = _default_score_weights()
    if raw_weights:
        for key in merged.keys():
            if key in raw_weights:
                merged[key] = _to_float(raw_weights.get(key), merged[key])

    total = sum(abs(v) for v in merged.values())
    if total <= 1e-12:
        merged = _default_score_weights()
        total = sum(abs(v) for v in merged.values())
    return {k: v / total for k, v in merged.items()}


def _weighted_score(metrics: Dict[str, float], normalized_weights: Dict[str, float]) -> float:
    # Normalize each metric into roughly comparable range before weighted sum.
    total_return_norm = _to_float(metrics.get("total_return")) / 100.0
    sharpe_norm = _to_float(metrics.get("sharpe_ratio")) / 3.0
    win_rate_norm = _to_float(metrics.get("win_rate")) / 100.0
    profit_factor_norm = min(_to_float(metrics.get("profit_factor")), 5.0) / 5.0

    trades_raw = max(0.0, _to_float(metrics.get("total_trades")))
    trades_norm = min(1.0, math.log1p(trades_raw) / math.log1p(500.0))
    mdd_penalty_norm = abs(_to_float(metrics.get("max_drawdown"))) / 100.0

    score = 0.0
    score += normalized_weights.get("total_return", 0.0) * total_return_norm
    score += normalized_weights.get("sharpe_ratio", 0.0) * sharpe_norm
    score += normalized_weights.get("win_rate", 0.0) * win_rate_norm
    score += normalized_weights.get("profit_factor", 0.0) * profit_factor_norm
    score += normalized_weights.get("trades", 0.0) * trades_norm
    score -= normalized_weights.get("max_drawdown", 0.0) * mdd_penalty_norm
    return score * 100.0


def _score_metrics(metrics: Dict[str, float], objective: str, score_weights: Optional[Dict[str, float]] = None) -> float:
    objective_lower = objective.lower()
    if objective_lower == "sharpe":
        return _to_float(metrics.get("sharpe_ratio"))
    if objective_lower == "return":
        return _to_float(metrics.get("total_return"))
    if objective_lower in {"weighted", "custom"}:
        normalized = _normalize_score_weights(score_weights)
        return _weighted_score(metrics, normalized)
    return float(
        calculate_trinity_score(
            _to_float(metrics.get("total_return")) / 100.0,
            _to_float(metrics.get("sharpe_ratio")),
            -_to_float(metrics.get("max_drawdown")) / 100.0,
        )
    )


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
# [API] 파라미터 최적화: 코드에서 수치 파라미터 스캔 후 조합 백테스트 [POST]
# -------------------------------------------------------------------------
@router.post("/optimize")
async def optimize_backtest_params(req: BacktestOptimizeRequest):
    try:
        strategy_key = req.strategy or "custom_strategy"
        source_code = (req.code or "").strip()

        if not source_code and req.strategy:
            source_code = get_strategy_source(req.strategy)
        if not source_code:
            return {"success": False, "error": "최적화할 전략 코드가 없습니다."}

        scanned = _scan_numeric_params_from_code(source_code)
        ranges = _build_param_ranges(scanned)
        if not ranges:
            return {"success": False, "error": "코드에서 조정 가능한 숫자 파라미터를 찾지 못했습니다."}

        selected_ranges = ranges[: min(req.param_count, len(ranges))]
        normalized_weights = (
            _normalize_score_weights(req.score_weights)
            if req.objective.lower() in {"weighted", "custom"}
            else None
        )
        combos = _build_param_combos(
            param_ranges=selected_ranges,
            max_limit=max(1, min(req.max_combos, 300)),
            method=req.method,
        )
        if not combos:
            return {"success": False, "error": "생성된 파라미터 조합이 없습니다."}

        baseline_payload = run_skill_backtest(
            symbol=req.symbol,
            interval=req.interval,
            strategy=strategy_key,
            leverage=req.leverage,
            start_date=req.start_date,
            end_date=req.end_date,
            include_candles=False,
            code=source_code,
        )
        baseline_metrics = _extract_metrics(baseline_payload) if baseline_payload.get("success") else {}

        tested: List[Dict[str, Any]] = []
        for combo in combos:
            candidate_code = _apply_param_values_to_code(source_code, combo)
            payload = run_skill_backtest(
                symbol=req.symbol,
                interval=req.interval,
                strategy=strategy_key,
                leverage=req.leverage,
                start_date=req.start_date,
                end_date=req.end_date,
                include_candles=False,
                code=candidate_code,
            )
            if not payload.get("success"):
                continue

            metrics = _extract_metrics(payload)
            tested.append(
                {
                    "params": combo,
                    "metrics": metrics,
                    "score": _score_metrics(metrics, req.objective, normalized_weights),
                }
            )

        if not tested:
            return {
                "success": False,
                "error": "모든 조합 백테스트가 실패했습니다.",
                "baseline": baseline_metrics,
                "selected_params": selected_ranges,
                "tested_combos": len(combos),
            }

        tested.sort(key=lambda x: _to_float(x.get("score")), reverse=True)
        best = tested[0]
        best_code = _apply_param_values_to_code(source_code, best["params"])
        best_payload = run_skill_backtest(
            symbol=req.symbol,
            interval=req.interval,
            strategy=strategy_key,
            leverage=req.leverage,
            start_date=req.start_date,
            end_date=req.end_date,
            include_candles=True,
            code=best_code,
        )

        top_rows = tested[: max(1, min(req.top_k, len(tested)))]
        return {
            "success": True,
            "objective": req.objective,
            "score_weights": normalized_weights,
            "method": req.method,
            "scanned_param_count": len(ranges),
            "selected_params": selected_ranges,
            "tested_combos": len(combos),
            "successful_combos": len(tested),
            "baseline": baseline_metrics,
            "best": {
                "score": _to_float(best.get("score")),
                "params": best.get("params", {}),
                "metrics": best.get("metrics", {}),
                "code": best_code,
                "backtest_payload": best_payload if best_payload.get("success") else None,
            },
            "top": top_rows,
        }
    except Exception as exc:
        logger.exception("Optimize params error")
        return {"success": False, "error": str(exc)}


def _resolve_regime_run_dir(run_id: str, out_dir: Optional[str]) -> Path:
    if not re.match(r"^[A-Za-z0-9_.-]+$", run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id format")
    base_dir = resolve_out_root(out_dir).resolve()
    run_dir = (base_dir / run_id).resolve()
    if not str(run_dir).startswith(str(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid run_id path")
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    return run_dir


@router.post("/regime/run")
async def run_regime_labeling(req: BacktestRegimeRunRequest):
    try:
        result = run_regime_labeler(
            symbol=req.symbol,
            timeframe=req.timeframe,
            start_date=req.start_date,
            end_date=req.end_date,
            out_dir=req.out_dir,
        )
        run_id = str(result["run_id"])
        base_dir = str(result["base_dir"])
        return {
            "success": True,
            "run_id": run_id,
            "base_dir": base_dir,
            "stats": result["stats"],
            "logs": result.get("logs", []),
            "artifact_paths": result["artifact_paths"],
            "preview_url": f"/api/backtest/regime/preview/{run_id}?out_dir={base_dir}",
            "download_urls": {
                "parquet": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['parquet']}?out_dir={base_dir}",
                "stats": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['stats']}?out_dir={base_dir}",
                "chart": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['chart']}?out_dir={base_dir}",
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Regime run error")
        return {"success": False, "error": str(exc)}


@router.get("/regime/result/{run_id}")
async def get_regime_result(run_id: str, out_dir: Optional[str] = Query(None)):
    run_dir = _resolve_regime_run_dir(run_id, out_dir)
    stats_path = run_dir / ARTIFACT_MAP["stats"]
    chart_path = run_dir / ARTIFACT_MAP["chart"]
    parquet_path = run_dir / ARTIFACT_MAP["parquet"]

    stats: Dict[str, Any] = {}
    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
        except Exception:
            stats = {}

    base_dir = str(run_dir.parent.relative_to(PROJECT_ROOT))
    return {
        "success": True,
        "run_id": run_id,
        "base_dir": base_dir,
        "stats": stats,
        "logs": stats.get("logs", []),
        "artifact_exists": {
            "parquet": parquet_path.exists(),
            "stats": stats_path.exists(),
            "chart": chart_path.exists(),
        },
        "preview_url": f"/api/backtest/regime/preview/{run_id}?out_dir={base_dir}",
        "download_urls": {
            "parquet": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['parquet']}?out_dir={base_dir}",
            "stats": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['stats']}?out_dir={base_dir}",
            "chart": f"/api/backtest/regime/download/{run_id}/{ARTIFACT_MAP['chart']}?out_dir={base_dir}",
        },
    }


@router.get("/regime/preview/{run_id}")
async def preview_regime_chart(run_id: str, out_dir: Optional[str] = Query(None)):
    run_dir = _resolve_regime_run_dir(run_id, out_dir)
    chart_path = run_dir / ARTIFACT_MAP["chart"]
    if not chart_path.exists():
        raise HTTPException(status_code=404, detail="Chart artifact not found")
    return HTMLResponse(content=chart_path.read_text(encoding="utf-8"), status_code=200)


@router.get("/regime/download/{run_id}/{artifact}")
async def download_regime_artifact(run_id: str, artifact: str, out_dir: Optional[str] = Query(None)):
    run_dir = _resolve_regime_run_dir(run_id, out_dir)
    if artifact in ARTIFACT_MAP:
        filename = ARTIFACT_MAP[artifact]
    elif artifact in ARTIFACT_MAP.values():
        filename = artifact
    else:
        raise HTTPException(status_code=404, detail="Unknown artifact")
    file_path = run_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path=file_path, filename=filename)


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
