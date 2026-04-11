# Agent Code Migration Plan

## Goal
- Move the current agent-related implementation out of `api/services/` and into `ai_trading/agents/` so the repository structure matches the design docs.
- Keep the FastAPI layer as a thin orchestration/API boundary.
- Document the migration clearly so future work knows where the canonical agent code lives.

## Current Reality
- `ai_trading/agents/` is effectively empty except for `CLAUDE.md`.
- The actual agent logic currently lives in:
  - `api/services/evolution_orchestrator.py`
  - `api/services/evolution_llm_client.py`
  - `api/services/evolution_trigger.py`
  - parts of `api/services/self_improvement.py`
- The four agent identities are logical IDs, not separate runtime daemons.

## Proposed Target Layout
- `ai_trading/agents/__init__.py`
- `ai_trading/agents/orchestrator.py`
- `ai_trading/agents/llm_client.py`
- `ai_trading/agents/trigger.py`
- `ai_trading/agents/personas.py` or `ai_trading/agents/constants.py` for agent-name mappings
- Keep infrastructure-only code in `api/services/`:
  - `supabase_client.py`
  - any API-specific transport/integration wrappers

## Migration Steps
- [x] Create a canonical `ai_trading/agents` package.
- [x] Move `EvolutionOrchestrator` into `ai_trading/agents/orchestrator.py`.
- [x] Move `EvolutionLLMClient` into `ai_trading/agents/llm_client.py`.
- [x] Move `EvolutionTrigger` into `ai_trading/agents/trigger.py`.
- [x] Extract agent ID/name mapping into a dedicated agents module.
- [x] Update `api/main.py` to import the moved orchestrator from `ai_trading.agents`.
- [x] Update `api/services/self_improvement.py` to call the new agents package rather than importing from `api.main`.
- [x] Keep `SupabaseManager` in the API layer unless the migration reveals a cleaner shared location.
- [x] Update imports in any other files that reference the old service paths.
- [x] Verify the package still loads under the project venv and `PYTHONPATH=..`.

## Documentation Tasks
- [x] Update `ai_trading/research.md` with the final migration decision and file locations.
- [x] Update `docs/superpowers/progress/current-state.md` after the move is complete.
- [x] Add or update a session checkpoint file for the migration session.
- [x] Update any project docs that still describe `api/services/` as the canonical home for agent orchestration.

## Verification Plan
- [x] `python -m` or direct import check for `ai_trading.agents` modules.
- [x] `api.main` import test under the venv with `PYTHONPATH=..`.
- [x] `trn` syntax remains valid after the move.
- [x] `./run api` still starts or prints the expected "already running" message if port 8000 is occupied.
- [x] Confirm the agent IDs still resolve to the same four personas in the frontend and backend.

## Risks / Notes
- `api/services/self_improvement.py` currently imports `evolution_orchestrator` from `api.main`, which is a tight coupling. This should be cleaned up during migration.
- The codebase currently mixes “agent persona” concerns and “API service” concerns, so some files may need to stay as wrappers instead of being moved wholesale.
- If a full move would create import cycles, prefer a small compatibility shim in `api/services/` while keeping the real implementation under `ai_trading/agents/`.

## Completion Criteria
- The canonical agent implementation lives under `ai_trading/agents/`.
- `api/services/` no longer owns the primary agent orchestration logic.
- The repository docs reflect the new structure.
- Imports and startup paths are verified after the move.
