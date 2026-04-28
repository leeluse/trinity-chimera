# Backtest System

## 구성
- API: `server/modules/engine/router.py`
- Runtime: `server/modules/engine/runtime.py`
- High-grade Engine: `server/modules/backtest/backtest_engine.py`
- Evolution Engine Wrapper: `server/modules/backtest/evolution/evolution_engine.py`

## 데이터 흐름
1. 전략 코드 확보(DB 또는 코드 직접 전달)
2. **Bybit** OHLCV 수집 (`server/shared/market/provider.py`) — 2026-04-28 Binance→Bybit 전환
3. 전략 함수 실행 -> signal 생성
4. `RealisticSimulator(freq=TF_BARS_PER_DAY[interval])`로 거래 시뮬레이션
5. `compute_metrics`로 성과 지표 계산
6. candles/trades/markers/equity payload 반환

## 주의: 룩어헤드 바이어스
`pivot_low/pivot_high`를 `s.shift(-right)` (미래 참조)로 구현하면 백테스트가 심각하게 과장됨.
올바른 구현: `pivot_bar = s.shift(right); left_ok = s.shift(right+left) > pivot_bar; right_ok = s > pivot_bar`
→ `server/strategies/robust_signal_v2_optimized.py` 2026-04-28 수정 완료

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
