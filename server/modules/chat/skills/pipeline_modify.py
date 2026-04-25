"""MODIFY_STRATEGY 파이프라인 (분석 → 설계 → 수정 코드 → 백테스트 + 비교)"""
import difflib
import json
import logging
import os
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import stream_quick_reply, stream_analysis_reply, stream_code_gen_reply
from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.chat.prompts import (
    DESIGN_PROMPT_TEMPLATE,
    MODIFY_ANALYZE_TEMPLATE,
    MODIFY_CODE_TEMPLATE,
)
from server.modules.chat.skills._base import (
    format_sse,
    extract_python_code,
    extract_strategy_title,
    sanitize_generated_code,
    salvage_valid_python,
    resolve_target_agent,
    build_memory_guardrail,
    get_last_strategy,
)
from server.modules.chat.skills.pipeline_backtest import run_backtest

logger = logging.getLogger(__name__)
_REQUIRED_SIGNAL_FN_RE = re.compile(
    r"def\s+generate_signal\s*\(\s*train_df\s*:\s*pd\.DataFrame\s*,\s*test_df\s*:\s*pd\.DataFrame\s*\)\s*->\s*pd\.Series",
    re.IGNORECASE,
)
_CODE_GEN_ERROR_RE = re.compile(r"\[코드 생성 오류:\s*(.+?)\]", re.IGNORECASE | re.DOTALL)


def _compact_code_for_analysis(code: str, max_chars: int) -> str:
    """Stage 1 분석 지연을 줄이기 위해 코드 컨텍스트 길이를 제한한다."""
    text = (code or "").strip()
    if len(text) <= max_chars:
        return text
    head_len = max_chars // 2
    tail_len = max_chars - head_len
    return (
        text[:head_len].rstrip()
        + "\n\n# ... [중간 코드 생략: 분석 속도 최적화] ...\n\n"
        + text[-tail_len:].lstrip()
    )


