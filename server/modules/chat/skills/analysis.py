"""분석형 스킬 (확인 없이 즉시 실행): explain / risk / code_review / suggest_next / code_from_design"""
import logging
from typing import Any, AsyncGenerator, Dict, List

from server.shared.llm.client import stream_analysis_reply
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.chat.prompts import (
    EXPLAIN_STRATEGY_TEMPLATE,
    RISK_ANALYSIS_TEMPLATE,
    CODE_REVIEW_TEMPLATE,
    SUGGEST_NEXT_TEMPLATE,
)
from server.modules.chat.skills._base import format_sse, get_last_strategy, resolve_target_agent
from server.modules.chat.skills.pipeline_code_only import run_code_only_pipeline

logger = logging.getLogger(__name__)

_DISPATCH = {}


def skill(key: str):
    def decorator(fn):
        _DISPATCH[key] = fn
        return fn
    return decorator


async def dispatch(
    skill_key: str,
    message: str,
    session_id: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]],
    db,
    session_memory: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    fn = _DISPATCH.get(skill_key)
    if fn:
        async for ev in fn(message, session_id, context, history, db, session_memory):
            yield ev
    else:
        logger.warning(f"[analysis] 알 수 없는 스킬: {skill_key!r}")
        yield format_sse({"type": "done"})


@skill("EXPLAIN_STRATEGY")
async def run_explain_strategy(
    message, session_id, context, history, db, session_memory
) -> AsyncGenerator[str, None]:
    prev = await get_last_strategy(session_id, db, session_memory)
    if not prev:
        yield format_sse({"type": "analysis", "content": "설명할 전략이 없어요. 먼저 전략을 생성해 주세요."})
        yield format_sse({"type": "done"})
        return

    yield format_sse({"type": "stage", "stage": 1, "label": f"📖 '{prev['title']}' 분석 중..."})
    prompt = EXPLAIN_STRATEGY_TEMPLATE.format(
        code=prev["code"],
        metrics=str(prev.get("metrics", {})),
    )
    full = ""
    async for chunk in stream_analysis_reply(prompt):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            full += content
            yield format_sse({"type": "analysis", "content": content})
    await db.save_chat_message(session_id, "assistant", full, "text")
    yield format_sse({"type": "done"})


@skill("RISK_ANALYSIS")
async def run_risk_analysis(
    message, session_id, context, history, db, session_memory
) -> AsyncGenerator[str, None]:
    prev = await get_last_strategy(session_id, db, session_memory)
    if not prev:
        yield format_sse({"type": "analysis", "content": "분석할 전략이 없어요."})
        yield format_sse({"type": "done"})
        return

    yield format_sse({"type": "stage", "stage": 1, "label": "🔬 리스크 시나리오 분석 중..."})
    code = prev["code"]
    prompt = RISK_ANALYSIS_TEMPLATE.format(
        title=prev.get("title", "전략"),
        metrics=str(prev.get("metrics", {})),
        code_snippet=code[:800] + ("..." if len(code) > 800 else ""),
    )
    full = ""
    async for chunk in stream_analysis_reply(prompt):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            full += content
            yield format_sse({"type": "analysis", "content": content})
    await db.save_chat_message(session_id, "assistant", full, "text")
    yield format_sse({"type": "done"})


@skill("CODE_REVIEW")
async def run_code_review(
    message, session_id, context, history, db, session_memory
) -> AsyncGenerator[str, None]:
    prev = await get_last_strategy(session_id, db, session_memory)
    if not prev:
        yield format_sse({"type": "analysis", "content": "리뷰할 코드가 없어요."})
        yield format_sse({"type": "done"})
        return

    yield format_sse({"type": "stage", "stage": 1, "label": f"🔍 '{prev['title']}' 코드 리뷰 중..."})
    prompt = CODE_REVIEW_TEMPLATE.format(
        code=prev["code"],
        metrics=str(prev.get("metrics", {})),
    )
    full = ""
    async for chunk in stream_analysis_reply(prompt):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            full += content
            yield format_sse({"type": "analysis", "content": content})
    await db.save_chat_message(session_id, "assistant", full, "text")
    yield format_sse({"type": "done"})


@skill("CODE_FROM_DESIGN")
async def run_code_from_design(
    message, session_id, context, history, db, session_memory
) -> AsyncGenerator[str, None]:
    async for ev in run_code_only_pipeline(message, session_id, context, history, db, session_memory):
        yield ev


@skill("SUGGEST_NEXT")
async def run_suggest_next(
    message, session_id, context, history, db, session_memory
) -> AsyncGenerator[str, None]:
    yield format_sse({"type": "stage", "stage": 1, "label": "🧭 다음 탐색 방향 분석 중..."})

    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)

    prev = await get_last_strategy(session_id, db, session_memory)
    prompt = SUGGEST_NEXT_TEMPLATE.format(
        memory_context=str(memory_context),
        last_title=prev.get("title", "없음") if prev else "없음",
        last_metrics=str(prev.get("metrics", {})) if prev else "없음",
    )
    full = ""
    async for chunk in stream_analysis_reply(prompt):
        thought = chunk.get("thought")
        content = chunk.get("content")
        if thought:
            yield format_sse({"type": "thought", "content": thought})
        if content:
            full += content
            yield format_sse({"type": "analysis", "content": content})
    await db.save_chat_message(session_id, "assistant", full, "text")
    yield format_sse({"type": "done"})
