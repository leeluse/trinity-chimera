"""공통 유틸리티, 상수, 세션 메모리 헬퍼"""
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.modules.evolution.constants import AGENT_IDS

logger = logging.getLogger(__name__)

DEFAULT_HARD_GATES = {
    "min_win_rate": 0.40,
    "min_profit_factor": 1.10,
    "min_total_return": -0.05,
    "max_drawdown": 0.30,
    "min_total_trades": 15,
    "min_sharpe_ratio": 0.20,
}


def format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def extract_python_code(text: str) -> str:
    m = re.search(r"```python\s*([\s\S]*?)```", text)
    return m.group(1).strip() if m else ""


def extract_strategy_title(text: str) -> str:
    patterns = [
        r"\[Title:\s*(.*?)\]",
        r"\[전략 이름:\s*(.*?)\]",
        r"전략명:\s*(.*)",
        r"Name:\s*(.*)",
        r"\"\"\"\s*\n?\s*(.*?Strategy.*?)\n",
        r"#\s*(.*?Strategy.*?)$",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            t = m.group(1).strip().replace('"', "").replace("'", "")
            if t:
                return t
    return "AI Generated Strategy"


def log_strategy_to_file(message: str, metrics: Dict[str, Any]):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = (
            f"\n\n### [{ts}] - AI Generated Strategy\n"
            f"- **요청**: {message}\n"
            f"- **성과**: 수익률 {metrics.get('total_return', 0):+.2f}%,"
            f" MDD {metrics.get('max_drawdown', 0):.2f}%\n"
        )
        with open(Path("STRATEGY.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logger.error(f"STRATEGY.md 로그 실패: {e}")


def normalize_ratio(value: float) -> float:
    if 1.0 < abs(value) <= 100.0:
        return value / 100.0
    return value


def normalize_metrics_for_gate(metrics: Dict[str, Any]) -> Dict[str, Any]:
    total_return = normalize_ratio(float(metrics.get("total_return", 0.0) or 0.0))
    win_rate = normalize_ratio(float(metrics.get("win_rate", 0.0) or 0.0))
    max_drawdown_raw = float(metrics.get("max_drawdown", 0.0) or 0.0)
    max_drawdown = normalize_ratio(max_drawdown_raw)
    if max_drawdown > 0:
        max_drawdown = -max_drawdown
    return {
        "total_return": total_return,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "profit_factor": float(metrics.get("profit_factor", 0.0) or 0.0),
        "total_trades": int(metrics.get("total_trades", 0) or 0),
        "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
        "trinity_score": float(metrics.get("trinity_score", 0.0) or 0.0),
    }


def resolve_target_agent(context: Dict[str, Any], message: str) -> str:
    for key in ("agent_id", "active_agent", "agent"):
        value = str(context.get(key) or "").strip()
        if value in AGENT_IDS:
            return value
    text = (message or "").lower()
    for agent_id in AGENT_IDS:
        if agent_id in text:
            return agent_id
    return "chat_global"


def build_memory_guardrail(memory_context: Dict[str, Any]) -> str:
    hard_gates = memory_context.get("hard_gates") or {}
    failures = memory_context.get("recent_failures") or []
    successes = memory_context.get("recent_successes") or []
    failure_summary = memory_context.get("failure_summary") or []
    best_accepted = memory_context.get("best_accepted") or {}
    unexplored_mutations = memory_context.get("unexplored_mutations") or []
    next_mutation = str(memory_context.get("next_mutation") or "").strip()

    fail_lines = [f"- {str(r.get('reason') or 'unknown')}" for r in failures[:5]] or ["- (최근 실패 없음)"]
    success_lines = []
    for row in successes[:3]:
        m = row.get("metrics") or {}
        success_lines.append(
            f"- win={float(m.get('win_rate',0)):.3f}, pf={float(m.get('profit_factor',0)):.3f},"
            f" ret={float(m.get('total_return',0)):.3f}, mdd={float(m.get('max_drawdown',0)):.3f},"
            f" trades={int(m.get('total_trades',0))}"
        )
    if not success_lines:
        success_lines = ["- (최근 성공 없음)"]
    summary_lines = [f"- {str(r.get('tag') or 'other')}: {int(r.get('count') or 0)}" for r in failure_summary[:6]] or ["- (없음)"]
    best_metrics = best_accepted.get("metrics") if isinstance(best_accepted, dict) else {}
    if isinstance(best_metrics, dict) and best_metrics:
        best_line = (
            f"- pf={float(best_metrics.get('profit_factor',0)):.3f},"
            f" win={float(best_metrics.get('win_rate',0)):.3f},"
            f" ret={float(best_metrics.get('total_return',0)):.3f},"
            f" mdd={float(best_metrics.get('max_drawdown',0)):.3f},"
            f" trades={int(best_metrics.get('total_trades',0))}"
        )
    else:
        best_line = "- (채택 전략 없음)"
    unexplored_lines = [f"- {str(i).strip()}" for i in unexplored_mutations[:6] if str(i).strip()] or ["- (없음)"]

    return (
        "\n\n[QUALITY_GUARDRAIL]\n"
        f"- min_win_rate: {hard_gates.get('min_win_rate',0.0)}\n"
        f"- min_profit_factor: {hard_gates.get('min_profit_factor',0.0)}\n"
        f"- min_total_return: {hard_gates.get('min_total_return',0.0)}\n"
        f"- max_drawdown(abs): {hard_gates.get('max_drawdown',1.0)}\n"
        f"- min_total_trades: {hard_gates.get('min_total_trades',0)}\n"
        f"- min_sharpe_ratio: {hard_gates.get('min_sharpe_ratio',0.0)}\n"
        "[RECENT_FAILURES]\n" + "\n".join(fail_lines) +
        "\n[RECENT_SUCCESSES]\n" + "\n".join(success_lines) +
        "\n[FAILURE_TAG_SUMMARY]\n" + "\n".join(summary_lines) +
        "\n[BEST_ACCEPTED]\n" + best_line +
        "\n[UNEXPLORED]\n" + "\n".join(unexplored_lines) +
        f"\n[NEXT_MUTATION]\n- {next_mutation or 'structural_novelty'}\n"
        "- 위 방향에 맞게 진입/청산/필터 구조를 실제로 변경하세요."
    )


async def get_last_strategy(
    session_id: str,
    db,
    session_memory: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """세션 메모리 → DB 순으로 마지막 전략을 조회."""
    if session_id in session_memory:
        return session_memory[session_id]
    history = await db.get_chat_history(session_id, limit=30)
    for msg in reversed(history):
        if msg.get("type") in ["strategy", "backtest"]:
            data = msg.get("data") or {}
            if data.get("code"):
                strat = {
                    "title": data.get("title", "복구된 전략"),
                    "code": data.get("code"),
                    "metrics": data.get("metrics") or {},
                }
                session_memory[session_id] = strat
                return strat
    return None
