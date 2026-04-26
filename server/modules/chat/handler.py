"""채팅 파이프라인 라우터 — INVOKE 감지 + 확인 흐름만 담당"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import generate_chat_reply, stream_chat_reply
from server.shared.db.supabase import SupabaseManager
from server.modules.engine.runtime import invalidate_strategy_cache
from server.modules.chat.prompts import SYSTEM_PROMPT, CLASSIFICATION_SYSTEM, CLASSIFICATION_MESSAGE
from server.modules.chat.skills import (
    dispatch_analysis,
    run_create_pipeline,
    run_modify_pipeline,
    run_backtest,
    run_optimize_pipeline,
    run_walk_forward_pipeline,
    run_pnl_analysis,
    get_last_strategy,
    format_sse,
    NO_CONFIRM_SKILLS,
)
from server.modules.chat.skills._base import extract_strategy_title

logger = logging.getLogger(__name__)

# ── 인텐트 상수 ───────────────────────────────────────────────────
INTENT_GENERAL   = "GENERAL_CHAT"
INTENT_CREATE    = "STRATEGY_CREATE"
INTENT_MODIFY    = "STRATEGY_MODIFY"
INTENT_EVOLVE    = "STRATEGY_EVOLVE"
INTENT_BACKTEST  = "STRATEGY_BACKTEST"
INTENT_OPTIMIZE  = "PARAM_OPTIMIZE"

_INTENT_LABEL = {
    INTENT_CREATE:   "전략 생성 파이프라인",
    INTENT_MODIFY:   "전략 수정 파이프라인",
    INTENT_EVOLVE:   "에볼루션 채굴 파이프라인",
    INTENT_BACKTEST: "백테스트",
    INTENT_OPTIMIZE: "파라미터 최적화/서치",
    "STRATEGY_WFO":  "워크포워드(롤링) 분석",
}

# ── INVOKE 마커 매핑 ──────────────────────────────────────────────
_INVOKE_MAP = {
    "CREATE_STRATEGY":  INTENT_CREATE,
    "MODIFY_STRATEGY":  INTENT_MODIFY,
    "RUN_BACKTEST":     INTENT_BACKTEST,
    "RUN_EVOLUTION":    INTENT_EVOLVE,
    "PARAM_SEARCH":     INTENT_OPTIMIZE,
    "WALK_FORWARD":     "STRATEGY_WFO",
    "PNL_ANALYSIS":     "PNL_ANALYSIS",
}
_INVOKE_RE = re.compile(r'\[INVOKE:(\w+)\]')
_THINK_BLOCK_RE = re.compile(r"<(thought|think|think_process|reasoning)>[\s\S]*?</\1>", re.IGNORECASE)
_THINK_TAG_RE = re.compile(r"</?(thought|think|think_process|reasoning)[^>]*>", re.IGNORECASE)
_CONTINUATION_META_RE = re.compile(
    r"(?:사용자가\s*직전\s*답변|직전\s*답변이\s*중간에\s*끊겼|문맥상|중복\s*없이\s*자연스럽게\s*이어서|"
    r"\[직전\s*답변\]|이것이中途)",
    re.IGNORECASE,
)

# 빠른 규칙 기반 분류 (LLM 없이 ~95% 커버)
_KEYWORD_INTENT_MAP = {
    "PARAM_SEARCH": [
        r"파라미터\s*(서치|최적화|튜닝|찾아|탐색)",
        r"(그리드|랜덤|베이지안)\s*(서치|검색|최적화)",
        r"(최적|좋은|나은)\s*파라미터",
        r"(하이퍼파라미터|hyperparameter)",
    ],
    "WALK_FORWARD": [
        r"(워크포워드|워크\s*포워드|walk\s*forward|wfo)",
        r"(롤링|전진)\s*(테스트|검사|분석)",
    ],
    "PNL_ANALYSIS": [
        r"(pnl|수익|손익)\s*(분석|분해|상세|리포트)",
        r"(롱|숏|포지션별).{0,5}(수익|손익|비교)",
    ],
    "CREATE_STRATEGY": [
        r"(전략|트레이딩|시스템)\s*(짜|만들|생성|구축|설계|개발|작성|코딩|구현)",
        r"(매매|거래)\s*(로직|지표|조건)\s*(만들|짜)",
        r"(코딩|구현|개발|작성)\s*(해\s*줘|해줘|해봐|해보자|부탁|좀)",
        r"(전략|트레이딩).{0,20}(짜|만들|코딩|구현|작성)",
    ],
    "MODIFY_STRATEGY": [r"(수정|개선|변경|고쳐|보완|강화)", r"(이전|기존|아까)\s*(거|전략)\s*(수정|개선|고쳐)"],
    "RUN_BACKTEST": [r"(돌려봐|검증|테스트|백테스트|실행해|결과)", r"(성과|수익|손실|성능)\s*(보|봐|확인)"],
    "RUN_EVOLUTION": [r"(채굴|에볼루션|자동|자율|진화|마이닝)", r"(최적|탐색|최상)\s*(후보|전략)"],
    "EXPLAIN_STRATEGY": [r"(설명|어떻게|작동|로직|왜|이유|원리)", r"(이\s*(전략|코드)|코드)\s*(어떻게|설명)"],
    "RISK_ANALYSIS": [r"(리스크|위험|손실|위험도|MDD|낙폭)", r"(언제|언제쯤)\s*(망|실패|손실)"],
    "CODE_REVIEW": [
        r"(버그|오버피팅|리뷰|검토)\s*(있|해|봐|줘|있어|있냐|있나)?",
        r"(코드|전략).{0,6}(뭐가|어디가|어떤\s*점).{0,6}(문제|이상|잘못|나쁜|별로)",
        r"(문제|이상한|잘못된|나쁜)\s*(점|부분|코드|거|게).{0,6}(있|뭐|어디|알|봐|찾)",
        r"(코드|전략)\s*(봐줘|점검|진단|확인해|체크)",
        r"(과최적화|오버피팅|룩어헤드|미래참조).{0,6}(있|됐|됩|체크|확인)",
        r"현재\s*(코드|전략).{0,10}(문제|이상|잘못|별로|나쁜|점검|진단)",
    ],
    "SUGGEST_NEXT": [r"(다음|뭘|뭘\s*할|아이디어|방향|시도)", r"(어떻게|뭐)\s*(해볼|시도|할)"],
    "CODE_FROM_DESIGN": [
        r"(코드만|코드\s*만|설계도)",
        r"(설계|디자인|블루프린트)\s*(기반|이용)",
        r"다시\s*(코드|생성|만들)",   # "재" 단독 제거 — "현재"의 재와 충돌
        r"재코딩|재생성",             # "재" + 코딩/생성이 붙어있을 때만
    ],
}

def _classify_by_keywords(text: str) -> Optional[str]:
    """규칙 기반 빠른 분류 (LLM 없이). 일치하면 INVOKE_KEY 반환."""
    t = text.lower().strip()
    for invoke_key, patterns in _KEYWORD_INTENT_MAP.items():
        for pattern in patterns:
            if re.search(pattern, t):
                return invoke_key
    return None


class ChatHandler:
    """대화형 전략 파이프라인 라우터"""

    _pending_pipeline_confirmations: Dict[str, Dict[str, Any]] = {}
    _pending_stage_confirmations: Dict[str, Dict[str, Any]] = {}
    _live_pipeline_streams: Dict[str, Dict[str, Any]] = {}
    _session_last_strategy: Dict[str, Any] = {}

    @staticmethod
    def _preview_text(text: str, limit: int = 80) -> str:
        if not text:
            return ""
        compact = " ".join(str(text).split())
        return compact if len(compact) <= limit else (compact[: limit - 1] + "…")

    @staticmethod
    def _short_model_name(model_name: str) -> str:
        text = str(model_name or "").strip()
        if not text:
            return ""
        return text.split("/")[-1]

    @staticmethod
    def _env_enabled(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _pipeline_model_stack(cls) -> Dict[str, str]:
        default_model = os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or ""
        return {
            "analysis": cls._short_model_name(os.getenv("ANALYSIS_MODEL") or default_model),
            "code": cls._short_model_name(os.getenv("CODE_GEN_MODEL") or default_model),
            "quick": cls._short_model_name(os.getenv("QUICK_MODEL") or default_model),
        }

    @classmethod
    def _should_require_pipeline_confirm(cls, intent: str) -> bool:
        if not cls._env_enabled("CHAT_PIPELINE_CONFIRM_ENABLED", True):
            return False
        if intent == INTENT_MODIFY and cls._env_enabled("CHAT_MODIFY_AUTO_RUN", True):
            return False
        if intent == INTENT_OPTIMIZE:
            return False
        return True

    @classmethod
    def _should_stage_review(cls, intent: str, stage_num: int) -> bool:
        if stage_num >= 5:
            return False
        if not cls._env_enabled("CHAT_STAGE_REVIEW_ENABLED", True):
            return False
        if intent == INTENT_MODIFY and not cls._env_enabled("CHAT_MODIFY_STAGE_REVIEW", False):
            return False
        return True

    @staticmethod
    def _sanitize_chat_text(text: str) -> str:
        clean = _INVOKE_RE.sub("", text or "")
        clean = _THINK_BLOCK_RE.sub("", clean)
        clean = _THINK_TAG_RE.sub("", clean)
        return clean.strip()

    @staticmethod
    def _looks_structured_response(text: str) -> bool:
        body = (text or "").strip()
        if not body:
            return False
        if "```" in body:
            return True
        if body.count("\n") >= 6:
            return True
        if re.search(r"(?m)^\s*[a-zA-Z_][\w\-]*\s*:\s*(?:\||$)", body):
            return True
        if re.search(r"(?m)^\s*def\s+\w+\s*\(", body):
            return True
        return False

    @staticmethod
    def _is_bad_continuation(text: str) -> bool:
        body = (text or "").strip()
        if not body:
            return True
        return bool(_CONTINUATION_META_RE.search(body))

    @staticmethod
    def _looks_code_request(message: str) -> bool:
        text = (message or "").lower()
        if not text:
            return False
        return bool(
            re.search(
                r"(generate_signal|python|코드|전략 코드|함수|def\s+\w+\(|yaml|json|백테스트 로직|signal\s*=)",
                text,
            )
        )

    @staticmethod
    def _execution_preface(intent: str) -> str:
        if intent == INTENT_CREATE:
            return "새 전략 생성 요청으로 분류했습니다. 승인하면 실제 파이프라인(설계→코드→백테스트)을 실행합니다."
        if intent == INTENT_MODIFY:
            return "전략 수정 요청으로 분류했습니다. 승인하면 기존 전략을 분석해 수정안과 백테스트 비교를 진행합니다."
        if intent == INTENT_EVOLVE:
            return "에볼루션 채굴 요청으로 분류했습니다. 승인하면 후보 생성/검증 루프를 시작합니다."
        if intent == INTENT_BACKTEST:
            return "백테스트 실행 요청으로 분류했습니다. 승인하면 마지막 전략으로 검증을 시작합니다."
        if intent == INTENT_OPTIMIZE:
            return "파라미터 서치 요청으로 분류했습니다. Grid/Random/Bayesian 탐색을 시작할까요?"
        if intent == "STRATEGY_WFO":
            return "워크포워드(롤링) 분석 요청으로 분류했습니다. 과거 데이터를 여러 구간으로 쪼개서 전진 분석을 수행합니다."
        return ""

    @staticmethod
    def _decode_sse_payload(event: str) -> Optional[Dict[str, Any]]:
        raw = (event or "").strip()
        if not raw.startswith("data: "):
            return None
        body = raw[len("data: "):].strip()
        if not body:
            return None
        try:
            return json.loads(body)
        except Exception:
            return None

    @staticmethod
    def _build_stage_confirm_text(intent: str, stage_num: int, stage_label: str) -> str:
        label = stage_label or f"단계 {stage_num}"
        return (
            f"검토 요청: `{label}` 단계 실행을 승인할까요?\n\n"
            "모든 스테이지는 사용자 검토 후 진행합니다.\n"
            "`예 / 네 / ㄱ` → 이 단계 실행,  `아니 / 취소` → 파이프라인 중단"
        )

    async def _close_live_pipeline(self, session_id: str) -> None:
        live = self._live_pipeline_streams.pop(session_id, None)
        if not live:
            return
        gen = live.get("gen")
        if gen:
            try:
                await gen.aclose()
            except Exception:
                logger.debug("[chat] live pipeline close failed session=%s", session_id, exc_info=True)

    async def _advance_live_pipeline_until_gate(
        self,
        session_id: str,
        db,
    ) -> AsyncGenerator[str, None]:
        live = self._live_pipeline_streams.get(session_id)
        if not live:
            text = "진행 중인 파이프라인 상태를 찾을 수 없습니다. 다시 요청해 주세요."
            yield format_sse({"type": "analysis", "content": text})
            await db.save_chat_message(session_id, "assistant", text, "text")
            yield format_sse({"type": "done"})
            return

        intent = str(live.get("intent") or INTENT_CREATE)
        gen = live.get("gen")
        if gen is None:
            text = "파이프라인 생성기가 유효하지 않습니다. 다시 요청해 주세요."
            yield format_sse({"type": "analysis", "content": text})
            await db.save_chat_message(session_id, "assistant", text, "text")
            yield format_sse({"type": "done"})
            await self._close_live_pipeline(session_id)
            return

        while True:
            try:
                event = await gen.__anext__()
            except StopAsyncIteration:
                logger.info("[chat] live pipeline completed session=%s intent=%s", session_id, intent)
                self._live_pipeline_streams.pop(session_id, None)
                self._pending_stage_confirmations.pop(session_id, None)
                yield format_sse({"type": "done"})
                return
            except Exception as e:
                logger.exception("[chat] live pipeline advance failed session=%s intent=%s", session_id, intent)
                self._live_pipeline_streams.pop(session_id, None)
                self._pending_stage_confirmations.pop(session_id, None)
                yield format_sse({"type": "analysis", "content": f"파이프라인 진행 중 오류: {e}"})
                yield format_sse({"type": "done"})
                return

            payload = self._decode_sse_payload(event)
            if payload and payload.get("type") == "stage":
                stage_num = int(payload.get("stage") or 0)
                stage_label = str(payload.get("label") or f"단계 {stage_num}")
                if not self._should_stage_review(intent, stage_num):
                    yield event
                    continue
                self._pending_stage_confirmations[session_id] = {
                    "intent": intent,
                    "stage": stage_num,
                    "label": stage_label,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
                review_text = self._build_stage_confirm_text(intent, stage_num, stage_label)
                logger.info(
                    "[chat] stage review requested session=%s intent=%s stage=%s",
                    session_id,
                    intent,
                    stage_num,
                )
                yield format_sse({"type": "analysis", "content": review_text})
                await db.save_chat_message(session_id, "assistant", review_text, "text")
                yield format_sse({"type": "done"})
                return

            yield event
            if payload and payload.get("type") == "done":
                logger.info("[chat] live pipeline emitted done session=%s intent=%s", session_id, intent)
                self._live_pipeline_streams.pop(session_id, None)
                self._pending_stage_confirmations.pop(session_id, None)
                return

    _CONTINUATION_PATTERNS = re.compile(
        r"^(이어서|계속|이어|이어가|마저|더\s*써|계속\s*써|이어\s*써|이어서\s*써|계속\s*이어|마저\s*써"
        r"|이어줘|계속해줘|계속\s*해줘|이어\s*해줘|이어서\s*해줘|이어서\s*작성|계속\s*작성"
        r"|나머지|나머지도|나머지\s*써|나머지\s*작성|계속해|이어가줘"
        r")"
        r"[\s\S]{0,30}$",
        re.IGNORECASE,
    )

    @classmethod
    def _is_continuation_request(cls, message: str) -> bool:
        return bool(cls._CONTINUATION_PATTERNS.match((message or "").strip()))

    @staticmethod
    def _smalltalk_fast_reply(message: str) -> Optional[str]:
        text = (message or "").strip().lower()
        if not text:
            return None
        if re.fullmatch(r"(안녕|안녕하세요|하이|ㅎㅇ|hello|hi|hey)[!?.~\s]*", text):
            return "안녕하세요. 전략 생성/수정/백테스트 요청을 바로 처리할 수 있어요."
        if re.fullmatch(r"(고마워|감사|감사해|thanks|thank you)[!?.~\s]*", text):
            return "언제든지요. 다음 요청 주시면 바로 진행할게요."
        if re.fullmatch(r"(테스트|test|ping|퐁)[!?.~\s]*", text):
            return "응답 정상입니다."
        if re.search(r"(넌\s*)?누구|who\s*(are\s*)?you|what\s*(are\s*)?you", text):
            return "저는 트레이딩 전략 생성 및 백테스트 어시스턴트입니다. 전략 작성, 수정, 검증을 도와드려요."
        return None

    # ─────────────────────────────────────────────────────────────────
    # 진입점
    # ─────────────────────────────────────────────────────────────────
    async def execute_pipeline(
        self,
        message: str,
        session_id: str,
        context: Dict[str, Any],
        history: List[Dict[str, Any]],
        force_chat_mode: bool = False,
        chat_model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        logger.info(
            "[chat] request start session=%s msg_len=%d history=%d ctx_keys=%s preview=%r",
            session_id,
            len(message or ""),
            len(history or []),
            sorted(list((context or {}).keys()))[:10],
            self._preview_text(message),
        )
        db = SupabaseManager()
        await db.save_chat_message(session_id, "user", message)

        # ── force_chat_mode: 파이프라인 라우팅 완전 생략 ──────────────
        if force_chat_mode:
            async for ev in self._direct_chat_reply(message, session_id, context, history, db, model=chat_model):
                yield ev
            return

        # ── 스테이지 검토 대기 중 처리 ─────────────────────────────
        pending_stage = self._pending_stage_confirmations.get(session_id)
        if pending_stage:
            stage_num = int(pending_stage.get("stage") or 0)
            intent = str(pending_stage.get("intent") or INTENT_CREATE)
            label = str(pending_stage.get("label") or f"단계 {stage_num}")
            logger.info(
                "[chat] pending stage review session=%s intent=%s stage=%s",
                session_id,
                intent,
                stage_num,
            )

            if self._is_rejection_reply(message):
                self._pending_stage_confirmations.pop(session_id, None)
                await self._close_live_pipeline(session_id)
                text = "알겠습니다. 현재 파이프라인을 중단했어요."
                yield format_sse({"type": "analysis", "content": text})
                await db.save_chat_message(session_id, "assistant", text, "text")
                yield format_sse({"type": "done"})
                return

            if self._is_approval_reply(message):
                self._pending_stage_confirmations.pop(session_id, None)
                logger.info(
                    "[chat] stage approved session=%s intent=%s stage=%s",
                    session_id,
                    intent,
                    stage_num,
                )
                yield format_sse({"type": "stage", "stage": stage_num, "label": label})
                async for ev in self._advance_live_pipeline_until_gate(session_id, db):
                    yield ev
                return

            # 검토 대기 중 다른 메시지가 오면 기존 파이프라인을 종료하고 새 요청으로 간주
            logger.info("[chat] pending stage replaced by new request session=%s", session_id)
            self._pending_stage_confirmations.pop(session_id, None)
            await self._close_live_pipeline(session_id)

        # ── 파이프라인 시작 확인 대기 중 처리 ─────────────────────
        pending = self._pending_pipeline_confirmations.get(session_id)
        if pending:
            saved_intent = pending.get("intent", INTENT_CREATE)
            saved_message = pending.get("message", "")
            logger.info("[chat] pending confirmation session=%s intent=%s", session_id, saved_intent)

            if self._is_rejection_reply(message):
                self._pending_pipeline_confirmations.pop(session_id, None)
                logger.info("[chat] pending rejected session=%s intent=%s", session_id, saved_intent)
                text = "알겠습니다. 취소했어요."
                yield format_sse({"type": "analysis", "content": text})
                await db.save_chat_message(session_id, "assistant", text, "text")
                yield format_sse({"type": "done"})
                return

            if self._is_approval_reply(message):
                self._pending_pipeline_confirmations.pop(session_id, None)
                logger.info("[chat] pending approved session=%s intent=%s", session_id, saved_intent)
                self._live_pipeline_streams[session_id] = {
                    "intent": saved_intent,
                    "gen": self._route_pipeline(saved_intent, saved_message, session_id, context, history, db),
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
                kickoff = (
                    f"검토 모드 활성화: `{_INTENT_LABEL.get(saved_intent, '파이프라인')}`을 "
                    "스테이지별 승인 방식으로 진행합니다."
                )
                yield format_sse({"type": "analysis", "content": kickoff})
                await db.save_chat_message(session_id, "assistant", kickoff, "text")
                async for ev in self._advance_live_pipeline_until_gate(session_id, db):
                    yield ev
                return

            logger.info("[chat] pending replaced by new request session=%s", session_id)
            self._pending_pipeline_confirmations.pop(session_id, None)

        # ── code_gen_mode 직행 (설계도 카드 버튼 경로) ────────────────
        code_gen_mode = str((context or {}).get("code_gen_mode") or "").strip()
        if code_gen_mode:
            logger.info(
                "[chat] code_gen_mode fast-path session=%s mode=%s has_design=%s",
                session_id,
                code_gen_mode,
                bool((context or {}).get("design")),
            )
            async for ev in self._route_pipeline(INTENT_CREATE, message, session_id, context, history, db):
                yield ev
            return

        # ── 1. 규칙 기반 트리거 확인 (즉시, <1ms) ────────────────────
        quick_invoke_key = _classify_by_keywords(message)
        if quick_invoke_key:
            logger.info("[chat] trigger matched session=%s invoke=%s", session_id, quick_invoke_key)
            # 분석형 스킬은 _INVOKE_MAP 없이 직접 dispatch (CODE_REVIEW 등이 intent=None 되는 버그 방지)
            if quick_invoke_key in NO_CONFIRM_SKILLS:
                yield format_sse({"type": "invocation", "skill": quick_invoke_key,
                                 "label": quick_invoke_key.replace("_", " ").title(), "model": "keyword-trigger"})
                async for ev in dispatch_analysis(
                    quick_invoke_key, message, session_id, context, history, db,
                    self._session_last_strategy,
                ):
                    yield ev
                return
            intent = _INVOKE_MAP.get(quick_invoke_key)
            if intent:
                # 실행형 스킬 (확인 필요)
                last_strat = await get_last_strategy(session_id, db, self._session_last_strategy)
                if intent == INTENT_MODIFY and not last_strat:
                    intent = INTENT_CREATE
                    fallback_note = "(이전 전략이 없어 신규 생성 파이프라인으로 진행합니다)\n\n"
                    confirm_text = "\n\n" + fallback_note + self._build_confirm_text(intent, message, None)
                else:
                    confirm_text = "\n\n" + self._build_confirm_text(intent, message, last_strat)
                yield format_sse({"type": "invocation", "skill": quick_invoke_key,
                                 "label": _INTENT_LABEL.get(intent), "model": "keyword-trigger"})
                if self._should_require_pipeline_confirm(intent):
                    self._pending_pipeline_confirmations[session_id] = {
                        "message": message,
                        "intent": intent,
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    }
                    yield format_sse({"type": "analysis", "content": confirm_text})
                    await db.save_chat_message(session_id, "assistant", confirm_text, "text")
                    yield format_sse({"type": "done"})
                else:
                    async for ev in self._route_pipeline(intent, message, session_id, context, history, db):
                        yield ev
                return

        # ── 2. 일반 대화 fast-path (인사/핑은 LLM 생략) ───────────
        smalltalk = self._smalltalk_fast_reply(message)
        if smalltalk:
            logger.info("[chat] fast smalltalk session=%s", session_id)
            yield format_sse({"type": "analysis", "content": smalltalk})
            await db.save_chat_message(session_id, "assistant", smalltalk, "text")
            yield format_sse({"type": "done"})
            return

        # ── 2b. 이어쓰기 요청 감지 ────────────────────────────────
        if self._is_continuation_request(message):
            logger.info("[chat] continuation request session=%s", session_id)
            async for ev in self._execute_continuation(session_id, history, db):
                yield ev
            return

        # ── 3. 일반 대화 (LLM 응답) ─────────────────────────────
        logger.info("[chat] general response session=%s", session_id)
        try:
            try:
                general_timeout = float(os.getenv("CHAT_GENERAL_TIMEOUT", "120"))
            except Exception:
                general_timeout = 120.0
            resp = await generate_chat_reply(
                user_message=message,
                context=context,
                history=history,
                model=(os.getenv("QUICK_MODEL") or None),
                temperature=0.2,
                timeout_sec=general_timeout,
            )
            full_response = self._sanitize_chat_text(resp.get("content", "응답을 생성할 수 없습니다."))

            # 응답이 잘렸거나 패턴으로 끊긴 경우 안전한 이어쓰기 수행 (최대 2회)
            finish_reason = str(resp.get("finish_reason") or "").strip().lower()
            for _ in range(2):
                _tail = full_response.strip()
                looks_cut = (
                    finish_reason == "length"
                    or bool(re.search(r"[~\-/(:`\[\{]$", _tail))
                    or bool(re.search(r"20\d{2}-\d{2}-$", _tail))
                    # 마지막 문자가 문장 종결부호가 아닌 상태로 length 종료
                )
                if not looks_cut:
                    break

                is_structured = self._looks_structured_response(full_response)
                if is_structured:
                    cont_user = (
                        "다음 본문은 중간에서 잘렸습니다. 동일한 형식으로 나머지 부분만 이어서 출력하세요.\n"
                        "- 이미 나온 내용 반복 금지\n"
                        "- 지시문/메타 설명 금지\n"
                        "- 코드/목록/YAML 형식이면 그 형식을 유지\n\n"
                        f"{full_response[-2200:]}"
                    )
                    cont_system = (
                        "너는 본문 복원 엔진이다. "
                        "중복 없는 continuation fragment만 출력하라."
                    )
                    cont_max_tokens = 900
                    cont_timeout = min(general_timeout, 35.0)
                else:
                    cont_user = (
                        "아래 텍스트의 마지막 문장만 자연스럽게 마무리하세요.\n"
                        "- 1~2문장만 출력\n"
                        "- 지시문/설명문/메타 문구 금지\n"
                        "- 본문 반복 금지\n\n"
                        f"{full_response[-1600:]}"
                    )
                    cont_system = (
                        "너는 문장 마무리 전용 엔진이다. "
                        "질문/설명/메타 발화 없이 결과 문장 1~2개만 반환하라."
                    )
                    cont_max_tokens = 192
                    cont_timeout = min(general_timeout, 20.0)

                continuation = await generate_chat_reply(
                    user_message=cont_user,
                    context=None,
                    history=[],
                    custom_system_prompt=cont_system,
                    model=(os.getenv("QUICK_MODEL") or None),
                    temperature=0.1,
                    timeout_sec=cont_timeout,
                    max_tokens=cont_max_tokens,
                )
                cont_text = self._sanitize_chat_text(continuation.get("content", ""))
                if self._is_bad_continuation(cont_text):
                    logger.warning("[chat] continuation artifact dropped session=%s", session_id)
                    cont_text = ""
                if not cont_text:
                    break
                glue = "\n" if is_structured else " "
                full_response = f"{full_response.rstrip()}{glue}{cont_text.lstrip()}".strip()
                finish_reason = str(continuation.get("finish_reason") or "").strip().lower()

            if not full_response:
                full_response = "요청을 이해했어요. 계속 진행할 내용을 한 줄로 알려주세요."
            thought_content = resp.get("thought")
            if thought_content:
                yield format_sse({"type": "thought", "content": thought_content})

            yield format_sse({"type": "analysis", "content": full_response})
            await db.save_chat_message(session_id, "assistant", full_response, "text")
        except Exception as e:
            logger.error(f"[chat] general response error: {e}")
            yield format_sse({"type": "analysis", "content": f"응답 생성 중 오류: {e}"})

        yield format_sse({"type": "done"})

    # ─────────────────────────────────────────────────────────────────
    # 이어쓰기 (이전 응답 끝 부분을 기준으로 LLM이 이어서 생성)
    # ─────────────────────────────────────────────────────────────────
    async def _execute_continuation(
        self, session_id: str, history: List[Dict[str, Any]], db
    ) -> AsyncGenerator[str, None]:
        # 히스토리에서 마지막 assistant 메시지 찾기
        last_assistant = ""
        for msg in reversed(history or []):
            if msg.get("role") == "assistant" and str(msg.get("content") or "").strip():
                last_assistant = str(msg["content"]).strip()
                break
        if not last_assistant:
            # DB에서 fallback
            db_history = await db.get_chat_history(session_id, 10)
            for msg in reversed(db_history or []):
                if msg.get("role") == "assistant" and str(msg.get("content") or "").strip():
                    last_assistant = str(msg["content"]).strip()
                    break

        tail = last_assistant[-1200:] if len(last_assistant) > 1200 else last_assistant
        continuation_system = (
            "너는 직전 응답을 이어서 작성하는 전용 엔진이다.\n"
            "규칙:\n"
            "1. 이미 작성된 내용을 절대 반복하지 않는다.\n"
            "2. 직전 응답의 마지막 문장/항목에서 자연스럽게 바로 이어 작성한다.\n"
            "3. 설명, 인사, 메타 발화 없이 본문만 출력한다.\n"
            "4. 형식(마크다운/표/코드 블록)이 있으면 그 형식을 유지한다.\n\n"
            f"[직전 응답 끝부분]\n{tail}"
        )
        continuation_user = "이어서 작성해 주세요. 위 직전 응답에서 마지막으로 다룬 내용 다음부터 바로 시작하세요."

        logger.info("[chat] continuation exec session=%s tail_len=%d", session_id, len(tail))
        full = ""
        try:
            try:
                max_tokens = int(os.getenv("CHAT_CONTINUATION_MAX_TOKENS", "4000"))
            except Exception:
                max_tokens = 4000
            async for chunk in stream_chat_reply(
                user_message=continuation_user,
                context=None,
                history=[],
                custom_system_prompt=continuation_system,
                temperature=0.2,
                max_tokens=max_tokens,
            ):
                thought = chunk.get("thought")
                content = chunk.get("content")
                if thought:
                    yield format_sse({"type": "thought", "content": thought})
                if content:
                    full += content
                    yield format_sse({"type": "analysis", "content": content})
            yield format_sse({"type": "done"})
        finally:
            # CancelledError(새로고침/연결 끊김) 포함 항상 저장
            if full:
                try:
                    await asyncio.shield(db.save_chat_message(session_id, "assistant", full, "text"))
                except Exception as e:
                    logger.error("[chat] continuation save failed: %s", e)

    # ─────────────────────────────────────────────────────────────────
    # 직접 채팅 응답 (파이프라인 라우팅 없음, force_chat_mode 전용)
    # ─────────────────────────────────────────────────────────────────
    async def _direct_chat_reply(
        self, message, session_id, context, history, db, model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        resolved_model = (model or os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or None)
        logger.info("[chat] direct_chat_reply session=%s model=%s", session_id, resolved_model or "default")
        full = ""
        try:
            async for chunk in stream_chat_reply(
                user_message=message,
                context=context,
                history=history,
                model=resolved_model,
                temperature=0.3,
            ):
                thought = chunk.get("thought")
                content = chunk.get("content")
                if thought:
                    yield format_sse({"type": "thought", "content": thought})
                if content:
                    full += content
                    yield format_sse({"type": "analysis", "content": content})
            yield format_sse({"type": "done"})
        finally:
            # CancelledError(새로고침/연결 끊김) 포함 항상 저장
            if full:
                try:
                    await asyncio.shield(db.save_chat_message(session_id, "assistant", full, "text"))
                except Exception as e:
                    logger.error("[chat] direct_chat_reply save failed: %s", e)

    # ─────────────────────────────────────────────────────────────────
    # 일반 대화 + INVOKE 감지
    # ─────────────────────────────────────────────────────────────────
    async def _execute_general_chat(
        self, message, session_id, context, history, db
    ) -> AsyncGenerator[str, None]:
        full_response = ""
        msg_id: Optional[str] = None
        try:
            # 즉시 빈 메시지 생성 (플레이스홀더)
            msg_id = await db.save_chat_message(session_id, "assistant", "...", "text")
            logger.info(
                "[chat] classify start (lightweight) session=%s model=%s temp=0.05",
                session_id,
                (os.getenv("QUICK_MODEL") or os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or "").split("/")[-1],
            )
            try:
                classify_timeout = float(os.getenv("CHAT_CLASSIFY_TIMEOUT", "10"))
            except Exception:
                classify_timeout = 10.0
            try:
                classify_max_tokens = int(os.getenv("CHAT_CLASSIFY_MAX_TOKENS", "32"))
            except Exception:
                classify_max_tokens = 32
            classify_max_tokens = max(16, classify_max_tokens)

            classify_result = await generate_chat_reply(
                user_message=CLASSIFICATION_MESSAGE.format(message=message),
                context=None,
                history=[],
                custom_system_prompt=CLASSIFICATION_SYSTEM,
                model=(os.getenv("QUICK_MODEL") or None),
                temperature=0.05,
                timeout_sec=classify_timeout,
                max_tokens=classify_max_tokens,
            )
            full_response = (classify_result.get("content") or "").strip()
            logger.info(
                "[chat] classify done session=%s provider=%s model=%s fallback=%s resp_len=%d",
                session_id,
                classify_result.get("provider", "-"),
                classify_result.get("model", "-"),
                classify_result.get("fallback", False),
                len(full_response),
            )
        except Exception:
            logger.exception("General chat classify failed")
            raise

        invoke_match = _INVOKE_RE.search(full_response)
        invoke_key = invoke_match.group(1) if invoke_match else ""
        intent = _INVOKE_MAP.get(invoke_key) if invoke_key else None
        logger.info(
            "[chat] classify result session=%s invoke=%s intent=%s resp_len=%d",
            session_id,
            invoke_key or "-",
            intent or INTENT_GENERAL,
            len(full_response),
        )

        clean_response = self._sanitize_chat_text(full_response)
        if intent in {INTENT_CREATE, INTENT_MODIFY, INTENT_EVOLVE, INTENT_BACKTEST}:
            preface = self._execution_preface(intent)
            if preface:
                clean_response = preface

        if clean_response:
            yield format_sse({"type": "analysis", "content": clean_response})

        if msg_id:
            await db.update_chat_message(msg_id, clean_response or "요청을 확인했습니다.")
        elif clean_response:
            await db.save_chat_message(session_id, "assistant", clean_response, "text")

        if invoke_match:
            # [UI 피드백] 발동 모델 + 파이프라인 모델 스택을 명시적으로 알림
            default_model = os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or "GPT-OSS 120B"
            router_model = self._short_model_name(os.getenv("QUICK_MODEL") or default_model)
            pipeline_models = self._pipeline_model_stack()
            yield format_sse({
                "type": "invocation", 
                "skill": invoke_key, 
                "label": _INTENT_LABEL.get(_INVOKE_MAP.get(invoke_key), invoke_key),
                "model": router_model,
                "router_model": router_model,
                "models": pipeline_models,
            })

            if invoke_key in NO_CONFIRM_SKILLS:
                logger.info("[chat] analysis skill dispatch session=%s skill=%s", session_id, invoke_key)
                async for ev in dispatch_analysis(
                    invoke_key, message, session_id, context, history, db,
                    self._session_last_strategy,
                ):
                    yield ev
                return

            if intent:
                last_strat = await get_last_strategy(session_id, db, self._session_last_strategy)
                if intent == INTENT_MODIFY and not last_strat:
                    # 수정 요청이지만 이전 전략이 없으면 신규 생성으로 fallback
                    logger.info("[chat] modify fallback to create session=%s reason=no_previous_strategy", session_id)
                    intent = INTENT_CREATE
                    fallback_note = "(이전 전략이 없어 신규 생성 파이프라인으로 진행합니다)\n\n"
                    confirm_text = "\n\n" + fallback_note + self._build_confirm_text(intent, message, None)
                else:
                    confirm_text = "\n\n" + self._build_confirm_text(intent, message, last_strat)
                if self._should_require_pipeline_confirm(intent):
                    self._pending_pipeline_confirmations[session_id] = {
                        "message": message,
                        "intent": intent,
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    }
                    logger.info("[chat] confirmation queued session=%s intent=%s", session_id, intent)
                    yield format_sse({"type": "analysis", "content": confirm_text})
                    await db.save_chat_message(session_id, "assistant", confirm_text, "text")
                else:
                    async for ev in self._route_pipeline(intent, message, session_id, context, history, db):
                        yield ev
                    return
            else:
                logger.warning(f"[invoke] 알 수 없는 스킬: {invoke_key!r}")
        else:
            logger.info("[chat] general response only session=%s", session_id)

        yield format_sse({"type": "done"})

    # ─────────────────────────────────────────────────────────────────
    # 파이프라인 라우터
    # ─────────────────────────────────────────────────────────────────
    async def _route_pipeline(
        self, intent, message, session_id, context, history, db
    ) -> AsyncGenerator[str, None]:
        logger.info("[chat] pipeline start session=%s intent=%s", session_id, intent)
        sm = self._session_last_strategy
        code_gen_mode = context.get("code_gen_mode")
        if intent == INTENT_CREATE:
            async for ev in run_create_pipeline(message, session_id, context, history, db, sm, code_gen_mode=code_gen_mode):
                yield ev
        elif intent == INTENT_MODIFY:
            async for ev in run_modify_pipeline(message, session_id, context, history, db, sm):
                yield ev
        elif intent == INTENT_EVOLVE:
            async for ev in run_create_pipeline(message, session_id, context, history, db, sm, is_mining=True, code_gen_mode=code_gen_mode):
                yield ev
        elif intent == INTENT_BACKTEST:
            prev = await get_last_strategy(session_id, db, sm)
            if prev:
                yield format_sse({"type": "stage", "stage": 4, "label": "📈 이전 전략 백테스트 중..."})
                async for ev in run_backtest(
                    prev["code"], prev["title"], message, context, session_id, db, sm,
                ):
                    yield ev
            else:
                yield format_sse({"type": "analysis", "content": "백테스트할 전략이 없습니다."})
            yield format_sse({"type": "done"})
        elif intent == INTENT_OPTIMIZE:
            prev = await get_last_strategy(session_id, db, sm)
            if prev:
                async for ev in run_optimize_pipeline(message, context, prev.get("code", ""), sm.get(session_id, {})):
                    yield ev
            else:
                yield format_sse({"type": "error", "content": "❌ 최적화할 전략이 없습니다. 먼저 전략을 생성해주세요."})
            yield format_sse({"type": "done"})
        elif intent == "STRATEGY_WFO":
            prev = await get_last_strategy(session_id, db, sm)
            if prev:
                async for ev in run_walk_forward_pipeline(message, context, prev.get("code", ""), sm.get(session_id, {})):
                    yield ev
            else:
                yield format_sse({"type": "error", "content": "❌ 분석할 전략이 없습니다. 먼저 전략을 생성해주세요."})
            yield format_sse({"type": "done"})
        elif intent == "PNL_ANALYSIS":
            prev = await get_last_strategy(session_id, db, sm)
            if prev:
                async for ev in run_pnl_analysis(message, context, prev.get("code", ""), sm.get(session_id, {})):
                    yield ev
            else:
                yield format_sse({"type": "error", "content": "❌ 분석할 전략이 없습니다. 먼저 전략을 생성해주세요."})
            yield format_sse({"type": "done"})
        logger.info("[chat] pipeline end session=%s intent=%s", session_id, intent)

    # ─────────────────────────────────────────────────────────────────
    # 확인 텍스트 빌더
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_confirm_text(intent: str, message: str, prev: Optional[Dict]) -> str:
        base_msgs = {
            INTENT_CREATE:   "전략 생성 파이프라인(설계 → 코드 → 백테스트)을 실행할까요?",
            INTENT_MODIFY:   f"'{prev.get('title', '이전 전략')}' 수정 파이프라인을 실행할까요?" if prev else "",
            INTENT_EVOLVE:   "에볼루션 채굴 파이프라인(WFO + Monte Carlo)을 실행할까요?\n⚠️ 수 분 소요.",
            INTENT_BACKTEST: "이전에 생성된 전략으로 백테스트를 실행할까요?",
            INTENT_OPTIMIZE: "현재 전략의 파라미터를 최적화할까요?",
            "STRATEGY_WFO":  "워크포워드(롤링) 분석을 실행할까요? (수분 소요)",
            "PNL_ANALYSIS":  "포지션별 PnL 분해 분석을 실행할까요?",
        }
        body = base_msgs.get(intent, "파이프라인을 실행할까요?")
        if intent in {INTENT_CREATE, INTENT_MODIFY, INTENT_EVOLVE}:
            base = os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or ""
            quick = (os.getenv("QUICK_MODEL") or base).split("/")[-1]
            analysis = (os.getenv("ANALYSIS_MODEL") or base).split("/")[-1]
            code = (os.getenv("CODE_GEN_MODEL") or base).split("/")[-1]
            body += f"\n\n모델 라우팅: 분류 `{quick}` · 설계 `{analysis}` · 코드 `{code}`"
        return body + "\n\n`예 / 네 / ㄱ` → 시작,  `아니 / 취소` → 취소\n(시작 후에도 모든 스테이지는 검토 승인 후 진행됩니다.)"

    # ─────────────────────────────────────────────────────────────────
    # 승인 / 거절 판별
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_approval_reply(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        if text in {"예", "네", "응", "ㅇㅇ", "ㄱ", "ㄱㄱ", "ok", "yes", "go", "고고"}:
            return True
        # "ㄱ 고고", "go go", "네 진행"처럼 짧은 승인 표현도 허용
        first_line = text.splitlines()[0].strip()
        if re.fullmatch(r"(?:ㄱㄱ?|예|네|응|ㅇㅇ|ok|yes|go|고고)[\s'\"`’‘“”.,!?~:;/_-]*", first_line):
            return True
        if re.search(r"(^|\s)ㄱ(ㄱ)?(\s|$)", first_line):
            return True
        if re.search(r"(^|\s)(go|yes|ok|고고)(\s|$)", first_line):
            return True
        return any(p in text for p in ["진행해", "시작해", "해줘", "ㄱㄱ해", "승인", "좋아요", "그래요", "okay", "start", "고고"])

    @staticmethod
    def _is_rejection_reply(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        if text in {"아니", "ㄴ", "ㄴㄴ", "no", "nope"}:
            return True
        return any(p in text for p in ["아니요", "안해", "취소", "중지", "멈춰", "하지마", "cancel", "stop"])

    # ─────────────────────────────────────────────────────────────────
    # 전략 배포
    # ─────────────────────────────────────────────────────────────────
    async def deploy_strategy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            db = SupabaseManager()
            code = data.get("code", "")
            if not code:
                return {"success": False, "error": "전략 코드가 없습니다."}
            title = extract_strategy_title(code)
            if title == "AI Generated Strategy":
                title = data.get("title", title)
            strategy_key = f"deployed_{datetime.now().strftime('%y%m%d_%H%M%S')}"
            strategy_id = db.save_system_strategy(
                strategy_key=strategy_key,
                code=code,
                name=title,
                params={
                    "strategy_key": strategy_key,
                    "display_name": title,
                    "source": "chat_deploy",
                    "deployed_at": datetime.now().isoformat(),
                },
                rationale="User manually deployed via Chat UI.",
            )
            if not strategy_id:
                return {"success": False, "error": "DB에서 strategy_id를 반환하지 않았습니다."}
            invalidate_strategy_cache()
            return {"success": True, "strategy_key": strategy_key, "strategy_id": strategy_id}
        except Exception as e:
            logger.exception("Strategy deployment failed")
            return {"success": False, "error": str(e)}
