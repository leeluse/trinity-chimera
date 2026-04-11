# [Autonomous Evolution Orchestrator] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a background orchestration system that triggers strategy evolution based on market regimes and performance, manages the LLM generation/correction loop, and commits improved strategies to Supabase.

**Architecture:**
- **Orchestration**: `EvolutionOrchestrator` using `APScheduler` to manage agent state transitions (`IDLE` $\rightarrow$ `TRIGGERED` $\rightarrow$ `GENERATING` $\rightarrow$ `VALIDATING` $\rightarrow$ `COMMITTING`).
- **LLM Interface**: `EvolutionLLMClient` to handle "C-mode" context assembly and the self-correction loop (up to 3 retries).
- **Integration**: Ties together `SupabaseManager` (data), `StrategyLoader` (execution), and `BacktestManager` (validation).

**Tech Stack:** FastAPI, APScheduler, Supabase, Python `ast`, `multiprocessing`

---

### Task 1: LLM Evolution Client (C-mode & Self-Correction) ✅ COMPLETED
**Files:**
- Create: `api/services/evolution_llm_client.py`
- Test: `tests/test_evolution_llm.py`

- [x] **Step 1: Define `EvolutionLLMClient` class**
Implement a class that handles the prompt construction for "C-mode" (summarized history, competitive metrics, regime) and the retry logic for `SecurityError` or `SyntaxError`.
```python
class EvolutionLLMClient:
    async def generate_strategy_code(self, evolution_package: Dict[str, Any], max_retries: int = 3) -> str:
        # Logic to call LLM and retry on failure with error logs
        pass
```
- [x] **Step 2: Implement C-mode Context Assembler**
Create a method to format the `evolution_package` (current code, Trinity Score, MDD logs, Regime, Rank) into a structured prompt.
- [x] **Step 3: Implement Self-Correction Loop**
Wrap the LLM call in a loop that catches `SecurityError` or `SyntaxError` from `StrategyLoader` and sends the traceback back to the LLM.
- [x] **Step 4: Write and run unit tests for the retry logic**
- [x] **Step 5: Commit**
```bash
git add api/services/evolution_llm_client.py tests/test_evolution_llm.py
git commit -m "feat: implement evolution LLM client with C-mode and self-correction"
```

### Task 2: Adaptive Trigger Logic ✅ COMPLETED
**Files:**
- Create: `api/services/evolution_trigger.py`
- Test: `tests/test_triggers.py`

- [x] **Step 1: Implement `EvolutionTrigger` class**
Implement a class that evaluates the 4 trigger levels:
- `check_regime_shift(current_regime, prev_regime)` $\rightarrow$ L1
- `check_performance_decay(current_score, avg_score)` $\rightarrow$ L2
- `check_competitive_pressure(agent_rank, top_score)` $\rightarrow$ L3
- `check_heartbeat(last_evolution_at)` $\rightarrow$ L4
- [x] **Step 2: Implement Trigger Intensity mapping**
Map triggers to intensities: `HIGH (Pivot)` or `LOW (Tuning)`.
- [x] **Step 3: Write and run unit tests for all 4 trigger conditions**
- [x] **Step 4: Commit**
```bash
git add api/services/evolution_trigger.py tests/test_triggers.py
git commit -m "feat: implement adaptive evolution trigger system"
```

### Task 3: Evolution Orchestrator (State Machine)
**Files:**
- Create: `api/services/evolution_orchestrator.py`
- Modify: `api/main.py` (to initialize scheduler)

- [x] **Step 1: Implement `EvolutionOrchestrator` state machine**
Implement the flow: `TRIGGER` $\rightarrow$ `GENERATE` $\rightarrow$ `VALIDATE` $\rightarrow$ `COMMIT`.
```python
class EvolutionOrchestrator:
    async def run_evolution_cycle(self, agent_id: str):
        # 1. Trigger Check
        # 2. Package Context -> LLMClient.generate_strategy_code()
        # 3. StrategyLoader.load_strategy() -> BacktestManager.validate_strategy()
        # 4. SupabaseManager.save_strategy() + save_backtest() + save_improvement_log()
        pass
```
- [x] **Step 2: Integrate APScheduler**
Setup a background scheduler that periodically polls agents for triggers or runs the heartbeat check.
- [x] **Step 3: Implement the `/api/agents/{id}/evolve` manual trigger endpoint**
- [x] **Step 4: Run integration test: Simulate a full loop from Trigger to Commit**
- [x] **Step 5: Commit**
```bash
git add api/services/evolution_orchestrator.py api/main.py
git commit -m "feat: implement autonomous evolution orchestrator state machine"
```

### Task 4: API & Supabase Integration ✅ COMPLETED
**Files:**
- Modify: `api/services/self_improvement.py`
- Modify: `api/main.py`

- [x] **Step 1: Replace mock `SelfImprovementService` with `EvolutionOrchestrator`**
Route the "Improve" requests through the real orchestrator.
- [x] **Step 2: Implement status polling endpoint**
Create an endpoint to return the current state (`GENERATING`, `VALIDATING`, etc.) of an agent's evolution.
- [x] **Step 3: Verify full end-to-end flow: Manual Trigger $\rightarrow$ LLM Code $\rightarrow$ Backtest $\rightarrow$ Supabase Update**
- [x] **Step 4: Commit**
```bash
git add api/services/self_improvement.py api/main.py
git commit -m "feat: integrate evolution orchestrator with API and Supabase"
```

### Task 5: Final Documentation & Progress Update ✅ COMPLETED
**Files:**
- Modify: `docs/superpowers/progress/backend-transition.md`
- Modify: `PROJECT.md`

- [x] **Step 1: Mark Phase 4 as completed in progress log**
- [x] **Step 2: Update `PROJECT.md` with the final Autonomous Evolution loop details**
- [x] **Step 3: Commit**
```bash
git add docs/superpowers/progress/backend-transition.md PROJECT.md
git commit -m "docs: mark phase 4 as completed and update project overview"
```
