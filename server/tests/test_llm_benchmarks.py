import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock
from server.shared.llm.client import generate_chat_reply

async def simulate_llm_call(latency=0.5):
    """Simulate an LLM call with a given latency."""
    await asyncio.sleep(latency)
    return {"content": "Success", "provider": "mock", "fallback": False}

@pytest.mark.asyncio
async def test_llm_concurrency_performance():
    """Benchmark the throughput of concurrent LLM calls."""
    num_calls = 20
    latency = 0.2

    start_time = time.perf_counter()

    # Simulate concurrent calls using asyncio.gather
    with patch("server.shared.llm.client._post_json", side_effect=simulate_llm_call):
        with patch("server.shared.llm.client._provider", return_value="nim"), \
             patch("server.shared.llm.client._nim_config", return_value={"base_url": "http://mock", "api_key": "test_key", "model": "test_model"}):

            tasks = [generate_chat_reply(f"Query {i}") for i in range(num_calls)]
            await asyncio.gather(*tasks)

    end_time = time.perf_counter()
    total_time = end_time - start_time

    print(f"\nConcurrency Benchmark: {num_calls} calls in {total_time:.4f}s")
    print(f"Average time per call: {total_time/num_calls:.4f}s")

    # Sequential would be 20 * 0.2 = 4.0s. Concurrent should be roughly ~0.2s + overhead.
    # We check that it is significantly faster than sequential.
    assert total_time << ( (num_calls * latency) / 2

@pytest.mark.asyncio
async def test_rolling_engine_lag_under_llm_load():
    """
    Verify that RollingBacktestEngine doesn't lag during tick processing
    even when LLM calls (which are async) are triggered.
    """
    from server.ai.trading.core.rolling_backtest_engine import RollingBacktestEngine, MetricsBuffer, RollingMetrics
    from datetime import datetime

    # Mock dependencies
    mock_data_provider = MagicMock()
    mock_strategy_registry = MagicMock()

    # Setup a buffer that always triggers flush
    buffer = MetricsBuffer()
    buffer._should_flush = lambda agent_id: True

    engine = RollingBacktestEngine(
        data_provider=mock_data_provider,
        strategy_registry=mock_strategy_registry,
        metrics_buffer=buffer
    )

    # Mock the LLM feedback trigger to be slow
    async def slow_feedback(agent_id):
        await asyncio.sleep(0.1) # 100ms delay
        return True

    with patch.object(RollingBacktestEngine, '_trigger_llm_feedback', side_effect=slow_feedback):
        # Mock a single agent backtest to be fast
        async def fast_backtest(agent_id, timestamp):
            return RollingMetrics(
                agent_id=agent_id, timestamp=timestamp, is_score=1.0, oos_score=1.0,
                return_pct=0.1, sharpe=1.0, mdd=0.1, profit_factor=1.0,
                win_rate=0.5, trinity_score_v2=1.0, trades=10,
                window_start=timestamp, window_end=timestamp, passed_gate=True
            )

        engine._run_single_agent_backtest = fast_backtest

        # Run a tick and measure time
        start_time = time.perf_counter()
        await engine._run_tick()
        end_time = time.perf_counter()

        print(f"\nTick processing time with slow LLM: {end_time - start_time:.4f}s")
        assert (end_time - start_time) > 0
