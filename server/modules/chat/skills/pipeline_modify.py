"""MODIFY_STRATEGY 파이프라인 (분석 → 설계 → 수정 코드 → 백테스트 + 비교)"""
import logging
import os
from typing import Any, AsyncGenerator, Dict, List

from server.shared.llm.client import stream_chat_reply, stream_analysis_reply, stream_code_gen_reply
from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.chat.prompts import (
    SYSTEM_PROMPT,
    DESIGN_PROMPT_TEMPLATE,
    MODIFY_ANALYZE_TEMPLATE,
    MODIFY_CODE_TEMPLATE,
)
from server.modules.chat.skills._base import (
    format_sse,
    extract_python_code,
    extract_strategy_title,
    resolve_target_agent,
    build_memory_guardrail,
    get_last_strategy,
)
from server.modules.chat.skills.pipeline_backtest import run_backtest

logger = logging.getLogger(__name__)


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

    quick_model = ((os.getenv("QUICK_MODEL") or os.getenv("LITELLM_MODEL") or "Quick Model").split("/")[-1]).strip()
    analysis_model = ((os.getenv("ANALYSIS_MODEL") or os.getenv("LITELLM_MODEL") or "Analysis Model").split("/")[-1]).strip()
    code_model = ((os.getenv("CODE_GEN_MODEL") or os.getenv("LITELLM_MODEL") or "Code Model").split("/")[-1]).strip()

    yield format_sse({"type": "stage", "stage": 1,
                      "label": f"🔍 '{prev_title}' 분석 및 약점 탐색 중... ({quick_model})"})
    prompt_analyze = MODIFY_ANALYZE_TEMPLATE.format(
        prev_code=prev_code,
        prev_metrics=str(prev_metrics),
        user_request=message,
    )
    analysis_full = ""
    async for chunk in stream_chat_reply(user_message=prompt_analyze, context=context,
                                          history=history, custom_system_prompt=SYSTEM_PROMPT,
                                          model=(os.getenv("QUICK_MODEL") or None)):
        if chunk is None or chunk == "":
            continue
        analysis_full += chunk
        yield format_sse({"type": "thought", "content": chunk})
    await db.save_chat_message(session_id, "assistant", analysis_full, "thought")

    yield format_sse({"type": "stage", "stage": 2, "label": f"📋 수정 설계도 작성 중... ({analysis_model})"})
    prompt_design = DESIGN_PROMPT_TEMPLATE.format(reasoning=analysis_full) + guardrail_block
    design_full = ""
    async for chunk in stream_analysis_reply(prompt_design):
        design_full += chunk
        yield format_sse({"type": "analysis", "content": chunk})
    await db.save_chat_message(session_id, "assistant", design_full, "text")

    yield format_sse({"type": "stage", "stage": 3, "label": f"⚙️ 수정된 코드 구현 중... ({code_model})"})
    prompt_code = MODIFY_CODE_TEMPLATE.format(
        analysis=analysis_full,
        design=design_full,
        prev_code=prev_code,
    ) + guardrail_block
    code_full = ""
    async for chunk in stream_code_gen_reply(prompt_code):
        code_full += chunk

    strategy_code = extract_python_code(code_full)
    if not strategy_code:
        yield format_sse({"type": "error", "content": "수정된 코드 추출 실패."})
        yield format_sse({"type": "done"})
        return

    try:
        StrategyLoader.validate_code(strategy_code)
    except (SecurityError, SyntaxError) as e:
        yield format_sse({"type": "error", "content": f"수정 코드 검증 실패: {e}"})
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
