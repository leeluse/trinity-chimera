# PROJECT.md — Trinity AI Trading System
### 목적: Claude 단독 운영 기준 지침서
> 이 문서는 Claude가 프로젝트를 개선할 때 기준으로 삼는 단일 소스입니다.

---

## 0. 최종 목표

> **백테스트가 항상 돌고, 그 결과가 LLM에 흘러들어가고, LLM이 전략을 자율적으로 진화시키며, 사용자는 대시보드에서 에이전트 간 성과 경쟁을 지켜보며 좋은 전략을 픽업한다.**

이 시스템의 핵심은 **피드백 루프**입니다:

```
[롤링 윈도우 백테스트 — 매 틱/분 갱신]
       ↓ 성과 지표 실시간 누적
[N분 또는 N회 누적 후 LLM 피드백 일괄 실행]
       ↓ 전략 수정 + 즉시 배포
[대시보드 실시간 갱신]
       ↓
[사용자가 좋은 전략 픽업]
```

- **백테스트**: 매 틱/분마다 최근 N개월 데이터로 전략 성과 재계산 (롤링 윈도우)
- **LLM 피드백**: 백테스트는 실시간, LLM 호출은 누적 후 일괄 — 비용/속도 분리
- **전략 수정**: 점수 낮으면 자동으로 계속 수정 (완전 자율, 사람 승인 없음)
- **트리거**: 루프를 보조하는 수단일 뿐, 루프를 시작시키는 조건이 아님

---

## 1. 시스템 구조 (To-Be 기준)

### 1.1 피드백 루프 아키텍처

```
RollingBacktestEngine (매 틱/분 실행)
  → 최근 N개월 데이터로 전략 성과 재계산
  → 성과 지표를 MetricsBuffer에 누적
  → 대시보드로 실시간 스트리밍

MetricsBuffer
  → N분 경과 또는 N회 누적 시 LLMFeedbackClient 트리거
  → 누적 컨텍스트: 성과 추이 + 현재 전략 코드 + 이전 실패 이유

LLMFeedbackClient
  → 컨텍스트 구성 후 LLM 호출
  → 수정된 전략 코드 수신 → AST 검증 → 즉시 배포
  → 점수 개선 없어도 다음 누적 후 재시도 (완전 자율)

StrategyRegistry (Supabase)
  → 모든 버전 저장, 현재 활성 전략 관리, 롤백 이력 포함

Dashboard (Next.js)
  → 에이전트별 실시간 성과 순위 (Trinity Score 기준, 틱마다 갱신)
  → 전략 진화 타임라인 + 점수 변화 그래프
  → 현재 돌아가는 전략 코드 + 주요 시그널
```

### 1.2 백테스트 vs LLM 피드백 주기 분리

| 레이어 | 주기 | 이유 |
|--------|------|------|
| 롤링 백테스트 (성과 재계산) | 매 틱 / 매 분 | 성과 지표를 항상 최신으로 유지 |
| LLM 피드백 (전략 수정) | N분 누적 또는 N회 누적 후 일괄 | LLM 호출 비용/레이턴시 분리 |
| 대시보드 갱신 | 백테스트와 동기 (실시간) | 사용자가 최신 성과를 즉시 확인 |

> **N값 초기 권장**: LLM 피드백은 30분 누적 또는 30틱 누적 중 먼저 도달한 조건 기준.
> 운영 중 비용/성능 관찰 후 조정.

### 1.3 에이전트 4종 (페르소나)

| agent_id         | 전략 스타일         |
|------------------|---------------------|
| momentum_hunter  | 추세 추종            |
| mean_reverter    | 평균 회귀            |
| macro_trader     | 거시경제 기반        |
| chaos_agent      | 비선형/이상 감지     |

4개 에이전트는 독립적으로 롤링 백테스트 → 누적 → LLM 피드백 → 배포 루프를 돌립니다.

### 1.4 Trinity Score v2 (scoring.py 단일 소스)

```
Trinity Score v2 =
  Return        × 0.30
  + Sharpe × 25 × 0.25
  + (1+MDD)×100 × 0.20
  + PF × 20     × 0.15
  + WinRate×100 × 0.10
```

백엔드/프론트엔드 모두 `ai_trading/core/scoring.py`에서 임포트합니다. 하드코딩 금지.

---

## 2. 현재 시스템의 핵심 문제 (Gap Analysis)

