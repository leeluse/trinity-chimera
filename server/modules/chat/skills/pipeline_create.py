"""CREATE_STRATEGY 파이프라인 (설계 → 코드 → 백테스트)"""
import logging
import os
import random
import re
from typing import Any, AsyncGenerator, Dict, Optional

from server.shared.llm.client import stream_analysis_reply, stream_code_gen_reply
from server.shared.market.strategy_loader import StrategyLoader, SecurityError
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.evolution.constants import BANNED_INDICATORS, PERSONAS, CROSS_DOMAIN_SEEDS
from server.modules.chat.prompts import (
    DESIGN_PROMPT_TEMPLATE,
    CODE_PROMPT_TEMPLATE,
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
_REQUIRED_SIGNAL_FN_RE = re.compile(
    r"def\s+generate_signal\s*\(\s*train_df\s*:\s*pd\.DataFrame\s*,\s*test_df\s*:\s*pd\.DataFrame\s*\)\s*->\s*pd\.Series",
    re.IGNORECASE,
)


def _build_direct_design_brief(
    message: str,
    is_mining: bool,
    persona: Optional[Dict[str, Any]],
    seed: Optional[str],
) -> str:
    lines = [
        f'사용자 요청: "{(message or "").strip()}"',
        "",
        "[공통 설계 제약]",
        "- 사전 추론 단계 없이 바로 YAML 설계를 작성한다.",
        "- train_df 기반 적응형 임계값을 최소 1개 이상 포함한다.",
        "- 시장 레짐 필터를 포함하고, 과도한 AND 적층(3개 초과)을 피한다.",
        "- 롱/숏 시그널은 구조적으로 일관되게 대칭 설계한다.",
    ]
    if is_mining and persona:
        lines.extend([
            "",
            "[에볼루션 채굴 컨텍스트]",
            f"- 페르소나: {persona.get('name', '')}",
            f"- 세계관: {persona.get('worldview', '')}",
            f"- 스타일: {persona.get('style', '')}",
            f"- 크로스 도메인 씨드: {seed or ''}",
            f"- 금지 지표: {', '.join(BANNED_INDICATORS)}",
            "- 목표: 독창성이 있으면서도 전체 구간 신호 빈도(>=50건)가 가능한 구조",
        ])
    return "\n".join(lines).strip()


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
    history,
    db,
    session_memory: Dict[str, Any],
    is_mining: bool = False,
    code_gen_mode: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    memory = EvolutionWikiMemory()
    constitution = memory.load_constitution()
    target_agent = resolve_target_agent(context, message)
    memory_context = memory.build_prompt_context(target_agent, constitution)
    chat_mutation_hint = str(memory_context.get("next_mutation") or "").strip()
    guardrail_block = build_memory_guardrail(memory_context)

    analysis_model = ((os.getenv("ANALYSIS_MODEL") or os.getenv("LITELLM_MODEL") or "Expert Reasoner").split("/")[-1]).strip()
    code_model = ((os.getenv("CODE_GEN_MODEL") or os.getenv("LITELLM_MODEL") or "DeepSeek Coder").split("/")[-1]).strip()

    persona = seed = None
    if is_mining:
        persona = random.choice(PERSONAS)
        seed = random.choice(CROSS_DOMAIN_SEEDS)
        stage1_label = f"💎 {persona['name']} 기반 전략 설계도 작성 중... ({analysis_model})"
    else:
        stage1_label = f"📋 전략 설계도 작성 중... ({analysis_model})"

    # ──────────────────────────────────────────────────────────────
    # code_gen_mode가 이미 있으면 Stage 1 생략 → 캐시된 설계로 바로 Stage 2
    # ──────────────────────────────────────────────────────────────
    if code_gen_mode:
        design_full = session_memory.get(session_id, {}).get("design", "")
        if not design_full:
            # 설계가 없으면 어쩔 수 없이 Stage 1부터
            code_gen_mode = None
        else:
            logger.info(f"[{session_id}] Skipping Stage 1 — using cached design, mode={code_gen_mode}")
            yield format_sse({"type": "stage", "stage": 2, "label": f"⚙️ Python 전략 코드 구현 중... ({code_model})"})

    if not code_gen_mode:
        # Stage 1: 설계 생성
        yield format_sse({"type": "stage", "stage": 1, "label": stage1_label})
        yield format_sse({"type": "thought", "content": "사전 추론 단계는 생략하고, 요청을 바로 설계도로 변환 중입니다..."})

        design_brief = _build_direct_design_brief(message, is_mining, persona, seed)
        prompt2 = DESIGN_PROMPT_TEMPLATE.format(reasoning=design_brief) + guardrail_block
        design_full = ""
        async for chunk in stream_analysis_reply(prompt2):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                yield format_sse({"type": "thought", "content": thought})
            if content:
                design_full += content
                yield format_sse({"type": "analysis", "content": content})
        session_memory.setdefault(session_id, {})["design"] = design_full
        yield format_sse({"type": "design", "content": design_full})
        try:
            await db.save_chat_message(session_id, "assistant", design_full, "design")
        except Exception as db_err:
            logger.error(f"Failed to save design message: {db_err}")

        # 모드 선택 대기
        yield format_sse({"type": "choice", "choices": [
            {"value": "loose",   "label": "느슨하게 (코드만 바로 짜기)", "description": "검증 기준 무시"},
            {"value": "relaxed", "label": "현실적 기준 (권장)",          "description": "승률 35%, PF 1.05 등"},
            {"value": "strict",  "label": "엄격한 기준",                 "description": "승률 45%, PF 1.20 등"},
        ]})
        logger.info(f"[{session_id}] Waiting for code generation mode choice")
        yield format_sse({"type": "done"})
        return

    yield format_sse({"type": "stage", "stage": 2, "label": f"⚙️ Python 전략 코드 구현 중... ({code_model})"})
    logger.info(f"[{session_id}] Starting Stage 2: Code Generation (mode={code_gen_mode})")
    
    prompt3 = CODE_PROMPT_TEMPLATE.format(design=design_full) + guardrail_block
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
                # 코드 청크를 위해 status 한 개씩 전송 (keepalive)
                if _code_chunk_count % 30 == 0:
                    yield format_sse({"type": "status", "content": f"⚙️ 코드 생성 중... ({len(code_full)}자)"})
    except Exception as gen_err:
        logger.error(f"Stage 2 Code Gen Error: {gen_err}")
        yield format_sse({"type": "error", "content": f"코드 생성 중 오류가 발생했습니다: {gen_err}"})
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

    yield format_sse({"type": "stage", "stage": 3, "label": "📈 백테스트 및 검증 중..."})
    async for ev in run_backtest(
        strategy_code, strategy_title, message, context, session_id, db, session_memory,
        memory=memory, constitution=constitution, target_agent=target_agent,
        chat_mutation_hint=chat_mutation_hint,
        is_mining_mode=is_mining, persona=persona, seed=seed,
    ):
        yield ev
    yield format_sse({"type": "done"})
