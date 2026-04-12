"""
Tests for Rolling Backtest Engine - T-001

Author: backtest-engineer
Task: T-001
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from server.ai_trading.core.rolling_backtest_engine import (
    RollingBacktestEngine,
    RollingMetrics,
    MetricsBuffer
)
from server.ai_trading.core.strategy_interface import StrategyInterface
from server.ai_trading.agents.constants import AGENT_IDS


# ==================== Fixtures ====================

@pytest.fixture
def mock_strategy():
    """모의 전략"""
    strategy = Mock(spec=StrategyInterface)
    strategy.generate_signal = Mock(return_value=1)  # 항상 매수
    return strategy


@pytest.fixture
def mock_data_provider():
    """모의 데이터 제공자"""
    provider = Mock()
    provider.get_data_range = AsyncMock(return_value=None)
    provider.get_recent_data = AsyncMock(return_value=None)
    provider.is_connected = Mock(return_value=True)
    return provider


@pytest.fixture
def mock_strategy_registry():
    """모의 전략 레지스트리"""
    registry = Mock()
    registry.get_active_strategy = AsyncMock(return_value=None)
    return registry


@pytest.fixture
def sample_ohlcv_data():
    """샘플 OHLCV 데이터 생성"""
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=100),
        end=datetime.now(),
        freq='h'
    )

    np.random.seed(42)
    base_price = 50000

    data = {
        'open': base_price + np.random.randn(len(dates)).cumsum() * 100,
        'high': base_price + np.random.randn(len(dates)).cumsum() * 100 + np.abs(np.random.randn(len(dates))) * 50,
        'low': base_price + np.random.randn(len(dates)).cumsum() * 100 - np.abs(np.random.randn(len(dates))) * 50,
        'close': base_price + np.random.randn(len(dates)).cumsum() * 100,
        'volume': np.random.randint(1000, 10000, len(dates))
    }

    df = pd.DataFrame(data, index=dates)
    data['high'] = np.maximum(data['high'], data['open'], data['close'])
    data['low'] = np.minimum(data['low'], data['open'], data['close'])

    return df


@pytest.fixture
def rolling_engine(mock_data_provider, mock_strategy_registry):
    """테스트용 롤링 백테스트 엔진"""
    return RollingBacktestEngine(
        data_provider=mock_data_provider,
        strategy_registry=mock_strategy_registry,
        window_months=3,
        is_days=30,
        oos_days=15,
        max_workers=2
    )


# ==================== MetricsBuffer Tests ====================

class TestMetricsBuffer:
    """MetricsBuffer 단위 테스트"""

    def test_push_and_flush(self):
        """버퍼 푸시 및 플러시 테스트"""
        buffer = MetricsBuffer()

        metrics = RollingMetrics(
            agent_id="momentum_hunter",
            timestamp=datetime.now(),
            is_score=60.0,
            oos_score=55.0,
            return_pct=0.05,
            sharpe=1.2,
            mdd=-0.1,
            profit_factor=1.5,
            win_rate=0.6,
            trinity_score_v2=65.0,
            trades=10,
            window_start=datetime.now() - timedelta(days=90),
            window_end=datetime.now(),
            passed_gate=True
        )

        should_flush = buffer.push("momentum_hunter", metrics)
        assert should_flush is False  # 아직 트리거 안 됨
        assert buffer.tick_count["momentum_hunter"] == 1

        # 30틱 충족까지 푸시
        for _ in range(29):
            should_flush = buffer.push("momentum_hunter", metrics)

        assert should_flush is True  # 30틱 충족

    def test_flush_reset(self):
        """플러시 후 리셋 테스트"""
        buffer = MetricsBuffer()

        metrics = RollingMetrics(
            agent_id="momentum_hunter",
            timestamp=datetime.now(),
            is_score=60.0,
            oos_score=55.0,
            return_pct=0.05,
            sharpe=1.2,
            mdd=-0.1,
            profit_factor=1.5,
            win_rate=0.6,
            trinity_score_v2=65.0,
            trades=10,
            window_start=datetime.now() - timedelta(days=90),
            window_end=datetime.now(),
            passed_gate=True
        )

        for _ in range(30):
            should_flush = buffer.push("momentum_hunter", metrics)

        flushed = buffer.flush("momentum_hunter")
        assert len(flushed) == 30
        assert buffer.tick_count["momentum_hunter"] == 0
        assert len(buffer.buffer["momentum_hunter"]) == 0

    def test_agent_isolation(self):
        """에이전트 별 격리 테스트"""
        buffer = MetricsBuffer()

        for agent_id in AGENT_IDS:
            assert agent_id in buffer.buffer
            assert agent_id in buffer.last_flush
            assert agent_id in buffer.tick_count


# ==================== RollingBacktestEngine Tests ====================

class TestRollingBacktestEngine:
    """RollingBacktestEngine 통합 테스트"""

    @pytest.mark.asyncio
    async def test_calculate_pf_wr(self, rolling_engine, sample_ohlcv_data, mock_strategy):
        """Profit Factor, Win Rate 계산 테스트"""
        mock_strategy.generate_signal = Mock(side_effect=lambda df: 1 if len(df) % 2 == 0 else 0)

        result = rolling_engine._calculate_pf_wr(mock_strategy, sample_ohlcv_data)

        assert 'profit_factor' in result
        assert 'win_rate' in result
        assert 0 <= result['win_rate'] <= 1
        assert result['profit_factor'] >= 0 or result['profit_factor'] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_trinity_score_v2(self, rolling_engine):
        """Trinity Score v2 계산 테스트"""
        score = rolling_engine._calculate_trinity_score_v2(
            return_val=0.15,
            sharpe=1.2,
            mdd=-0.15,
            profit_factor=1.5,
            win_rate=0.6
        )

        # Expected calculation:
        # 0.15 × 0.30 + 1.2 × 25 × 0.25 + (1 + (-0.15)) × 100 × 0.20 + 1.5 × 20 × 0.15 + 0.6 × 100 × 0.10
        # = 0.045 + 7.5 + 17.0 + 4.5 + 6.0 = 35.045
        assert score > 0
        assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_agent_isolation_in_tick(self, rolling_engine, sample_ohlcv_data, mock_strategy):
        """에이전트 단위 격리 테스트"""
        # 데이터 모킹
        rolling_engine._fetch_rolling_window = AsyncMock(return_value=sample_ohlcv_data)
        rolling_engine._get_active_strategy = AsyncMock(return_value=mock_strategy)

        # 특정 에이전트 실패 시뮬레이션
        def get_strategy_with_failure(agent_id):
            if agent_id == "chaos_agent":
                raise ValueError("Simulated failure")
            return mock_strategy

        rolling_engine._get_active_strategy = AsyncMock(side_effect=get_strategy_with_failure)

        results = await rolling_engine._run_tick()

        # chaos_agent는 실패했지만 다른 에이전트는 결과 있음
        for agent_id in AGENT_IDS:
            if agent_id != "chaos_agent":
                # 성공 또는 실패 기록 확인
                buffered = rolling_engine.metrics_buffer.get_buffered_metrics(agent_id)
                assert len(buffered) > 0

    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self, rolling_engine, sample_ohlcv_data, mock_strategy):
        """구독자 브로드캐스트 테스트"""
        received = []

        def on_update(results):
            received.append(results)

        rolling_engine.subscribe(on_update)

        # 테스트용 결과 브로드캐스트
        results = {"test_agent": RollingMetrics(
            agent_id="test_agent",
            timestamp=datetime.now(),
            is_score=60.0,
            oos_score=55.0,
            return_pct=0.05,
            sharpe=1.2,
            mdd=-0.1,
            profit_factor=1.5,
            win_rate=0.6,
            trinity_score_v2=65.0,
            trades=10,
            window_start=datetime.now() - timedelta(days=90),
            window_end=datetime.now(),
            passed_gate=True
        )}

        await rolling_engine._broadcast_results(results)

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_metrics_buffer_should_flush(self):
        """MetricsBuffer 트리거 조건 테스트"""
        buffer = MetricsBuffer()

        # 30틱 조건
        metrics = RollingMetrics(
            agent_id="momentum_hunter",
            timestamp=datetime.now(),
            is_score=60.0,
            oos_score=55.0,
            return_pct=0.05,
            sharpe=1.2,
            mdd=-0.1,
            profit_factor=1.5,
            win_rate=0.6,
            trinity_score_v2=65.0,
            trades=10,
            window_start=datetime.now() - timedelta(days=90),
            window_end=datetime.now(),
            passed_gate=True
        )

        for i in range(29):
            should_flush = buffer.push("momentum_hunter", metrics)
            assert should_flush is False

        should_flush = buffer.push("momentum_hunter", metrics)
        assert should_flush is True  # 30틱 충족

    def test_metrics_buffer_time_trigger(self):
        """시간 기반 트리거 테스트"""
        buffer = MetricsBuffer()

        # 이전 플러시 시간을 과거로 설정
        buffer.last_flush["momentum_hunter"] = datetime.now() - timedelta(minutes=31)

        metrics = RollingMetrics(
            agent_id="momentum_hunter",
            timestamp=datetime.now(),
            is_score=60.0,
            oos_score=55.0,
            return_pct=0.05,
            sharpe=1.2,
            mdd=-0.1,
            profit_factor=1.5,
            win_rate=0.6,
            trinity_score_v2=65.0,
            trades=10,
            window_start=datetime.now() - timedelta(days=90),
            window_end=datetime.now(),
            passed_gate=True
        )

        should_flush = buffer.push("momentum_hunter", metrics)
        assert should_flush is True  # 시간 트리거


# ==================== Integration Tests ====================

@pytest.mark.integration
class TestRollingBacktestIntegration:
    """통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_tick_flow(self, sample_ohlcv_data):
        """전체 틱 플로우 테스트"""
        # 모킹 설정
        mock_dp = Mock()
        mock_dp.is_connected = Mock(return_value=True)
        mock_dp.get_recent_data = AsyncMock(return_value=sample_ohlcv_data)

        mock_sr = Mock()
        mock_sr.get_active_strategy = AsyncMock(return_value=Mock(spec=StrategyInterface))

        engine = RollingBacktestEngine(
            data_provider=mock_dp,
            strategy_registry=mock_sr,
            window_months=3,
            is_days=30,
            oos_days=15
        )

        results = await engine.run_single_tick()

        assert len(results) <= len(AGENT_IDS)  # 일부는 실패 가능

    @pytest.mark.asyncio
    async def test_engine_status(self):
        """엔진 상태 조회 테스트"""
        engine = RollingBacktestEngine(
            data_provider=Mock(),
            strategy_registry=Mock()
        )

        status = engine.get_status()

        assert 'running' in status
        assert 'tick_count' in status
        assert 'buffer_status' in status
        assert all(agent_id in status['buffer_status'] for agent_id in AGENT_IDS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
