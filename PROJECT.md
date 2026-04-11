# PROJECT.md - Trinity AI Trading System

> 이 문서는 현재 코드베이스의 실제 구조와 실행 흐름을 기준으로 정리한 프로젝트 개요입니다.
> 설계 의도와 구현 위치가 어긋난 부분은 가능한 한 현재 상태를 기준으로 설명합니다.

관련 세부 문서:
- Backtest: [`docs/backtest/README.md`](docs/backtest/README.md)
- LLM: [`docs/llm/README.md`](docs/llm/README.md)
- Server Structure: [`docs/server-structure.md`](docs/server-structure.md)

## 0. 현재 기준 (Backtest/LLM)

백테스트/채팅 결합 구간의 canonical 경로는 아래입니다.

- API 진입
  - `POST /api/backtest/chat-run` (`server/api/routes/chat.py`)
  - `GET /api/backtest*` (`server/api/routes/backtest.py`)
- 전략 선택/카드 구성
  - `server/api/services/backtest_strategy_catalog.py`
  - `server/api/services/llm/strategy_runner.py`
- 백테스트 실행
  - `server/api/services/skill_backtest_runtime.py`
  - `server/backtesting-trading-strategies/scripts/backtest.py`
- 전략 코드 저장소 (source of truth)
  - Supabase `strategies` 테이블 (`source: system|agent|user`, `params.strategy_key` 기준)

즉 현재 백테스트 실행은 파일 직접 호출보다 DB 전략 코드 로드를 우선합니다.

---

## 1. 시스템 한눈에 보기

Trinity Chimery는 다음 4개 층으로 돌아갑니다.

- `client/` - 대시보드와 사용자 인터페이스
- `server/api/` - FastAPI 기반 실행/오케스트레이션 계층
- `server/ai_trading/agents/` - 에이전트 오케스트레이션, LLM, 트리거, 에이전트 ID 정의
- `server/ai_trading/core/` - 전략 검증, 백테스트, 샌드박스, 공용 전략 인터페이스

현재는 `server/ai_trading/agents/`가 에이전트 로직의 canonical 위치이고, `server/api/services/`는 호환 래퍼와 인프라 코드가 남아 있는 형태입니다.

---

## 2. 현재 실행 흐름

### 2.1 기본 실행 순서

```text
사용자/프론트엔드
  -> FastAPI /api 엔드포인트
  -> server.ai_trading.agents.EvolutionOrchestrator
  -> EvolutionLLMClient
  -> server.ai_trading.core.StrategyLoader / BacktestManager
  -> Supabase 저장소
  -> 결과가 다시 프론트엔드로 노출
```

### 2.2 실제 서버 구성

- `./run client` - Next.js 개발 서버 실행
- `./run server` - FastAPI 서버 실행
- `./trn` - tmux 세션으로 `client`, `server`, `trading` 작업 창을 동시에 띄움

---

## 3. 에이전트 모델

### 3.1 논리적 에이전트 4개

프로젝트는 아래 4개의 논리적 에이전트 ID를 사용합니다.

- `momentum_hunter`
- `mean_reverter`
- `macro_trader`
- `chaos_agent`

이들은 현재 개별 프로세스가 아니라, 하나의 중앙 오케스트레이터가 다루는 전략 페르소나입니다.

### 3.2 에이전트 식별 기준

이전에는 프론트엔드 표시명과 백엔드 `agent_id`를 연결하는 매핑이 있었지만, 지금은 그 계층을 제거했습니다.

- 백엔드와 프론트엔드는 공통으로 `agent_id`를 사용합니다.
- UI의 일부 예시 텍스트만 사람이 읽기 쉬운 이름을 유지할 수 있지만, 데이터 경로에는 이름 변환이 없습니다.

따라서 에이전트 식별의 기준은 항상 `agent_id`입니다.

### 3.3 에이전트가 실제로 하는 일

에이전트는 별도 서버가 아니라 다음 역할을 수행합니다.

