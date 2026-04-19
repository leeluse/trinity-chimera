"""채팅 파이프라인 라우터 — INVOKE 감지 + 확인 흐름만 담당"""
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from server.shared.llm.client import stream_chat_reply
from server.shared.db.supabase import SupabaseManager
from server.modules.engine.runtime import invalidate_strategy_cache
from server.modules.chat.prompts import SYSTEM_PROMPT
from server.modules.chat.skills import (
    dispatch_analysis,
    run_create_pipeline,
    run_modify_pipeline,
    run_backtest,
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

_INTENT_LABEL = {
    INTENT_CREATE:   "전략 생성 파이프라인",
    INTENT_MODIFY:   "전략 수정 파이프라인",
    INTENT_EVOLVE:   "에볼루션 채굴 파이프라인",
    INTENT_BACKTEST: "백테스트",
}

# ── INVOKE 마커 매핑 ──────────────────────────────────────────────
_INVOKE_MAP = {
    "CREATE_STRATEGY": INTENT_CREATE,
    "MODIFY_STRATEGY": INTENT_MODIFY,
    "RUN_BACKTEST":    INTENT_BACKTEST,
    "RUN_EVOLUTION":   INTENT_EVOLVE,
}
_INVOKE_RE = re.compile(r'\[INVOKE:(\w+)\]')
_THINK_BLOCK_RE = re.compile(r"<(thought|think|think_process|reasoning)>[\s\S]*?</\1>", re.IGNORECASE)
_THINK_TAG_RE = re.compile(r"</?(thought|think|think_process|reasoning)[^>]*>", re.IGNORECASE)


class ChatHandler:
    """대화형 전략 파이프라인 라우터"""

    _pending_pipeline_confirmations: Dict[str, Dict[str, Any]] = {}
    _session_last_strategy: Dict[str, Any] = {}

    @staticmethod
    def _short_model_name(model_name: str) -> str:
        text = str(model_name or "").strip()
        if not text:
            return ""
        return text.split("/")[-1]

    @classmethod
    def _pipeline_model_stack(cls) -> Dict[str, str]:
        default_model = os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or ""
        return {
            "analysis": cls._short_model_name(os.getenv("ANALYSIS_MODEL") or default_model),
            "code": cls._short_model_name(os.getenv("CODE_GEN_MODEL") or default_model),
            "quick": cls._short_model_name(os.getenv("QUICK_MODEL") or default_model),
        }

    @staticmethod
    def _sanitize_chat_text(text: str) -> str:
        clean = _INVOKE_RE.sub("", text or "")
        clean = _THINK_BLOCK_RE.sub("", clean)
        clean = _THINK_TAG_RE.sub("", clean)
        return clean.strip()

    @staticmethod
    def _execution_preface(intent: str) -> str:
        if intent == INTENT_CREATE:
            return "새 전략 생성 요청으로 분류했습니다. 승인하면 실제 파이프라인(분석→설계→코드→백테스트)을 실행합니다."
        if intent == INTENT_MODIFY:
            return "전략 수정 요청으로 분류했습니다. 승인하면 기존 전략을 분석해 수정안과 백테스트 비교를 진행합니다."
        if intent == INTENT_EVOLVE:
            return "에볼루션 채굴 요청으로 분류했습니다. 승인하면 후보 생성/검증 루프를 시작합니다."
        if intent == INTENT_BACKTEST:
            return "백테스트 실행 요청으로 분류했습니다. 승인하면 마지막 전략으로 검증을 시작합니다."
        return ""

    # ─────────────────────────────────────────────────────────────────
    # 진입점
    # ─────────────────────────────────────────────────────────────────
    async def execute_pipeline(
        self,
        message: str,
        session_id: str,
        context: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        db = SupabaseManager()
        await db.save_chat_message(session_id, "user", message)

        # ── 확인 대기 중 처리 ──────────────────────────────────────
        pending = self._pending_pipeline_confirmations.get(session_id)
        if pending:
            saved_intent = pending.get("intent", INTENT_CREATE)
            saved_message = pending.get("message", "")

            if self._is_rejection_reply(message):
                self._pending_pipeline_confirmations.pop(session_id, None)
                text = "알겠습니다. 취소했어요."
                yield format_sse({"type": "analysis", "content": text})
                await db.save_chat_message(session_id, "assistant", text, "text")
                yield format_sse({"type": "done"})
                return

            if self._is_approval_reply(message):
                self._pending_pipeline_confirmations.pop(session_id, None)
                yield format_sse({"type": "stage", "stage": 0,
                                  "label": f"🚀 {_INTENT_LABEL.get(saved_intent, '파이프라인')} 시작"})
                async for ev in self._route_pipeline(saved_intent, saved_message,
                                                     session_id, context, history, db):
                    yield ev
                return

            self._pending_pipeline_confirmations.pop(session_id, None)

        # ── LLM 대화 + INVOKE 감지 ────────────────────────────────
        async for ev in self._execute_general_chat(message, session_id, context, history, db):
            yield ev

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
            # SSE first-byte를 빠르게 보내 타임아웃/무응답 체감을 줄인다.
            yield format_sse({"type": "analysis", "content": "요청을 분류하고 있어요..."})

            async for chunk in stream_chat_reply(
                user_message=message,
                context=context,
                history=history,
                custom_system_prompt=SYSTEM_PROMPT,
                model=(os.getenv("QUICK_MODEL") or None),
            ):
                full_response += chunk
        except Exception:
            logger.exception("General chat stream failed")
            raise

        invoke_match = _INVOKE_RE.search(full_response)
        invoke_key = invoke_match.group(1) if invoke_match else ""
        intent = _INVOKE_MAP.get(invoke_key) if invoke_key else None

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
                async for ev in dispatch_analysis(
                    invoke_key, message, session_id, context, history, db,
                    self._session_last_strategy,
                ):
                    yield ev
                return

            if intent:
                last_strat = await get_last_strategy(session_id, db, self._session_last_strategy)
                if intent == INTENT_MODIFY and not last_strat:
                    yield format_sse({"type": "analysis",
                                      "content": "\n\n⚠️ 수정할 이전 전략이 없어요. 먼저 전략을 생성해 주세요."})
                else:
                    confirm_text = "\n\n" + self._build_confirm_text(intent, message, last_strat)
                    self._pending_pipeline_confirmations[session_id] = {
                        "message": message,
                        "intent": intent,
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    }
                    yield format_sse({"type": "analysis", "content": confirm_text})
                    await db.save_chat_message(session_id, "assistant", confirm_text, "text")
            else:
                logger.warning(f"[invoke] 알 수 없는 스킬: {invoke_key!r}")

        yield format_sse({"type": "done"})

    # ─────────────────────────────────────────────────────────────────
    # 파이프라인 라우터
    # ─────────────────────────────────────────────────────────────────
    async def _route_pipeline(
        self, intent, message, session_id, context, history, db
    ) -> AsyncGenerator[str, None]:
        sm = self._session_last_strategy
        if intent == INTENT_CREATE:
            async for ev in run_create_pipeline(message, session_id, context, history, db, sm):
                yield ev
        elif intent == INTENT_MODIFY:
            async for ev in run_modify_pipeline(message, session_id, context, history, db, sm):
                yield ev
        elif intent == INTENT_EVOLVE:
            async for ev in run_create_pipeline(message, session_id, context, history, db, sm, is_mining=True):
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

    # ─────────────────────────────────────────────────────────────────
    # 확인 텍스트 빌더
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_confirm_text(intent: str, message: str, prev: Optional[Dict]) -> str:
        base_msgs = {
            INTENT_CREATE:   "전략 생성 파이프라인(추론 → 설계 → 코드 → 백테스트)을 실행할까요?",
            INTENT_MODIFY:   f"'{prev.get('title', '이전 전략')}' 수정 파이프라인을 실행할까요?" if prev else "",
            INTENT_EVOLVE:   "에볼루션 채굴 파이프라인(WFO + Monte Carlo)을 실행할까요?\n⚠️ 수 분 소요.",
            INTENT_BACKTEST: "이전에 생성된 전략으로 백테스트를 실행할까요?",
        }
        body = base_msgs.get(intent, "파이프라인을 실행할까요?")
        if intent in {INTENT_CREATE, INTENT_MODIFY, INTENT_EVOLVE}:
            base = os.getenv("LITELLM_MODEL") or os.getenv("OLLAMA_MODEL") or ""
            quick = (os.getenv("QUICK_MODEL") or base).split("/")[-1]
            analysis = (os.getenv("ANALYSIS_MODEL") or base).split("/")[-1]
            code = (os.getenv("CODE_GEN_MODEL") or base).split("/")[-1]
            body += f"\n\n모델 라우팅: 분류 `{quick}` · 설계 `{analysis}` · 코드 `{code}`"
        return body + "\n\n`예 / 네 / ㄱ` → 실행,  `아니 / 취소` → 취소"

    # ─────────────────────────────────────────────────────────────────
    # 승인 / 거절 판별
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_approval_reply(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        if text in {"예", "네", "응", "ㅇㅇ", "ㄱ", "ㄱㄱ", "ok", "yes", "go"}:
            return True
        return any(p in text for p in ["진행해", "시작해", "해줘", "ㄱㄱ해", "승인", "좋아요", "그래요", "okay", "start"])

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
