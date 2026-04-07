# Research: IS/OOS Splitter Implementation

## Current State Analysis

### Existing Files
1. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/core/backtest_manager.py` - Already exists with partial implementation
   - Has `split_data()` method but with bugs (syntax error on line 30: `<<` should be `<`)
   - Has `validation_gate()` method with correct logic
   - Has `calculate_trinity_score()` method
   - Has basic `run_backtest()` method

2. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/core/strategy_interface.py` - Abstract base class for strategies

3. `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/tests/test_sandbox.py` - Existing tests for strategy sandbox

### Issues Found in backtest_manager.py
1. Line 30: `if len(recent_data) << total total_window * 24:` - Syntax error (should be `<`)
2. The split_data logic assumes hourly data which may not be flexible enough
3. Missing comprehensive IS/OOS validation workflow

## Requirements Analysis

### Task Requirements
1. **Data Splitter**: Recent 60-day window split into:
   - Train (IS): First 30 days
   - Validation (OOS): Last 30 days

2. **Validation Gate**: Reject if `oos_score < is_score * 0.7`

3. **Implementation Details**:
   - Create/modify `BacktestManager` class
   - Work with OHLCV data
   - Store IS and OOS metrics separately
   - Final Trinity Score from OOS performance
   - Add `validate_strategy()` method

## Implementation Plan

### Step 1: Write failing tests for IS/OOS splitting
### Step 2: Run tests to verify they fail
### Step 3: Implement the data splitter (fix bugs)
### Step 4: Implement validation gate
### Step 5: Run tests to verify they pass
### Step 6: Commit with proper message

## References
- ADR-006: 과적합 방지를 위해 In-Sample/Out-of-Sample 분리 및 보수적 비용 모델 적용
- PROJECT.md: Trinity Score formula
