# Backtest System

## 구성
- API: `server/modules/engine/router.py`
- Runtime: `server/modules/engine/runtime.py`
- High-grade Engine: `server/modules/backtest/backtest_engine.py`
- Evolution Engine Wrapper: `server/modules/backtest/evolution/evolution_engine.py`

## 데이터 흐름
1. 전략 코드 확보(DB 또는 코드 직접 전달)
2. Binance OHLCV 수집
3. 전략 함수 실행 -> signal 생성
4. `RealisticSimulator`로 거래 시뮬레이션
5. `compute_metrics`로 성과 지표 계산
6. candles/trades/markers/equity payload 반환

## 주요 산출 지표
- `total_return`, `max_drawdown`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`
- `profit_factor`, `win_rate`, `total_trades`
- `best_trade`, `worst_trade`, `avg_profit`, `avg_loss`
- `long_return`, `short_return`, `long_pf`, `short_pf`
- `buy_hold`, `alpha`, `total_fees`

## 검증 기법
- Walk-Forward split
- Monte Carlo 재샘플링
- 시장 레짐별 성능 비교(엔진 구현 범위 내)
