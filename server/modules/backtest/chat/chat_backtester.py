import logging
from typing import Dict, Any
from server.modules.engine.runtime import run_skill_backtest
from server.modules.engine.utils import extract_symbol, extract_timeframe, resolve_backtest_dates, safe_float

logger = logging.getLogger(__name__)

class ChatBacktester:
    """
    [Chat API Layer]
    채팅 사용자의 자연어 요청을 해석하고, AI가 생성한 코드를 즉시 구동하여 
    시각화에 적합한 요약된 지표를 반환합니다.
    """

    # -------------------------------------------------------------------------
    # 백테스트 통합 실행: 자연어 파싱 -> 코어 엔진 구동 -> 결과 요약 및 포맷팅
    # -------------------------------------------------------------------------
    @staticmethod
    async def run(code: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 메시지 및 컨텍스트에서 거래 환경(심볼, 타임프레임, 기간) 추출
        symbol = extract_symbol(message, context.get("symbol", "BTCUSDT"))
        timeframe = extract_timeframe(message, context.get("timeframe", "1h"))
        start_date, end_date = resolve_backtest_dates(context)
        leverage = safe_float(context.get("leverage"), 10.0)

        logger.info(f"[Chat] Running backtest for {symbol} ({timeframe}) from {start_date} to {end_date}")

        # 2. Core 엔진(runtime.py) 호출: 실제 데이터 수집 및 코드 시뮬레이션 수행
        payload = run_skill_backtest(
            symbol=symbol,
            interval=timeframe,
            strategy="custom_ai_strategy", # 채팅용 임시 전략 식별자
            leverage=leverage,
            start_date=start_date,
            end_date=end_date,
            include_candles=True,         # UI 차트 표시를 위해 캔들 데이터 포함
            code=code,                    # AI가 생성한 로직 코드
        )

        # 3. 엔진 처리 도중 에러가 발생한 경우 그대로 반환
        if not payload.get("success"):
            return payload

        # 4. 프론트엔드 카드 UI 및 통계 섹션에 표시할 핵심 지표(Metrics)만 요약 추출
        results = payload.get("results", {})
        metrics = {
            "total_return": safe_float(results.get("total_return")),
            "max_drawdown": abs(safe_float(results.get("max_drawdown"))), # MDD는 양수로 표시 관례
            "sharpe_ratio": safe_float(results.get("sharpe_ratio")),
            "win_rate": safe_float(results.get("win_rate")),
            "profit_factor": safe_float(results.get("profit_factor")),
            "total_trades": int(results.get("total_trades", 0))
        }

        # 5. 최종 가공된 정보 반환
        return {
            "success": True,
            "metrics": metrics,
            "backtest_payload": payload,  # 상세 데이터 (차트용 캔들, 마커 등 포함)
            "symbol": symbol,
            "timeframe": timeframe
        }
