import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from server.shared.market.provider import fetch_ohlcv_dataframe
from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code
from server.modules.engine.utils import safe_float

logger = logging.getLogger(__name__)

class EvolutionEngine:
    """
    [Evolution Core Engine - Upgraded]
    고성능 백테스트 엔진(WFO, Monte Carlo)을 사용하여 
    에이전트 전략의 강건성을 다각도로 검증합니다.
    """

    async def run(
        self, 
        code: str, 
        agent_id: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        고급 검증 파이프라인(WFO + Monte Carlo + Regime Analysis) 실행
        """
        context = context or {}
        symbol = context.get("symbol", "BTCUSDT")
        timeframe = context.get("timeframe", "1h")
        quick_mode = bool(context.get("quick_mode", False))
        lookback_days = int(context.get("lookback_days") or (45 if quick_mode else 180))
        run_test_set = bool(context.get("run_test_set", not quick_mode))
        
        # 1. 데이터 수집 (quick/full 모드에 따라 기간 조절)
        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = end_ms - (lookback_days * 24 * 60 * 60 * 1000)
        
        try:
            df = fetch_ohlcv_dataframe(
                symbol=symbol,
                interval=timeframe,
                start_ms=start_ms,
                end_ms=end_ms
            )
            if df.empty:
                raise ValueError("가져온 마켓 데이터가 비어 있습니다.")
            
            # 인덱스를 Datetime으로 설정
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
        except Exception as e:
            logger.error(f"[Evolution] Data fetch failed: {e}")
            return {"success": False, "error": f"데이터 수집 실패: {e}"}

        # 2. 고급 백테스트 엔진 초기화
        engine = BacktestEngine(df, freq=24 if timeframe == "1h" else 1)
        if quick_mode:
            # Quick gate는 비용/시간 절감을 위해 Monte Carlo 샘플 수를 낮춘다.
            engine.mc.n_sims = min(120, int(engine.mc.n_sims))
        
        try:
            # 3. LLM 코드에서 실행 가능한 전략 함수 추출
            strategy_fn = strategy_from_code(code)
            
            # 4. 전체 검증 파이프라인 실행 (WFO, Monte Carlo 등)
            # 진화 단계이므로 최종 테스트 구간까지 포함하여 검증 (run_test_set=True)
            validation_res = engine.run_full_validation(
                strategy_fn=strategy_fn,
                strategy_name=f"Evolved_{agent_id}",
                run_test_set=run_test_set
            )
            
            # 5. 결과 인덱싱 및 메트릭 산출
            # 가장 좋은 성과를 낸 WFO 구간 또는 최종 테스트 결과를 메인 메트릭으로 사용
            main_res = validation_res.period_results[0] if validation_res.period_results else \
                       (validation_res.wfo_results[-1] if validation_res.wfo_results else None)
            
            if not main_res:
                raise ValueError("유효한 백테스트 결과가 생성되지 않았습니다.")

            metrics = {
                "total_return": safe_float(main_res.total_return),
                "sharpe_ratio": safe_float(main_res.sharpe),
                "max_drawdown": safe_float(main_res.max_drawdown),
                "win_rate": safe_float(main_res.win_rate),
                "profit_factor": safe_float(main_res.profit_factor),
                "total_trades": int(main_res.n_trades),
                "trinity_score": safe_float(main_res.calmar * 10) # 예시 점수화
            }

            return {
                "success": True,
                "quick_mode": quick_mode,
                "is_robust": validation_res.is_robust,
                "verdict": validation_res.verdict,
                "metrics": metrics,
                "summary": validation_res.summary(),
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Evolution] Validation error: {e}")
            return {"success": False, "error": f"검증 프로세스 에러: {e}"}
