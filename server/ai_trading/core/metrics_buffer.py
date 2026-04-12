"""
MetricsBuffer - T-002 구현

에이전트별 성과 지표를 버퍼링하고 트리거 조건 충족 시 LLMFeedbackClient 호출.
트리거 조건: 30분 경과 OR 30틱 누적 중 먼저 도달한 조건
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from inspect import iscoroutinefunction
from typing import Dict, List, Optional, Callable, Any, Awaitable, Union
from threading import Lock

from server.ai_trading.agents.constants import AGENT_IDS

logger = logging.getLogger(__name__)


@dataclass
class MetricTick:
    """단일 백테스트 결과 (틱)"""
    timestamp: float
    trinity_score: float
    return_pct: float
    sharpe: float
    mdd: float
    profit_factor: Optional[float] = None
    win_rate: Optional[float] = None
    trade_count: int = 0


@dataclass
class BufferedMetrics:
    """에이전트별 누적 메트릭 버퍼"""
    agent_id: str
    ticks: deque = field(default_factory=lambda: deque(maxlen=100))
    start_time: float = field(default_factory=time.time)
    last_trigger_time: Optional[float] = None
    failed_reasons: List[str] = field(default_factory=list)

    def add_tick(self, tick: MetricTick) -> None:
        """새로운 메트릭 틱 추가"""
        self.ticks.append(tick)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """누적된 메트릭 요약"""
        if not self.ticks:
            return {}

        scores = [t.trinity_score for t in self.ticks]
        returns = [t.return_pct for t in self.ticks]
        sharpes = [t.sharpe for t in self.ticks]

        return {
            "tick_count": len(self.ticks),
            "duration_minutes": (time.time() - self.start_time) / 60,
            "avg_trinity_score": sum(scores) / len(scores),
            "max_trinity_score": max(scores),
            "min_trinity_score": min(scores),
            "score_trend": scores[-1] - scores[0] if len(scores) > 1 else 0,
            "avg_return": sum(returns) / len(returns),
            "avg_sharpe": sum(sharpes) / len(sharpes),
            "failed_reasons": self.failed_reasons.copy(),
        }

    def reset(self) -> None:
        """버퍼 초기화 후 다음 누적 시작"""
        self.ticks.clear()
        self.start_time = time.time()
        self.failed_reasons.clear()


class MetricsBuffer:
    """
    에이전트별 성과 지표 버퍼링 및 트리거 관리

    트리거 조건:
    - TRIGGER_DURATION_MINUTES (30분) 경과
    - TRIGGER_TICK_COUNT (30틱) 누적
    중 먼저 도달한 조건
    """

    TRIGGER_DURATION_MINUTES = 30
    TRIGGER_TICK_COUNT = 30

    def __init__(self, trigger_callback: Optional[Callable[[str, Dict[str, Any]], Union[None, Awaitable[None]]]] = None):
        """
        Args:
            trigger_callback: (agent_id, context) -> None | Awaitable[None]
                             트리거 발생 시 호출될 콜백 (동기/비동기 모두 지원)
        """
        self._buffers: Dict[str, BufferedMetrics] = {}
        self._trigger_callback = trigger_callback
        self._lock = Lock()
        self._last_trigger_reason: Dict[str, str] = {}

        # 에이전트별 버퍼 초기화
        for agent_id in AGENT_IDS:
            self._buffers[agent_id] = BufferedMetrics(agent_id=agent_id)

        logger.info(f"MetricsBuffer initialized for agents: {AGENT_IDS}")

    def push(self, agent_id: str, tick: MetricTick) -> Optional[str]:
        """
        새로운 메트릭 틱을 버퍼에 추가하고 트리거 조건 체크

        Args:
            agent_id: 에이전트 ID
            tick: 메트릭 틱 데이터

        Returns:
            트리거 발생 시 트리거 사유, 아니면 None
        """
        if agent_id not in self._buffers:
            logger.warning(f"Unknown agent_id: {agent_id}")
            return None

        with self._lock:
            buffer = self._buffers[agent_id]
            buffer.add_tick(tick)

            trigger_reason = self._check_trigger(agent_id, buffer)

            if trigger_reason:
                # 컨텍스트 구성 및 콜백 호출
                context = buffer.get_metrics_summary()
                context["trigger_reason"] = trigger_reason
                context["agent_id"] = agent_id
                context["trigger_timestamp"] = time.time()

                # 버퍼 초기화 (다음 누적 시작)
                buffer.reset()
                buffer.last_trigger_time = time.time()

                self._last_trigger_reason[agent_id] = trigger_reason

                logger.info(f"Trigger fired for {agent_id}: {trigger_reason}")

                # async 콜백은 백그라운드에서 실행
                if self._trigger_callback:
                    asyncio.create_task(self._invoke_callback(agent_id, context))

                return trigger_reason

        return None

    async def _invoke_callback(self, agent_id: str, context: Dict[str, Any]) -> None:
        """콜백 호출 - 동기/비동기 자동 처리"""
        if self._trigger_callback is None:
            return

        try:
            if iscoroutinefunction(self._trigger_callback):
                await self._trigger_callback(agent_id, context)
            else:
                self._trigger_callback(agent_id, context)
        except Exception as e:
            logger.error(f"Trigger callback failed for {agent_id}: {e}")

    def _check_trigger(self, agent_id: str, buffer: BufferedMetrics) -> Optional[str]:
        """
        트리거 조건 체크

        Returns:
            트리거 사유 문자열 또는 None
        """
        elapsed_minutes = (time.time() - buffer.start_time) / 60
        tick_count = len(buffer.ticks)

        # 조건 1: 시간 경과
        if elapsed_minutes >= self.TRIGGER_DURATION_MINUTES:
            return f"duration_threshold_{self.TRIGGER_DURATION_MINUTES}min"

        # 조건 2: 틱 누적
        if tick_count >= self.TRIGGER_TICK_COUNT:
            return f"tick_threshold_{self.TRIGGER_TICK_COUNT}ticks"

        return None

    def get_buffer_status(self, agent_id: str) -> Dict[str, Any]:
        """에이전트별 버퍼 상태 조회"""
        if agent_id not in self._buffers:
            return {}

        buffer = self._buffers[agent_id]
        with self._lock:
            status = {
                "agent_id": agent_id,
                "tick_count": len(buffer.ticks),
                "elapsed_minutes": (time.time() - buffer.start_time) / 60,
                "trigger_progress": self._calculate_trigger_progress(buffer),
            }
        return status

    def _calculate_trigger_progress(self, buffer: BufferedMetrics) -> Dict[str, float]:
        """트리거 진행률 계산"""
        elapsed_minutes = (time.time() - buffer.start_time) / 60
        tick_count = len(buffer.ticks)

        return {
            "duration_pct": min(100.0, (elapsed_minutes / self.TRIGGER_DURATION_MINUTES) * 100),
            "tick_pct": min(100.0, (tick_count / self.TRIGGER_TICK_COUNT) * 100),
        }

    def add_failure_reason(self, agent_id: str, reason: str) -> None:
        """이전 LLM 피드백 실패 사유 기록"""
        if agent_id in self._buffers:
            with self._lock:
                self._buffers[agent_id].failed_reasons.append(reason)
                # 최근 5개만 유지
                if len(self._buffers[agent_id].failed_reasons) > 5:
                    self._buffers[agent_id].failed_reasons.pop(0)

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """모든 에이전트 버퍼 상태 조회"""
        return {agent_id: self.get_buffer_status(agent_id) for agent_id in AGENT_IDS}

    def force_trigger(self, agent_id: str) -> bool:
        """수동 트리거 (테스트용)"""
        if agent_id not in self._buffers:
            return False

        with self._lock:
            buffer = self._buffers[agent_id]
            context = buffer.get_metrics_summary()
            context["trigger_reason"] = "manual_force"
            context["agent_id"] = agent_id

            buffer.reset()
            buffer.last_trigger_time = time.time()

            if self._trigger_callback:
                asyncio.create_task(self._invoke_callback(agent_id, context))

        return True


# Global singleton instance
_metrics_buffer_instance: Optional[MetricsBuffer] = None


def get_metrics_buffer(
    trigger_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> MetricsBuffer:
    """전역 MetricsBuffer 인스턴스 반환"""
    global _metrics_buffer_instance
    if _metrics_buffer_instance is None:
        _metrics_buffer_instance = MetricsBuffer(trigger_callback=trigger_callback)
    return _metrics_buffer_instance
