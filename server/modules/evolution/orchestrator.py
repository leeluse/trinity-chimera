import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from server.modules.backtest.evolution.evolution_engine import EvolutionEngine
from server.modules.evolution.agents import AgentStateManager, EvolutionState
from server.modules.evolution.constants import AGENT_IDS, ACTIVE_AGENT_IDS
from server.modules.evolution.llm import EvolutionLLM
from server.modules.evolution.scoring import (
    calculate_trinity_score,
    evaluate_hard_gates,
    evaluate_improvement,
)
from server.modules.evolution.trigger import EvolutionTrigger
from server.modules.evolution.wiki_memory import EvolutionWikiMemory
from server.shared.db.supabase import SupabaseManager
from server.shared.market.strategy_loader import SecurityError, StrategyLoader

logger = logging.getLogger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_ratio(value: float) -> float:
    # If ratio is likely given in percentage form, convert to decimal.
    if 1.0 < abs(value) <= 100.0:
        return value / 100.0
    return value


class EvolutionOrchestrator:
    # -------------------------------------------------------------------------
    # 시스템 초기화: DB 연결, LLM 클라이언트 및 에이전트 상태 관리자 생성
    # -------------------------------------------------------------------------
    def __init__(self):
        self.db = SupabaseManager()
        self.llm = EvolutionLLM()
        self.trigger_engine = EvolutionTrigger()
        self.agent_manager = AgentStateManager(list(AGENT_IDS), self.db)
        self.engine = EvolutionEngine()
        self.memory = EvolutionWikiMemory()
        self._manual_iteration = 0

        # per-agent 동시 실행 방지 Lock
        self._agent_locks: Dict[str, asyncio.Lock] = {}

        # LLM Circuit Breaker: 연속 실패 N회 시 일시 중단
        self._llm_consecutive_failures: int = 0
        self._llm_backoff_until: float = 0.0
        _LLM_FAILURE_THRESHOLD = 5
        _LLM_BACKOFF_SECONDS = 300
        self._LLM_FAILURE_THRESHOLD = _LLM_FAILURE_THRESHOLD
        self._LLM_BACKOFF_SECONDS = _LLM_BACKOFF_SECONDS

        # 성과 요약 통계
        self.stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
        }

    # -------------------------------------------------------------------------
    # 수동 루프 시작: UI의 RUN LOOP 호출용 iteration 카운트/로그
    # -------------------------------------------------------------------------
    def start_manual_loop(self, agent_ids: List[str]) -> int:
        self._manual_iteration += 1
        self.agent_manager.add_event(
            "info",
            "loop",
            f"—— ITERATION #{self._manual_iteration} 시작 ({len(agent_ids)} agents) ——",
            None,
        )
        return self._manual_iteration

    # -------------------------------------------------------------------------
    # 상태 조회: Router에서 await 호출하는 호환 메서드
    # -------------------------------------------------------------------------
    async def get_state(self, agent_id: str) -> EvolutionState:
        return self.agent_manager.get_state(agent_id)

    # -------------------------------------------------------------------------
    # 진화 한 주기 실행: 중복 차단 + 퀵게이트 + 풀게이트 + 채택
    # -------------------------------------------------------------------------
    async def run_evolution_cycle(
        self,
        agent_id: str,
        force: bool = False,
        force_trigger: Optional[bool] = None,
    ):
        if force_trigger is not None:
            force = bool(force_trigger)

        if agent_id not in AGENT_IDS:
            raise ValueError(f"Unknown agent_id: {agent_id}")

        label = self.agent_manager.resolve_label(agent_id)

        # 0-a) per-agent 중복 실행 방지
        if agent_id not in self._agent_locks:
            self._agent_locks[agent_id] = asyncio.Lock()
        lock = self._agent_locks[agent_id]
        if lock.locked():
            logger.info(f"[{label}] 이미 진화 사이클 실행 중, 스킵합니다.")
            return

        # 0-b) LLM Circuit Breaker: 연속 실패 임계 초과 시 대기
        if time.time() < self._llm_backoff_until:
            remaining = int(self._llm_backoff_until - time.time())
            logger.warning(f"[{label}] LLM Circuit Breaker 활성 — {remaining}초 후 재시도.")
            self.agent_manager.add_event(
                "warning",
                "skipped",
                f"[{label}] LLM 연속 실패로 Circuit Breaker 작동 중 ({remaining}초 남음). 자동 해제 대기.",
                agent_id,
            )
            return

        # 1) 트리거 체크
        if not force and not await self.trigger_engine.check_trigger(agent_id):
            logger.info(f"[{label}] 트리거 미충족, 스킵합니다.")
            self.agent_manager.add_event(
                "info",
                "skipped",
                f"[{label}] 아직 새로운 아이디어를 구상하기엔 일러요. 조금 더 시장을 지켜볼게요! 💤",
                agent_id,
            )
            return

        async with lock:
            await self._run_evolution_cycle_inner(agent_id, label, force)

    async def _run_evolution_cycle_inner(self, agent_id: str, label: str, force: bool):
        self.stats["total"] += 1
        self.agent_manager.set_state(agent_id, EvolutionState.TRIGGERED, "진화 트리거 통과")

        try:
            # 2) 현재 전략 로드
            self.agent_manager.set_state(agent_id, EvolutionState.GENERATING, "현재 전략/기준 성과 조회 중")
            strategy_data = await self.db.get_agent_strategy(agent_id)
            if not strategy_data:
                raise ValueError("현재 활성 전략을 찾을 수 없습니다.")
            prev_strategy_id = strategy_data.get("id")

            baseline_metrics = await self._load_baseline_metrics(strategy_data)
            constitution = self.memory.load_constitution()
            memory_cfg = constitution.get("memory", {})
            budgets_cfg = constitution.get("budgets", {})

            # L2 트리거: 현재 trinity_score가 목표의 80% 미달 시 HIGH 강도 변이
            baseline_trinity = float(baseline_metrics.get("trinity_score", 0) or 0)
            target_score = float((constitution.get("hard_gates") or {}).get("min_trinity_score", 30.0))
            if self.trigger_engine.check_performance_decay(baseline_trinity, target_score, threshold=0.8):
                trigger_level = "L2"
            elif baseline_trinity == 0 or int(baseline_metrics.get("total_trades", 0)) == 0:
                trigger_level = "L2"   # 전략 없음 = 최고 강도
            else:
                trigger_level = "L4"   # 일반 주기적 업데이트
            evolution_intensity = self.trigger_engine.get_intensity(trigger_level)

            max_candidates = max(1, min(int(budgets_cfg.get("max_candidates_per_cycle", 5)), 12))
            max_llm_calls = max(1, min(int(budgets_cfg.get("max_llm_calls_per_cycle", 5)), 12))
            attempts_budget = min(max_candidates, max_llm_calls)
            dedupe_window = max(10, min(int(memory_cfg.get("dedupe_window", 120)), 500))

            self.agent_manager.add_event(
                "info",
                "baseline",
                (
                    f"[{label}] baseline: score={baseline_metrics.get('trinity_score', 0):.3f}, "
                    f"win={baseline_metrics.get('win_rate', 0):.3f}, "
                    f"pf={baseline_metrics.get('profit_factor', 0):.3f}"
                ),
                agent_id,
                meta={
                    "decision": {
                        "result": "baseline_loaded",
                        "stage": "baseline",
                        "hard_gates": constitution.get("hard_gates", {}),
                        "quick_gates": constitution.get("quick_gates", {}),
                        "attempt_budget": attempts_budget,
                    },
                    "metrics": baseline_metrics,
                },
            )
            await self._persist_db_log(
                agent_id=agent_id,
                analysis=f"[baseline] score={baseline_metrics.get('trinity_score', 0):.3f}",
                expected={
                    "decision": {
                        "result": "baseline_loaded",
                        "stage": "baseline",
                        "attempt_budget": attempts_budget,
                    },
                    "baseline_metrics": baseline_metrics,
                    "metrics": baseline_metrics,
                },
                prev_strategy_id=prev_strategy_id,
                new_strategy_id=None,
            )

            last_reason = "no_candidate"
            blocked_fingerprints: List[str] = []

            for attempt in range(1, attempts_budget + 1):
                # 3) 후보 생성
                self.agent_manager.set_state(
                    agent_id,
                    EvolutionState.GENERATING,
                    f"후보 코드 생성 {attempt}/{attempts_budget}",
                )
                self.agent_manager.add_event(
                    "info",
                    "generating",
                    f"[{label}] 후보 생성 시작 ({attempt}/{attempts_budget})",
                    agent_id,
                    meta={
                        "decision": {
                            "result": "candidate_generation",
                            "stage": "generate",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                        }
                    },
                )

                memory_context = self.memory.build_prompt_context(agent_id, constitution)
                attempt_mutation = str(memory_context.get("next_mutation") or "").strip()
                evolution_package = self._build_evolution_package(
                    agent_id=agent_id,
                    strategy_data=strategy_data,
                    baseline_metrics=baseline_metrics,
                    memory_context=memory_context,
                    constitution=constitution,
                    attempt=attempt,
                    last_reason=last_reason,
                    blocked_fingerprints=blocked_fingerprints[-8:],
                    trigger_level=trigger_level,
                    intensity=evolution_intensity,
                )

                try:
                    new_code = await self.llm.generate_improved_code(
                        evolution_package,
                        max_retries=2,
                    )
                    self._llm_consecutive_failures = 0
                except Exception as exc:
                    self._llm_consecutive_failures += 1
                    if self._llm_consecutive_failures >= self._LLM_FAILURE_THRESHOLD:
                        self._llm_backoff_until = time.time() + self._LLM_BACKOFF_SECONDS
                        logger.error(
                            f"[{label}] LLM 연속 {self._llm_consecutive_failures}회 실패 — "
                            f"Circuit Breaker 작동, {self._LLM_BACKOFF_SECONDS}초 대기."
                        )
                        self.agent_manager.add_event(
                            "error",
                            "circuit_breaker",
                            f"[{label}] LLM 연속 실패 {self._llm_consecutive_failures}회 — Circuit Breaker 작동 ({self._LLM_BACKOFF_SECONDS}초).",
                            agent_id,
                        )
                    last_reason = f"llm_generation_error: {exc}"
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="error_generation",
                        stage="generate",
                        reason=last_reason,
                        code="",
                        metrics=None,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    continue

                fingerprint = self.memory.compute_fingerprint(new_code)
                selected_mode = evolution_package.get("_selected_mode")
                self.agent_manager.add_event(
                    "info",
                    "generated",
                    f"[{label}] 후보 코드 생성 완료 ({attempt}/{attempts_budget}, hash={fingerprint[:12]})",
                    agent_id,
                    meta={
                        "decision": {
                            "result": "candidate_generated",
                            "stage": "generate",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                        }
                    },
                )
                await self._persist_db_log(
                    agent_id=agent_id,
                    analysis=f"[generated] attempt={attempt}/{attempts_budget} hash={fingerprint[:12]}",
                    expected={
                        "decision": {
                            "result": "candidate_generated",
                            "stage": "generate",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                        },
                    },
                    prev_strategy_id=prev_strategy_id,
                    new_strategy_id=None,
                )

                # 3.1) 중복 차단
                is_dup, dup_row = self.memory.is_duplicate(
                    agent_id=agent_id,
                    fingerprint=fingerprint,
                    dedupe_window=dedupe_window,
                )
                if is_dup:
                    prev_time = dup_row.get("time") if isinstance(dup_row, dict) else "unknown"
                    last_reason = f"duplicate_candidate (previous={prev_time})"
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_duplicate",
                        stage="precheck",
                        reason=last_reason,
                        code=new_code,
                        metrics=None,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                # 3.2) 정적 게이트
                try:
                    StrategyLoader.validate_code(new_code)
                except SecurityError as exc:
                    last_reason = f"static_gate_failed: {exc}"
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_static",
                        stage="precheck",
                        reason=last_reason,
                        code=new_code,
                        metrics=None,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                # 4) 퀵 게이트
                self.agent_manager.set_state(agent_id, EvolutionState.VALIDATING, "퀵 게이트 백테스트")
                quick_res = await self.engine.run(
                    new_code,
                    agent_id,
                    {"agent_id": agent_id, "quick_mode": True},
                )
                if not quick_res.get("success"):
                    last_reason = f"quick_backtest_failed: {quick_res.get('error')}"
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_quick_error",
                        stage="quick_gate",
                        reason=last_reason,
                        code=new_code,
                        metrics=None,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                quick_metrics = self._normalize_metrics(quick_res.get("metrics", {}))
                quick_ok, quick_reasons = evaluate_hard_gates(
                    quick_metrics,
                    constitution.get("quick_gates", {}),
                )
                self.agent_manager.add_event(
                    "info" if quick_ok else "warning",
                    "validation",
                    f"[{label}] 퀵 게이트 {'통과! 다음 단계로 넘어갑니다.' if quick_ok else '통과 실패, 다시 고민해볼게요.'}",
                    agent_id,
                    meta={
                        "decision": {
                            "result": "quick_gate_passed" if quick_ok else "quick_gate_failed",
                            "stage": "quick_gate",
                            "attempt": attempt,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "gate_reasons": quick_reasons,
                            "gate_thresholds": constitution.get("quick_gates", {}),
                        },
                        "metrics": quick_metrics,
                    },
                )
                await self._persist_db_log(
                    agent_id=agent_id,
                    analysis=(
                        f"[quick_gate] {'pass' if quick_ok else 'fail'} "
                        f"attempt={attempt}/{attempts_budget}"
                    ),
                    expected={
                        "decision": {
                            "result": "quick_gate_passed" if quick_ok else "quick_gate_failed",
                            "stage": "quick_gate",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "gate_reasons": quick_reasons,
                            "gate_thresholds": constitution.get("quick_gates", {}),
                        },
                        "metrics": quick_metrics,
                        "baseline_metrics": baseline_metrics,
                    },
                    prev_strategy_id=prev_strategy_id,
                    new_strategy_id=None,
                )
                if not quick_ok:
                    last_reason = "quick_gate_failed: " + "; ".join(quick_reasons)
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_quick_gate",
                        stage="quick_gate",
                        reason=last_reason,
                        code=new_code,
                        metrics=quick_metrics,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                                "gate_reasons": quick_reasons,
                                "gate_thresholds": constitution.get("quick_gates", {}),
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                # 5) 풀 게이트
                self.agent_manager.set_state(agent_id, EvolutionState.VALIDATING, "풀 게이트 백테스트")
                full_res = await self.engine.run(
                    new_code,
                    agent_id,
                    {"agent_id": agent_id, "quick_mode": False},
                )
                if not full_res.get("success"):
                    last_reason = f"full_backtest_failed: {full_res.get('error')}"
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_full_error",
                        stage="full_gate",
                        reason=last_reason,
                        code=new_code,
                        metrics=None,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                            }
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                candidate_metrics = self._normalize_metrics(full_res.get("metrics", {}))
                hard_ok, hard_reasons = evaluate_hard_gates(
                    candidate_metrics,
                    constitution.get("hard_gates", {}),
                )
                improved = evaluate_improvement(baseline_metrics, candidate_metrics)
                improvements = self._build_improvement_summary(baseline_metrics, candidate_metrics)
                self.agent_manager.add_event(
                    "info" if hard_ok else "warning",
                    "validation",
                    f"[{label}] 풀 게이트 {'통과! 최종 검증 중입니다.' if hard_ok else '통과 실패, 아쉽네요.'}",
                    agent_id,
                    meta={
                        "decision": {
                            "result": "full_gate_passed" if hard_ok else "full_gate_failed",
                            "stage": "full_gate",
                            "attempt": attempt,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "gate_reasons": hard_reasons,
                            "gate_thresholds": constitution.get("hard_gates", {}),
                            "improved": improved,
                            "improvement_summary": improvements,
                        },
                        "baseline_metrics": baseline_metrics,
                        "metrics": candidate_metrics,
                        "verdict": str(full_res.get("verdict") or ""),
                    },
                )
                await self._persist_db_log(
                    agent_id=agent_id,
                    analysis=(
                        f"[full_gate] {'pass' if hard_ok else 'fail'} "
                        f"improved={improved} attempt={attempt}/{attempts_budget}"
                    ),
                    expected={
                        "decision": {
                            "result": "full_gate_passed" if hard_ok else "full_gate_failed",
                            "stage": "full_gate",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "gate_reasons": hard_reasons,
                            "gate_thresholds": constitution.get("hard_gates", {}),
                            "improved": improved,
                            "improvement_summary": improvements,
                        },
                        "baseline_metrics": baseline_metrics,
                        "metrics": candidate_metrics,
                        "verdict": str(full_res.get("verdict") or ""),
                    },
                    prev_strategy_id=prev_strategy_id,
                    new_strategy_id=None,
                )

                if not hard_ok:
                    last_reason = "hard_gate_failed: " + "; ".join(hard_reasons)
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_hard_gate",
                        stage="full_gate",
                        reason=last_reason,
                        code=new_code,
                        metrics=candidate_metrics,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                                "gate_reasons": hard_reasons,
                                "gate_thresholds": constitution.get("hard_gates", {}),
                                "improved": improved,
                                "improvement_summary": improvements,
                            },
                            "baseline_metrics": baseline_metrics,
                            "verdict": str(full_res.get("verdict") or ""),
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                if not improved:
                    last_reason = (
                        f"no_oos_improvement baseline={baseline_metrics.get('trinity_score', 0):.3f} "
                        f"candidate={candidate_metrics.get('trinity_score', 0):.3f}"
                    )
                    await self._record_rejection(
                        agent_id=agent_id,
                        status="rejected_no_improvement",
                        stage="decision",
                        reason=last_reason,
                        code=new_code,
                        metrics=candidate_metrics,
                        details={
                            "decision": {
                                "result": "rejected",
                                "attempt": attempt,
                                "attempt_budget": attempts_budget,
                                "llm_mode": selected_mode,
                                "fingerprint": fingerprint[:12],
                                "improved": False,
                                "improvement_summary": improvements,
                            },
                            "baseline_metrics": baseline_metrics,
                            "verdict": str(full_res.get("verdict") or ""),
                        },
                        prev_strategy_id=prev_strategy_id,
                        mutation_hint=attempt_mutation,
                    )
                    if fingerprint not in blocked_fingerprints:
                        blocked_fingerprints.append(fingerprint)
                    continue

                # 6) 채택/저장
                self.agent_manager.set_state(agent_id, EvolutionState.COMMITTING, "채택 전략 저장/로그 반영 중")
                new_strategy_id = await self._commit_candidate(
                    agent_id=agent_id,
                    prev_strategy=strategy_data,
                    code=new_code,
                    candidate_metrics=candidate_metrics,
                    baseline_metrics=baseline_metrics,
                    verdict=str(full_res.get("verdict") or ""),
                    expected_payload={
                        "decision": {
                            "result": "accepted",
                            "stage": "decision",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "improved": True,
                            "improvement_summary": improvements,
                        },
                        "baseline": baseline_metrics,
                        "candidate": candidate_metrics,
                        "verdict": str(full_res.get("verdict") or ""),
                    },
                )

                self.memory.log_experiment(
                    agent_id=agent_id,
                    status="accepted",
                    stage="decision",
                    reason=f"accepted attempt={attempt}",
                    fingerprint=fingerprint,
                    metrics=candidate_metrics,
                    mutation_hint=attempt_mutation,
                )
                self.memory.log_accepted(
                    agent_id=agent_id,
                    strategy_id=new_strategy_id,
                    fingerprint=fingerprint,
                    metrics=candidate_metrics,
                )

                self.stats["completed"] += 1
                self.agent_manager.add_event(
                    "success",
                    "completed",
                    f"🎉 축하합니다! {label} 에이전트가 새로운 전략으로 무장하여 더 똑똑해졌어요! 🚀",
                    agent_id,
                    meta={
                        "decision": {
                            "result": "accepted",
                            "stage": "decision",
                            "attempt": attempt,
                            "attempt_budget": attempts_budget,
                            "llm_mode": selected_mode,
                            "fingerprint": fingerprint[:12],
                            "improved": True,
                            "improvement_summary": improvements,
                            "strategy_id": new_strategy_id,
                        },
                        "baseline_metrics": baseline_metrics,
                        "metrics": candidate_metrics,
                        "verdict": str(full_res.get("verdict") or ""),
                    },
                )
                return

            # 후보 전량 거절
            self.stats["failed"] += 1
            self.agent_manager.add_event(
                "warning",
                "rejected",
                f"[{label}] 이번엔 적합한 전략을 찾지 못했어요. 다음 기회를 노려볼게요! 🛡️",
                agent_id,
            )

        except Exception as exc:
            logger.exception(f"[{label}] 진화 루프 중 에러 발생")
            self.stats["failed"] += 1
            self.agent_manager.add_event(
                "error",
                "failed",
                f"[{label}] 에러: {str(exc)}",
                agent_id,
            )
        finally:
            self.agent_manager.set_state(agent_id, EvolutionState.IDLE)

    async def _record_rejection(
        self,
        agent_id: str,
        status: str,
        stage: str,
        reason: str,
        code: str,
        metrics: Optional[Dict[str, Any]],
        details: Optional[Dict[str, Any]] = None,
        prev_strategy_id: Optional[str] = None,
        mutation_hint: Optional[str] = None,
    ) -> None:
        fingerprint = self.memory.compute_fingerprint(code)
        self.memory.log_experiment(
            agent_id=agent_id,
            status=status,
            stage=stage,
            reason=reason,
            fingerprint=fingerprint,
            metrics=metrics or {},
            mutation_hint=mutation_hint,
        )
        self.memory.log_failure_pattern(
            agent_id=agent_id,
            reason=reason,
            fingerprint=fingerprint,
            metrics=metrics or {},
        )
        label = self.agent_manager.resolve_label(agent_id)
        meta: Dict[str, Any] = {
            "decision": {
                "result": "rejected",
                "status": status,
                "stage": stage,
                "reason": reason,
                "fingerprint": fingerprint[:12],
            },
            "metrics": metrics or {},
        }
        if isinstance(details, dict):
            for key, value in details.items():
                if key == "decision" and isinstance(value, dict):
                    current = meta.get("decision")
                    if not isinstance(current, dict):
                        current = {}
                    current.update(value)
                    meta["decision"] = current
                else:
                    meta[key] = value
        self.agent_manager.add_event(
            "warning",
            "decision",
            f"[{label}] 후보 거절({stage}): {reason[:220]}",
            agent_id,
            meta=meta,
        )
        await self._persist_db_log(
            agent_id=agent_id,
            analysis=f"[reject:{stage}] {reason}",
            expected={
                "decision": meta.get("decision") or {},
                "metrics": meta.get("metrics") or {},
                "baseline_metrics": meta.get("baseline_metrics") or {},
                "verdict": meta.get("verdict") or "",
            },
            prev_strategy_id=prev_strategy_id,
            new_strategy_id=None,
        )

    async def _persist_db_log(
        self,
        agent_id: str,
        analysis: str,
        expected: Dict[str, Any],
        prev_strategy_id: Optional[str] = None,
        new_strategy_id: Optional[str] = None,
    ) -> None:
        try:
            await self.db.save_improvement_log(
                agent_id=agent_id,
                prev_id=prev_strategy_id,
                new_id=new_strategy_id,
                analysis=analysis,
                expected=expected if isinstance(expected, dict) else {},
            )
        except Exception as exc:
            logger.debug(f"[{agent_id}] DB log persist skipped: {exc}")

    async def _load_baseline_metrics(self, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        strategy_id = strategy_data.get("id")
        if strategy_id:
            try:
                bt = await self.db.get_backtest_for_period(strategy_id=strategy_id, period_type="OOS")
                if bt:
                    metrics = {
                        "total_return": _to_float(bt.get("return"), 0.0),
                        "sharpe_ratio": _to_float(bt.get("sharpe"), 0.0),
                        "max_drawdown": _to_float(bt.get("mdd"), 0.0),
                        "win_rate": _to_float(bt.get("win_rate"), 0.0),
                        "profit_factor": _to_float(bt.get("profit_factor"), 0.0),
                        "total_trades": int(_to_float(bt.get("total_trades"), 0)),
                    }
            except Exception:
                metrics = {}

        if not metrics:
            raw = strategy_data.get("metrics", {})
            if not isinstance(raw, dict):
                raw = {}
            metrics = {
                "total_return": _to_float(raw.get("total_return"), 0.0),
                "sharpe_ratio": _to_float(raw.get("sharpe_ratio"), 0.0),
                "max_drawdown": _to_float(raw.get("max_drawdown"), 0.0),
                "win_rate": _to_float(raw.get("win_rate"), 0.0),
                "profit_factor": _to_float(raw.get("profit_factor"), 0.0),
                "total_trades": int(_to_float(raw.get("total_trades"), 0)),
            }

        return self._normalize_metrics(metrics)

    async def _commit_candidate(
        self,
        agent_id: str,
        prev_strategy: Dict[str, Any],
        code: str,
        candidate_metrics: Dict[str, Any],
        baseline_metrics: Dict[str, Any],
        verdict: str,
        expected_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        prev_strategy_id = prev_strategy.get("id")
        params = prev_strategy.get("params", {})
        if not isinstance(params, dict):
            params = {}
        params = dict(params)
        params["metrics"] = candidate_metrics
        params["evolution_meta"] = {
            "baseline_trinity": baseline_metrics.get("trinity_score"),
            "candidate_trinity": candidate_metrics.get("trinity_score"),
            "accepted_at": datetime.utcnow().isoformat() + "Z",
        }

        rationale = (
            "Auto evolution accepted. "
            f"baseline={baseline_metrics.get('trinity_score', 0):.3f}, "
            f"candidate={candidate_metrics.get('trinity_score', 0):.3f}. "
            f"{verdict}"
        )

        new_strategy_id = await self.db.save_strategy(
            agent_id=agent_id,
            code=code,
            rationale=rationale,
            params=params,
        )

        if new_strategy_id:
            await self.db.save_backtest(
                strategy_id=new_strategy_id,
                metrics={
                    "trinity_score": candidate_metrics.get("trinity_score", 0.0),
                    "return": candidate_metrics.get("total_return", 0.0),
                    "sharpe": candidate_metrics.get("sharpe_ratio", 0.0),
                    "mdd": candidate_metrics.get("max_drawdown", 0.0),
                    "win_rate": candidate_metrics.get("win_rate", 0.0),
                    "test_period": {"type": "OOS", "source": "evolution_full_gate"},
                },
            )

            await self.db.save_improvement_log(
                agent_id=agent_id,
                prev_id=prev_strategy_id,
                new_id=new_strategy_id,
                analysis=verdict or "Auto evolution accepted via hard gate + improvement check.",
                expected=expected_payload
                if isinstance(expected_payload, dict)
                else {
                    "baseline": baseline_metrics,
                    "candidate": candidate_metrics,
                },
            )
        return new_strategy_id

    def _normalize_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        total_return = _normalize_ratio(_to_float(raw_metrics.get("total_return"), 0.0))
        sharpe_ratio = _to_float(raw_metrics.get("sharpe_ratio"), 0.0)
        max_drawdown = _to_float(raw_metrics.get("max_drawdown"), 0.0)
        if max_drawdown > 0:
            max_drawdown = -_normalize_ratio(max_drawdown)
        elif max_drawdown < -1:
            max_drawdown = max_drawdown / 100.0

        win_rate = _normalize_ratio(_to_float(raw_metrics.get("win_rate"), 0.0))
        profit_factor = _to_float(raw_metrics.get("profit_factor"), 0.0)
        total_trades = int(_to_float(raw_metrics.get("total_trades"), 0))

        trinity_score = _to_float(
            raw_metrics.get("trinity_score"),
            calculate_trinity_score(total_return, sharpe_ratio, max_drawdown),
        )

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "trinity_score": trinity_score,
        }

    def _build_improvement_summary(
        self,
        baseline: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        def _entry(
            key: str,
            label: str,
            ratio: bool = False,
            invert_sign: bool = False,
        ) -> Dict[str, Any]:
            b = float(baseline.get(key, 0.0) or 0.0)
            c = float(candidate.get(key, 0.0) or 0.0)
            delta = c - b
            if invert_sign:
                # drawdown은 절댓값이 낮을수록 개선이므로 표기상 반전
                delta = -delta

            if ratio:
                b_disp = f"{b * 100:.2f}%"
                c_disp = f"{c * 100:.2f}%"
                d_disp = f"{delta * 100:+.2f}%"
            elif key == "total_trades":
                b_disp = str(int(round(b)))
                c_disp = str(int(round(c)))
                d_disp = f"{delta:+.0f}"
            else:
                b_disp = f"{b:.3f}"
                c_disp = f"{c:.3f}"
                d_disp = f"{delta:+.3f}"

            return {
                "metric": key,
                "label": label,
                "baseline": b,
                "candidate": c,
                "delta": delta,
                "baseline_display": b_disp,
                "candidate_display": c_disp,
                "delta_display": d_disp,
            }

        return [
            _entry("trinity_score", "Trinity Score"),
            _entry("total_return", "Total Return", ratio=True),
            _entry("win_rate", "Win Rate", ratio=True),
            _entry("profit_factor", "Profit Factor"),
            _entry("sharpe_ratio", "Sharpe Ratio"),
            _entry("max_drawdown", "Max Drawdown", ratio=True, invert_sign=True),
            _entry("total_trades", "Total Trades"),
        ]

    # -------------------------------------------------------------------------
    # 진화 데이터 패키징: LLM에게 현재 전략과 성과 지표를 묶어 전달
    # -------------------------------------------------------------------------
    def _build_evolution_package(
        self,
        agent_id: str,
        strategy_data: Dict[str, Any],
        baseline_metrics: Dict[str, Any],
        memory_context: Dict[str, Any],
        constitution: Dict[str, Any],
        attempt: int,
        last_reason: Optional[str] = None,
        blocked_fingerprints: Optional[List[str]] = None,
        trigger_level: str = "L4",
        intensity: str = "LOW (Tuning)",
    ) -> Dict[str, Any]:
        return {
            "current_strategy_code": strategy_data.get("code", ""),
            "metrics": {
                "trinity_score": baseline_metrics.get("trinity_score", 0.0),
                "return": baseline_metrics.get("total_return", 0.0),
                "mdd": baseline_metrics.get("max_drawdown", 0.0),
                "win_rate": baseline_metrics.get("win_rate", 0.0),
                "profit_factor": baseline_metrics.get("profit_factor", 0.0),
                "total_trades": baseline_metrics.get("total_trades", 0),
            },
            "agent_id": agent_id,
            "evolution_count": self.memory.get_agent_attempt_count(agent_id),
            "attempt": attempt,
            "memory_context": memory_context,
            "constitution": constitution,
            "last_reason": (last_reason or "").strip(),
            "blocked_fingerprints": list(blocked_fingerprints or []),
            # 트리거 강도: LLM이 변이 폭을 결정할 때 사용
            "trigger_level": trigger_level,
            "intensity": intensity,
            "_selected_mode": intensity,
        }

    # -------------------------------------------------------------------------
    # 대시보드 상태 요약: 모든 에이전트의 현재 진척도와 성공/실패 통계 반환
    # -------------------------------------------------------------------------
    def get_dashboard_snapshot(self) -> Dict[str, Any]:
        snapshot = self.agent_manager.get_snapshot()
        return {
            "total_improvements": self.stats["total"],
            "completed_improvements": self.stats["completed"],
            "failed_improvements": self.stats["failed"],
            "active_improvements": snapshot.get("active_improvements", 0),
            "agents": snapshot.get("agents", list(AGENT_IDS)),
            "active_agents": list(ACTIVE_AGENT_IDS),
            "latest_improvements": snapshot.get("latest_improvements", []),
        }

    def get_evolution_events(self, limit: int = 120, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if hasattr(self.agent_manager, "get_events"):
            return self.agent_manager.get_events(limit=limit, agent_id=agent_id)
        return []


# 싱글톤 인스턴스 관리 (thread-safe)
_orchestrator: Optional[EvolutionOrchestrator] = None
_orchestrator_lock = __import__("threading").Lock()


def get_evolution_orchestrator() -> EvolutionOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:          # double-checked locking
                _orchestrator = EvolutionOrchestrator()
    return _orchestrator
