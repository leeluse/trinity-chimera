# [설계 문서] Trinity AI Trading System: 백엔드 구조 전환

## 1. 개요
본 설계는 기존의 Mock 기반 API 서버를 실제 LLM 자율 진화 루프가 작동하는 시스템으로 전환하는 것을 목표로 합니다.
- **핵심 루프**: 시장 데이터 $\rightarrow$ LLM 전략 코드 생성 $\rightarrow$ 샌드박스 백테스트 $\rightarrow$ Trinity Score 계산 $\rightarrow$ Supabase 저장 $\rightarrow$ 다음 진화 주기 예약.
- **핵심 결정 사항**: 동적 코드 실행(B), 자율 스케줄링(A), Supabase 경량 저장.

## 2. Supabase 데이터 모델 (ERD)
데이터베이스는 에이전트의 '진화 계보'를 추적하는 데 최적화합니다.

### `agents` 테이블
- `id`: UUID (PK)
- `name`: string (예: MINARA V2)
- `persona`: text (페르소나 정의)
- `current_strategy_id`: UUID (FK $\rightarrow$ `strategies.id`)
- `status`: string (IDLE, EVOLVING, BACKTESTING)
- `last_evolution_at`: timestamp

### `strategies` 테이블 (전략 버전 관리)
- `id`: UUID (PK)
- `agent_id`: UUID (FK)
- `version`: integer (v1, v2...)
- `code`: text (**LLM이 생성한 실제 Python 코드**)
- `params`: jsonb (코드 내 사용된 주요 하이퍼파라미터)
- `rationale`: text (LLM이 이 전략을 선택한 이유)
- `created_at`: timestamp

### `backtest_results` 테이블 (성과 추적)
- `id`: UUID (PK)
- `strategy_id`: UUID (FK)
- `trinity_score`: float (핵심 KPI)
- `return_val`: float
- `sharpe`: float
- `mdd`: float
- `win_rate`: float
- `test_period`: string (예: "2026-01-01 to 2026-02-01")
- `created_at`: timestamp

### `improvement_logs` 테이블 (피드백 루프)
- `id`: UUID (PK)
- `agent_id`: UUID (FK)
- `prev_strategy_id`: UUID (FK)
- `new_strategy_id`: UUID (FK)
- `llm_analysis`: text (강점, 약점, 개선 제안)
- `expected_improvement`: jsonb (예상 상승 수치)

## 3. 핵심 컴포넌트 설계

### 3.1 Dynamic Strategy Sandbox (동적 코드 실행기)
LLM이 생성한 코드를 안전하게 실행하기 위한 계층입니다.
- **`StrategyInterface`**: 모든 생성 전략이 반드시 구현해야 할 추상 클래스 (예: `generate_signal()`, `get_params()`).
- **`StrategyLoader`**:
    - Supabase에서 `code`를 가져와 `exec()`를 통해 메모리에 클래스로 로드.
    - **안전장치**: `ast.parse`를 이용해 금지된 키워드(`os`, `sys`, `subprocess`, `shutil` 등)가 포함되었는지 사전 검사.
    - **Timeout**: 백테스트 실행 시 `multiprocessing`을 이용해 최대 실행 시간 제한 (예: 30초).

### 3.2 Autonomous Evolution Orchestrator (자율 루프 관리자)
`APScheduler`를 사용하여 에이전트별로 진화 주기를 관리합니다.
- **상태 머신(State Machine)**:
    1. `TRIGGER`: 주기 도래 또는 Regime 변경 감지.
    2. `GENERATE`: LLM에게 [최근 성과 + 시장 데이터 + 현재 코드] 제공 $\rightarrow$ 새 코드 생성.
    3. `VALIDATE`: 샌드박스에서 백테스트 실행 $\rightarrow$ Trinity Score 계산.
    4. `COMMIT`: $\text{New Score} > \text{Old Score}$ (또는 기준치 이상)일 경우 Supabase에 새 버전으로 저장 및 반영.

## 4. API 엔드포인트 전환 (Mock $\rightarrow$ Real)

| 기존 엔드포인트 | 변경 사항 | 데이터 소스 |
| :--- | :--- | :--- |
| `/api/agents/{id}/improve` | 루프 강제 실행 트리거로 변경 | Supabase $\rightarrow$ Orchestrator |
| `/api/agents/{id}/backtest` | 최신 `backtest_results` 조회 | Supabase `backtest_results` |
| `/api/agents/{id}/feedback` | `improvement_logs` 이력 조회 | Supabase `improvement_logs` |
| `/api/dashboard/metrics` | 에이전트별 최신 Trinity Score 집계 | Supabase `backtest_results` |
| `/api/agents/{id}/timeseries` | `backtest_results`에서 시간순 추출 | Supabase `backtest_results` |

## 5. 프론트엔드 연동 전략
- **실시간 업데이트**: Supabase의 **Realtime** 기능을 사용하여, 백엔드에서 전략 진화가 완료되는 즉시 프론트엔드의 '전략 로그'와 '성과 차트'가 새로고침 없이 업데이트되도록 구현.
- **코드 뷰어**: 대시보드에 LLM이 생성한 `strategies.code`를 확인할 수 있는 코드 뷰어 컴포넌트 추가 제안.