| 문제 | 위치 | 심각도 |
|------|------|--------|
| 백테스트가 실시간 롤링으로 돌지 않음 — 트리거 후 1회성 실행 | backtest_manager.py | 🔴 Critical |
| 백테스트 결과가 LLM에 자동으로 전달되지 않음 | llm_client.py, orchestrator.py | 🔴 Critical |
| MetricsBuffer 없음 — 누적/일괄 피드백 구조 자체가 없음 | (신규 필요) | 🔴 Critical |
| LLM 없을 때 mock 반환 — 조용한 실패 | llm_client.py | 🔴 Critical |
| Profit Factor 미계산 — Trinity Score에 PF 미반영 | backtest_manager.py | 🟠 High |
| 진화 모드 전환 기준 없음 | llm_client.py | 🟠 High |
| 대시보드가 성과 경쟁 구조를 보여주지 않음 | front/ | 🟠 High |
| 자율 트리거 비활성 — force_trigger=False이면 진화 미발생 | trigger.py | 🟡 Medium |
| 로그 파일 없음 — stdout만 사용 | api/main.py | 🟡 Medium |
| 전략 다양성 없음 — 모든 에이전트가 동일 프롬프트 구조 사용 | llm_client.py | 🟡 Medium |
| IS/OOS 분리 검증 약함 | backtest_manager.py | 🟡 Medium |

---

## 3. 개선 작업 목록 (Task Backlog)

> **우선순위: P0 → P1 → P2 순으로 처리**

---

### P0 — 피드백 루프 핵심 완성

#### T-001: 롤링 윈도우 백테스트 엔진
- **파일**: `ai_trading/core/rolling_backtest_engine.py` (신규)
- **작업**:
  - 매 틱/분마다 최근 N개월 데이터로 전략 성과 재계산
  - 계산 결과를 `MetricsBuffer`에 push
  - 에이전트 단위 격리 — 1개 실패해도 나머지 계속 진행
  - 대시보드 실시간 스트리밍용 WebSocket 또는 SSE 엔드포인트 연결
- **완료 기준**: 서버 시작 후 사람 개입 없이 성과 지표가 틱마다 갱신됨

#### T-002: MetricsBuffer — 누적 후 LLM 트리거
- **파일**: `ai_trading/core/metrics_buffer.py` (신규)
- **작업**:
  - 에이전트별 성과 지표를 버퍼링
  - 트리거 조건: 30분 경과 OR 30틱 누적 중 먼저 도달한 조건
  - 조건 충족 시 `LLMFeedbackClient` 자동 호출
  - 버퍼 초기화 후 다음 누적 시작
- **완료 기준**: 백테스트 누적 후 자동으로 LLM 호출까지 발생

#### T-003: LLM 자동 피드백 + 전략 배포
- **파일**: `ai_trading/agents/llm_client.py`, `ai_trading/agents/orchestrator.py`
- **작업**:
  - MetricsBuffer 트리거 수신 시 컨텍스트 구성:
    - 현재 전략 코드 + 최근 성과 추이 + 이전 실패 이유 + 탐색한 파라미터 범위
  - LLM 호출 → 수정된 전략 코드 수신
  - AST 검증 통과 시 즉시 배포
  - 점수 개선 없어도 다음 누적 후 재시도 (완전 자율)
- **완료 기준**: 버퍼 트리거 후 자동으로 전략 갱신까지 발생

#### T-004: LLM 실패 시 명시적 오류 처리
- **파일**: `ai_trading/agents/llm_client.py`
- **작업**:
  - mock 반환 제거
  - 실패 시 `LLMUnavailableError` → 해당 에이전트 건너뜀, 루프 유지
  - Supabase에 `evolution_failed` 상태 기록
- **완료 기준**: LLM 다운 시 silent fail 없이 오류 기록, 루프 중단 없음

#### T-005: Profit Factor + Win Rate 계산
- **파일**: `ai_trading/core/backtest_manager.py`
- **작업**:
  ```python
  profit_factor = sum(winning_trades) / abs(sum(losing_trades))
  win_rate = len(winning_trades) / total_trades
  ```
  - 손실 거래 0건, 거래 없음 엣지 케이스 처리 포함
- **완료 기준**: 모든 백테스트 결과에 PF + WR 포함

#### T-006: Trinity Score v2 단일 소스화
- **파일**: `ai_trading/core/scoring.py` (신규), `front/`
- **작업**: 공식을 `scoring.py`에 정의, 백엔드/프론트 임포트 구조 구성
- **완료 기준**: 공식 중복 정의 없음, 기존 전략 점수 재계산

---

### P1 — 진화 품질 향상

#### T-007: 진화 모드 자동 선택
- **파일**: `ai_trading/agents/llm_client.py`
- **작업**:
  ```python
  if evolution_count < 3 or trinity_score > 70:
      mode = "parameter_tuning"   # 모드 1: 파라미터 조정
  else:
      mode = "free_generation"    # 모드 2: 전략 구조 자유 생성
  ```
