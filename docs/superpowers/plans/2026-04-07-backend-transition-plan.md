# [Trinity Backend Transition] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition the mock backend to a real autonomous evolution system using Supabase, dynamic Python strategy execution (B-mode), and a robust backtesting loop with anti-overfitting guards.

**Architecture:** 
- **Data Layer**: Supabase (PostgreSQL) for strategy versioning, metrics, and logs.
- **Execution Layer**: Isolated `StrategyLoader` using `ast` validation and `multiprocessing` timeouts to execute LLM-generated code.
- **Orchestration Layer**: `APScheduler` state machine managing the [Trigger -> Generate -> Validate -> Commit] loop.
- **Validation Layer**: In-Sample/Out-of-Sample splitting and conservative slippage/fee models.

**Tech Stack:** FastAPI, Supabase (PostgreSQL), APScheduler, Python `ast` module, `ai_trading` core.

---

## Phase 1: Supabase Infrastructure & Data Layer
**Goal:** Establish the source of truth for agents and their evolutionary history.

### Task 1: Supabase Schema Initialization ✅ COMPLETED
**Files:**
- Create: `docs/superpowers/plans/supabase_schema.sql`

- [x] **Step 1: Define SQL Schema**
Create a SQL file with the following tables:
- `agents`: id (UUID), name, persona, current_strategy_id (FK), status, last_evolution_at.
- `strategies`: id (UUID), agent_id (FK), version, code (text), params (jsonb), rationale, created_at.
- `backtest_results`: id (UUID), strategy_id (FK), trinity_score, return_val, sharpe, mdd, win_rate, test_period, created_at.
- `improvement_logs`: id (UUID), agent_id (FK), prev_strategy_id (FK), new_strategy_id (FK), llm_analysis, expected_improvement (jsonb).
- [ ] **Step 2: Commit Schema Doc**
```bash
git add docs/superpowers/plans/supabase_schema.sql
git commit -m "docs: define supabase schema for trinity evolution"
```

### Task 2: Supabase Client Integration ✅ COMPLETED
**Files:**
- Create: `api/services/supabase_client.py`

- [x] **Step 1: Implement Supabase Client**
```python
from supabase import create_client, Client
import os

class SupabaseManager:
    def __init__(self):
        self.client: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    async def get_agent_strategy(self, agent_id: str):
        # Fetch current strategy code from strategies table
        pass

    async def save_strategy(self, agent_id: str, code: str, rationale: str, params: dict):
        # Insert into strategies, update agents.current_strategy_id
        pass

    async def save_backtest(self, strategy_id: str, metrics: dict):
        # Insert into backtest_results
        pass
```
- [x] **Step 2: Verify connection with a simple test script**
- [x] **Step 3: Commit**

---

## Phase 2: Dynamic Strategy Sandbox (B-Mode) ✅ COMPLETED
**Goal:** Safely execute LLM-generated Python code without compromising the server.

### Task 3: Strategy Interface & Loader ✅ COMPLETED
**Files:**
- Create: `ai_trading/core/strategy_interface.py`
- Create: `ai_trading/core/strategy_loader.py`

- [x] **Step 1: Define StrategyInterface**
```python
from abc import ABC, abstractmethod

class StrategyInterface(ABC):
    @abstractmethod
    def generate_signal(self, data):
        pass

    @abstractmethod
    def get_params(self) -> dict:
        pass
```
- [x] **Step 2: Implement AST-based Validator**
In `StrategyLoader`, implement a method to check for forbidden imports/calls:
```python
import ast

FORBIDDEN_NODES = {'os', 'sys', 'subprocess', 'shutil', 'socket', 'open'}
def validate_code(code: str):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            # check for forbidden modules
            pass
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'open':
            raise SecurityError("Open call forbidden")
```
- [x] **Step 3: Implement Dynamic Loader with Timeout**
Use `multiprocessing` to wrap the `exec()` call of the generated code to prevent infinite loops.
- [x] **Step 4: Commit**

---

## Phase 3: Robust Backtesting Engine ✅ COMPLETED
**Goal:** Implement anti-overfitting and realistic cost models.

### Task 4: In-Sample/Out-of-Sample Splitter ✅ COMPLETED
**Files:**
- Modify: `ai_trading/core/backtest_manager.py`

- [x] **Step 1: Implement Data Splitter**
Divide the recent 60-day window into:
- Train (In-Sample): First 30 days.
- Validation (Out-of-Sample): Last 30 days.
- [x] **Step 2: Implement Validation Gate**
Logic: `if (oos_score << is is_score * 0.7): return REJECT` (Prevent overfitting).
- [x] **Step 3: Commit**

### Task 5: Conservative Cost Model ⏳ PENDING (Tests)
**Files:**
- Modify: `ai_trading/rl/trading_env.py` (apply similar logic to backtester)

- [ ] **Step 1: Apply Slippage and Fees**
Add a constant fee (e.g., 0.05% per trade) and a random slippage factor (0.01% to 0.03%) to every simulated trade.
- [ ] **Step 2: Commit**

---

## Phase 4: Autonomous Evolution Orchestrator
**Goal:** Build the background loop that drives the evolution.

### Task 6: Loop State Machine & Scheduler ✅ COMPLETED
**Files:**
- Create: `api/services/evolution_orchestrator.py`

- [x] **Step 1: Implement State Machine**
Define states: `TRIGGERED` $\rightarrow$ `GENERATING` $\rightarrow$ `VALIDATING` $\rightarrow$ `COMMITTING`.
- [x] **Step 2: Integrate LLM Generation Loop**
Call LLM with: [Current Code + Backtest Results + Market Regime].
- [x] **Step 3: Integrate Backtest & Commit**
Run the sandbox $\rightarrow$ Calculate Trinity Score $\rightarrow$ Update Supabase if score improved.
- [x] **Step 4: Setup APScheduler**
Configure the loop to run every 14 days per agent.
- [x] **Step 5: Commit**

---

## Phase 5: API & Frontend Integration ⏳ PENDING
**Goal:** Replace mock endpoints with real Supabase data.

### Task 7: API Endpoint Transition
**Files:**
- Modify: `api/main.py`
- Modify: `api/services/self_improvement.py`

- [ ] **Step 1: Replace `SelfImprovementService` mocks with `SupabaseManager` and `EvolutionOrchestrator` calls.**
- [ ] **Step 2: Verify `/api/agents/{id}/timeseries` fetches real data from `backtest_results`.**
- [ ] **Step 3: Commit**

### Task 8: Frontend Realtime Sync
**Files:**
- Modify: `front/lib/api.ts`
- Modify: `front/app/page.tsx`

- [ ] **Step 1: Implement Supabase Realtime subscription for strategy updates.**
- [ ] **Step 2: Add "View Code" modal to the dashboard to display `strategies.code`.**
- [ ] **Step 3: Commit**
