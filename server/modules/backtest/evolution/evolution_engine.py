import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from server.shared.market.provider import fetch_ohlcv_dataframe
from server.modules.backtest.backtest_engine import BacktestEngine, strategy_from_code
from server.modules.engine.utils import safe_float
from server.modules.evolution.scoring import calculate_trinity_score

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
        # Quick gate: 90일(1h 기준 ~2160봉) — BacktestEngine 최소 요건 충족
        # Full gate: 365일(1h 기준 ~8760봉) — WFO 슬라이스 충분히 확보
        lookback_days = int(context.get("lookback_days") or (90 if quick_mode else 365))
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
            # 최종 홀드아웃(period_results) 우선 → 없으면 WFO 슬라이스 평균 사용
            if validation_res.period_results:
                main_res = validation_res.period_results[0]
            elif validation_res.wfo_results:
                # WFO 전체 슬라이스 평균으로 대표 메트릭 계산
                wfo = validation_res.wfo_results
                total_trades = sum(getattr(r, "n_trades", 0) for r in wfo)
                if total_trades == 0:
                    raise ValueError("WFO 전 구간에서 거래가 발생하지 않았습니다 (zero trades).")
                avg_return    = sum(safe_float(r.total_return) for r in wfo) / len(wfo)
                avg_sharpe    = sum(safe_float(r.sharpe) for r in wfo) / len(wfo)
                avg_mdd       = sum(safe_float(r.max_drawdown) for r in wfo) / len(wfo)
                avg_win_rate  = sum(safe_float(r.win_rate) for r in wfo) / len(wfo)
                avg_pf        = sum(safe_float(r.profit_factor) for r in wfo) / len(wfo)

                class _AggResult:
                    total_return = avg_return
                    sharpe       = avg_sharpe
                    max_drawdown = avg_mdd
                    win_rate     = avg_win_rate
                    profit_factor = avg_pf
                    n_trades     = total_trades

                main_res = _AggResult()
            else:
                raise ValueError("유효한 백테스트 결과가 생성되지 않았습니다.")

            ret   = safe_float(main_res.total_return)
            sharpe = safe_float(main_res.sharpe)
            mdd   = safe_float(main_res.max_drawdown)
            metrics = {
                "total_return": ret,
                "sharpe_ratio": sharpe,
                "max_drawdown": mdd,
                "win_rate": safe_float(main_res.win_rate),
                "profit_factor": safe_float(main_res.profit_factor),
                "total_trades": int(main_res.n_trades),
                "trinity_score": calculate_trinity_score(ret, sharpe, mdd),
                "is_robust": validation_res.is_robust,
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
