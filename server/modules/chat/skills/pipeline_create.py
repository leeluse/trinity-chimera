"""CREATE_STRATEGY 파이프라인 (추론 → 설계 → 코드 → 백테스트)"""
import logging
import os
import random
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import stream_chat_reply, stream_analysis_reply, stream_code_gen_reply
from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.evolution.constants import BANNED_INDICATORS, PERSONAS, CROSS_DOMAIN_SEEDS
from server.modules.chat.prompts import (
    REASONING_PROMPT_TEMPLATE,
    DESIGN_PROMPT_TEMPLATE,
    CODE_PROMPT_TEMPLATE,
    MINING_PROMPT_TEMPLATE,
)
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
        f"[원래 생성 지시 일부]\n{original_prompt[-2500:]}\n\n"
        f"[끊긴 출력 일부]\n{broken[-3500:]}\n"
    )
    repaired_full = ""
    async for chunk in stream_code_gen_reply(recovery_prompt):
        repaired_full += chunk
    return extract_python_code(repaired_full)


async def run_create_pipeline(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    history: List[Dict[str, Any]],
    db,
    session_memory: Dict[str, Any],
    is_mining: bool = False,
) -> AsyncGenerator[str, None]:
    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)
    chat_mutation_hint = str(memory_context.get("next_mutation") or "").strip()
    guardrail_block = build_memory_guardrail(memory_context)

    persona = seed = None
    if is_mining:
        persona = random.choice(PERSONAS)
        seed = random.choice(CROSS_DOMAIN_SEEDS)
        yield format_sse({"type": "stage", "stage": 1,
                          "label": f"💎 {persona['name']} 페르소나로 전략 채굴 중..."})
        prompt1 = MINING_PROMPT_TEMPLATE.format(
            message=message,
            persona_name=persona["name"],
            persona_worldview=persona["worldview"],
            persona_style=persona["style"],
            seed=seed,
            banned_indicators=", ".join(BANNED_INDICATORS),
        ) + guardrail_block
    else:
        reasoning_model = ((os.getenv("LITELLM_MODEL") or os.getenv("QUICK_MODEL") or "Brain Model").split("/")[-1]).strip()
        yield format_sse({"type": "stage", "stage": 1, "label": f"🧠 의도 파악 및 전략 분석 중... ({reasoning_model})"})
        prompt1 = REASONING_PROMPT_TEMPLATE.format(message=message) + guardrail_block

    reasoning_full = ""
    async for chunk in stream_chat_reply(user_message=prompt1, context=context,
                                         history=history,
                                         model=(os.getenv("LITELLM_MODEL") or None)):
        if chunk is None or chunk == "":
            continue
        reasoning_full += chunk
        yield format_sse({"type": "thought", "content": chunk})
    await db.save_chat_message(session_id, "assistant", reasoning_full, "thought")

    yield format_sse({"type": "stage", "stage": 2, 
                      "label": f"📋 전략 설계도 작성 중... ({((os.getenv('ANALYSIS_MODEL') or 'Expert Reasoner').split('/')[-1])})"})
    prompt2 = DESIGN_PROMPT_TEMPLATE.format(reasoning=reasoning_full) + guardrail_block
    design_full = ""
    async for chunk in stream_analysis_reply(prompt2):
        design_full += chunk
        yield format_sse({"type": "analysis", "content": chunk})
    try:
        await db.save_chat_message(session_id, "assistant", design_full, "text")
    except Exception as db_err:
        logger.error(f"Failed to save design message: {db_err}")

    yield format_sse({"type": "stage", "stage": 3, 
                      "label": f"⚙️ Python 전략 코드 구현 중... ({((os.getenv('CODE_GEN_MODEL') or 'DeepSeek Coder').split('/')[-1])})"})
    logger.info(f"[{session_id}] Starting Stage 3: Code Generation")
    
    prompt3 = CODE_PROMPT_TEMPLATE.format(design=design_full) + guardrail_block
    code_full = ""
    try:
        async for chunk in stream_code_gen_reply(prompt3):
            code_full += chunk
            # No yield for code chunks to avoid UI clutter, but we could add a progress signal
    except Exception as gen_err:
        logger.error(f"Stage 3 Code Gen Error: {gen_err}")
        yield format_sse({"type": "error", "content": f"코드 생성 중 오류가 발생했습니다: {gen_err}"})
        yield format_sse({"type": "done"})
        return

    strategy_code = extract_python_code(code_full)
    strategy_code = salvage_valid_python(strategy_code)
    validation_error: Optional[str] = None
    if not strategy_code:
        validation_error = "코드 추출 실패"
    else:
        try:
            StrategyLoader.validate_code(strategy_code)
        except (SecurityError, SyntaxError) as e:
            validation_error = str(e)

    if validation_error:
        yield format_sse({"type": "analysis", "content": "\n코드가 중간에 끊겨 자동 복구를 시도합니다...\n"})
        recovered = await _recover_code_once(code_full, prompt3, validation_error)
        recovered = salvage_valid_python(recovered)
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
        yield format_sse({"type": "error", "content": f"코드 검증 오류: {validation_error}"})
        yield format_sse({"type": "done"})
        return

    strategy_fingerprint = memory.compute_fingerprint(strategy_code)
    dedupe_window = int((constitution.get("memory") or {}).get("dedupe_window", 120))
    is_dup, dup_row = memory.is_duplicate(target_agent, strategy_fingerprint, dedupe_window=dedupe_window)
    if is_dup:
        memory.log_experiment(
            agent_id=target_agent, status="rejected_duplicate_chat", stage="precheck",
            reason=f"duplicate previous={dup_row.get('time') if dup_row else 'unknown'}",
            fingerprint=strategy_fingerprint, metrics={}, mutation_hint=chat_mutation_hint,
        )
        yield format_sse({"type": "analysis", "content": "\n⚠️ 이전 실험과 거의 동일한 코드입니다. 다른 접근으로 재시도해 주세요.\n"})
        yield format_sse({"type": "done"})
        return

    strategy_title = extract_strategy_title(code_full) or extract_strategy_title(design_full)
    strategy_data = {"title": strategy_title, "code": strategy_code, "params": {"agent_title": strategy_title}}
    yield format_sse({"type": "strategy", "data": strategy_data})
    await db.save_chat_message(session_id, "assistant", strategy_title, "strategy", strategy_data)

    yield format_sse({"type": "stage", "stage": 4, "label": "📈 백테스트 및 검증 중..."})
    async for ev in run_backtest(
        strategy_code, strategy_title, message, context, session_id, db, session_memory,
        memory=memory, constitution=constitution, target_agent=target_agent,
        chat_mutation_hint=chat_mutation_hint,
        is_mining_mode=is_mining, persona=persona, seed=seed,
    ):
        yield ev
    yield format_sse({"type": "done"})