- **완료 기준**: 각 진화 로그에 사용된 모드 기록됨

#### T-008: 에이전트별 LLM 프롬프트 개인화
- **파일**: `ai_trading/agents/prompts/`
- **작업**: agent_id별 전용 프롬프트 파일 작성
  - `momentum_hunter`: 추세 강도, 모멘텀 지속성 집중
  - `mean_reverter`: 과매수/과매도 탐지, 회귀 속도 최적화
  - `macro_trader`: 금리/환율/원자재 상관관계 활용
  - `chaos_agent`: 비선형 패턴, 이상 거래량, 갭 활용
  - 공통: 이전 실패 이유 + 탐색 이력 주입 (같은 실패 반복 방지)
- **완료 기준**: 4개 에이전트가 구조적으로 다른 전략을 생성

#### T-009: IS/OOS 동적 분리
- **파일**: `ai_trading/core/backtest_manager.py`
- **작업**:
  - IS: 최근 6개월, OOS: 직전 2개월
  - Walk-forward 슬라이딩 윈도우 적용
- **완료 기준**: OOS Sharpe ≥ IS Sharpe × 0.7 이상일 때만 통과

---

### P2 — 대시보드 + 운영 안정성

#### T-010: 성과 경쟁 대시보드
- **파일**: `front/`
- **작업**: 한 화면에 3가지 표시
  1. **에이전트별 실시간 성과 순위** — Trinity Score 기준 랭킹, 틱마다 갱신
  2. **전략 진화 타임라인 + 점수 변화** — 어떤 진화 때 점수가 올랐는지
  3. **현재 돌아가는 전략 코드 + 주요 시그널** — 에이전트별 현재 전략 요약
- **완료 기준**: 사용자가 대시보드만 보고 좋은 전략을 가진 에이전트를 식별 가능

#### T-011: 구조화된 로그 파일 저장
- **파일**: `api/main.py`, `ai_trading/agents/orchestrator.py`
- **작업**: JSON Lines 포맷, 일별 파일 자동 생성
  ```
  logs/evolution_YYYYMMDD.log
  # 각 이벤트: agent_id, mode, score_before, score_after, duration_sec, buffer_trigger_reason
  ```
- **완료 기준**: `trn`에서 실시간 tail 가능

#### T-012: 진화 성공률 추적
- **파일**: `api/services/supabase_client.py`, `front/`
- **작업**: Supabase `evolution_stats` 테이블
  ```
  agent_id, date, total_attempts, success_count, avg_score_delta, avg_duration_sec
  ```
- **완료 기준**: 대시보드에 에이전트별 주간 진화 성공률 표시

#### T-013: 전략 롤백 기능
- **파일**: `api/main.py`, `ai_trading/agents/orchestrator.py`
- **작업**: 새 전략이 72시간 내 성과 급락 시 자동 롤백
  ```python
  if current_score < previous_score * 0.85:
      rollback_to_previous_version(agent_id)
      set_cooldown(agent_id, hours=6)  # 롤백 후 재진화 쿨다운
  ```
- **완료 기준**: `POST /api/agents/{agent_id}/rollback` 엔드포인트 + 자동 감지

#### T-014: 전략 코드 안전성 강화
- **파일**: `ai_trading/core/strategy_loader.py`
- **작업**: AST 검증 강화
  - 외부 네트워크 호출 금지 (`requests`, `urllib` 차단)
  - 파일 I/O 금지
  - 최대 사이클로매틱 복잡도 제한
- **완료 기준**: 위험 코드 자동 거부, 통과/거부 테스트 케이스 포함

---

## 4. 작업 방식 가이드라인 (Claude 단독)

각 태스크를 다음 순서로 처리합니다:

1. **분석**: 관련 파일과 현재 구현 파악
2. **설계**: 변경 범위와 인터페이스 정의
3. **구현**: 완료 기준 충족 + 엣지 케이스 처리
4. **검증**: 피드백 루프가 중단되지 않는지 확인
5. **문서화**: 완료 체크박스 + 변경 이력 업데이트

---

## 5. 코드 작성 원칙

### 5.1 공통 원칙
- Trinity Score 공식은 `scoring.py` 단일 소스 — 백엔드/프론트 모두 임포트
- agent_id는 항상 4개 중 하나: `momentum_hunter`, `mean_reverter`, `macro_trader`, `chaos_agent`
- 이름 변환 레이어 금지 — 데이터 경로에는 항상 agent_id 사용
- **피드백 루프는 어떤 오류에서도 중단되지 않아야 함** (에이전트 단위 격리)
- 백테스트(실시간)와 LLM 피드백(일괄)은 항상 분리된 레이어로 유지

