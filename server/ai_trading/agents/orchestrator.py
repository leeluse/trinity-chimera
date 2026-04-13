import logging
import ast
import os
from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from collections import deque

import pandas as pd
import numpy as np

from dotenv import load_dotenv

from server.api.services.supabase_client import SupabaseManager

from .llm_client import EvolutionLLMClient, LLMUnavailableError, build_default_llm_service
from .trigger import EvolutionTrigger
from .constants import AGENT_IDS

try:
    from server.ai_trading.core.strategy_loader import StrategyLoader
    from server.ai_trading.core.backtest_manager import BacktestManager
    from server.ai_trading.core.metrics_buffer import MetricsBuffer
    from server.ai_trading.core.strategy_interface import StrategyInterface
except ImportError:
    class MetricsBuffer:
        def __init__(self, trigger_callback=None):
            self._trigger_callback = trigger_callback

        def set_callback(self, callback):
            self._trigger_callback = callback

        async def push(self, agent_id: str, tick: Any) -> Optional[str]:
            """No-op fallback push"""
            return None

    class StrategyLoader:
        @staticmethod
        def load_strategy(code: str):
            return True

        @staticmethod
        def validate_code(code: str):
            pass

    class BacktestManager:
        def validate_strategy(self, strategy: Any, data: pd.DataFrame, train_days: int = 60, val_days: int = 30):
            return {
                "is_metrics": {"trinity_score": 100.0},
                "oos_metrics": {
                    "trinity_score": 110.0,
                    "return": 0.12,
                    "sharpe": 1.4,
                    "mdd": -0.08,
                    "win_rate": 0.56,
                    "profit_factor": 1.3,
                    "trades": 40,
                },
            }

    class StrategyInterface:
        def generate_signal(self, data):
            return 0

        def get_params(self):
            return {}

logger = logging.getLogger(__name__)

class EvolutionState(Enum):
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMMITTING = "COMMITTING"


