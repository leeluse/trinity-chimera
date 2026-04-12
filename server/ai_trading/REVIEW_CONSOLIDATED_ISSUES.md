# Trinity AI Trading System - 종합 우려사항 리포트

**작성일:** 2026-04-12  
**검토자:** backtest-engineer, llm-feedback-expert  
**총 발견 이슈:** 23개

---

## 🔴 Critical (6개) - 즉시 수정 필요

| # | 영역 | 파일 | 라인 | 문제 | 설명 |
|---|------|------|------|------|------|
| 1 | 백테스트 | backtest_manager.py | 146-147 | trade_pnl 버그 | `sale_value - 10000.0` 잘못된 계산. 실제 진입가 기준으로 계산해야 함 |
| 2 | 백테스트 | backtest_manager.py | 194-215 | Sharpe 비정상 | `np.sqrt(252)` 일별 가정인데 틱 단위 사용. 값이 -52930처럼 비정상 |
| 3 | 백테스트 | rolling_backtest_engine.py | 306-322 | data_provider 미연동 | `get_data_range`, `get_recent_data` 모두 None 반환. 실제 동작 불가 |
| 4 | 백테스트 | rolling_backtest_engine.py | 324-336 | strategy 객체 미생성 | 문자열 코드만 반환하고 Strategy 객체 생성이 TODO. 실제 백테스트 불가 |
| 5 | LLM | orchestrator.py | 54 | fallback 동기/비동기 혼용 | ImportError 시 fallback MetricsBuffer의 `set_callback`이 동기 |
| 6 | LLM | metrics_buffer.py | 142 | 콜백 비동기 처리 누락 | `trigger_callback`이 async인지 확인하고 await 필요 |

---

## 🟠 High (8개) - 빠른 수정 권장

| # | 영역 | 파일 | 라인 | 문제 | 설명 |
|---|------|------|------|------|------|
| 7 | 백테스트 | rolling_backtest_engine.py | 267-280 | PF/WR 중복 계산 | run_backtest 내부에서 이미 계산 후 다시 `_calculate_pf_wr` 호출 |
| 8 | 백테스트 | backtest_manager.py | 178-192 | MDD 이중 부호 | `-max_dd` 반환 후 scoring.py에서 또 `-mdd` 처리 |
| 9 | LLM | llm_feedback_client.py | 76 | 초기화 실패 시 중단 | Anthropic API 키 없으면 `__init__`에서 Exception |
| 10 | LLM | llm_feedback_client.py | 250 | LLM 호출 await 문제 | `messages.create()` 동기/비동기 확인 필요 |
| 11 | LLM | orchestrator.py | 125 | validate_code 동기 호출 | StrategyLoader.validate_code가 AST 검증 시 시간 소요 가능 |
| 12 | LLM | metrics_buffer.py | 119 | Lock 범위 과도 | `get_buffer_status`에서도 Lock 잡음 → 성능 저하 |
| 13 | LLM | metrics_buffer.py | 37 | Deque 메모리 고정 | maxlen 100이지만 tick마다 객체 생성 |
| 14 | 백테스트 | backtest_manager.py | 77-89 | 슬리피지 랜덤성 | `np.random.uniform`으로 인해 재현성 없음 |

---

## 🟡 Medium (9개) - 개선 권장

| # | 영역 | 파일 | 라인 | 문제 | 설명 |
|---|------|------|------|------|------|
| 15 | 백테스트 | scoring.py | 55-58 | PF 0.5 강제 상향 | 왜곡된 값으로 계산됨 |
| 16 | 백테스트 | scoring.py | 51 | MDD 양수 변환 | 음수로 전달되면 자동 변환, but 중복 처리 위험 |
| 17 | LLM | llm_feedback_client.py | 355 | 메모리 누수 | `_last_failure_reasons` 무한 증가 |
| 18 | LLM | orchestrator.py | 77 | check_trigger async | EvolutionTrigger.check_trigger가 동기인지 확인 |
| 19 | 백테스트 | backtest_manager.py | 166 | 상대 임포트 | `from .scoring import` 상대 경로 사용 |
| 20 | 백테스트 | rolling_backtest_engine.py | 399 | PF inf 처리 | `float('inf')`를 0.0으로 변환 |
| 21 | 백테스트 | test_rolling_backtest_engine.py | 73-74 | np.maximum deprecated | Positional arguments 3개 이상 사용 |
| 22 | LLM | llm_feedback_client.py | 102 | 예외 처리 불충분 | `_init_llm_client` 예외 누락 |
| 23 | 백테스트 | backtest_manager.py | 140-146 | 초기 자본 고정 | 10000.0 하드코딩 |

---

## 시스템별 총평

### 백테스트 엔진 (13개 이슈)
**가장 심각한 문제:**
1. **실제 동작 불가** (data_provider, strategy 미연동)
2. **핵심 지표 계산 오류** (trade_pnl, Sharpe)
3. **중복 계산** (PF/WR 계산 2회)

**상태:** 테스트는 통과하나 실제 운영 시 동작하지 않음

### LLM 피드백 시스템 (10개 이슈)
**가장 심각한 문제:**
1. **동기/비동기 혼용** (fallback, 콜백 처리)
2. **초기화 실패 시 중단** (API 키 없으면 전체 시스템 다운)
3. **성능 저하** (Lock 범위, 객체 생성)

**상태:** 비동기 처리 미흡으로 인해 런타임 오류 가능성

---

## 수정 우선순위

### Phase 1: Critical Path (필수)
1. backtest_manager.py:146 - trade_pnl 버그 수정
2. backtest_manager.py:209 - Sharpe 계산 수정
3. rolling_backtest_engine.py:306 - data_provider 연동
4. rolling_backtest_engine.py:324 - strategy 객체 생성
5. metrics_buffer.py:142 - 콜백 async 처리

### Phase 2: High Priority
6. metrics_buffer.py:119 - Lock 범위 최적화
7. rolling_backtest_engine.py:267 - PF/WR 중복 제거
8. llm_feedback_client.py:76 - lazy initialization

### Phase 3: Medium Priority
9. 슬리피지 랜덤성 → 시드 추가
10. MDD 이중 부호 검증
11. 메모리 누수 방지

---

## 영향도 분석

| 기능 | 상태 | 영향 |
|------|------|------|
| IS/OOS 백테스트 | ⚠️ 부분 작동 | trade_pnl 버그로 PF/WR 왜곡 |
| Trinity Score 계산 | ✅ 정상 | 캐핑 적용됨 |
| 롤링 백테스트 엔진 | ❌ 미작동 | data_provider/strategy 미연동 |
| MetricsBuffer | ⚠️ 부분 작동 | 콜백 async 처리 필요 |
| LLM 피드백 트리거 | ⚠️ 부분 작동 | fallback 문제 |

---

## 결론

**즉시 수정 필요:**
- 백테스트 핵심 지표 계산 오류 (trade_pnl, Sharpe)
- 롤링 엔진 data_provider/strategy 연동
- LLM 콜백 async 처리

**현재 시스템은 테스트만 통과하고 실제 운영 시 여러 문제 발생 예상**