def _env_enabled(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _metric_float(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "")
        return float(value)
    except Exception:
        return default


def _has_any(text: str, patterns: List[str]) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except re.error:
            logger.warning(f"[modify.fast] invalid regex pattern skipped: {pattern!r}")
            continue
    return False


def _build_feedback_block(last_failure: str, last_feedback: str, metrics: Dict[str, Any]) -> str:
    failure = (last_failure or "").strip()
    feedback = (last_feedback or "").strip()
    has_metrics = bool(metrics)
    if not failure and not feedback and not has_metrics:
        return ""

    lines = ["\n\n[직전 백테스트 피드백]"]
    if failure:
        lines.append(f"- failure_type: {failure}")
    if feedback:
        lines.append(f"- failure_reason: {feedback[:700]}")
    if has_metrics:
        lines.append(
            "- metrics: "
            f"return={_metric_float(metrics, 'total_return'):+.2f}, "
            f"mdd={_metric_float(metrics, 'max_drawdown'):.2f}, "
            f"win_rate={_metric_float(metrics, 'win_rate'):.2f}, "
            f"pf={_metric_float(metrics, 'profit_factor'):.2f}, "
            f"trades={int(_metric_float(metrics, 'total_trades'))}"
        )
    lines.append("- instruction: 이번 수정은 위 실패 원인을 직접 해결하는 구조 변경을 포함해야 한다.")
    if failure == "zero_trades" or (has_metrics and int(_metric_float(metrics, "total_trades")) == 0):
        lines.append("- zero_trade_rule: 조건을 더 쌓지 말고, 임계값 완화/OR fallback/쿨다운 축소로 최소 거래 수를 먼저 회복한다.")
    return "\n".join(lines)


def _build_fast_modify_analysis(
    prev_code: str,
    metrics: Dict[str, Any],
    user_request: str,
    last_failure: str = "",
    last_feedback: str = "",
) -> str:
    code = prev_code or ""
    has_metrics = bool(metrics)
    ret = _metric_float(metrics, "total_return")
    mdd = abs(_metric_float(metrics, "max_drawdown"))
    win = _metric_float(metrics, "win_rate")
    sharpe = _metric_float(metrics, "sharpe_ratio")
    trades = int(_metric_float(metrics, "total_trades"))
    pf = _metric_float(metrics, "profit_factor")
    failure = (last_failure or "").strip()
    feedback = (last_feedback or "").strip()

    findings = []
    if failure == "zero_trades" or (has_metrics and trades == 0):
        findings.append("- 직전 백테스트 거래 0건: 진입 조건이 너무 엄격하거나 서로 충돌함. 이번 수정은 신호 수 회복이 최우선.")
    elif failure == "hard_gate_failed":
        findings.append("- 직전 하드게이트 미통과: 단순 파라미터 조정보다 실패 지표를 겨냥한 구조 변경이 필요.")
    elif failure == "backtest_error":
        findings.append("- 직전 백테스트 오류: 코드 안정성과 필수 함수/반환 타입 검증을 우선 확인해야 함.")
    if feedback:
        findings.append(f"- 직전 피드백: {feedback[:260]}")
    if has_metrics and ret < 0:
        findings.append(f"- 수익률 {ret:+.2f}%: 현재 진입 방향/필터가 기대값을 만들지 못함.")
    if has_metrics and pf and pf < 1.05:
        findings.append(f"- PF {pf:.2f}: 손익비 또는 진입 품질이 부족해 손실 거래 영향이 큼.")
    if has_metrics and sharpe < 0.3:
        findings.append(f"- Sharpe {sharpe:.2f}: 수익 경로가 불안정하고 노이즈 구간 진입 가능성이 높음.")
    if has_metrics and mdd > 15:
        findings.append(f"- MDD {mdd:.2f}%: 변동성 과열/역추세 구간에서 방어 장치가 약함.")
    if has_metrics and win and win < 35:
        findings.append(f"- 승률 {win:.1f}%: 신호 확인 조건 또는 진입 타이밍 보강 필요.")
    if has_metrics and trades > 120:
        findings.append(f"- 거래 {trades}건: 과거래 가능성이 있어 쿨다운/레짐 필터가 필요.")
    elif has_metrics and 0 < trades < 30:
        findings.append(f"- 거래 {trades}건: 조건이 너무 좁아 검증 표본이 부족함.")
    if not findings:
        findings.append("- 성과 지표는 극단적으로 나쁘지 않지만, 구조 변경으로 안정성 개선 여지가 있음.")

    features = []
    features.append(f"- VWAP 사용: {'예' if _has_any(code, [r'vwap']) else '아니오'}")
    features.append(f"- 거래량/수급 사용: {'예' if _has_any(code, [r'volume_delta', r'vol_zscore', r'volume']) else '아니오'}")
    features.append(f"- ATR 레짐 사용: {'예' if _has_any(code, [r'atr', r'true range', r'tr\d?\s*=']) else '아니오'}")
    features.append(f"- 추세 필터(EMA/SMA 장단기) 사용: {'예' if _has_any(code, [r'ema', r'rolling\(.*mean']) else '약함/확인 필요'}")
    features.append(f"- 쿨다운/손실 방어 로직: {'예' if _has_any(code, [r'cooldown', r'loss', r'drawdown', r'stop']) else '아니오'}")

    return (
        "[빠른 수정 분석]\n"
        f"사용자 요청: {user_request}\n\n"
        "핵심 약점\n" + "\n".join(findings[:6]) + "\n\n"
        "기존 구조 진단\n" + "\n".join(features) + "\n\n"
        "수정 방향\n"
        "- 파라미터만 바꾸지 말고 진입 구조를 바꾼다.\n"
        "- VWAP/거래량 아이디어는 유지하되 추세, 변동성, 수급 확인을 분리한다.\n"
        "- train_df 기반 임계값을 유지/강화하고 test_df에는 미래참조 없이 적용한다.\n"
        "- 거래 수를 크게 죽이지 않도록 조건은 3개 내외의 핵심 필터로 제한한다.\n"
    )


def _build_fast_modify_design(
    prev_code: str,
    metrics: Dict[str, Any],
    user_request: str,
    analysis: str,
    last_failure: str = "",
    last_feedback: str = "",
) -> str:
    code = prev_code or ""
    has_metrics = bool(metrics)
    pf = _metric_float(metrics, "profit_factor")
    mdd = abs(_metric_float(metrics, "max_drawdown"))
    win = _metric_float(metrics, "win_rate")
    trades = int(_metric_float(metrics, "total_trades"))
    failure = (last_failure or "").strip()
    zero_trade_failure = failure == "zero_trades" or (has_metrics and trades == 0)

    keep = []
    if _has_any(code, [r'vwap']):
        keep.append("rolling/session VWAP 기반 가격 위치")
    if _has_any(code, [r'vol_zscore', r'volume']):
        keep.append("거래량 급증 감지")
    if _has_any(code, [r'volume_delta']):
        keep.append("수급 압력/volume delta")
    if not keep:
        keep.append("기존 전략의 핵심 진입 아이디어")

    objectives = [
        "PF 1.05 이상을 우선 목표로 거짓 신호를 줄인다.",
        "MDD를 낮추기 위해 변동성 과열 구간과 역추세 진입을 제한한다.",
        "신호 수는 30건 이상 유지하되 과도한 AND 적층은 피한다.",
    ]
    if zero_trade_failure:
        objectives.insert(0, "거래 0건 탈출: 조건 충돌을 제거하고 최소 30건 이상의 진입 신호를 회복한다.")
    if has_metrics and pf and pf < 1.0:
        objectives.append("PF가 1 미만이므로 진입 품질 필터를 손익비 개선 중심으로 재설계한다.")
    if has_metrics and mdd > 20:
        objectives.append("MDD가 높으므로 ATR 상단 과열 필터와 쿨다운을 추가한다.")
    if has_metrics and win and win < 35:
        objectives.append("승률이 낮으므로 VWAP 이탈 후 확인봉/수급 방향 확인을 추가한다.")
    if has_metrics and trades > 120:
        objectives.append("거래 수가 많으므로 최근 신호 중복을 줄이는 간단한 쿨다운 마스크를 둔다.")

    if zero_trade_failure:
        required_changes = [
            "AND 조건 적층을 줄이고 long/short 각각 core trigger + direction filter + broad risk filter 3개 이하로 제한",
            "volume z-score 임계값은 train_df quantile 0.60~0.75 수준으로 완화하고 NaN/inf fallback 제공",
            "VWAP distance 기준은 0.05~0.10% 수준으로 완화하거나 momentum fallback을 OR로 허용",
            "ATR regime은 너무 좁히지 말고 극저변동/극과열만 제거하는 넓은 범위로 설정",
            "cooldown은 생략하거나 2~3봉 이하로 제한해 신호를 죽이지 않음",
        ]
    else:
        required_changes = [
            "train_df에서 adaptive quantile threshold를 계산하고 test_df에는 고정 적용",
            "EMA fast/slow 또는 slope 기반 추세 필터 추가",
            "ATR regime을 하한/상한 양쪽으로 제한해 저변동/과열 구간 제외",
            "volume_delta 또는 VWAP distance를 smoothing해서 단발성 노이즈 감소",
        ]
        if has_metrics and trades > 120:
            required_changes.append("최근 N봉 내 같은 방향 신호 중복을 줄이는 cooldown mask 추가")
        elif has_metrics and trades < 30:
            required_changes.append("거래 수 부족을 피하도록 필터를 추가하지 말고 기존 임계값을 완화")

    return (
        "strategy_modify_design:\n"
        f"  base_strategy: \"{extract_strategy_title(prev_code)}\"\n"
        f"  user_request: \"{user_request}\"\n"
        f"  previous_failure: \"{last_failure or 'none'}\"\n"
        f"  previous_feedback: \"{(last_feedback or '')[:220]}\"\n"
        "  preserve:\n"
        + "".join(f"    - {item}\n" for item in keep[:4])
        + "  objectives:\n"
        + "".join(f"    - {item}\n" for item in objectives[:6])
        + "  required_changes:\n"
        + "".join(f"    - {item}\n" for item in required_changes)
        + "  code_rules:\n"
        "    - 함수 시그니처는 def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series 유지\n"
        "    - import는 numpy, pandas만 사용\n"
        "    - shift(-1) 미래참조 금지\n"
        "    - 최종 조건은 long/short 각각 3개 내외의 핵심 조건으로 구성\n"
        "    - return sig.fillna(0).astype(int)\n"
        "\nanalysis_summary:\n"
        + analysis[:1800]
    )


def _metrics_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    total_return = context.get("total_return")
    if total_return is None:
        total_return = context.get("totalReturn")
    if total_return is None:
        total_return = context.get("totalReturnNum")
    metrics: Dict[str, Any] = {}
    if total_return is not None:
        metrics["total_return"] = _metric_float({"v": total_return}, "v")
    if context.get("maxDrawdown") is not None:
        metrics["max_drawdown"] = _metric_float({"v": context.get("maxDrawdown")}, "v")
    if context.get("winRate") is not None:
        metrics["win_rate"] = _metric_float({"v": context.get("winRate")}, "v")
    if context.get("profitFactor") is not None:
        metrics["profit_factor"] = _metric_float({"v": context.get("profitFactor")}, "v")
    if context.get("sharpe") is not None:
        metrics["sharpe_ratio"] = _metric_float({"v": context.get("sharpe")}, "v")
    if context.get("trades") is not None:
        metrics["total_trades"] = int(_metric_float({"v": context.get("trades")}, "v"))
    return metrics


def _extract_context_strategy(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(context, dict):
        return None

    candidates: List[str] = []
    for key in ("editor_code", "strategy_code", "code"):
        raw = context.get(key)
        if isinstance(raw, str) and raw.strip():
            candidates.append(raw)

    current = context.get("current_strategy")
    if isinstance(current, dict):
        for key in ("code", "strategy_code"):
            raw = current.get(key)
            if isinstance(raw, str) and raw.strip():
                candidates.append(raw)
    elif isinstance(current, str) and current.strip():
        candidates.append(current)

    source_code = ""
    for cand in candidates:
        clean = sanitize_generated_code(cand)
        if clean and ("def generate_signal(" in clean or "def generate_signals(" in clean):
            source_code = clean
            break
    if not source_code:
        return None

    title = (
        str(context.get("strategy_title") or "").strip()
        or str(context.get("strategy") or "").strip()
    )
    if not title and isinstance(current, dict):
        title = (
            str(current.get("title") or "").strip()
            or str(current.get("name") or "").strip()
        )
    title = title or extract_strategy_title(source_code) or "에디터 전략"

    return {
        "title": title,
        "code": source_code,
        "metrics": _metrics_from_context(context),
    }


async def _recover_code_once(raw_output: str, original_prompt: str, reason: str) -> str:
    """중간 끊김/형식 깨짐 대응용 1회 복구."""
    broken = (raw_output or "").strip()
    recovery_prompt = (
        "아래 출력은 중간에 끊겼거나 형식이 깨진 전략 코드다.\n"
        "이전 출력 조각을 이어 쓰지 말고, 실행 가능한 완전한 Python 코드 전체를 처음부터 다시 출력하라.\n"
        "필수 함수 시그니처:\n"
        "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series\n"
        "설명문/마크다운 문장 금지. 백틱(```) 절대 사용 금지. 순수 코드만 출력.\n"
        "코드는 간결하게 작성하고, 불필요한 클래스/긴 주석/장문 설명을 넣지 마라.\n\n"
        f"[실패 원인]\n{reason}\n\n"
        f"[원래 수정 지시]\n{original_prompt[-5000:]}\n\n"
        f"[이전 출력 일부]\n{broken[-3500:] if broken else '(없음: 첫 생성이 비어 있거나 오류 출력만 반환됨)'}\n"
    )
    repaired_full = ""
    async for chunk in stream_code_gen_reply(recovery_prompt):
        content = chunk.get("content")
        if content:
            repaired_full += content
    return sanitize_generated_code(extract_python_code(repaired_full))


def _validate_strategy_code(strategy_code: str) -> Optional[str]:
    if not strategy_code:
        return "수정된 코드 추출 실패"
    if not _REQUIRED_SIGNAL_FN_RE.search(strategy_code):
        return "필수 함수 시그니처 누락: def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series"
    try:
        StrategyLoader.validate_code(strategy_code)
    except (SecurityError, SyntaxError) as e:
        return str(e)
    return None


def _build_patch_plan_prompt(
    prev_code: str,
    prev_title: str,
    user_request: str,
    metrics: Dict[str, Any],
    last_failure: str,
    last_feedback: str,
) -> str:
    return (
        "너는 Python 트레이딩 전략 코드의 최소 변경 패치 생성기다.\n"
        "전체 재작성 금지. 기존 코드에서 1~4개 find/replace만 제안하라.\n"
        "find 문자열은 아래 코드에서 정확히 복붙 가능한 원문이어야 한다.\n"
        "JSON만 출력하고 설명문/코드블록/마크다운은 금지.\n\n"
        f"[전략명]\n{prev_title}\n\n"
        f"[사용자 요청]\n{user_request}\n\n"
        f"[직전 실패]\n{last_failure or 'none'}\n"
        f"[직전 피드백]\n{(last_feedback or '')[:360]}\n"
        f"[지표]\n{json.dumps(metrics or {}, ensure_ascii=False)}\n\n"
        "[출력 JSON 스키마]\n"
        "{\n"
        '  "title": "수정 전략명(선택)",\n'
        '  "summary": "어떤 약점을 고쳤는지 한 줄",\n'
        '  "edits": [\n'
        '    {"find": "...", "replace": "...", "count": 1, "reason": "..."}\n'
        "  ]\n"
        "}\n\n"
        "[제약]\n"
        "- import는 numpy/pandas만 유지\n"
        "- 함수 시그니처 변경 금지\n"
        "- 미래참조 shift(-1) 금지\n"
        "- 임계값 완화/필터 충돌 해소 같은 실질 수정 우선\n"
        "- count는 보통 1, 전체 edits 최대 4\n\n"
        f"[기존 코드]\n{prev_code}"
    )


def _extract_json_payload(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}

    candidates: List[str] = [text]
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE):
        block = m.group(1).strip()
        if block:
            candidates.append(block)

    left = text.find("{")
    right = text.rfind("}")
    if left != -1 and right > left:
        candidates.append(text[left:right + 1])

    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def _apply_patch_edits(prev_code: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
    patched = prev_code
    applied = 0
    normalized_edits: List[Dict[str, Any]] = []

    for edit in edits[:4]:
        if not isinstance(edit, dict):
            continue
        find = str(edit.get("find") or "")
        replace = str(edit.get("replace") or "")
        if not find:
            continue
        try:
            count = int(edit.get("count", 1))
        except Exception:
            count = 1
        if count <= 0:
            count = patched.count(find)
        if count <= 0:
            continue
        if find not in patched:
            continue
        next_code = patched.replace(find, replace, count)
        if next_code == patched:
            continue
        patched = next_code
        applied += 1
        normalized_edits.append({
            "reason": str(edit.get("reason") or "").strip(),
            "count": count,
        })

    return {
        "code": patched,
        "applied": applied,
        "edits": normalized_edits,
        "requested": min(len(edits), 4),
    }


def _changed_line_ratio(before: str, after: str) -> float:
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
    base = max(len(before_lines), len(after_lines), 1)
    sm = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changed += max(i2 - i1, j2 - j1)
    return changed / base


async def _attempt_patch_first(
    prev_code: str,
    prev_title: str,
    user_request: str,
    metrics: Dict[str, Any],
    last_failure: str,
    last_feedback: str,
) -> Dict[str, Any]:
    prompt = _build_patch_plan_prompt(
        prev_code=prev_code,
        prev_title=prev_title,
        user_request=user_request,
        metrics=metrics,
        last_failure=last_failure,
        last_feedback=last_feedback,
    )

    raw = ""
    async for chunk in stream_quick_reply(prompt):
        content = chunk.get("content")
        if content:
            raw += content

    payload = _extract_json_payload(raw)
    edits = payload.get("edits") if isinstance(payload, dict) else None
    if not isinstance(edits, list) or not edits:
        return {"ok": False, "reason": "no_patch_edits"}

    patch_result = _apply_patch_edits(prev_code, edits)
    patched = sanitize_generated_code(patch_result.get("code", ""))
    patched = salvage_valid_python(patched)
    if not patched:
        return {"ok": False, "reason": "empty_patch_output"}
    if patch_result.get("applied", 0) <= 0:
        return {"ok": False, "reason": "no_edit_applied"}

    ratio = _changed_line_ratio(prev_code, patched)
    max_ratio = max(0.10, min(0.60, float(os.getenv("CHAT_MODIFY_PATCH_MAX_RATIO", "0.38"))))
    if ratio > max_ratio:
        return {"ok": False, "reason": f"patch_too_large({ratio:.2f})"}

    validation_error = _validate_strategy_code(patched)
    if validation_error:
        return {"ok": False, "reason": f"patch_invalid({validation_error})"}

    title_hint = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    return {
        "ok": True,
        "code": patched,
        "title": title_hint,
        "summary": summary,
        "applied": int(patch_result.get("applied", 0)),
        "requested": int(patch_result.get("requested", 0)),
        "ratio": ratio,
    }


async def run_modify_pipeline(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    _history: List[Dict[str, Any]],
    db,
    session_memory: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    prev = await get_last_strategy(session_id, db, session_memory)
    context_prev = _extract_context_strategy(context or {})
    if context_prev:
        if prev:
            merged = dict(prev)
            merged.update(context_prev)
            if not context_prev.get("metrics"):
                merged["metrics"] = prev.get("metrics", {})
            merged["last_failure"] = context_prev.get("last_failure") or prev.get("last_failure") or ""
            merged["last_feedback"] = context_prev.get("last_feedback") or prev.get("last_feedback") or ""
            prev = merged
        else:
            prev = context_prev

    if not prev:
        yield format_sse({"type": "analysis", "content": "수정할 이전 전략이 없습니다."})
        yield format_sse({"type": "done"})
        return

    prev_code = prev["code"]
    prev_metrics = prev.get("metrics", {})
    prev_title = prev.get("title", "이전 전략")
    last_failure = str(prev.get("last_failure") or "").strip()
    last_feedback = str(prev.get("last_feedback") or "").strip()
    feedback_block = _build_feedback_block(last_failure, last_feedback, prev_metrics)

    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)
    chat_mutation_hint = str(memory_context.get("next_mutation") or "").strip()
    guardrail_block = build_memory_guardrail(memory_context)

    reasoning_model = ((os.getenv("QUICK_MODEL") or os.getenv("LITELLM_MODEL") or "Quick Model").split("/")[-1]).strip()
    analysis_model = ((os.getenv("ANALYSIS_MODEL") or os.getenv("LITELLM_MODEL") or "Analysis Model").split("/")[-1]).strip()
    code_model = ((os.getenv("CODE_GEN_MODEL") or os.getenv("LITELLM_MODEL") or "Code Model").split("/")[-1]).strip()
    analyze_code_chars = max(2000, int(os.getenv("CHAT_MODIFY_ANALYZE_CODE_CHARS", "6000")))
    analyze_output_chars = max(800, int(os.getenv("CHAT_MODIFY_ANALYSIS_MAX_CHARS", "2200")))
    fast_mode = _env_enabled("CHAT_MODIFY_FAST_MODE", True)
    patch_first = _env_enabled("CHAT_MODIFY_PATCH_FIRST", True)
    patch_fallback_full = _env_enabled("CHAT_MODIFY_PATCH_FALLBACK_FULL", True)

    if patch_first:
        yield format_sse({
            "type": "stage",
            "stage": 1,
            "label": f"🩹 '{prev_title}' 최소 변경 패치 적용 중... ({reasoning_model})",
        })
        patch_result = await _attempt_patch_first(
            prev_code=prev_code,
            prev_title=prev_title,
            user_request=message,
            metrics=prev_metrics,
            last_failure=last_failure,
            last_feedback=last_feedback,
        )
        if patch_result.get("ok"):
            strategy_code = str(patch_result.get("code") or "")
            strategy_title = (
                str(patch_result.get("title") or "").strip()
                or extract_strategy_title(strategy_code)
                or f"{prev_title} (수정)"
            )
            ratio_pct = float(patch_result.get("ratio", 0.0)) * 100.0
            summary = str(patch_result.get("summary") or "").strip()
            brief = (
                f"\n🛠️ 최소 변경 패치 적용 완료 "
                f"(적용 {int(patch_result.get('applied', 0))}/{int(patch_result.get('requested', 0))}, "
                f"변경 라인 {ratio_pct:.1f}%).\n"
            )
            if summary:
                brief += f"- 핵심 수정: {summary[:220]}\n"
            yield format_sse({"type": "analysis", "content": brief})

            strategy_data = {"title": strategy_title, "code": strategy_code, "params": {"agent_title": strategy_title}}
            yield format_sse({"type": "strategy", "data": strategy_data})
            await db.save_chat_message(session_id, "assistant", strategy_title, "strategy", strategy_data)

            yield format_sse({"type": "stage", "stage": 4, "label": "📈 수정 전략 백테스트 및 비교 중..."})
            if prev_metrics:
                yield format_sse({"type": "analysis", "content": (
                    f"\n**[기존 '{prev_title}' 성과]**\n"
                    f"- 수익률: {prev_metrics.get('total_return', 0):+.2f}%"
                    f"  MDD: {prev_metrics.get('max_drawdown', 0):.2f}%"
                    f"  Sharpe: {prev_metrics.get('sharpe_ratio', 0):.2f}"
                    f"  거래 수: {int(prev_metrics.get('total_trades', 0))}\n\n"
                )})

            fast_context = dict(context or {})
            fast_context["skip_tips"] = True
            async for ev in run_backtest(
                strategy_code, strategy_title, message, fast_context, session_id, db, session_memory,
                memory=memory, constitution=constitution, target_agent=target_agent,
                chat_mutation_hint=chat_mutation_hint,
                is_mining_mode=False, prev_metrics=prev_metrics,
            ):
                yield ev
            yield format_sse({"type": "done"})
            return

        logger.info("[modify] patch-first failed, fallback=%s reason=%s", patch_fallback_full, patch_result.get("reason"))
        if not patch_fallback_full:
            yield format_sse({"type": "error", "content": "최소 변경 패치 적용에 실패했습니다. 요청을 더 구체적으로 적어 주세요."})
            yield format_sse({"type": "done"})
            return
        yield format_sse({"type": "status", "content": "패치 적용이 어려워 전체 코드 재생성 모드로 전환합니다..."})

    yield format_sse({"type": "stage", "stage": 1,
                      "label": f"🔍 '{prev_title}' 빠른 약점 분석 중... ({'local' if fast_mode else reasoning_model})"})

    if fast_mode:
        analysis_full = _build_fast_modify_analysis(
            prev_code, prev_metrics, message, last_failure, last_feedback
        )
        yield format_sse({"type": "thought", "content": analysis_full})
        yield format_sse({"type": "status", "content": "⚡ 빠른 분석 완료 — 수정 설계로 진행합니다..."})
    else:
        # ✅ 초기 thought 메시지 → AI Reasoning 카드 열림
        yield format_sse({"type": "thought", "content": "기존 전략의 약점과 개선 지점을 분석 중입니다..."})
        prompt_analyze = MODIFY_ANALYZE_TEMPLATE.format(
            prev_code=_compact_code_for_analysis(prev_code, analyze_code_chars),
            prev_metrics=str(prev_metrics),
            user_request=message,
        ) + feedback_block
        analysis_full = ""
        analysis_capped = False
        async for chunk in stream_quick_reply(prompt_analyze):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                yield format_sse({"type": "thought", "content": thought})
            if content:
                analysis_full += content
                yield format_sse({"type": "thought", "content": content})
                if len(analysis_full) >= analyze_output_chars:
                    analysis_capped = True
                    break
        if analysis_capped:
            analysis_full = analysis_full[:analyze_output_chars].rstrip()
            yield format_sse({"type": "status", "content": "⚡ 핵심 분석 요약 확보 완료 — 설계 단계로 진행합니다..."})

    await db.save_chat_message(session_id, "assistant", analysis_full[:12000], "thought")

    yield format_sse({"type": "stage", "stage": 2, "label": f"📋 수정 설계도 작성 중... ({'local' if fast_mode else analysis_model})"})
    if fast_mode:
        design_full = _build_fast_modify_design(
            prev_code, prev_metrics, message, analysis_full, last_failure, last_feedback
        )
        yield format_sse({"type": "analysis", "content": design_full})
    else:
        prompt_design = DESIGN_PROMPT_TEMPLATE.format(reasoning=analysis_full) + feedback_block + guardrail_block
        design_full = ""
        async for chunk in stream_analysis_reply(prompt_design):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                yield format_sse({"type": "thought", "content": thought})
            if content:
                design_full += content
                yield format_sse({"type": "analysis", "content": content})

    session_memory.setdefault(session_id, {})["design"] = design_full
    # design 이벤트 후 프론트는 직전 text 블록을 카드로 교체 (이중 표시 없음)
    yield format_sse({"type": "design", "content": design_full})
    await db.save_chat_message(session_id, "assistant", design_full, "design")

    yield format_sse({"type": "stage", "stage": 3, "label": f"⚙️ 수정된 코드 구현 중... ({code_model})"})
    prompt_code = MODIFY_CODE_TEMPLATE.format(
        analysis=analysis_full,
        design=design_full,
        prev_code=prev_code,
    ) + feedback_block + guardrail_block
    _modify_max_tokens = int(os.getenv("CHAT_CODE_GEN_MAX_TOKENS", "2000"))
    code_full = ""
    _thought_buf = ""
    _last_status_t = time.monotonic()
    _STATUS_INTERVAL = 3.0
    async for chunk in stream_code_gen_reply(prompt_code, max_tokens=_modify_max_tokens):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            _thought_buf += thought
            yield format_sse({"type": "thought", "content": thought})
        if content:
            code_full += content
            yield format_sse({"type": "analysis", "content": content})
            _now = time.monotonic()
            if _now - _last_status_t >= _STATUS_INTERVAL:
                yield format_sse({"type": "status", "content": f"⚙️ 코드 구현 중... ({len(code_full):,}자)"})
                _last_status_t = _now

    if not code_full.strip() and _thought_buf.strip():
        logger.warning("[modify] code_full empty, falling back to thought buffer (%d chars)", len(_thought_buf))
        code_full = _thought_buf

    codegen_error = _CODE_GEN_ERROR_RE.search(code_full or "")
    if codegen_error:
        err_text = codegen_error.group(1).strip()
        yield format_sse({"type": "error", "content": f"수정 코드 생성 실패: {err_text}"})
        yield format_sse({"type": "done"})
        return

    strategy_code = sanitize_generated_code(extract_python_code(code_full))
    strategy_code = salvage_valid_python(strategy_code)
    validation_error = _validate_strategy_code(strategy_code)

    if validation_error:
        for attempt in range(2):
            yield format_sse({"type": "analysis", "content": (
                f"\n코드가 중간에 끊겨 자동 복구를 시도합니다... ({attempt + 1}/2)\n"
            )})
            recovered = await _recover_code_once(code_full, prompt_code, validation_error)
            recovered = salvage_valid_python(sanitize_generated_code(recovered))
            if recovered:
                strategy_code = recovered
                validation_error = _validate_strategy_code(strategy_code)
            if not validation_error:
                break

    if not strategy_code:
        yield format_sse({"type": "error", "content": "수정된 코드 추출 실패: 출력이 중간에 끊겼습니다."})
        yield format_sse({"type": "done"})
        return

    if validation_error:
        yield format_sse({"type": "error", "content": f"수정 코드 검증 실패: {validation_error}"})
        yield format_sse({"type": "done"})
        return

    strategy_title = extract_strategy_title(code_full) or f"{prev_title} (수정)"
    strategy_data = {"title": strategy_title, "code": strategy_code, "params": {"agent_title": strategy_title}}
    yield format_sse({"type": "strategy", "data": strategy_data})
    await db.save_chat_message(session_id, "assistant", strategy_title, "strategy", strategy_data)

    yield format_sse({"type": "stage", "stage": 4,
                      "label": "📈 수정 전략 백테스트 및 비교 중..."})
    if prev_metrics:
        yield format_sse({"type": "analysis", "content": (
            f"\n**[기존 '{prev_title}' 성과]**\n"
            f"- 수익률: {prev_metrics.get('total_return', 0):+.2f}%"
            f"  MDD: {prev_metrics.get('max_drawdown', 0):.2f}%"
            f"  Sharpe: {prev_metrics.get('sharpe_ratio', 0):.2f}"
            f"  거래 수: {int(prev_metrics.get('total_trades', 0))}\n\n"
        )})

    async for ev in run_backtest(
        strategy_code, strategy_title, message, context, session_id, db, session_memory,
        memory=memory, constitution=constitution, target_agent=target_agent,
        chat_mutation_hint=chat_mutation_hint,
        is_mining_mode=False, prev_metrics=prev_metrics,
    ):
        yield ev
    yield format_sse({"type": "done"})
