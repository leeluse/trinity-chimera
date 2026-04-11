# Backtest Docs

이 문서는 TRINITY-CHIMERY의 백테스트 계층만 다룹니다.

## Scope
- 실시간/히스토리 OHLCV 수집
- Skill 엔진 기반 전략 백테스트
- LLM 전략-실행 파이프라인(`chat-run`)에서 백테스트 결과 산출/정규화
- 전략 코드 DB 저장/로드 기반 실행

## Server Modules
- `server/api/services/market_data.py`
  - 바이낸스 OHLCV 조회
- `server/api/services/skill_backtest_runtime.py`
  - 스킬 로딩/전략 목록/코드 조회
  - 백테스트 실행
  - 결과(`results`, `trades`, `markers`, `candles`) 정규화
  - 로컬 전략을 Supabase `strategies` 테이블로 시드
  - DB 전략 코드를 런타임에 동적 등록 후 실행

## Skill Layer
- `server/backtesting-trading-strategies`
  - LLM `chat-run`에서 사용하는 기본 백테스트 스킬 위치
  - `scripts/backtest.py`: 전략 실행 엔진
  - `scripts/strategies.py`: 전략 클래스 구현
- 레거시 fallback: `.agents/skills/backtesting-trading-strategies`
- `server/backtest/`는 선택적 레거시 모듈로 간주 (현재 API 필수 의존 아님)
- `server/api/services/skill_backtest_runtime.py`
  - 로컬 전략 코드를 `strategies` 테이블(`source='system'`)에 시드
  - 실행 시 DB 전략 코드를 동적 로드하여 백테스트 수행

## DB-First Runtime Flow
1. `list_skill_strategies()` 호출 시 `seed_local_strategies_to_db()`가 1회 실행됩니다.
2. 시드 대상: `server/backtesting-trading-strategies/scripts/strategies.py`에 있는 로컬 전략.
3. 저장 위치: Supabase `strategies` 테이블 (`source='system'`, `params.strategy_key` 기준).
4. 실행 시 `get_strategy_source(strategy_key)`가 DB 코드를 우선 조회합니다.
5. 코드를 런타임 클래스(`db::<strategy_key>`)로 등록해 `run_skill_backtest()`에서 실행합니다.
6. DB 미연결/조회 실패 시 로컬 스킬 코드로 fallback 합니다.

## Strategies Table Contract
백테스트 런타임이 기대하는 최소 조건은 아래와 같습니다.

- `strategies.code`: 실행 가능한 전략 클래스 코드
- `strategies.source`: `system | agent | user`
- `strategies.params.strategy_key`: 전략 식별 키 (필수)
- `strategies.params.native_key`: 내부 매핑 키 (선택)
- `strategies.params.display_name`: 표시 이름 (선택)
- `strategies.params.supported_timeframes`: 허용 타임프레임 배열 (선택)

전략을 DB에서 불러 실행하려면 `params.strategy_key`가 API 요청 `strategy`와 일치해야 합니다.

## 전략을 DB에 넣는 기준
- 시스템 기본 전략: `source='system'` (시드 자동 생성)
- 에이전트가 진화로 만든 전략: `source='agent'`
- 사용자가 수동 저장한 전략: `source='user'`

권장 패턴:
1. `strategies`에 코드 저장
2. `params.strategy_key`/`display_name`/`supported_timeframes` 채우기
3. `/api/backtest?strategy=<strategy_key>` 또는 `/api/backtest/chat-run`으로 실행

## API Endpoints
- `GET /api/backtest`
  - 전략 백테스트 실행
- `GET /api/backtest/strategies`
  - 사용 가능한 전략 목록
- `GET /api/backtest/strategies/{strategy_key}/code`
  - 전략 소스 코드 조회
- `POST /api/backtest/leaderboard`
  - 멀티 타임프레임/전략 랭킹 계산
- `GET /api/market/ohlcv`
  - 차트용 OHLCV 조회
- `POST /api/llm/backtest-analysis`
  - 백테스트 결과의 deterministic 요약

## Chat-Run Coupling
- `POST /api/backtest/chat-run`은 내부적으로:
  1. 전략 선택/파라미터 생성
  2. 백테스트 실행
  3. UI 친화 payload(`backtest_payload`) 생성
- 결과 payload는 프론트 `parseResults()`와 직접 호환되도록 설계됨.

## Output Contract (요약)
- `results`
  - `total_pnl`, `total_return`, `win_rate`, `max_drawdown`, `sharpe_ratio`, `profit_factor`, `total_trades`, `best_trade`, `worst_trade`, `win_count`, `loss_count`
- `trades`: 표/로그용 체결 리스트
- `markers`: 차트 마커
- `candles`: 캔들 차트 데이터
