# Module Map

## Backend Modules
- `server/modules/evolution`
  - `router.py`: 루프/상태/대시보드 API
  - `orchestrator.py`: 진화 사이클 오케스트레이션
  - `trigger.py`: 트리거(heartbeat 등)
  - `scoring.py`: Trinity v1 기반 비교 함수

- `server/modules/chat`
  - `router.py`: chat run/history/backtest/deploy API
  - `handler.py`: SSE 파이프라인(추론→설계→코드→검증)
  - `prompts.py`: 시스템/단계별 프롬프트 템플릿

- `server/modules/engine`
  - `router.py`: 백테스트 API 집합
  - `runtime.py`: 전략 코드 실행, 데이터 수집, 결과 집계

- `server/modules/backtest`
  - `backtest_engine.py`: 고급 검증 엔진 (WFO/MC/Regime)
  - `evolution/evolution_engine.py`: 진화용 검증 파이프라인

## Shared
- `server/shared/db/supabase.py`: DB CRUD, 전략/로그/채팅 기록
- `server/shared/market/provider.py`: Binance OHLCV 수집
- `server/shared/market/strategy_loader.py`: AST 검증 + 동적 로더
- `server/shared/llm/client.py`: Ollama 채팅 스트리밍
- `server/shared/llm/llm_client.py`: OpenAI 호환 LLM 클라이언트

## Frontend
- `client/app/page.tsx`: 대시보드
- `client/app/backtest/BacktestClientPage.tsx`: 백테스트+채팅
- `client/lib/api.ts`: API Client + fetch fallback
- `client/components/panel/sections/EvolutionLogPanel.tsx`: 로그 패널
