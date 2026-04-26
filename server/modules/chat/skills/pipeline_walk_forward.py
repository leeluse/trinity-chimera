"""워크포워드(Walk-Forward Optimization) 분석 파이프라인"""
import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict

import pandas as pd

from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code
from server.shared.market.provider import fetch_ohlcv_dataframe
from server.modules.chat.skills._base import format_sse

logger = logging.getLogger(__name__)

async def run_walk_forward_pipeline(
    message: str,
    context: Dict[str, Any],
    strategy_code: str,
    _: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    try:
        if not strategy_code:
            yield format_sse({"type": "error", "content": "❌ 분석할 전략 코드가 없습니다."})
            return

        yield format_sse({"type": "stage", "stage": 1, "label": "📊 마켓 데이터 준비 중..."})
        
        symbol = context.get("symbol", "BTCUSDT")
        timeframe = context.get("timeframe", "1h")
        # 최근 1년 데이터
        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = end_ms - (365 * 24 * 60 * 60 * 1000)

        df = fetch_ohlcv_dataframe(symbol=symbol, interval=timeframe, limit=10000, start_ms=start_ms, end_ms=end_ms)
        if df is None or df.empty:
            yield format_sse({"type": "error", "content": "데이터 수집 실패"})
            return
        
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        yield format_sse({"type": "stage", "stage": 2, "label": "⚙️ 워크포워드 구간 분석 중..."})
        
        engine = BacktestEngine(df, freq=24 if timeframe == "1h" else 1)
        strategy_fn = strategy_from_code(strategy_code)

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def progress_callback(msg: str):
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        # 무거운 연산은 별도 스레드에서
        validation_task = asyncio.create_task(asyncio.to_thread(
            engine.run_full_validation,
            strategy_fn=strategy_fn,
            strategy_name="WF Analysis",
            run_test_set=False,
            callback=progress_callback,
        ))

        while not validation_task.done() or not queue.empty():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield format_sse({"type": "status", "content": msg})
            except asyncio.TimeoutError:
                if validation_task.done():
                    break

        result = await validation_task
        
        # 결과 요약 마크다운 생성
        yield format_sse({"type": "stage", "stage": 3, "label": "🏆 분석 결과 정리 중..."})
        
        summary = result.summary()
        robust_text = "✅ **견고함(Robustness) 확인 완료**" if result.is_robust else "⚠️ **과최적화(Overfitting) 위험 감지**"
        
        final_md = f"## 🔄 Walk-Forward 분석 결과\n\n{robust_text}\n\n{result.verdict}\n\n```text\n{summary}\n```"
        yield format_sse({"type": "analysis", "content": final_md})
        yield format_sse({"type": "done"})

    except Exception as e:
        logger.exception("Walk-Forward pipeline error")
        yield format_sse({"type": "error", "content": f"분석 오류: {str(e)}"})
