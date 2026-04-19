# Route Map

## FastAPI Router Mount
- `chat_router` -> `/api/chat/*`
- `evolution_router` -> `/api/agents/*`
- `dashboard_router` -> `/api/dashboard/*`
- `engine_router` -> `/api/backtest/*`

## 주요 프론트 호출
- Dashboard: `APIClient.getDashboardProgress/metrics/evolution-log/automation`
- Run Loop: `APIClient.runEvolutionLoop`
- Backtest: `/api/backtest/strategies`, `/api/backtest/run`
- Chat: `/api/chat/run`, `/api/chat/history`, `/api/chat/deploy`

## Next Rewrite
- `/api/:path* -> {backendBase}/api/:path*`
- `backendBase = BACKEND_API_URL || NEXT_PUBLIC_API_URL || localhost`