- 현재 전략 코드와 메트릭을 받아서
- LLM 컨텍스트를 구성하고
- 새 전략 코드를 생성하고
- `StrategyLoader`로 검증하고
- `BacktestManager`로 성능을 재평가하고
- 통과하면 Supabase에 버전 저장

즉, “에이전트 = 실행 중인 독립 프로세스”가 아니라 “전략 진화 대상 + 진화 로직”에 가깝습니다.

---

## 4. Canonical 코드 위치

### 4.1 에이전트 계층

`server/ai_trading/agents/`가 현재 canonical 위치입니다.

- `constants.py` - 에이전트 ID 정의
- `trigger.py` - regime shift, performance decay, competitive pressure, heartbeat 판단
- `llm_client.py` - C-mode 컨텍스트 조립 및 LLM 코드 생성
- `orchestrator.py` - 진화 상태 머신과 저장/검증/커밋 흐름

### 4.2 공용 전략 계층

`server/ai_trading/core/`는 전략 실행과 검증의 기반입니다.

- `strategy_interface.py` - 모든 전략이 구현해야 하는 인터페이스
- `strategy_loader.py` - AST 기반 안전성 검증과 동적 로딩
- `backtest_manager.py` - IS/OOS 분리, 백테스트, Trinity Score 계산

### 4.3 API 계층

`server/api/`는 외부 진입점과 저장소 연결을 담당합니다.

- `main.py` - FastAPI 앱, 스케줄러, 엔드포인트
- `services/supabase_client.py` - Supabase 읽기/쓰기
- `services/*` - 기존 경로 호환용 래퍼

---

## 5. 핵심 루프

```text
시장 데이터 + 현재 전략
  -> 트리거 판정
  -> LLM이 C-mode 컨텍스트를 보고 새 코드 생성
  -> 코드 안전성 검사
  -> 백테스트 실행
  -> IS/OOS 또는 성과 게이트 통과 여부 확인
  -> Supabase에 전략 버전/백테스트/로그 저장
  -> 상태를 IDLE로 복귀
```

### 5.1 스케줄 기반 흐름

`server/api/main.py`의 `scheduled_evolution_poll()`는 매 시간 4개 에이전트 ID를 순회합니다.

하지만 현재 구현에서는 `force_trigger=False`일 때 내부 트리거가 사실상 비활성이라, 이 스케줄러는 “주기적으로 확인하는 틀”에 가깝습니다.

### 5.2 수동 진화 흐름

`POST /api/agents/{agent_id}/evolve`

- 특정 에이전트에 대해 진화 사이클을 강제로 시작
- 백그라운드 작업으로 진화 오케스트레이터 실행

### 5.3 자가 개선 요청 흐름

`POST /api/agents/{agent_id}/improve`

- 프론트엔드에서 개선 요청을 보내면
- `SelfImprovementService`가 `EvolutionOrchestrator`를 `force_trigger=True`로 호출
- 비동기 진화 사이클이 시작됩니다

---

## 6. LLM 전략 생성 방식

### 6.1 모드 1 - 파라미터 조정

초기 단계에서는 기존 전략 템플릿 안에서 수치만 조정하는 방식입니다.

### 6.2 모드 2 - 자유 생성

목표 단계에서는 LLM이 전략의 구조 자체를 코드로 생성합니다.

구현 방식은 다음과 같습니다.

- 동적 Python 코드 생성
- `StrategyLoader.validate_code()`로 AST 검증
- `StrategyLoader.load_strategy()`로 동적 인스턴스화
- `execute_with_timeout()`으로 실행 시간 제한

### 6.3 C-mode 컨텍스트

`EvolutionLLMClient`는 다음 정보를 묶어서 LLM 프롬프트를 만듭니다.

- 현재 전략 코드
- Trinity Score, Return, Sharpe, MDD
- 손실 구간 로그
- 과거 진화 이력
- 경쟁 순위
- 시장 국면과 변동성

