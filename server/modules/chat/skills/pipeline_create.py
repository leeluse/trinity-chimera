"""CREATE_STRATEGY 파이프라인 (설계 → 코드 → 백테스트)"""
import logging
import os
import random
import re
import time
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
    sanitize_generated_code,
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
_CODE_GEN_ERROR_RE = re.compile(r"\[코드 생성 오류:\s*(.+?)\]", re.IGNORECASE | re.DOTALL)


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
    recovery_prompt = (
        "아래 출력은 중간에 끊겼거나 형식이 깨진 전략 코드다.\n"
        "이전 출력 조각을 이어 쓰지 말고, 실행 가능한 완전한 Python 코드 전체를 처음부터 다시 출력하라.\n"
        "필수 함수 시그니처:\n"
        "def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series\n"
        "설명문/마크다운 문장 금지. 백틱(```) 절대 사용 금지. 순수 코드만 출력.\n"
        "코드는 간결하게 작성하고, 불필요한 클래스/긴 주석/장문 설명을 넣지 마라.\n\n"
        f"[실패 원인]\n{reason}\n\n"
        f"[원래 생성 지시]\n{original_prompt[-5000:]}\n\n"
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
        return "코드 추출 실패"
    if not _REQUIRED_SIGNAL_FN_RE.search(strategy_code):
        return "필수 함수 시그니처 누락: def generate_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series"
    try:
        StrategyLoader.validate_code(strategy_code)
    except (SecurityError, SyntaxError) as e:
        return str(e)
    return None


async def run_create_pipeline(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    _history,
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
    # context에 design이 직접 있으면 최우선 사용 (설계도 카드 버튼 경로)
    design_from_context = (context or {}).get("design", "")

    logger.info(f"[{session_id}] pipeline start: code_gen_mode={code_gen_mode!r}, design_from_context={bool(design_from_context)}, session_keys={list(session_memory.get(session_id, {}).keys())}")

    if code_gen_mode:
        design_full = design_from_context or session_memory.get(session_id, {}).get("design", "")
        logger.info(f"[{session_id}] cached design length={len(design_full)}")
        if not design_full:
            logger.warning(f"[{session_id}] no cached design found → falling back to Stage 1")
            code_gen_mode = None
        else:
            logger.info(f"[{session_id}] Skipping Stage 1 — using cached design, mode={code_gen_mode}")

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

        # 설계 완료 → 자동으로 Stage 2 진입 (버튼 없이)
        code_gen_mode = "relaxed"
        logger.info(f"[{session_id}] Stage 1 complete, auto-proceeding to Stage 2 (relaxed)")

    _mode_max_tokens = {"loose": 1500, "relaxed": 2000, "strict": 2500}.get(code_gen_mode or "", 2000)
    yield format_sse({"type": "stage", "stage": 2, "label": f"⚙️ Python 전략 코드 구현 중... ({code_model})"})
    logger.info(f"[{session_id}] Starting Stage 2: Code Generation (mode={code_gen_mode}, max_tokens={_mode_max_tokens})")

    prompt3 = CODE_PROMPT_TEMPLATE.format(design=design_full) + guardrail_block
    code_full = ""
    _thought_buf = ""  # thinking 모델이 content 없이 reasoning_content만 내보낼 때 대비
    _last_status_t = time.monotonic()
    _STATUS_INTERVAL = 3.0
    try:
        async for chunk in stream_code_gen_reply(prompt3, max_tokens=_mode_max_tokens):
            thought = chunk.get("thought")
            content = chunk.get("content")
            if thought:
                _thought_buf += thought
                yield format_sse({"type": "thought", "content": thought})
            if content:
                code_full += content
                yield format_sse({"type": "analysis", "content": content})
                now = time.monotonic()
                if now - _last_status_t >= _STATUS_INTERVAL:
                    yield format_sse({"type": "status", "content": f"⚙️ 코드 생성 중... ({len(code_full):,}자)"})
                    _last_status_t = now
    except Exception as gen_err:
        logger.error(f"Stage 2 Code Gen Error: {gen_err}")
        yield format_sse({"type": "error", "content": f"코드 생성 중 오류가 발생했습니다: {gen_err}"})
        yield format_sse({"type": "done"})
        return

    # Thinking 전용 모델이 reasoning_content에만 코드를 출력했을 경우 대체 소스로 사용
    if not code_full.strip() and _thought_buf.strip():
        logger.warning(f"[{session_id}] code_full empty, falling back to thought buffer ({len(_thought_buf)} chars)")
        code_full = _thought_buf

    codegen_error = _CODE_GEN_ERROR_RE.search(code_full or "")
    if codegen_error:
        err_text = codegen_error.group(1).strip()
        yield format_sse({"type": "error", "content": f"코드 생성 실패: {err_text}"})
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
            recovered = await _recover_code_once(code_full, prompt3, validation_error)
            recovered = salvage_valid_python(sanitize_generated_code(recovered))
            if recovered:
                strategy_code = recovered
                validation_error = _validate_strategy_code(strategy_code)
            if not validation_error:
                break

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

    # ── 백테스트 실패 시 자동 1회 개선 재시도 ──────────────────────────
    _sm = session_memory.get(session_id, {})
    _last_failure = _sm.get("last_failure", "")
    _last_feedback = _sm.get("last_feedback", "")

    if _last_failure:
        yield format_sse({"type": "analysis", "content": (
            f"\n🔄 **자동 개선 재시도** — 실패 원인 피드백을 반영해 코드를 재생성합니다.\n"
            f"> {_last_feedback}\n"
        )})
        yield format_sse({"type": "stage", "stage": 2, "label": f"⚙️ 개선 코드 재생성 중... ({code_model})"})

        _retry_hint = (
            f"\n\n[자동 재시도 — 이전 실패 원인]\n{_last_feedback}\n"
            "위 문제를 반드시 해결하라:\n"
            "- zero_trades 면 진입 조건을 대폭 완화하고 AND 연산자를 줄여라\n"
            "- 승률 미달 이면 청산 로직과 손절선을 개선하라\n"
            "- profit_factor 미달 이면 손실 거래의 평균 손실 크기를 줄여라\n"
            "- 거래 수 미달 이면 시그널 발생 빈도를 높여라\n"
        )
        prompt_retry = CODE_PROMPT_TEMPLATE.format(design=design_full) + guardrail_block + _retry_hint
        code_retry = ""
        _lst = time.monotonic()
        try:
            async for chunk in stream_code_gen_reply(prompt_retry, max_tokens=_mode_max_tokens):
                t = chunk.get("thought")
                c = chunk.get("content")
                if t:
                    yield format_sse({"type": "thought", "content": t})
                if c:
                    code_retry += c
                    yield format_sse({"type": "analysis", "content": c})
                    if time.monotonic() - _lst >= _STATUS_INTERVAL:
                        yield format_sse({"type": "status", "content": f"⚙️ 개선 재시도 중... ({len(code_retry):,}자)"})
                        _lst = time.monotonic()
        except Exception as _re:
            logger.error(f"[{session_id}] auto-retry codegen failed: {_re}")
            yield format_sse({"type": "done"})
            return

        strategy_code_r = salvage_valid_python(sanitize_generated_code(extract_python_code(code_retry)))
        if not _validate_strategy_code(strategy_code_r):
            title_r = extract_strategy_title(code_retry) or strategy_title
            yield format_sse({"type": "strategy", "data": {"title": title_r, "code": strategy_code_r, "params": {"agent_title": title_r}}})
            await db.save_chat_message(session_id, "assistant", title_r, "strategy", {"title": title_r, "code": strategy_code_r})
            yield format_sse({"type": "stage", "stage": 3, "label": "📈 개선 전략 백테스트 중..."})
            async for ev in run_backtest(
                strategy_code_r, title_r, message, context, session_id, db, session_memory,
                memory=memory, constitution=constitution, target_agent=target_agent,
                chat_mutation_hint=chat_mutation_hint,
                is_mining_mode=is_mining, persona=persona, seed=seed,
            ):
                yield ev
        else:
            yield format_sse({"type": "analysis", "content": "\n⚠️ 개선 재시도 코드 검증 실패 — 첫 번째 결과를 참고하세요.\n"})

    yield format_sse({"type": "done"})
