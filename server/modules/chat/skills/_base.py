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
    "min_win_rate": 0.35,
    "min_profit_factor": 1.05,
    "min_total_return": -0.10,
    "max_drawdown": 0.35,
    "min_total_trades": 15,
    "min_sharpe_ratio": -0.10,
}


def format_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def extract_python_code(text: str) -> str:
    if not text:
        return ""

    def _first_code_tail(src: str) -> str:
        m = re.search(r"(?m)^(?:from\s+\w+|import\s+\w+|class\s+\w+|def\s+\w+)", src or "")
        return (src[m.start():] if m else src).strip()

    def _score(block: str) -> int:
        s = 0
        lower = block.lower()
        if "def generate_signal(" in block:
            s += 10
        if "def generate_signals(" in block:
            s += 7
        if "class " in block and ("generate_signals(" in block or "generate_signal(" in block):
            s += 5
        if "import pandas as pd" in lower or "pd." in block:
            s += 3
        if "class " in block:
            s += 1
        if "```" in block:
            s -= 2
        return s

    candidates: List[str] = []

    # 1) python/py fenced blocks
    for m in re.finditer(r"```(?:python|py)\s*([\s\S]*?)```", text, re.IGNORECASE):
        block = m.group(1).strip()
        if block:
            candidates.append(block)

    # 2) generic fenced blocks (모델이 언어 태그를 생략하는 경우 대응)
    for m in re.finditer(r"```\s*([\s\S]*?)```", text):
        block = m.group(1).strip()
        if block:
            candidates.append(block)

    # 2-1) fence가 닫히지 않은 채 잘린 응답 대응 (마지막 fence 이후 tail 사용)
    open_fence_matches = list(re.finditer(r"```(?:python|py)?\s*", text, re.IGNORECASE))
    if open_fence_matches:
        tail = text[open_fence_matches[-1].end():].strip()
        if tail:
            candidates.append(tail)

    # 3) fenced block이 없고 함수 시그니처가 본문에 직접 있는 경우
    if not candidates and ("def generate_signal(" in text or "def generate_signals(" in text):
        tail = _first_code_tail(text)
        if tail:
            candidates.append(tail)

    # 4) fenced block이 없고 클래스 기반 전략 코드가 본문에 직접 있는 경우
    if not candidates and "class " in text and ("generate_signals(" in text or "generate_signal(" in text):
        tail = _first_code_tail(text)
        if tail:
            candidates.append(tail)

    # 5) 장문 서술 + 코드가 섞여 있을 때, 첫 코드 라인부터 tail 추출
    if not candidates:
        tail = _first_code_tail(text)
        if tail and ("class " in tail or "def " in tail or "import " in tail):
            candidates.append(tail)

    if not candidates:
        return ""

    candidates.sort(key=_score, reverse=True)
    best = candidates[0].strip()

    # 텍스트 전체를 후보로 쓴 경우 남아있는 fence 잔재 제거
    best = re.sub(r"^```(?:python|py)?\s*", "", best, flags=re.IGNORECASE)
    best = re.sub(r"\s*```$", "", best)
    return best.strip()


def salvage_valid_python(code: str) -> str:
    """후행 잡음/미완성 응답에서 컴파일 가능한 최대 prefix를 복구."""
    text = (code or "").strip()
    if not text:
        return ""

    try:
        compile(text, "<strategy>", "exec")
        return text
    except Exception:
        pass

    lines = text.splitlines()
    if len(lines) < 8:
        return text

    min_keep = max(8, int(len(lines) * 0.5))
    for end in range(len(lines) - 1, min_keep - 1, -1):
        candidate = "\n".join(lines[:end]).strip()
        has_signal_fn = "def generate_signal(" in candidate or "def generate_signals(" in candidate
        has_strategy_class = "class " in candidate and ("generate_signals(" in candidate or "generate_signal(" in candidate)
        if not (has_signal_fn or has_strategy_class):
            continue
        try:
            compile(candidate, "<strategy>", "exec")
            return candidate
        except Exception:
            continue
    return text


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
    """세션 메모리 → 세션 메시지 → 글로벌 메시지 → strategies 순으로 마지막 전략을 조회."""
    if session_id in session_memory:
        return session_memory[session_id]

    def _decode_strategy(msg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not msg:
            return None
        data = msg.get("data") or {}
        # Supabase가 JSONB를 문자열로 반환하는 경우 파싱
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except Exception:
                data = {}
        code = data.get("code")
        if code:
            return {
                "title": data.get("title", "복구된 전략"),
                "code": code,
                "metrics": data.get("metrics") or {},
            }
        return None

    def _decode_strategy_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        code = row.get("code")
        if not code:
            return None
        params = row.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        title = (
            row.get("name")
            or (params.get("display_name") if isinstance(params, dict) else None)
            or (params.get("agent_title") if isinstance(params, dict) else None)
            or "복구된 전략"
        )
        return {
            "title": title,
            "code": code,
            "metrics": {},
        }

    # 1) 현재 세션 최신 전략
    msg = await db.get_last_strategy_message(session_id)
    strat = _decode_strategy(msg)
    if strat:
        session_memory[session_id] = strat
        return strat

    # 2) 세션에 없으면 전체 세션 기준 최신 전략으로 fallback
    msg_any = await db.get_last_strategy_message_any()
    strat_any = _decode_strategy(msg_any)
    if strat_any:
        session_memory[session_id] = strat_any
        return strat_any

    # 3) 메시지 기록이 없다면 strategies 최신 배포본을 fallback
    row_any = await db.get_last_strategy_row_any()
    strat_row = _decode_strategy_row(row_any)
    if strat_row:
        session_memory[session_id] = strat_row
        return strat_row

    return None
