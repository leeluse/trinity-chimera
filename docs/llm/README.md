# LLM Docs

이 문서는 TRINITY-CHIMERY의 LLM 계층만 다룹니다.

## Scope
- 백테스트 채팅 응답 생성
- 전략 생성 + 백테스트 실행 오케스트레이션
- provider 선택(`openai-compatible`, `nim`, `ollama`, `local`)
- 우측 채팅 패널과 좌측 백테스트 패널 동기화

## Server Modules
- `server/api/routes/chat.py`
  - 채팅 관련 API 엔드포인트 집합
- `server/api/services/llm/chat_client.py`
  - 공통 LLM 호출 클라이언트
  - provider/timeout/메시지 포맷 처리
- `server/api/services/backtest_strategy_catalog.py`
  - 백테스트 전략 메타/키워드 라우팅 분리 모듈
  - 전략 선택 로직(`resolve_strategy_key`)과 표시 메타(`get_strategy_meta`) 제공
- `server/api/services/llm/strategy_runner.py`
  - 분리된 카탈로그에서 전략 선택/메타 로드
  - `backtesting-trading-strategies` 스킬 런타임 실행
  - 스킬 백테스트 실행 + 결과 정규화
  - 전략 카드/백테스트 카드/최종 분석 텍스트 구성

## Backtest Skill Coupling
- 기본 경로: `server/backtesting-trading-strategies`
- fallback 경로: `.agents/skills/backtesting-trading-strategies`
- `strategy_runner`는 스킬의 `scripts/backtest.py`를 로드해 실행합니다.
- 전략 코드는 `strategies` 테이블에서 우선 로드하며, 런타임에서 `db::<strategy_key>`로 실행됩니다.

## Chat-Run UX Flow (백테스트 페이지)
`POST /api/backtest/chat-run` 응답은 아래 순서의 UI 렌더를 목표로 합니다.

1. 어시스턴트 ACK
- `assistant_ack`: "지금 바로 전략을 구축하겠습니다. 코드를 생성하고 백테스트를 실행합니다."
2. 전략 카드
- `strategy_card.title`, `strategy_card.description`, `strategy_card.code`
3. 백테스트 카드
- `backtest_card.ret/mdd/winRate/sharpe/trades/pf`
4. 최종 분석 텍스트 + 좌측 패널 동기화
- `analysis` (자연어 요약)
- `backtest_payload` (좌측 백테스트 결과 렌더용 원본 데이터)

즉 우측 채팅 패널은 카드/요약을 보여주고, 좌측 패널은 같은 요청의 `backtest_payload`로 즉시 갱신합니다.

## DB 전략 코드 연동 규칙
- 전략 선택: `backtest_strategy_catalog.resolve_strategy_key()`
- 전략 코드 조회: `skill_backtest_runtime.get_strategy_source()`
- 코드 실행: `skill_backtest_runtime.run_skill_backtest()`
- 결과 요약: `strategy_runner.run_strategy_chat_backtest()`에서 카드/분석 조립

운영 기준:
- `strategies.source='system'`: 시드/기본 전략
- `strategies.source='agent'`: 에이전트 생성 전략
- `strategies.source='user'`: 사용자 저장 전략

## API Endpoints
- `POST /api/backtest/chat`
  - 일반 백테스트 질의응답
- `POST /api/backtest/chat-run`
  - 단일 요청 파이프라인:
  - 전략 생성 안내
  - 전략 카드
  - 백테스트 카드
  - 최종 요약
  - 왼쪽 패널 반영용 `backtest_payload`

## Env Keys
- `LLM_PROVIDER`
- `LLM_TIMEOUT`
- `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `NIM_BASE_URL`, `NVIDIA_NIM_API_KEY`, `NIM_MODEL`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

## Frontend Coupling
- `client/components/chat/ChatInterface.tsx`
  - 예시 프롬프트 클릭 -> `/api/backtest/chat-run` 호출
  - `strategy`/`backtest` 카드 렌더
  - `onBacktestGenerated(backtest_payload)` 콜백으로 좌측 패널 동기화
