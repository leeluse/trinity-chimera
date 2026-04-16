import json
import logging
import re
import random
import pandas as pd
from typing import Dict, Any, List, Optional, AsyncGenerator
from pathlib import Path
from datetime import datetime

from server.shared.llm.client import stream_chat_reply
from server.modules.backtest.chat.chat_backtester import ChatBacktester
from server.shared.db.supabase import SupabaseManager
from server.modules.evolution.constants import (
    AGENT_IDS,
    PERSONAS, 
    CROSS_DOMAIN_SEEDS, 
    BANNED_INDICATORS
)
from server.modules.evolution.scoring import evaluate_hard_gates
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.modules.chat.prompts import (
    SYSTEM_PROMPT,
    REASONING_PROMPT_TEMPLATE, 
    DESIGN_PROMPT_TEMPLATE, 
    CODE_PROMPT_TEMPLATE, 
    TIPS_PROMPT_TEMPLATE,
    MINING_PROMPT_TEMPLATE
)
from server.modules.engine.runtime import invalidate_strategy_cache

logger = logging.getLogger(__name__)

class ChatHandler:
    """대화형 전략 생성 파이프라인의 실질적인 처리 로직"""

    # -------------------------------------------------------------------------
    # SSE 응답 포맷팅: 스트리밍 데이터를 브라우저 규격에 맞게 변환
    # -------------------------------------------------------------------------
    @staticmethod
    def format_sse(payload: dict) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    # -------------------------------------------------------------------------
    # 파이썬 코드 추출: LLM 응답 텍스트에서 ```python 블록 안의 코드만 추출
    # -------------------------------------------------------------------------
    @staticmethod
    def extract_python_code(text: str) -> str:
        m = re.search(r"```python\s*([\s\S]*?)```", text)
        return m.group(1).strip() if m else ""

    @staticmethod
    def extract_strategy_title(text: str) -> str:
        """LLM 응답 또는 코드 내 주석/독스프링에서 전략명 추출"""
        patterns = [
            r"\[Title:\s*(.*?)\]",
            r"\[전략 이름:\s*(.*?)\]",
            r"전략명:\s*(.*)",
            r"Name:\s*(.*)",
            r"\"\"\"\s*\n?\s*(.*?Strategy.*?)\n", # Docstring 첫 줄 (Strategy 포함 시)
            r"#\s*(.*?Strategy.*?)$"              # 주석 라인 (Strategy 포함 시)
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
            if m:
                # 불필요한 공백/따옴표 제거
                t = m.group(1).strip().replace('"', '').replace("'", "")
                if t: return t
        return "AI Generated Strategy"

    # -------------------------------------------------------------------------
    # 전략 로그 아카이빙: 생성된 결과와 성과를 STRATEGY.md 파일에 영구 기록
    # -------------------------------------------------------------------------
    @staticmethod
    def log_strategy_to_file(message: str, metrics: Dict[str, Any]):
        try:
            doc_path = Path("STRATEGY.md")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = (
                f"\n\n### [{ts}] - AI Generated Strategy\n"
                f"- **요청**: {message}\n"
                f"- **성과**: 수익률 {metrics.get('total_return', 0):+.2f}%, MDD {metrics.get('max_drawdown', 0):.2f}%\n"
            )
            with open(doc_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"STRATEGY.md 로그 기록 실패: {e}")

    @staticmethod
    def _normalize_ratio(value: float) -> float:
        if 1.0 < abs(value) <= 100.0:
            return value / 100.0
        return value

    @classmethod
    def _normalize_metrics_for_gate(cls, metrics: Dict[str, Any]) -> Dict[str, Any]:
        total_return = cls._normalize_ratio(float(metrics.get("total_return", 0.0) or 0.0))
        win_rate = cls._normalize_ratio(float(metrics.get("win_rate", 0.0) or 0.0))
        max_drawdown_raw = float(metrics.get("max_drawdown", 0.0) or 0.0)
        max_drawdown = cls._normalize_ratio(max_drawdown_raw)
        if max_drawdown > 0:
            max_drawdown = -max_drawdown

        return {
            "total_return": total_return,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "profit_factor": float(metrics.get("profit_factor", 0.0) or 0.0),
            "total_trades": int(metrics.get("total_trades", 0) or 0),
            "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0) or 0.0),
            "trinity_score": float(metrics.get("trinity_score", 0.0) or 0.0),
        }

    @staticmethod
    def _resolve_target_agent(context: Dict[str, Any], message: str) -> str:
        for key in ("agent_id", "active_agent", "agent"):
            value = str(context.get(key) or "").strip()
            if value in AGENT_IDS:
                return value

        text = (message or "").lower()
        for agent_id in AGENT_IDS:
            if agent_id in text:
                return agent_id

        return "chat_global"

    @staticmethod
    def _build_memory_guardrail(memory_context: Dict[str, Any]) -> str:
        hard_gates = memory_context.get("hard_gates") or {}
        failures = memory_context.get("recent_failures") or []
        successes = memory_context.get("recent_successes") or []

        fail_lines = []
        for row in failures[:5]:
            fail_lines.append(f"- {str(row.get('reason') or 'unknown')}")
        if not fail_lines:
            fail_lines = ["- (최근 실패 이력 없음)"]

        success_lines = []
        for row in successes[:3]:
            m = row.get("metrics") or {}
            success_lines.append(
                f"- win={float(m.get('win_rate', 0.0)):.3f}, pf={float(m.get('profit_factor', 0.0)):.3f}, "
                f"ret={float(m.get('total_return', 0.0)):.3f}, mdd={float(m.get('max_drawdown', 0.0)):.3f}, "
                f"trades={int(m.get('total_trades', 0))}"
            )
        if not success_lines:
            success_lines = ["- (최근 성공 이력 없음)"]

        return (
            "\n\n[QUALITY_GUARDRAIL]\n"
            "아래 하드 게이트를 만족할 가능성이 낮은 전략은 피하고,\n"
            "최근 실패 패턴을 반복하지 마세요.\n"
            f"- min_win_rate: {hard_gates.get('min_win_rate', 0.0)}\n"
            f"- min_profit_factor: {hard_gates.get('min_profit_factor', 0.0)}\n"
            f"- min_total_return: {hard_gates.get('min_total_return', 0.0)}\n"
            f"- max_drawdown(abs): {hard_gates.get('max_drawdown', 1.0)}\n"
            f"- min_total_trades: {hard_gates.get('min_total_trades', 0)}\n"
            f"- min_sharpe_ratio: {hard_gates.get('min_sharpe_ratio', 0.0)}\n"
            "[RECENT_FAILURES]\n"
            + "\n".join(fail_lines)
            + "\n[RECENT_SUCCESSES]\n"
            + "\n".join(success_lines)
        )

    async def deploy_strategy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """사용자가 선택한 전략을 시스템 전략 라이브러리에 영구 저장"""
        try:
            db = SupabaseManager()
            code = data.get("code", "")
            
            # [IMPROVEMENT] 코드 내용에서 제목을 먼저 추출하도록 시도
            extracted_title = self.extract_strategy_title(code)
            # 수동 입력 제목보다 코드 내 제목을 우선(코드 중심)
            title = extracted_title if extracted_title != "AI Generated Strategy" else data.get("title", "AI Generated Strategy")
            
            if not code:
                return {"success": False, "error": "전략 코드가 없습니다."}

            # 유니크한 키 생성 (시간 기반)
            strategy_key = f"deployed_{datetime.now().strftime('%y%m%d_%H%M%S')}"
            
            # DB 저장
            strategy_id = db.save_system_strategy(
                strategy_key=strategy_key,
                code=code,
                name=title, # [IMPROVEMENT] name 컬럼에 직접 저장
                params={
                    "strategy_key": strategy_key,
                    "display_name": title,
                    "source": "chat_deploy",
                    "deployed_at": datetime.now().isoformat()
                },
                rationale="User manually deployed via Chat Desktop UI."
            )

            if not strategy_id:
                return {
                    "success": False,
                    "error": "전략 저장은 요청되었지만 DB에서 strategy_id를 반환하지 않았습니다."
                }

            invalidate_strategy_cache()
            return {
                "success": True,
                "strategy_key": strategy_key,
                "strategy_id": strategy_id,
            }
        except Exception as e:
            logger.exception("Strategy deployment failed")
            return {"success": False, "error": str(e)}
    
    async def execute_pipeline(
        self, 
        message: str, 
        session_id: str, 
        context: Dict[str, Any], 
        history: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """4단계(추론-설계-코드-검증) 파이프라인 실행"""
        
        db = SupabaseManager()
        yield self.format_sse({"type": "stage", "stage": 0, "label": "🚀 파이프라인 시작"})
        
        # 1. 메시지 저장
        await db.save_chat_message(session_id, "user", message)

        # [REFINED] 키워드 여부에 따른 가동 조건 설정
        is_mining = "에볼루션" in message
        enable_full_pipeline = "전략" in message or is_mining
        memory = None
        constitution: Dict[str, Any] = {}
        target_agent = "chat_global"
        memory_context: Dict[str, Any] = {}
        guardrail_block = ""

        if enable_full_pipeline:
            memory = EvolutionWikiMemory()
            constitution = memory.load_constitution()
            target_agent = self._resolve_target_agent(context, message)
            memory_context = memory.build_prompt_context(target_agent, constitution)
            guardrail_block = self._build_memory_guardrail(memory_context)

        try:
            # STAGE 1: Reasoning (Conversational Response)
            if is_mining:
                persona = random.choice(PERSONAS)
                seed = random.choice(CROSS_DOMAIN_SEEDS)
                yield self.format_sse({
                    "type": "stage", 
                    "stage": 1, 
                    "label": f"💎 {persona['name']} 페르소나로 전략 채굴 중..."
                })
                prompt1 = MINING_PROMPT_TEMPLATE.format(
                    message=message,
                    persona_name=persona['name'],
                    persona_worldview=persona['worldview'],
                    persona_style=persona['style'],
                    seed=seed,
                    banned_indicators=", ".join(BANNED_INDICATORS)
                ) + guardrail_block
            else:
                yield self.format_sse({"type": "stage", "stage": 1, "label": "🧠 의도 파악 및 분석 중..."})
                prompt1 = REASONING_PROMPT_TEMPLATE.format(message=message) + guardrail_block
            
            reasoning_full = ""
            async for chunk in stream_chat_reply(
                user_message=prompt1, 
                context=context, 
                history=history, 
                custom_system_prompt=SYSTEM_PROMPT
            ):
                reasoning_full += chunk
                yield self.format_sse({"type": "thought", "content": chunk})
            
            # [IMPROVEMENT] '전략/채굴' 단어가 없으면 여기서 종료 (일반 대화 모드)
            if not enable_full_pipeline:
                # 생각 과정 완료 후 최종 응답 정리
                clean_response = reasoning_full.split("</thought>")[-1] if "</thought>" in reasoning_full else reasoning_full
                clean_response = clean_response.replace("[CHAT]", "").strip()
                
                yield self.format_sse({"type": "analysis", "content": clean_response})
                await db.save_chat_message(session_id, "assistant", clean_response, "text")
                yield self.format_sse({"type": "done"})
                return

            await db.save_chat_message(session_id, "assistant", reasoning_full, "thought")

            # STAGE 2: Design
            yield self.format_sse({"type": "stage", "stage": 2, "label": "📋 전략 설계도 작성 중..."})
            prompt2 = DESIGN_PROMPT_TEMPLATE.format(reasoning=reasoning_full) + guardrail_block
            design_full = ""
            async for chunk in stream_chat_reply(prompt2, {}, []):
                design_full += chunk
                yield self.format_sse({"type": "analysis", "content": chunk})
            await db.save_chat_message(session_id, "assistant", design_full, "text")

            # STAGE 3: Code
            yield self.format_sse({"type": "stage", "stage": 3, "label": "⚙️ Python 전략 코드 구현 중..."})
            prompt3 = CODE_PROMPT_TEMPLATE.format(design=design_full) + guardrail_block
            code_full = ""
            async for chunk in stream_chat_reply(prompt3, {}, []):
                code_full += chunk
            
            strategy_code = self.extract_python_code(code_full)
            if strategy_code:
                strategy_fingerprint = memory.compute_fingerprint(strategy_code) if memory else ""

                if memory and constitution:
                    dedupe_window = int((constitution.get("memory") or {}).get("dedupe_window", 120))
                    is_dup, dup_row = memory.is_duplicate(
                        target_agent,
                        strategy_fingerprint,
                        dedupe_window=dedupe_window,
                    )
                    if is_dup:
                        reason = f"duplicate_candidate_chat previous={dup_row.get('time') if dup_row else 'unknown'}"
                        memory.log_experiment(
                            agent_id=target_agent,
                            status="rejected_duplicate_chat",
                            stage="precheck",
                            reason=reason,
                            fingerprint=strategy_fingerprint,
                            metrics={},
                        )
                        memory.log_failure_pattern(
                            agent_id=target_agent,
                            reason=reason,
                            fingerprint=strategy_fingerprint,
                            metrics={},
                        )
                        yield self.format_sse({
                            "type": "analysis",
                            "content": "\n⚠️ 이전 실험과 거의 동일한 코드로 감지되어 중복 후보를 중단했습니다. 다른 구조로 다시 시도합니다.\n",
                        })
                        yield self.format_sse({"type": "done"})
                        return

                # [IMPROVEMENT] AI가 제안한 제목 추출
                strategy_title = self.extract_strategy_title(code_full)
                if strategy_title == "AI Generated Strategy":
                    strategy_title = self.extract_strategy_title(design_full)
                
                strategy_data = {
                    "title": strategy_title,
                    "code": strategy_code,
                    "params": {"agent_title": strategy_title}
                }
                yield self.format_sse({"type": "strategy", "data": strategy_data})
                await db.save_chat_message(session_id, "assistant", "", "strategy", strategy_data)

                # STAGE 4: Backtest
                yield self.format_sse({"type": "stage", "stage": 4, "label": "📈 백테스트 및 검증 중..."})
                
                if is_mining:
                    # 마이닝 모드: 고성능 에볼루션 엔진 가동
                    from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code
                    from server.shared.market.provider import fetch_ohlcv_dataframe, parse_date_to_ms
                    
                    symbol = context.get("symbol", "BTCUSDT")
                    timeframe = context.get("timeframe", "1h")
                    
                    # 데이터 수집 (최근 365일)
                    end_ms = int(datetime.now().timestamp() * 1000)
                    start_ms = end_ms - (365 * 24 * 60 * 60 * 1000)
                    
                    try:
                        yield self.format_sse({"type": "stage", "stage": 4, "label": "📊 마켓 데이터 수집 중..."})
                        df = fetch_ohlcv_dataframe(
                            symbol=symbol, 
                            interval=timeframe, 
                            limit=10000, 
                            start_ms=start_ms, 
                            end_ms=end_ms
                        )
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df.set_index('timestamp', inplace=True)
                        
                        engine = BacktestEngine(df, freq=24 if timeframe == '1h' else 1)
                        strategy_fn = strategy_from_code(strategy_code)
                        
                        # [Stage 4] 전략 검증 (WFO + Monte Carlo)
                        yield self.format_sse({"type": "analysis", "content": f"\n⚙️ **{persona['name']}** 에이전트가 고강도 검증을 시작합니다... (1년치 데이터 사용)\n"})
                        
                        import asyncio
                        queue = asyncio.Queue()
                        loop = asyncio.get_event_loop()
                        
                        def progress_callback(msg: str):
                            # 이 함수는 validator 내부 쓰레드에서 호출되므로 thread-safe하게 큐에 넣음
                            loop.call_soon_threadsafe(queue.put_nowait, msg)
                        
                        # 백테스트 실행을 별도 쓰레드로 분리하여 블로킹 방지
                        validation_task = asyncio.create_task(asyncio.to_thread(
                            engine.run_full_validation,
                            strategy_fn=strategy_fn, 
                            strategy_name="Mining Strategy",
                            run_test_set=False,
                            callback=progress_callback
                        ))
                        
                        # 큐에서 메세지를 꺼내 실시간으로 전송하면서 백테스트 태스크 대기
                        while not validation_task.done() or not queue.empty():
                            try:
                                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                                yield self.format_sse({"type": "analysis", "content": f"  {msg}\n"})
                            except asyncio.TimeoutError:
                                if validation_task.done(): break

                        validation_res = await validation_task
                        
                        # [Stage 5] 최종 품질 판정 및 금고 보관
                        yield self.format_sse({"type": "stage", "stage": 5, "label": "🏆 전략 품질 판정 및 금고 보관 중..."})
                        yield self.format_sse({"type": "analysis", "content": "🛡️ 모든 구간에 대한 견고함(Robustness) 판정 완료.\n"})
                        
                        # 결과 리포트 생성 및 점수화
                        report = validation_res.summary()
                        
                        # [NEW] 트리니티 점수 계산 (0~100)
                        # WFO 수익률 보존율, 샤프지수, 파산 확률 등을 종합
                        sharpe = sum([r.sharpe for r in validation_res.wfo_results]) / max(len(validation_res.wfo_results), 1)
                        mdd = max([abs(r.max_drawdown) for r in validation_res.wfo_results]) if validation_res.wfo_results else 1.0
                        ruin_score = (1.0 - (validation_res.monte_carlo.get("ruin_prob", 0.1))) * 100
                        
                        trinity_score = min(100, max(0, (sharpe * 30) + (ruin_score * 0.5) + (max(0, 20 - mdd*100))))
                        score_color = "🟢 GOOD" if trinity_score >= 70 else "🟡 FAIR" if trinity_score >= 40 else "🔴 RISKY"
                        
                        yield self.format_sse({"type": "analysis", "content": f"\n### 🛡️ 트리니티 전략 품질 점수: **{trinity_score:.1f}/100** ({score_color})\n"})
                        yield self.format_sse({"type": "analysis", "content": f"```text\n{report}\n```"})
                        
                        # [NEW] 성공한 전략 고정 저장 (DB 등록)
                        if validation_res.is_robust:
                            try:
                                db = SupabaseManager()
                                mining_key = f"mining_{datetime.now().strftime('%y%m%d_%H%M%S')}"
                                db.save_system_strategy(
                                    strategy_key=mining_key,
                                    code=strategy_code,
                                    params={
                                        "strategy_key": mining_key,
                                        "display_name": f"💎 [{persona['name']}] {seed}",
                                        "description": f"Mined via Chat: {persona['name']} | {seed}",
                                        "persona": persona['name'],
                                        "seed": seed
                                    },
                                    rationale=f"Mined via interactive evolution chat session. Trinity Score: {trinity_score:.1f}"
                                )
                                yield self.format_sse({"type": "analysis", "content": f"\n✅ 발굴된 전략이 시스템 금고(`{mining_key}`)에 안전하게 보관되었습니다."})
                            except Exception as save_err:
                                logger.error(f"Failed to save mined strategy: {save_err}")
                        else:
                            yield self.format_sse({"type": "analysis", "content": "\n⚠️ 견고함 기준에 미달하여 금고에 보관되지 않았습니다. 전략 보완이 필요합니다."})

                        # 차트용 데이터는 기존 ChatBacktester로 한 번 더 돌려서 획득 (UI 호환성)
                        chat_engine = ChatBacktester()
                        bt_res = await chat_engine.run(strategy_code, message, context)
                    except Exception as e:
                        logger.error(f"Mining backtest failed: {e}")
                        chat_engine = ChatBacktester()
                        bt_res = await chat_engine.run(strategy_code, message, context)
                else:
                    # 일반 모드: 기존 경량 백테스터 사용
                    engine = ChatBacktester()
                    bt_res = await engine.run(strategy_code, message, context)
                
                if bt_res.get("success"):
                    metrics = bt_res.get("metrics", {})
                    gate_metrics = self._normalize_metrics_for_gate(metrics)
                    hard_ok = True
                    hard_reasons: List[str] = []
                    if memory and constitution:
                        hard_ok, hard_reasons = evaluate_hard_gates(
                            gate_metrics,
                            constitution.get("hard_gates", {}),
                        )
                        status = "accepted_chat_gate" if hard_ok else "rejected_chat_gate"
                        reason = "hard_gate_passed" if hard_ok else "; ".join(hard_reasons)
                        fingerprint = memory.compute_fingerprint(strategy_code)
                        memory.log_experiment(
                            agent_id=target_agent,
                            status=status,
                            stage="chat_backtest",
                            reason=reason,
                            fingerprint=fingerprint,
                            metrics=gate_metrics,
                        )
                        if hard_ok:
                            memory.log_accepted(
                                agent_id=target_agent,
                                strategy_id=None,
                                fingerprint=fingerprint,
                                metrics=gate_metrics,
                            )
                        else:
                            memory.log_failure_pattern(
                                agent_id=target_agent,
                                reason=f"chat_hard_gate_failed: {reason}",
                                fingerprint=fingerprint,
                                metrics=gate_metrics,
                            )

                    backtest_data = {
                        "ret": f"{metrics.get('total_return', 0):+.2f}%",
                        "mdd": f"{metrics.get('max_drawdown', 0):.2f}%",
                        "winRate": f"{metrics.get('win_rate', 0):.1f}%",
                        "sharpe": f"{metrics.get('sharpe_ratio', 0):.2f}",
                    }
                    yield self.format_sse({
                        "type": "backtest", 
                        "data": backtest_data,
                        "payload": bt_res.get("backtest_payload")
                    })
                    await db.save_chat_message(session_id, "assistant", "", "backtest", backtest_data)

                    if not hard_ok:
                        yield self.format_sse({
                            "type": "analysis",
                            "content": (
                                "\n⚠️ 하드게이트 미통과 전략입니다. 자동 채택/배포 비권장.\n"
                                + "\n".join([f"- {r}" for r in hard_reasons])
                                + "\n"
                            ),
                        })
                    
                    # Tips
                    prompt4 = TIPS_PROMPT_TEMPLATE.format(metrics=metrics)
                    tips_full = ""
                    async for chunk in stream_chat_reply(prompt4, {}, []):
                        tips_full += chunk
                        yield self.format_sse({"type": "analysis", "content": chunk})
                    await db.save_chat_message(session_id, "assistant", tips_full, "text")
                    
                    self.log_strategy_to_file(message, metrics)
                else:
                    yield self.format_sse({"type": "error", "content": f"백테스트 실패: {bt_res.get('error')}"})

            yield self.format_sse({"type": "done"})

        except Exception as e:
            logger.exception("Pipeline execution error")
            yield self.format_sse({"type": "error", "content": str(e)})
