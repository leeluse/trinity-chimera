# Server Structure

이 문서는 `server/` 구조를 역할별로 분리한 현재 상태를 설명합니다.

## Design Principles
Context7/FastAPI 권장 패턴을 기준으로 아래 원칙을 적용했습니다.

- 라우터(`routes`)는 HTTP 입출력과 유효성 검사에 집중
- 서비스(`services`)는 비즈니스 로직 실행
- 도메인 모듈(`server/backtesting-trading-strategies`, `server/ai_trading`)은 독립 실행 가능
- 호환성 유지를 위해 이전 import path는 래퍼로 유지
- 전략 실행 소스는 파일 우선이 아니라 DB 우선(`strategies` 테이블)으로 통일

## Current Layout
```text
server/
  api/
    main.py
    routes/
      agents.py
      backtest.py      # 백테스트 API
      chat.py          # LLM/채팅 API (분리)
    services/
      backtest_strategy_catalog.py # 전략 라우팅/메타
      market_data.py               # OHLCV 수집
      skill_backtest_runtime.py    # DB-first 백테스트 런타임
      supabase_client.py           # strategies/agents/backtest_results 접근
      llm/
        chat_client.py
        strategy_runner.py
      light_chat_llm.py        # backward-compat wrapper
      strategy_chat_runner.py  # backward-compat wrapper
      ...
  ai_trading/
    agents/
    core/
  backtesting-trading-strategies/
    SKILL.md
    scripts/
      backtest.py
      strategies.py

.agents/
  skills/
    backtesting-trading-strategies/
      SKILL.md
      scripts/
        backtest.py
        strategies.py

legacy (optional):
  server/backtest/
```

## Runtime Ownership
- `server/api/routes/backtest.py`
  - `/api/backtest`, `/api/backtest/strategies`, `/api/backtest/leaderboard`, `/api/market/ohlcv`
- `server/api/routes/chat.py`
  - `/api/backtest/chat`, `/api/backtest/chat-run`
- `server/api/services/skill_backtest_runtime.py`
  - 로컬 전략 시드(`source='system'`)
  - DB 코드 조회 + 동적 클래스 등록(`db::<strategy_key>`) + 실행
- `server/api/services/backtest_strategy_catalog.py`
  - 프롬프트 키워드 라우팅과 전략 표시 메타 분리

## Strategy Source of Truth
실행 기준 전략 코드는 `strategies` 테이블입니다.

- `source='system'`: 로컬 스킬 전략을 시드한 기본 전략
- `source='agent'`: 에이전트 생성 전략
- `source='user'`: 사용자 직접 저장 전략

`params.strategy_key`가 런타임 조회 키이며, 동일 키 최신 행이 실행 대상이 됩니다.

## Why This Split
- `backtest.py`가 LLM 엔드포인트까지 포함하던 결합을 해소
- LLM 기능은 `routes/chat.py` + `services/llm/*`로 모아 변경 영향 범위를 축소
- 테스트/운영 시 `Backtest`와 `LLM` 장애 영역을 구분하기 쉬워짐

## Migration Policy
- 기존 import 경로:
  - `server.api.services.light_chat_llm`
  - `server.api.services.strategy_chat_runner`
- 위 경로는 wrapper를 통해 계속 사용 가능 (점진 마이그레이션 가능)