class EvolutionOrchestrator:
    def __init__(self):
        self.llm_client = EvolutionLLMClient(llm_service=build_default_llm_service())
        self.trigger_engine = EvolutionTrigger()
        self.supabase = SupabaseManager()
        self.backtest_manager = BacktestManager()
        self.metrics_buffer = MetricsBuffer()  # 신규 추가
        self.metrics_buffer.set_callback(self._on_metrics_buffer_trigger)  # 콜백 설정
        self.states: Dict[str, EvolutionState] = {}
        self.total_improvements = 0
        self.completed_improvements = 0
        self.failed_improvements = 0
        self._latest_improvements: Dict[str, Dict[str, Any]] = {}
        self._event_seq = 0
        self._loop_iteration = 0
        self._event_logs: deque = deque(maxlen=600)
        self._agent_name_cache: Dict[str, str] = {}
        self._refresh_agent_name_cache()
        self._append_event(
            level="system",
            phase="boot",
            message="시스템 초기화 완료. 루프 실행 대기 중.",
        )

    def _agent_label(self, agent_id: str, refresh: bool = False) -> str:
        if not refresh:
            cached = self._agent_name_cache.get(agent_id)
            if cached:
                return cached

        resolved_name = agent_id
        try:
            if hasattr(self.supabase, "_resolve_agent_row"):
                row = self.supabase._resolve_agent_row(agent_id)
                candidate = (row or {}).get("name")
                if isinstance(candidate, str) and candidate.strip():
                    resolved_name = candidate.strip()
        except Exception as exc:
            logger.debug("Failed to resolve agent label from DB for %s: %s", agent_id, exc)

        self._agent_name_cache[agent_id] = resolved_name
        return resolved_name

    def _refresh_agent_name_cache(self):
        for agent_id in AGENT_IDS:
            self._agent_label(agent_id, refresh=True)

    def _append_event(
        self,
        level: str,
        phase: str,
        message: str,
        agent_id: Optional[str] = None,
    ):
        self._event_seq += 1
        self._event_logs.append(
            {
                "id": self._event_seq,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "level": level,
                "phase": phase,
                "message": message,
                "agent_id": agent_id,
                "agent_label": self._agent_label(agent_id) if agent_id else None,
            }
        )

    def start_manual_loop(self, agent_ids: List[str]) -> int:
        self._refresh_agent_name_cache()
        self._loop_iteration += 1
        iteration = self._loop_iteration
        self._append_event(
            level="system",
            phase="loop",
            message=f"━━ ITERATION #{iteration} 시작 ━━",
        )
        for agent_id in agent_ids:
            label = self._agent_label(agent_id)
            self._append_event(
                level="queued",
                phase="queued",
                message=f"[{label}] 전략 분석 요청 중...",
                agent_id=agent_id,
            )
        return iteration

    def start_scheduled_loop(self, agent_ids: List[str]) -> int:
        self._refresh_agent_name_cache()
        self._loop_iteration += 1
        iteration = self._loop_iteration
        self._append_event(
            level="system",
            phase="loop",
            message=f"━━ AUTO ITERATION #{iteration} 시작 ━━",
        )
        for agent_id in agent_ids:
            label = self._agent_label(agent_id)
            self._append_event(
                level="queued",
                phase="queued",
                message=f"[{label}] 자동 루프 분석 요청 중...",
                agent_id=agent_id,
            )
        return iteration

    def get_evolution_events(self, limit: int = 120, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        logs = list(self._event_logs)
        if agent_id:
            logs = [event for event in logs if event.get("agent_id") == agent_id]
        logs.reverse()  # newest first
        return logs[: max(1, min(limit, 500))]

    @staticmethod
    def _extract_class_name(code: str) -> Optional[str]:
        try:
            tree = ast.parse(code)
        except Exception:
            return None

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                return node.name
        return None

    @staticmethod
    def _build_validation_data(periods: int = 24 * 120) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        returns = rng.normal(0.0002, 0.01, periods)
        prices = 50000 * np.exp(np.cumsum(returns))
        dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=periods, freq="h")

        return pd.DataFrame(
            {
                "open": prices * (1 + rng.normal(0, 0.001, periods)),
                "high": prices * (1 + np.abs(rng.normal(0, 0.002, periods))),
                "low": prices * (1 - np.abs(rng.normal(0, 0.002, periods))),
                "close": prices,
                "volume": rng.integers(1000000, 10000000, periods),
            },
            index=dates,
        )

    def _record_latest(self, agent_id: str, status: str, progress: int, detail: Optional[str] = None):
        self._latest_improvements[agent_id] = {
            "agent_id": agent_id,
            "status": status,
            "progress": progress,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "detail": detail,
        }

    def _set_state(self, agent_id: str, state: EvolutionState):
        self.states[agent_id] = state
        mapping = {
            EvolutionState.TRIGGERED: ("triggered", 15),
            EvolutionState.GENERATING: ("generating", 45),
            EvolutionState.VALIDATING: ("backtesting", 75),
            EvolutionState.COMMITTING: ("committing", 90),
            EvolutionState.IDLE: ("idle", 0),
        }
        status, progress = mapping.get(state, ("idle", 0))
        if state != EvolutionState.IDLE:
            self._record_latest(agent_id, status, progress)
            label = self._agent_label(agent_id)
            phase_message = {
                EvolutionState.TRIGGERED: f"[{label}] 트리거 감지",
                EvolutionState.GENERATING: f"[{label}] 후보 전략 생성 중...",
                EvolutionState.VALIDATING: f"[{label}] 백테스트/검증 진행 중...",
                EvolutionState.COMMITTING: f"[{label}] 개선 전략 반영 중...",
            }.get(state)
            if phase_message:
                self._append_event(
                    level="info",
                    phase=status,
                    message=phase_message,
                    agent_id=agent_id,
                )

    def get_dashboard_snapshot(self) -> Dict[str, Any]:
        latest = []
        now = datetime.utcnow().isoformat() + "Z"
        for agent_id in AGENT_IDS:
            latest.append(
                self._latest_improvements.get(
                    agent_id,
                    {
                        "agent_id": agent_id,
                        "status": "idle",
                        "progress": 0,
                        "created_at": now,
                    },
                )
            )

        active_improvements = sum(1 for item in latest if item.get("status") not in {"idle", "completed", "failed"})
        return {
            "active_improvements": active_improvements,
            "completed_improvements": self.completed_improvements,
            "failed_improvements": self.failed_improvements,
            "total_improvements": self.total_improvements,
            "agents": list(AGENT_IDS),
            "latest_improvements": latest,
        }

    async def _on_metrics_buffer_trigger(self, agent_id: str, metrics_entries: List):
        """Handle MetricsBuffer trigger"""
        try:
            if self.states.get(agent_id) != EvolutionState.IDLE:
                self._append_event(
                    level="warning",
                    phase="skipped",
                    message=f"[{self._agent_label(agent_id)}] 실행 중이어서 MetricsBuffer 트리거를 건너뜀.",
                    agent_id=agent_id,
                )
                return  # 이미 진행 중인 에이전트는 건너뜀

            await self.run_evolution_cycle(agent_id, force_trigger=True)
        except Exception as e:
            self._append_event(
                level="error",
                phase="error",
                message=f"[{self._agent_label(agent_id)}] MetricsBuffer trigger 실패: {e}",
                agent_id=agent_id,
            )
            logger.error(f"MetricsBuffer trigger failed for {agent_id}: {e}")

    async def get_state(self, agent_id: str) -> Optional[EvolutionState]:
        return self.states.get(agent_id, EvolutionState.IDLE)

    async def run_evolution_cycle(self, agent_id: str, force_trigger: bool = False):
        label = self._agent_label(agent_id)
        try:
            current_state = self.states.get(agent_id, EvolutionState.IDLE)
            if current_state != EvolutionState.IDLE:
                self._append_event(
                    level="warning",
                    phase="skipped",
                    message=f"[{label}] 이미 실행 중이라 요청을 건너뜀.",
                    agent_id=agent_id,
                )
                return

            if not force_trigger:
                # V2.0: Replace hardcoded False with dynamic trigger logic
                # In a full implementation, this would check for performance decay,
                # regime change, or a specific time interval.
                is_triggered = await self.trigger_engine.check_trigger(agent_id)
                if not is_triggered:
                    self._append_event(
                        level="info",
                        phase="skipped",
                        message=f"[{label}] 트리거 조건 미충족, 이번 루프는 스킵.",
                        agent_id=agent_id,
                    )
                    return
            elif hasattr(self.trigger_engine, "mark_trigger"):
                self.trigger_engine.mark_trigger(agent_id)

            self.total_improvements += 1
            self._set_state(agent_id, EvolutionState.TRIGGERED)
            logger.info(f"Agent {agent_id} evolution triggered.")

            self._set_state(agent_id, EvolutionState.GENERATING)

            strategy_data = await self.supabase.get_agent_strategy(agent_id)
            if not strategy_data:
                logger.error(f"Could not find current strategy for agent {agent_id}")
                self.failed_improvements += 1
                reason = "No current strategy found"
                self._record_latest(agent_id, "failed", 100, reason)
                self._append_event(
                    level="error",
                    phase="failed",
                    message=f"[{label}] 현재 전략을 찾지 못해 개선 실패.",
                    agent_id=agent_id,
                )
                self._set_state(agent_id, EvolutionState.IDLE)
                return

            # V2.0: Prevent Look-ahead Bias.
            # Fetch backtest metrics for a specific OOS window ending at the trigger point.
            # This ensures the LLM doesn't see "future" data.
            if hasattr(self.trigger_engine, "get_last_trigger_date"):
                trigger_date = self.trigger_engine.get_last_trigger_date(agent_id)
            else:
                trigger_date = datetime.utcnow()
            metrics = await self.supabase.get_backtest_for_period(
                strategy_id=strategy_data.get("id"),
                end_date=trigger_date,
                period_type="OOS"
            ) if strategy_data.get("id") else {
                "trinity_score": 0, "return": 0.0, "sharpe": 0.0, "mdd": 0.0
            }

            # V2.0: Data Validation Gate (Analyst Recommended)
            if not metrics or metrics.get("trinity_score") is None:
                logger.warning(
                    f"Missing baseline metrics for agent {agent_id}. Falling back to zero baseline."
                )
                self._append_event(
                    level="warning",
                    phase="baseline",
                    message=f"[{label}] 기준 백테스트 지표 누락. 0 기준으로 대체.",
                    agent_id=agent_id,
                )
                metrics = {
                    "trinity_score": 0.0,
                    "return": 0.0,
                    "sharpe": 0.0,
                    "mdd": 0.0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                }

            evolution_package = {
                "current_strategy_code": strategy_data.get("code", ""),
                "metrics": metrics,
                "market_regime": "Unknown", # TODO: Integrate with MarketContextProvider
                "competitive_rank": "Unknown", # TODO: Implement Cross-Agent Rank Calculation
                "evolution_history": "Analyzing structural patterns...", # TODO: Abstracted Pattern Summary
                "loss_period_logs": "Analyzing drawdown periods...",
                "top_agent_traits": "Comparing with high-sharpe agents...",
                "market_volatility": "Medium",
            }
            prev_strategy_id = strategy_data.get("id")

            baseline_score = float(evolution_package["metrics"].get("trinity_score") or 0.0)
            try:
                candidate_attempts = int(os.getenv("EVOLUTION_CANDIDATE_ATTEMPTS", "2"))
            except ValueError:
                candidate_attempts = 2
            candidate_attempts = max(1, min(candidate_attempts, 5))

            try:
                min_trinity_delta = float(os.getenv("EVOLUTION_MIN_TRINITY_DELTA", "0.0"))
            except ValueError:
                min_trinity_delta = 0.0

            self._set_state(agent_id, EvolutionState.VALIDATING)

            accepted_code: Optional[str] = None
            accepted_metrics: Optional[Dict[str, Any]] = None
            best_candidate_metrics: Optional[Dict[str, Any]] = None
            best_candidate_score = float("-inf")
            last_failure_reason: Optional[str] = None

            for candidate_attempt in range(candidate_attempts):
                attempt_no = candidate_attempt + 1
                if candidate_attempt > 0:
                    self._append_event(
                        level="info",
                        phase="retry",
                        message=f"[{label}] 개선 후보 재생성 시도 {attempt_no}/{candidate_attempts}.",
                        agent_id=agent_id,
                    )

                try:
                    new_code = await self.llm_client.generate_strategy_code(evolution_package)
                    self._append_event(
                        level="success",
                        phase="generated",
                        message=(
                            f"[{label}] 후보 전략 코드 생성 완료 "
                            f"(시도 {attempt_no}/{candidate_attempts}), 검증 단계 진입."
                        ),
                        agent_id=agent_id,
                    )
                except LLMUnavailableError as llm_error:
                    last_failure_reason = f"Candidate strategy rejected: LLM unavailable ({llm_error})."
                    self._append_event(
                        level="warning",
                        phase="retry",
                        message=f"[{label}] LLM 호출 실패(시도 {attempt_no}/{candidate_attempts}): {llm_error}",
                        agent_id=agent_id,
                    )
                    continue

                try:
                    StrategyLoader.validate_code(new_code)
                    class_name = self._extract_class_name(new_code)
                    if not class_name:
                        raise ValueError(f"Could not extract strategy class name for {agent_id}")
                    strategy_instance = StrategyLoader.load_strategy(new_code, class_name)
                except Exception as strategy_error:
                    last_failure_reason = (
                        f"Candidate strategy rejected: failed to load strategy code ({strategy_error})."
                    )
                    self._append_event(
                        level="warning",
                        phase="retry",
                        message=(
                            f"[{label}] 후보 전략 로드 실패(시도 {attempt_no}/{candidate_attempts}): "
                            f"{strategy_error}"
                        ),
                        agent_id=agent_id,
                    )
                    continue

                validation_data = self._build_validation_data()
                runtime_fix_retries = 1
                validation_result = None
                candidate_runtime_failed = False

                for runtime_attempt in range(runtime_fix_retries + 1):
                    try:
                        validation_result = self.backtest_manager.validate_strategy(
                            strategy_instance,
                            validation_data,
                            train_days=60,
                            val_days=30,
                            threshold=0.7,
                        )
                        break
                    except Exception as runtime_error:
                        if runtime_attempt >= runtime_fix_retries:
                            candidate_runtime_failed = True
                            last_failure_reason = (
                                f"Candidate strategy rejected: runtime validation failed ({runtime_error})."
                            )
                            self._append_event(
                                level="warning",
                                phase="retry",
                                message=(
                                    f"[{label}] 백테스트 실행 오류(시도 {attempt_no}/{candidate_attempts}): "
                                    f"{runtime_error}"
                                ),
                                agent_id=agent_id,
                            )
                            break

                        self._append_event(
                            level="warning",
                            phase="retry",
                            message=(
                                f"[{label}] 런타임 오류 감지({runtime_error}). "
                                f"수정 코드 재생성 시도 {runtime_attempt + 1}/{runtime_fix_retries}."
                            ),
                            agent_id=agent_id,
                        )

                        correction_context = (
                            "Runtime backtest validation failed with the following error:\n"
                            f"{runtime_error}\n"
                            "Regenerate complete strategy code that fixes this error."
                        )
                        try:
                            new_code = await self.llm_client.generate_strategy_code(
                                evolution_package,
                                max_retries=2,
                                initial_error_context=correction_context,
                            )
                            StrategyLoader.validate_code(new_code)
                            class_name = self._extract_class_name(new_code)
                            if not class_name:
                                raise ValueError(
                                    f"Could not extract corrected strategy class name for {agent_id}"
                                )
                            strategy_instance = StrategyLoader.load_strategy(new_code, class_name)
                        except Exception as correction_error:
                            candidate_runtime_failed = True
                            last_failure_reason = (
                                f"Candidate strategy rejected: runtime correction failed ({correction_error})."
                            )
                            self._append_event(
                                level="warning",
                                phase="retry",
                                message=(
                                    f"[{label}] 런타임 보정 실패(시도 {attempt_no}/{candidate_attempts}): "
                                    f"{correction_error}"
                                ),
                                agent_id=agent_id,
                            )
                            break
                        self._append_event(
                            level="info",
                            phase="generated",
                            message=f"[{label}] 런타임 오류 보정 후보 생성 완료, 재검증 진행.",
                            agent_id=agent_id,
                        )

                if candidate_runtime_failed or validation_result is None:
                    continue

                candidate_metrics = validation_result["oos_metrics"]
                candidate_metrics["test_period"] = {
                    "type": "OOS",
                    "generated_at": datetime.utcnow().isoformat(),
                }
                candidate_score = float(candidate_metrics.get("trinity_score") or 0.0)

                if candidate_score > best_candidate_score:
                    best_candidate_score = candidate_score
                    best_candidate_metrics = candidate_metrics

                if candidate_score >= baseline_score + min_trinity_delta:
                    accepted_code = new_code
                    accepted_metrics = candidate_metrics
                    break

                last_failure_reason = "Candidate strategy rejected: no OOS trinity score improvement."
                self._append_event(
                    level="warning",
                    phase="retry",
                    message=(
                        f"[{label}] 개선 미달 "
                        f"(Trinity {baseline_score:.1f} -> {candidate_score:.1f}), "
                        f"다음 후보 시도."
                    ),
                    agent_id=agent_id,
                )

            if accepted_code is None or accepted_metrics is None:
                reason = "Candidate strategy rejected: no OOS trinity score improvement."
                if best_candidate_metrics is not None:
                    reason = (
                        "Candidate strategy rejected: no OOS trinity score improvement "
                        f"(baseline={baseline_score:.4f}, best_candidate={best_candidate_score:.4f}, "
                        f"min_delta={min_trinity_delta:.4f}, attempts={candidate_attempts})."
                    )
                elif last_failure_reason:
                    reason = last_failure_reason

                logger.info(f"Evolution rejected for agent {agent_id}: {reason}")
                self.failed_improvements += 1
                self._record_latest(agent_id, "failed", 100, reason)
                self._append_event(
                    level="warning",
                    phase="failed",
                    message=f"[{label}] 후보 최종 거부: {reason}",
                    agent_id=agent_id,
                )
                await self.supabase.save_improvement_log(
                    agent_id=agent_id,
                    prev_id=prev_strategy_id,
                    new_id=None,
                    analysis=reason,
                    expected={
                        "baseline_trinity_score": baseline_score,
                        "candidate_trinity_score": best_candidate_score if best_candidate_metrics else None,
                    },
                )
                self._set_state(agent_id, EvolutionState.IDLE)
                return

            new_code = accepted_code
            metrics = accepted_metrics

            self._set_state(agent_id, EvolutionState.COMMITTING)

            new_strategy_id = await self.supabase.save_strategy(
                agent_id=agent_id,
                code=new_code,
                rationale="Automated evolution based on C-mode analysis",
                params=strategy_data.get("params", {}),
            )

            if new_strategy_id:
                await self.supabase.save_backtest(new_strategy_id, metrics)
                await self.supabase.save_improvement_log(
                    agent_id=agent_id,
                    prev_id=prev_strategy_id,
                    new_id=new_strategy_id,
                    analysis="C-mode optimization successful",
                    expected={"trinity_score": metrics["trinity_score"]},
                )
                self.completed_improvements += 1
                self._record_latest(agent_id, "completed", 100, "Strategy saved and backtest recorded")
                self._append_event(
                    level="success",
                    phase="completed",
                    message=(
                        f"[{label}] Trinity 개선 "
                        f"{evolution_package['metrics']['trinity_score']:.1f} -> {metrics['trinity_score']:.1f} "
                        "및 전략 저장 완료."
                    ),
                    agent_id=agent_id,
                )
                logger.info(f"Agent {agent_id} successfully evolved to version {new_strategy_id}")
            else:
                self.failed_improvements += 1
                self._record_latest(agent_id, "failed", 100, "Failed to save new strategy")
                self._append_event(
                    level="error",
                    phase="failed",
                    message=f"[{label}] 전략 저장 실패로 개선 사이클 중단.",
                    agent_id=agent_id,
                )
                logger.error(f"Failed to save new strategy for agent {agent_id}")
        except Exception as e:
            self.failed_improvements += 1
            self._record_latest(agent_id, "failed", 100, str(e))
            self._append_event(
                level="error",
                phase="error",
                message=f"[{label}] 개선 사이클 예외: {e}",
                agent_id=agent_id,
            )
            logger.exception(f"Error during evolution cycle for agent {agent_id}: {e}")
        finally:
            self._set_state(agent_id, EvolutionState.IDLE)


_evolution_orchestrator: Optional[EvolutionOrchestrator] = None


def _load_environment_once() -> None:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(project_root / "server" / "api" / ".env", override=False)


def get_evolution_orchestrator() -> EvolutionOrchestrator:
    global _evolution_orchestrator
    if _evolution_orchestrator is None:
        _load_environment_once()
        _evolution_orchestrator = EvolutionOrchestrator()
    return _evolution_orchestrator
