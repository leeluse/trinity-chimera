"""CODE_FROM_DESIGN 파이프라인 — 저장된 설계도 기반 Stage 3+4만 실행 (빠른 재생성)"""
import logging
import os
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import stream_code_gen_reply
from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.chat.prompts import CODE_PROMPT_TEMPLATE
from server.modules.chat.skills._base import (
    format_sse,
    extract_python_code,
    extract_strategy_title,
    salvage_valid_python,
    resolve_target_agent,
    build_memory_guardrail,
)
from server.modules.chat.skills.pipeline_backtest import run_backtest

logger = logging.getLogger(__name__)
_REQUIRED_SIGNAL_FN_RE = re.compile(
    r"def\s+generate_signal\s*\(\s*train_df\s*:\s*pd\.DataFrame\s*,\s*test_df\s*:\s*pd\.DataFrame\s*\)\s*->\s*pd\.Series",
    re.IGNORECASE,
)


async def _get_last_design(session_id: str, db) -> Optional[str]:
    """DB에서 마지막 design 메시지 복구."""
    try:
        def _query():
            return (
                db.client.table("chat_messages")
                .select("content")
                .eq("session_id", session_id)
                .eq("type", "design")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        import asyncio
        res = await asyncio.to_thread(_query)
        rows = res.data or []
        return rows[0]["content"] if rows else None
    except Exception:
        return None


async def run_code_only_pipeline(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]],
    db,
    session_memory: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    # 1. 설계도 조회 (세션 메모리 → DB 순)
    design = (session_memory.get(session_id) or {}).get("design")
    if not design:
        design = await _get_last_design(session_id, db)
    if not design:
        yield format_sse({"type": "analysis", "content": (
            "⚠️ 저장된 설계도가 없습니다. 먼저 전략 생성/수정 파이프라인을 실행해 주세요."
        )})
        yield format_sse({"type": "done"})
        return

    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)
    chat_mutation_hint = str(memory_context.get("next_mutation") or "").strip()
    guardrail_block = build_memory_guardrail(memory_context)

    code_model = ((os.getenv("CODE_GEN_MODEL") or "deepseek").split("/")[-1]).strip()
    yield format_sse({"type": "stage", "stage": 3,
                      "label": f"⚡ 설계도 기반 코드 생성 중... ({code_model})"})

    prompt3 = CODE_PROMPT_TEMPLATE.format(design=design) + guardrail_block
    code_full = ""
    _code_chunk_count = 0
    try:
        async for chunk in stream_code_gen_reply(prompt3):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                yield format_sse({"type": "thought", "content": thought})
            if content:
                code_full += content
                _code_chunk_count += 1
                if _code_chunk_count % 30 == 0:
                    yield format_sse({"type": "status", "content": f"⚡ 코드 생성 중... ({len(code_full)}자)"})
    except Exception as gen_err:
        logger.error(f"CODE_FROM_DESIGN codegen error: {gen_err}")
        yield format_sse({"type": "error", "content": f"코드 생성 중 오류: {gen_err}"})
        yield format_sse({"type": "done"})
        return

    strategy_code = extract_python_code(code_full)
    strategy_code = salvage_valid_python(strategy_code)
    validation_error: Optional[str] = None

    if not strategy_code:
        validation_error = "코드 추출 실패"
    elif not _REQUIRED_SIGNAL_FN_RE.search(strategy_code):
        validation_error = "필수 함수 시그니처 누락: def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series"
    else:
        try:
            StrategyLoader.validate_code(strategy_code)
        except (SecurityError, SyntaxError) as e:
            validation_error = str(e)

    # 1회 복구 시도
    if validation_error:
        yield format_sse({"type": "analysis", "content": "\n코드가 중간에 끊겨 자동 복구를 시도합니다...\n"})
        recovery_prompt = (
            "아래 출력은 중간에 끊겼거나 형식이 깨진 전략 코드다.\n"
            "실행 가능한 완전한 Python 코드만 출력하라.\n"
            "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series\n"
            "코드블록 1개 또는 순수 코드만 출력.\n\n"
            f"[실패 원인]\n{validation_error}\n\n"
            f"[원래 설계도]\n{design[-2000:]}\n\n"
            f"[끊긴 출력]\n{code_full[-3000:]}\n"
        )
        repaired = ""
        async for chunk in stream_code_gen_reply(recovery_prompt):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                yield format_sse({"type": "thought", "content": thought})
            if content:
                repaired += content
        recovered = salvage_valid_python(extract_python_code(repaired))
        if recovered:
            strategy_code = recovered
            try:
                StrategyLoader.validate_code(strategy_code)
                validation_error = None
            except (SecurityError, SyntaxError) as e:
                validation_error = str(e)

    if not strategy_code:
        yield format_sse({"type": "error", "content": "코드 추출 실패: 출력이 중간에 끊겼습니다."})
        yield format_sse({"type": "done"})
        return
    if validation_error:
        yield format_sse({"type": "error", "content": f"코드 검증 실패: {validation_error}"})
        yield format_sse({"type": "done"})
        return

    strategy_title = extract_strategy_title(code_full) or "설계도 기반 전략"
    strategy_data = {"title": strategy_title, "code": strategy_code, "params": {"agent_title": strategy_title}}
    yield format_sse({"type": "strategy", "data": strategy_data})
    await db.save_chat_message(session_id, "assistant", strategy_title, "strategy", strategy_data)

    yield format_sse({"type": "stage", "stage": 4, "label": "📈 백테스트 및 검증 중..."})
    async for ev in run_backtest(
        strategy_code, strategy_title, message, context, session_id, db, session_memory,
        memory=memory, constitution=constitution, target_agent=target_agent,
        chat_mutation_hint=chat_mutation_hint,
    ):
        yield ev
    yield format_sse({"type": "done"})
