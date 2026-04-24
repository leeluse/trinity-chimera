"""MODIFY_STRATEGY 파이프라인 (분석 → 설계 → 수정 코드 → 백테스트 + 비교)"""
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import stream_chat_reply, stream_analysis_reply, stream_code_gen_reply
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

async def _recover_code_once(raw_output: str, original_prompt: str, reason: str) -> str:
    """중간 끊김/형식 깨짐 대응용 1회 복구."""
    broken = (raw_output or "").strip()
    if not broken:
        return ""

    recovery_prompt = (
        "아래 출력은 중간에 끊겼거나 형식이 깨진 전략 코드다.\n"
        "실행 가능한 완전한 Python 코드만 출력하라.\n"
        "필수 함수 시그니처:\n"
        "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series\n"
        "설명문/마크다운 문장 금지. 코드블록 1개 또는 순수 코드만 출력.\n\n"
        f"[실패 원인]\n{reason}\n\n"
        f"[원래 수정 지시 일부]\n{original_prompt[-2500:]}\n\n"
        f"[끊긴 출력 일부]\n{broken[-3500:]}\n"
    )
    repaired_full = ""
    async for chunk in stream_code_gen_reply(recovery_prompt):
        repaired_full += chunk
    return extract_python_code(repaired_full)


async def run_modify_pipeline(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]],
    db,
    session_memory: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    prev = await get_last_strategy(session_id, db, session_memory)
    if not prev:
        yield format_sse({"type": "analysis", "content": "수정할 이전 전략이 없습니다."})
        yield format_sse({"type": "done"})
        return

    prev_code = prev["code"]
    prev_metrics = prev.get("metrics", {})
    prev_title = prev.get("title", "이전 전략")

    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)
    chat_mutation_hint = str(memory_context.get("next_mutation") or "").strip()
    guardrail_block = build_memory_guardrail(memory_context)

    reasoning_model = ((os.getenv("LITELLM_MODEL") or os.getenv("QUICK_MODEL") or "Brain Model").split("/")[-1]).strip()
    analysis_model = ((os.getenv("ANALYSIS_MODEL") or os.getenv("LITELLM_MODEL") or "Analysis Model").split("/")[-1]).strip()
    code_model = ((os.getenv("CODE_GEN_MODEL") or os.getenv("LITELLM_MODEL") or "Code Model").split("/")[-1]).strip()

    yield format_sse({"type": "stage", "stage": 1,
                      "label": f"🔍 '{prev_title}' 분석 및 약점 탐색 중... ({reasoning_model})"})
    # ✅ 초기 thought 메시지 → AI Reasoning 카드 열림
    yield format_sse({"type": "thought", "content": "기존 전략의 약점과 개선 지점을 분석 중입니다..."})
    prompt_analyze = MODIFY_ANALYZE_TEMPLATE.format(
        prev_code=prev_code,
        prev_metrics=str(prev_metrics),
        user_request=message,
    )
    analysis_full = ""
    # ✅ 분석 청크 실시간 스트리밍
    async for chunk in stream_chat_reply(user_message=prompt_analyze, context=context,
                                          history=[],
                                          model=(os.getenv("LITELLM_MODEL") or None)):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            analysis_full += content
            yield format_sse({"type": "thought", "content": content})
    # thought 이벤트 스트리밍 완료 → 카드가 자동 접힘 (isStreaming=false)
    await db.save_chat_message(session_id, "assistant", analysis_full[:12000], "thought")

    yield format_sse({"type": "stage", "stage": 2, "label": f"📋 수정 설계도 작성 중... ({analysis_model})"})
    prompt_design = DESIGN_PROMPT_TEMPLATE.format(reasoning=analysis_full) + guardrail_block
    design_full = ""
    # ✅ analysis/thought 실시간 스트리밍
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
    ) + guardrail_block
    code_full = ""
    _code_chunk_count = 0
    async for chunk in stream_code_gen_reply(prompt_code):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            code_full += content
            _code_chunk_count += 1
            if _code_chunk_count % 30 == 0:
                yield format_sse({"type": "status", "content": f"⚙️ 코드 구현 중... ({len(code_full)}자)"})

    strategy_code = extract_python_code(code_full)
    strategy_code = salvage_valid_python(strategy_code)
    validation_error: Optional[str] = None
    if not strategy_code:
        validation_error = "수정된 코드 추출 실패"
    elif not _REQUIRED_SIGNAL_FN_RE.search(strategy_code):
        validation_error = "필수 함수 시그니처 누락: def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series"
    else:
        try:
            StrategyLoader.validate_code(strategy_code)
        except (SecurityError, SyntaxError) as e:
            validation_error = str(e)

    if validation_error:
        yield format_sse({"type": "analysis", "content": "\n코드가 중간에 끊겨 자동 복구를 시도합니다...\n"})
        recovered = await _recover_code_once(code_full, prompt_code, validation_error)
        recovered = salvage_valid_python(recovered)
        if recovered:
            strategy_code = recovered
            try:
                StrategyLoader.validate_code(strategy_code)
                validation_error = None
            except (SecurityError, SyntaxError) as e:
                validation_error = str(e)

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