### 5.2 백테스트 원칙
- 거래 비용 항상 포함 (슬리피지 + 수수료)
- IS/OOS 반드시 분리, look-ahead bias 금지
- 최소 거래 횟수: OOS 기간 내 20회 이상

### 5.3 LLM 프롬프트 원칙
- 전략 코드는 반드시 `BaseStrategy` 인터페이스 구현
- 생성된 코드에 `# Generated by Trinity AI` 주석 포함
- 프롬프트에 이전 실패 이유 + 탐색 이력 주입 (같은 실패 반복 방지)

---

## 6. 파일 구조 (Canonical)

```
trinity-chimery/
├── run                                  # 단일 서비스 실행
├── trn                                  # tmux 통합 실행
├── client/                               # Next.js 대시보드
│   └── (성과 경쟁 대시보드 — T-010)
├── api/
│   ├── main.py                          # FastAPI + 루프 시작점
│   └── services/
│       └── supabase_client.py           # evolution_stats — T-012
├── server/
│   ├── backtesting-trading-strategy/   # 단일 백테스팅 전용 백테스팅 로직
│   ├── ai_trading/
│   │   ├── core/
│   │   │   ├── strategy_interface.py        # BaseStrategy 인터페이스
│   │   │   ├── strategy_loader.py           # AST 검증 강화 — T-014
│   │   │   ├── backtest_manager.py          # PF + WR + IS/OOS — T-005, T-009
│   │   │   ├── rolling_backtest_engine.py   # 실시간 롤링 백테스트 — T-001 (ser)
│   │   ├── metrics_buffer.py            # 누적 후 LLM 트리거 — T-002 (신규)
│   │   └── scoring.py                   # Trinity Score v2 단일 소스 — T-006 (신규)
│   └── agents/
│       ├── constants.py                 # agent_id 정의
│       ├── trigger.py                   # 보조 트리거
│       ├── llm_client.py                # 피드백 수신 + 모드 분기 — T-003, T-007
│       ├── orchestrator.py              # 루프 조율 + 롤백 — T-013
│       └── prompts/                     # 에이전트별 프롬프트 — T-008 (신규)
│           ├── momentum_hunter.txt
│           ├── mean_reverter.txt
│           ├── macro_trader.txt
│           └── chaos_agent.txt
└── logs/
    └── evolution_YYYYMMDD.log           # 진화 이벤트 로그 — T-011
```

---

## 7. 완료 기준 (Definition of Done)

- [ ] 서버 시작 후 사람 개입 없이 매 틱/분마다 성과 지표 재계산
- [ ] 30분 또는 30틱 누적 후 LLM 피드백 자동 실행
- [ ] LLM 피드백으로 전략 수정 + 즉시 배포까지 자동 발생
- [ ] LLM 다운 시 silent fail 없이 명시적 오류 기록, 루프는 계속
- [ ] 모든 백테스트 결과에 Profit Factor, Win Rate 포함
- [ ] Trinity Score v2 공식이 `scoring.py` 단일 소스에서 백/프론트 공유
- [ ] 대시보드에서 에이전트별 실시간 성과 순위 확인 가능 (틱마다 갱신)
- [ ] 대시보드에서 전략 진화 타임라인 + 점수 변화 확인 가능
- [ ] 대시보드에서 현재 돌아가는 전략 코드 + 시그널 확인 가능
- [ ] 전략 롤백 기능 작동, 롤백 후 6시간 쿨다운 적용
- [ ] AST 검증이 네트워크/파일 I/O 포함 위험 코드 자동 거부

---

## 8. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
|------|-----------|--------|
| 초기 | As-Is 분석 및 To-Be 설계, 태스크 정의 | Claude |
| 2차 | Claude 단독 운영 체계로 전환 | Claude |
| 3차 | 트리거 중심 → 백테스트 상시 실행 + LLM 자동 피드백 루프 중심으로 재설계 | Claude |
| 4차 | 백테스트를 실시간 롤링 윈도우 방식으로 확정. LLM 피드백을 누적 후 일괄 구조로 분리. `rolling_backtest_engine.py`, `metrics_buffer.py` 신규 추가. | Claude |

---

> **이 문서는 살아있는 문서입니다.**
> Claude는 작업 전 반드시 이 문서를 읽고 시작합니다.
> 백테스트(실시간)와 LLM 피드백(일괄)은 항상 분리된 레이어로 유지합니다.