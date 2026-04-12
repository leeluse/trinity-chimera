import pytest
import time
import asyncio
from unittest.mock import MagicMock
from server.ai_trading.core.metrics_buffer import MetricsBuffer, MetricTick


class TestMetricsBuffer:
    @pytest.fixture
    def buffer(self):
        """테스트용 MetricsBuffer 인스턴스 생성"""
        return MetricsBuffer(trigger_callback=None)

    def test_buffer_push_and_trigger_count(self, buffer):
        """틱 수 기준 트리거 테스트"""
        triggered_agents = []

        def callback(agent_id, context):
            triggered_agents.append(agent_id)

        buffer._trigger_callback = callback

        # MetricTick 생성하여 push
        # 29개 틱 추가 (임계값 미만 - 30개 필요)
        for i in range(29):
            tick = MetricTick(
                timestamp=time.time(),
                trinity_score=float(50 + i),
                return_pct=0.01,
                sharpe=1.5,
                mdd=-5.0
            )
            result = buffer.push("momentum_hunter", tick)
            assert result is None  # 트리거 안 됨

        # 30번째 틱 추가 (임계값 도달)
        tick = MetricTick(
            timestamp=time.time(),
            trinity_score=80.0,
            return_pct=0.02,
            sharpe=2.0,
            mdd=-3.0
        )
        result = buffer.push("momentum_hunter", tick)
        assert result is not None  # 트리거 발생 (tick_threshold_30ticks)
        assert "momentum_hunter" in triggered_agents

    def test_buffer_push_unknown_agent(self, buffer):
        """Unknown agent_id 테스트"""
        tick = MetricTick(
            timestamp=time.time(),
            trinity_score=50.0,
            return_pct=0.01,
            sharpe=1.5,
            mdd=-5.0
        )
        result = buffer.push("unknown_agent", tick)
        assert result is None  # Unknown agent returns None

    def test_buffer_status_empty(self, buffer):
        """빈 버퍼 상태 테스트"""
        status = buffer.get_buffer_status("momentum_hunter")
        assert "tick_count" in status
        assert status["tick_count"] == 0

    def test_buffer_status_populated(self, buffer):
        """데이터가 있는 버퍼 상태 테스트"""
        # 데이터 추가
        for i in range(3):
            tick = MetricTick(
                timestamp=time.time(),
                trinity_score=float(50 + i * 10),
                return_pct=0.01,
                sharpe=1.5,
                mdd=-5.0
            )
            buffer.push("momentum_hunter", tick)

        status = buffer.get_buffer_status("momentum_hunter")
        assert status is not None
        assert "tick_count" in status
        assert "elapsed_minutes" in status
        assert "trigger_progress" in status

        assert status["tick_count"] == 3

    def test_force_trigger(self, buffer):
        """수동 트리거 테스트"""
        triggered = []

        def callback(agent_id, context):
            triggered.append((agent_id, context.get("trigger_reason")))

        buffer._trigger_callback = callback

        # 데이터 추가
        tick = MetricTick(
            timestamp=time.time(),
            trinity_score=75.0,
            return_pct=0.15,
            sharpe=2.0,
            mdd=-5.0
        )
        buffer.push("momentum_hunter", tick)

        # 수동 트리거
        result = buffer.force_trigger("momentum_hunter")
        assert result is True
        assert len(triggered) == 1
        assert triggered[0][1] == "manual_force"

    def test_add_failure_reason(self, buffer):
        """실패 사유 기록 테스트"""
        buffer.add_failure_reason("momentum_hunter", "Test failure reason")
        status = buffer.get_buffer_status("momentum_hunter")
        # failed_reasons는 get_metrics_summary에 포함
        assert status is not None
