from __future__ import annotations

import uuid
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from server.api.services.backtest_strategy_catalog import get_strategy_meta, resolve_strategy_key
from server.api.services.skill_backtest_runtime import get_strategy_source, run_skill_backtest


ALLOWED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h"}


def _extract_symbol(message: str, fallback: str = "BTCUSDT") -> str:
    m = re.search(r"\b([A-Z]{2,10}USDT)\b", message.upper())
    if m:
        return m.group(1)

    m = re.search(r"\b([A-Z]{2,10})/(USDT|USD)\b", message.upper())
    if m:
        return f"{m.group(1)}{m.group(2)}"

    return fallback.upper()


def _extract_timeframe(message: str, fallback: str = "1h") -> str:
    m = re.search(r"\b(1m|5m|15m|30m|1h|4h|1d)\b", (message or "").lower())
    return m.group(1) if m else fallback


def _resolve_dates(context: Dict[str, Any]) -> Tuple[str, str]:
    start = str(context.get("start_date") or "").strip()
    end = str(context.get("end_date") or "").strip()
    if start and end:
        return start, end

    end_dt = datetime.utcnow().date()
    start_dt = end_dt - timedelta(days=120)
    return start_dt.isoformat(), end_dt.isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_direction_stats(trades: List[Dict[str, Any]], side: str) -> Dict[str, Any]:
    side_key = side.upper()
    selected = [t for t in trades if str(t.get("type") or "").upper() == side_key]

    pnls = [_safe_float(t.get("profitAmt"), 0.0) for t in selected]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]

    gross_profit = sum(wins)
    gross_loss = sum(losses)
    if gross_loss < 0:
        pf = gross_profit / abs(gross_loss)
    else:
        pf = gross_profit if gross_profit > 0 else 0.0

    count = len(selected)
    win_rate = (len(wins) / count * 100.0) if count else 0.0

    return {
        "count": count,
        "win_rate": win_rate,
        "pnl": sum(pnls),
        "profit_factor": pf,
    }


def _build_analysis_text(
    title: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    leverage: float,
    metrics: Dict[str, Any],
    features: List[str],
    long_stats: Dict[str, Any],
    short_stats: Dict[str, Any],
) -> str:
    def _fmt_pct(v: float) -> str:
        return f"{v:+.2f}%"

    lines = [
        "요약은 다음과 같습니다:",
        "",
        f"{title} — 백테스트 결과",
        f"전략: {title} | 종목: {symbol} | 타임프레임: {timeframe} | 기간: {start_date} → {end_date}",
        "",
        "핵심 지표",
        f"순수익: ${metrics['total_pnl']:+,.2f} ({_fmt_pct(metrics['total_return'])})",
        f"바이앤홀드: {_fmt_pct(metrics['buy_hold_return'])}",
        f"최대 낙폭: {abs(metrics['max_drawdown']):.2f}%",
        f"샤프 비율: {metrics['sharpe_ratio']:.2f}",
        f"총 거래 수: {metrics['total_trades']}",
        f"손익 배수: {metrics['profit_factor']:.2f}",
        f"평균 수익: ${metrics['avg_win']:.0f} vs 평균 손실: ${abs(metrics['avg_loss']):.0f}",
        f"최대 수익: ${metrics['best_trade']:.0f} | 최대 손실: ${abs(metrics['worst_trade']):.0f}",
        f"평균 레버리지: {leverage:.0f}x",
        "",
        "방향별 분석",
        f"롱: {long_stats['count']}건, 승률 {long_stats['win_rate']:.1f}%, ${long_stats['pnl']:+,.0f}",
        f"숏: {short_stats['count']}건, 승률 {short_stats['win_rate']:.1f}%, ${short_stats['pnl']:+,.0f}",
        "",
        "전략 설계",
    ]

    lines.extend([f"- {feature}" for feature in features])

    lines += [
        "",
        "진단 인사이트",
        # "- 반전 청산 비중이 높으면 트레일링 스탑 도입 시 추가 개선 여지가 있습니다.",
        # "- 손실 거래의 미실현 수익 구간을 보호하도록 부분청산 규칙을 검토해보세요.",
        # "- 숏/롱 성과 격차가 크면 방향별 최소 보유 시간 필터를 분리하는 것이 유효합니다.",
    ]
    return "\n".join(lines)


