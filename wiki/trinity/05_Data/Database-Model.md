# Database Model (Supabase)

## 접근 계층
`server/shared/db/supabase.py`

## 주요 테이블
- `agents`
- `strategies`
- `backtest_results`
- `evolution_logs`
- `improvement_logs`
- `chat_messages`

## 전략 관련 흐름
1. `get_agent_strategy(agent_id)`
2. `save_strategy(...)` 또는 `save_system_strategy(...)`
3. `save_backtest(...)`
4. `save_improvement_log(...)`

## 채팅 이력
- 저장: `save_chat_message(session_id, role, content, type, data)`
- 조회: `get_chat_history(session_id, limit)`

## 시스템 전략 카탈로그
`ensure_system_agent()`가 `system_strategy_catalog` 에이전트를 보장.
