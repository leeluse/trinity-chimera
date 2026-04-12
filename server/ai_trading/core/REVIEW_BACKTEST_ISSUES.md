# 백테스트 엔진 실사용 우려사항 검토 결과

> **검토일:** 2026-04-12 | **검토자:** backtest-engineer | **제한시간:** 10분

## 요약

| 파일 | 문제 수 | 심각도 | 주요 이슈 |
|------|---------|--------|-----------|
| backtest_manager.py | 5 | 🔴 Critical 2개 | MDD 계산, Sharpe 비정상, trade_pnl 버그 |
| rolling_backtest_engine.py | 4 | 🟠 High 2개 | data_provider 인터페이스, 중복 계산 |
| scoring.py | 2 | 🟡 Medium 2개 | MDD 부호, Profit Factor 캡핑 |

---

## 상세 문제 목록

### 🔴 Critical (즉시 수정 필요)

| # | 파일 | 라인 | 문제 | 심각도 | 설명 |
|---|------|------|------|--------|------|
| 1 | backtest_manager.py | 146-147 | trade_pnl 계산 버그 | 🔴 Critical | `sale_value - 10000.0`은 잘못된 계산. 초기 잔액이 아닌 포지션 진입 가격 기준으로 P&L 계산해야 함. 현재 모든 trade가 동일한 10000 기준으로 계산되어 왜곡됨 |
| 2 | backtest_manager.py | 194-215 | Sharpe 비정상 계산 | 🔴 Critical | `_calculate_sharpe`에서 `np.sqrt(252)`는 일별 리턴 가정인데, 실제로는 틱 단위 리턴. 연율화 계산이 잘못되어 값이 비정상적으로 높거나 낮게 나옴. 실제로 `test_costs.py` 실행 시 `-52930.9007` 같은 비정상 값 발생 |

### 🟠 High (빠른 수정 권장)

| # | 파일 | 라인 | 문제 | 심각도 | 설명 |
|-----|------|------|------|--------|------|
| 3 | rolling_backtest_engine.py | 306-322 | data_provider 인터페이스 문제 | 🟠 High | `_fetch_rolling_window`가 두 가지 다른 인터페이스를 시도하지만 실제로는 `None` 반환됨. 하드코딩된 `symbol="BTC/USDT"`, `timeframe="1h"`. 실제 data_provider 연동 안 됨 |
| 4 | rolling_backtest_engine.py | 324-336 | strategy 반환 타입 불일치 | 🟠 High | `_get_active_strategy`는 `strategy_code`를 반환하는데 타입 힌트는 `Optional[StrategyInterface]`. 실제로는 문자열 코드 반환하고 실제 Strategy 객체 생성 TODO 주석만 있음 |
| 5 | backtest_manager.py | 178-192 | MDD 계산 누락 가능성 | 🟠 High | `_calculate_mdd`는 음수 값 반환(`-max_dd`)하는데, 이후 `calculate_trinity_score_v2`에서도 MDD를 음수로 변환. 이중 부호 변환으로 MDD 기여도가 반대로 계산될 수 있음 |
| 6 | rolling_backtest_engine.py | 267-280 | 중복 계산 | 🟠 High | IS/OOS 각각 `run_backtest` 호출 시 내부에서 PF/WR 계산됨. 그런데 다시 `_calculate_pf_wr`로 계산. 결과적으로 같은 데이터로 2번 계산됨 (비용 낭비) |

### 🟡 Medium (개선 권장)