def run_strategy_chat_backtest(
    message: str,
    context: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    del history

    preferred_strategy = str(
        context.get("strategy") or context.get("strategy_key") or ""
    ).strip() or None

    strategy_key = resolve_strategy_key(
        message=message,
        preferred_strategy=preferred_strategy,
    )
    strategy_meta = get_strategy_meta(strategy_key)

    symbol = str(context.get("symbol") or _extract_symbol(message)).upper()
    timeframe = str(context.get("timeframe") or _extract_timeframe(message)).lower()
    if timeframe not in ALLOWED_TIMEFRAMES:
        timeframe = "1h"

    start_date, end_date = _resolve_dates(context)
    leverage = float(context.get("leverage") or 10.0)
    run_id = f"run_{uuid.uuid4().hex[:10]}"

    backtest_payload = run_skill_backtest(
        symbol=symbol,
        interval=timeframe,
        strategy=strategy_key,
        leverage=leverage,
        start_date=start_date,
        end_date=end_date,
        include_candles=True,
    )
    if not backtest_payload.get("success"):
        raise RuntimeError(str(backtest_payload.get("error") or "Backtest failed"))

    results = backtest_payload.get("results", {}) or {}
    trades = backtest_payload.get("trades", []) or []

    long_stats = _compute_direction_stats(trades, "LONG")
    short_stats = _compute_direction_stats(trades, "SHORT")

    metrics = {
        "total_pnl": _safe_float(results.get("total_pnl"), 0.0),
        "total_return": _safe_float(results.get("total_return"), 0.0),
        "win_rate": _safe_float(results.get("win_rate"), 0.0),
        "max_drawdown": abs(_safe_float(results.get("max_drawdown"), 0.0)),
        "sharpe_ratio": _safe_float(results.get("sharpe_ratio"), 0.0),
        "profit_factor": _safe_float(results.get("profit_factor"), 0.0),
        "total_trades": int(results.get("total_trades") or 0),
        "best_trade": _safe_float(results.get("best_trade"), 0.0),
        "worst_trade": _safe_float(results.get("worst_trade"), 0.0),
        "win_count": int(results.get("win_count") or 0),
        "loss_count": int(results.get("loss_count") or 0),
        "avg_win": _safe_float(results.get("avg_profit"), 0.0),
        "avg_loss": _safe_float(results.get("avg_loss"), 0.0),
        "buy_hold_return": _safe_float(results.get("buy_hold"), 0.0),
    }

    analysis_text = _build_analysis_text(
        title=strategy_meta["title"],
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        leverage=leverage,
        metrics=metrics,
        features=list(strategy_meta.get("features") or []),
        long_stats=long_stats,
        short_stats=short_stats,
    )

    strategy_code = get_strategy_source(strategy_key) or "// Strategy source is unavailable."

    return {
        "success": True,
        "run_id": run_id,
        "assistant_ack": "지금 바로 전략을 구축하겠습니다. 코드를 생성하고 백테스트를 실행합니다.",
        "strategy_card": {
            "title": strategy_meta["title"],
            "description": strategy_meta["description"],
            "code": strategy_code,
            "strategy_key": strategy_key,
            "params": dict(strategy_meta.get("params") or {}),
        },
        "backtest_card": {
            "ret": f"{metrics['total_return']:+.2f}%",
            "mdd": f"{metrics['max_drawdown']:.2f}%",
            "winRate": f"{metrics['win_rate']:.1f}%",
            "sharpe": f"{metrics['sharpe_ratio']:.2f}",
            "trades": str(metrics["total_trades"]),
            "pf": f"{metrics['profit_factor']:.2f}",
        },
        "analysis": analysis_text,
        "backtest_payload": backtest_payload,
    }
