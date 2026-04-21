# API Reference

## Base
- 기본 Prefix: `/api`
- CORS: `allow_origins=["*"]`

## System
- `GET /api/system/status`
- `GET /api/system/automation`
- `POST /api/system/automation`

## Evolution / Agents
- `POST /api/agents/run-loop`
- `POST /api/agents/{agent_id}/evolve`
- `GET /api/agents/{agent_id}/status`
- `GET /api/agents/{agent_id}/performance`
- `GET /api/agents/{agent_id}/timeseries?metric=score|return|sharpe|mdd|win`
- `POST /api/agents/{agent_id}/improve`

## Dashboard
- `GET /api/dashboard/improvement`
- `GET /api/dashboard/evolution-log?limit=120&agent_id=...`
- `GET /api/dashboard/metrics`

## Chat
- `GET /api/chat/history?session_id=...&limit=50`
- `POST /api/chat/run` (SSE)
- `POST /api/chat/backtest`
- `POST /api/chat/deploy`

## Backtest Engine
- `GET /api/backtest/run`
- `GET /api/backtest/strategies`
- `GET /api/backtest/strategies/{strategy_key}/code`
- `POST /api/backtest/leaderboard`
- `GET /api/backtest/market/ohlcv`
- `POST /api/backtest/llm/backtest-analysis`
