import pytest
import time
from server.ai_trading.core.metrics_buffer import MetricsBuffer, MetricTick, BufferedMetrics

class TestMetricsBuffer:
    @pytest.fixture
    def buffer(self):
        """테스트용 MetricsBuffer 인스턴스 생성"""
        return MetricsBuffer(time_threshold=60, count_threshold=5)  # 1분, 5틱으로 테스트

    def test_buffer_push_and_trigger_count(self, buffer):
        """틱 수 기준 트리거 테스트"""
        triggered_agents = []

        async def callback(agent_id, entries):
            triggered_agents.append(agent_id)

        buffer.set_callback(callback)

        # 4개 항목 추가 (임계값 미만)
        for i in range(4):
            result = await buffer.push("test_agent", {"score": i})
            assert result is False

        # 5번째 항목 추가 (임계값 초과)
        result = await buffer.push("test_agent", {"score": 4})
        assert result is True
        assert "test_agent" in triggered_agents

    @pytest.mark.asyncio
    async def test_buffer_push_and_trigger_time(self, buffer, mocker):
        """시간 기준 트리거 테스트"""
        triggered_agents = []

        async def callback(agent_id, entries):
            triggered_agents.append(agent_id)

        buffer.set_callback(callback)

        # 시간 모킹
        mock_time = mocker.patch('time.time')
        mock_time.return_value = 1000.0

        # 초기 항목 추가
        await buffer.push("test_agent", {"score": 0})

        # 시간 경과 (임계값 초과)
        mock_time.return_value = 1070.0  # 70초 경과

        result = await buffer.push("test_agent", {"score": 1})
        assert result is True
        assert "test_agent" in triggered_agents

    def test_buffer_stats_empty(self, buffer):
        """빈 버퍼 통계 테스트"""
        stats = buffer.get_buffer_stats("test_agent")
        assert stats is None

    def test_buffer_stats_populated(self, buffer):
        """데이터가 있는 버퍼 통계 테스트"""
        # 데이터 추가
        for i in range(3):
            buffer.push("test_agent", {"score": i})

        stats = buffer.get_buffer_stats("test_agent")
        assert stats is not None
        assert "count" in stats
        assert "time_elapsed" in stats
        assert "time_remaining" in stats
        assert "count_remaining" in stats

        assert stats["count"] == 3
        assert stats["count_remaining"] == 27  # 30 - 3

class TestBufferEntry:
    def test_buffer_entry_creation(self):
        """BufferEntry 생성 테스트"""
        timestamp = time.time()
        metrics = {"score": 75.0, "return": 0.15}
        entry = BufferEntry(timestamp=timestamp, metrics=metrics)

        assert entry.timestamp == timestamp
        assert entry.metrics == metrics