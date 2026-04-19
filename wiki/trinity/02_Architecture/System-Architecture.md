# System Architecture

```mermaid
flowchart LR
  UI[Next.js Dashboard/Backtest/Chat] --> API[FastAPI /api]
  API --> EVO[Evolution Orchestrator]
  API --> CHAT[Chat Handler SSE]
  API --> ENG[Backtest Runtime]

  EVO --> DB[(Supabase)]
  EVO --> LLM[LLM Client]
  EVO --> BTE[Backtest Evolution Engine]

  CHAT --> LLM
  CHAT --> BTE
  CHAT --> DB

  ENG --> BINANCE[Binance Kline API]
  ENG --> DB
```

## 계층
- Presentation: `client/*`
- API Layer: `server/api/main.py`, `server/modules/*/router.py`
- Domain Layer: `server/modules/evolution|chat|backtest|engine/*`
- Shared Infra: `server/shared/db|llm|market/*`

## 스케줄러
- `APScheduler`가 startup 시 `evolution_poll` 등록
- 기본 상태 `paused`
- `/api/system/automation`으로 resume/pause 제어
