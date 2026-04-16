# Project Overview

## 목표
전략 생성을 LLM에 맡기되, 실제 채택은 백테스트 품질(OOS 포함)로 판단하는 자동 진화형 트레이딩 연구 플랫폼 구축.

## 기술 스택
- Frontend: Next.js 16.2.2, React 19, TypeScript
- Backend: FastAPI, APScheduler
- Data: Supabase, Binance Futures Kline API
- LLM: Ollama 직접 호출 + OpenAI/Anthropic 호환 엔드포인트

## 주요 도메인 객체
- Agent: `momentum_hunter`, `mean_reverter`, `macro_trader`, `chaos_agent`
- Strategy: 코드 + 파라미터 + rationale + 버전
- BacktestResult: 수익률/샤프/MDD/PF/WinRate/Trinity
- EvolutionEvent: 상태 전이/검증/채택 로그

## 운영 모드
- 수동 루프: `POST /api/agents/run-loop`
- 자동 루프: APScheduler (`/api/system/automation` on/off)
- 채팅 전략 생성: `POST /api/chat/run` (SSE)
- 백테스트 분석: `/api/backtest/*`