현재 구현은 이 구조를 기준으로 프롬프트를 만들고, LLM 서비스가 없으면 mock 전략 코드를 반환합니다.

---

## 7. Trinity Score

현재 코드는 다음 공식을 사용합니다.

```text
Trinity Score = Return × 0.40 + Sharpe × 25 × 0.35 + (1 + MDD) × 100 × 0.25
```

실제로는 백엔드와 프론트엔드에서 같은 공식을 공유하도록 맞춰져 있습니다.

---

## 8. 저장소와 메트릭

### 8.1 Supabase 역할

Supabase는 다음을 저장합니다.

- 전략 버전
- 백테스트 결과
- 개선 로그
- 에이전트 현재 전략 참조

### 8.2 현재 저장 계층 분리

- `SupabaseManager`는 `server/api/services/supabase_client.py`에 유지
- 에이전트 진화 로직은 `server/ai_trading/agents/orchestrator.py`에 유지
- API는 둘 사이의 연결점 역할

### 8.3 로깅 상태

현재 백엔드는 `logging.basicConfig(level=logging.INFO)`를 사용합니다.

즉, 로그는 기본적으로 프로세스 stdout/stderr로 나가고, `logs/evolution.log`에 자동으로 쓰는 별도 파일 핸들러는 아직 없습니다.

그래서 `trn`의 `trading` 창에서 tail 하는 파일은 “로그 파일이 생기면 보여주는 감시창”이고, 실제 파일이 없으면 `Waiting for logs...`가 보이는 것이 정상입니다.

---

## 9. 디렉터리 구조

```text
trinity-chimery/
├── run                # 단일 서비스 실행 스크립트
├── trn                # tmux 기반 통합 실행 스크립트
├── client/          # Next.js 프론트엔드
├── server/           # 백엔드 코드 모음
│   ├── api/           # FastAPI API 레이어
│   ├── ai_trading/    # 트레이딩 엔진, 에이전트, 백테스트
│   │   ├── core/      # 전략 인터페이스, 로더, 백테스트 매니저
│   │   ├── agents/    # 에이전트 오케스트레이터, LLM, 트리거, 매핑
│   │   ├── rl/        # 강화학습 실험 코드
│   │   ├── freqai/    # FreqAI 관련 실험/데이터
│   │   └── tests/     # 전략/통합/샌드박스 테스트
│   └── tests/         # API/오케스트레이션 단위 테스트
└── docs/              # 계획, 상태, 세션 체크포인트
```

---

## 10. 실행 및 인프라

- **Database**: Supabase (PostgreSQL)
- **Scheduler**: APScheduler
- **Frontend**: Next.js
- **Backend**: FastAPI
- **전략 실행**: `StrategyLoader` + `BacktestManager`
- **통합 실행**: `./trn`

---

## 11. 설계 결정

- **ADR-001**: 전략 생성은 템플릿 기반에서 자유 생성으로 점진 확장
- **ADR-002**: LLM 입력은 백테스트 결과와 실시간 시장 데이터의 조합
- **ADR-003**: Trinity Score를 최적화 목표 지표로 사용
- **ADR-006**: IS/OOS 분리와 보수적 비용 모델로 과적합 완화
- **ADR-007**: 전략 이력과 메트릭은 Supabase에 경량 저장

---

## 12. 현재 구현의 중요한 해석

이 프로젝트에서 “에이전트”라는 말은 두 가지 의미를 가집니다.

1. UI/설계 관점의 에이전트
   - 4개의 페르소나
   - 전략 스타일과 성향을 대표

2. 코드 관점의 에이전트
   - `server/ai_trading/agents/` 안의 오케스트레이터/LLM/트리거 로직
   - `server/api/main.py`가 주기적으로 혹은 수동으로 호출하는 진화 대상

현재 코드는 1번의 개념을 2번의 로직으로 구현하는 구조입니다.

즉, “4개의 독립 AI”가 있는 것이 아니라, 하나의 오케스트레이션 계층이 4개의 전략 페르소나를 관리하는 형태입니다.
