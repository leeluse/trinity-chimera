# 프로젝트 구조 분석 보고서

## 분석 일자: 2026-04-12
## 분석자: system-architect

---

## 1. 현재 구조 vs MENUAL.md 요구사항 비교

### 1.1 파일 구조 현황

```
server/ai_trading/
├── __init__.py
├── agents/
│   ├── __init__.py
│   ├── constants.py          # AGENT_IDS 정의 (4개 에이전트)
│   ├── llm_client.py         # EvolutionLLMClient
│   ├── orchestrator.py       # EvolutionOrchestrator
│   └── trigger.py            # EvolutionTrigger
├── core/
│   ├── backtest_manager.py   # BacktestManager
│   ├── competitive_rank.py
│   ├── market_context.py
│   ├── strategy_interface.py # StrategyInterface
│   └── strategy_loader.py    # StrategyLoader, AST 검증
├── rl/
└── tests/
    ├── test_backtest_manager.py
    ├── test_costs.py
    ├── test_integration.py
    └── test_sandbox.py
```

### 1.2 Gap Analysis (주요 문제점)

| MENUAL.md 요구사항 | 현재 상태 | 상태 |
|-------------------|----------|------|
| **rolling_backtest_engine.py** (T-001) | ❌ 없음 | 🔴 Critical |
| **metrics_buffer.py** (T-002) | ❌ 없음 | 🔴 Critical |
| **scoring.py** Trinity Score v2 (T-006) | ❌ 없음, backtest_manager에 하드코딩 | 🔴 Critical |
| **prompts/** 에이전트별 프롬프트 (T-008) | ❌ 없음 | 🟡 Medium |
| **logs/** 진화 이벤트 로그 (T-011) | ❌ 없음 | 🟡 Medium |
| Profit Factor 계산 (T-005) | ❌ 없음 | 🟠 High |
| Win Rate 계산 (T-005) | ❌ 없음 | 🟠 High |
| LLM 실패 시 mock 반환 | ⚠️ `_call_llm`에서 mock 반환 존재 | 🔴 Critical |
| IS/OOS Walk-forward | ⚠️ 기본 분리만 있음, 동적 슬라이딩 없음 | 🟡 Medium |
| 자율 트리거 비활성 | ⚠️ force_trigger=False시 진화 없음 | 🟡 Medium |

---

## 2. 핵심 파일 상세 분석

### 2.1 backtest_manager.py

**현재 기능:**
- `split_data()`: IS/OOS 분리 (30일/30일 고정)
- `calculate_trinity_score()`: 구버전 공식 사용
  ```python
  # 현재 공식 (구버전)
  score = (return_val * 0.40) + (sharpe * 25 * 0.35) + ((1 + mdd) * 100 * 0.25)
  ```
- `run_backtest()`: 단일 실행 백테스트
- `validate_strategy()`: IS/OOS 검증 게이트

**문제점:**
- ❌ Trinity Score v2 공식 미적용
- ❌ Profit Factor 미계산
- ❌ Win Rate 미계산
- ❌ 롤링 윈도우 방식 미구현 (1회성 검증만 존재)

### 2.2 llm_client.py

**현재 기능:**
- `EvolutionLLMClient` 클래스
- `_assemble_c_mode_context()`: C-mode 프롬프트 조립
- `_call_llm()`: LLM 호출 또는 mock 반환
- `_clean_code()`: 코드 추출 및 정리

**문제점:**
- ❌ 101줄: LLM 없을 시 mock 반환 (조용한 실패)
  ```python
  if self.llm_service:
      return await self.llm_service.generate(prompt)
  return "# Mock Strategy Code..."  # ❌ Silent fail
  ```
- ❌ 에이전트별 개인화 프롬프트 없음 (모든 에이전트 동일 프롬프트)
- ❌ 진화 모드 자동 선택 로직 없음

### 2.3 orchestrator.py

**현재 기능:**
- `EvolutionOrchestrator` 클래스
- `run_evolution_cycle()`: 진화 사이클 실행
- 상태 관리: IDLE → TRIGGERED → GENERATING → VALIDATING → COMMITTING → IDLE

**문제점:**
- ❌ MetricsBuffer와 연결 없음 (누적/일괄 피드백 구조 없음)
- ❌ 롤백 기능 없음 (T-013)
- ❌ 로그 파일 기록 없음 (T-011)
- ⚠️ `force_trigger=False` 시 자동 진화 없음

---

## 3. MENUAL.md Canonical 구조와의 차이

### 누락된 파일 목록 (Critical)

| 파일 | 우선순위 | 설명 |
|------|---------|------|
| `core/rolling_backtest_engine.py` | P0 | 실시간 롤링 백테스트 엔진 |
| `core/metrics_buffer.py` | P0 | 성과 지표 누적 및 LLM 트리거 |
| `core/scoring.py` | P0 | Trinity Score v2 단일 소스 |
| `agents/prompts/momentum_hunter.txt` | P1 | 추세 추종 전용 프롬프트 |
| `agents/prompts/mean_reverter.txt` | P1 | 평균 회귀 전용 프롬프트 |
| `agents/prompts/macro_trader.txt` | P1 | 거시경제 기반 프롬프트 |
| `agents/prompts/chaos_agent.txt` | P1 | 비선형/이상 감지 프롬프트 |

---

## 4. 구현 우선순위 및 권장 접근법

### Phase 1: P0 핵심 피드백 루프 (반드시 선행)

1. **scoring.py 생성** (T-006)
   - Trinity Score v2 공식 단일 소스화
   - backtest_manager.py에서 임포트하도록 수정

2. **rolling_backtest_engine.py 생성** (T-001)
   - 매 틱/분마다 실행되는 롤링 윈도우 엔진
   - MetricsBuffer에 결과 push

3. **metrics_buffer.py 생성** (T-002)
   - 에이전트별 버퍼링
   - 30분 또는 30틱 누적 시 LLMFeedbackClient 트리거

4. **llm_client.py 수정** (T-003, T-004)
   - mock 반환 제거 → `LLMUnavailableError` 명시적 처리
   - MetricsBuffer와 연결

5. **backtest_manager.py 수정** (T-005)
   - Profit Factor 계산 추가
   - Win Rate 계산 추가

### Phase 2: P1 진화 품질 향상

6. **에이전트별 프롬프트 파일 작성** (T-008)
7. **진화 모드 자동 선택** (T-007)
8. **IS/OOS 동적 분리 강화** (T-009)

### Phase 3: P2 대시보드 및 운영

9. **성과 경쟁 대시보드** (T-010)
10. **구조화된 로그 저장** (T-011)
11. **진화 성공률 추적** (T-012)
12. **전략 롤백 기능** (T-013)

---

## 5. 기술 부채 요약

| 위치 | 문제 | 영향 | 해결 방안 |
|------|------|------|----------|
| llm_client.py:101 | mock 반환 | Silent fail | 예외 발생 후 Supabase 기록 |
| backtest_manager.py:61-66 | 구버전 점수 공식 | 점수 산출 오류 | scoring.py 임포트 |
| backtest_manager.py 전체 | PF, WR 미계산 | Trinity Score 불완전 | 지표 계산 추가 |
| orchestrator.py | MetricsBuffer 없음 | 피드백 루프 미작동 | 버퍼 클래스 신규 구현 |
| 전체 | rolling 엔진 없음 | 실시간 성과 재계산 불가 | rolling_backtest_engine 신규 |

---

## 6. 다음 단계 권장사항

**즉시 필요한 작업:**
1. Task #6 (Trinity Score v2 단일 소스화) - 다른 계산의 기초
2. Task #1 (롤링 백테스트 엔진) - 피드백 루프의 핵심
3. Task #2 (MetricsBuffer) - 누적/일괄 구조

**병렬 수행 가능한 독립 작업:**
- Task #8 (에이전트별 프롬프트 개인화)
- Task #5 (Profit Factor + Win Rate 계산)