| # | 파일 | 라인 | 문제 | 심각도 | 설명 |
|-----|------|------|------|--------|------|
| 7 | scoring.py | 51-52 | MDD 부호 처리 | 🟡 Medium | `if mdd > 0: mdd = -mdd` 로직. MDD가 이미 음수인데 다시 음수로 변환하면 양수가 됨. 호출자가 MDD를 어떤 부호로 전달하는지 일관성 없음 |
| 8 | scoring.py | 55 | Profit Factor 캡핑 | 🟡 Medium | `max(0.5, min(profit_factor, 10))`. PF가 0.5 미만인 전략은 0.5로 강제 상향되어 실제 성능 왜곡. 손실 전략도 양수로 보일 수 있음 |
| 9 | backtest_manager.py | 82 | 슬리피지 랜덤성 | 🟡 Medium | `np.random.uniform`으로 매 호출마다 다른 슬리피지. 재현성 없는 백테스트 결과. 시드 고정 필요 |
| 10 | rolling_backtest_engine.py | 393-394 | inf 처리 | 🟡 Medium | `profit_factor = float('inf')` 시 0.0으로 반환. 승률 100%인 전략의 PF를 0으로 처리하는 것은 왜곡. 별도 표기 필요 |

### 🟢 Low (향후 개선)

| # | 파일 | 라인 | 문제 | 심각도 | 설명 |
|-----|------|------|------|--------|------|
| 11 | backtest_manager.py | 55-57 | split_data 경계 조건 | 🟢 Low | `split_point`가 데이터 길이 초과 시 `iloc`에 빈 배열 전달 가능. IndexError 발생 위험 |
| 12 | rolling_backtest_engine.py | 165,175 | ThreadPoolExecutor 미사용 | 🟢 Low | `executor` 생성만 하고 실제로 사용하지 않음. 병렬 처리 미구현 |
| 13 | scoring.py | 74-97 | Legacy 함수 중복 | 🟢 Low | `calculate_trinity_score_legacy`는 사용되지 않고, 대부분 v2 사용. 코드 복잡성 증가 |

---

## 임계 경로 분석

### Critical Path (즉시 수정 필요)

```
1. backtest_manager.py:146
   문제: trade_pnl = sale_value - 10000.0
   고쳐야 할 값: trade_pnl = (position * cost_price_sell) - (position * cost_price_buy)
   영향: Profit Factor, Win Rate, 모든 성과 지표

2. backtest_manager.py:209-210
   문제: Annualized Sharpe sqrt(252) 적용 위치
   고쳐야 할 값: 일별 데이터 기준으로만 252 적용, 틱/시간 데이터는 다르게 처리
   영향: Trinity Score 계산 (큰 가중치)
```

### Data Flow Bug

```
rolling_backtest_engine.py _calculate_pf_wr()
    ↓ (호출)
backtest_manager.py run_backtest()
    ↓ (내부에서 이미 PF/WR 계산)
backtest_manager.py _calculate_profit_factor()
    ↓ (리턴)
rolling_backtest_engine.py _calculate_pf_wr()에서 다시 계산 ← 중복!
```

---

## 권장 수정 우선순위

1. **즉시 (Critical)**
   - backtest_manager.py:146 trade_pnl 계산 수정
   - backtest_manager.py:209 Sharpe 계산 로직 수정

2. **당일 (High)**
   - rolling_backtest_engine.py:306 data_provider 인터페이스 실제 구현
   - rolling_backtest_engine.py:324 strategy 객체 실제 생성
   - backtest_manager.py:82 슬리피지 시드 고정

3. **주간 (Medium)**
   - scoring.py MDD 부호 명확화
   - scoring.py PF 캡핑 로직 검토
   - 중복 계산 제거

---

## 테스트 통과 여부

| 테스트 | 상태 | 비고 |
|--------|------|------|
| test_costs.py | ❌ 실패 | trade count mismatch |
| test_sandbox.py | ❓ 미확인 | SecurityError 메시지 한국어 변경 완료 |
| test_rolling_backtest_engine.py | ⚠️ 통과하지만 | 없는 data_provider로 None 반환만 테스트 |

**참고**: 실제 시장 데이터로 백테스트 시 `data_provider=None`으로 인해 `None` 반환 → 엔진 실제 동작 불가.
