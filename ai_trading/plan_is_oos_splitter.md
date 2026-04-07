# Implementation Plan: IS/OOS Splitter (Task 4)

## Overview
Implement data splitting and validation gates in the backtesting engine to prevent overfitting.

## Steps

### Step 1: Write failing tests for IS/OOS splitting
- Create `/Users/lsy/Desktop/project/trinity-chimery/ai_trading/tests/test_backtest_manager.py`
- Test cases:
  1. `test_split_data_60_day_window` - Verify 60-day data is split into 30+30 days
  2. `test_split_data_hourly_data` - Test hourly OHLCV data splitting
  3. `test_validation_gate_pass` - Test when OOS score >= 70% of IS score
  4. `test_validation_gate_fail` - Test when OOS score < 70% of IS score (overfitting)
  5. `test_validation_gate_invalid_is_score` - Handle edge case when IS score <= 0
  6. `test_validate_strategy_workflow` - Full IS backtest -> OOS backtest -> validate flow
  7. `test_store_is_oos_metrics_separately` - Verify metrics storage
  8. `test_trinity_score_from_oos_only` - Final score from OOS, not IS

### Step 2: Run tests to verify they fail
- Execute `python -m pytest ai_trading/tests/test_backtest_manager.py -v`
- Expect failures since implementation not complete

### Step 3: Implement the data splitter
- Fix syntax error in `backtest_manager.py` line 30
- Refactor `split_data()` to support configurable data frequency
- Add proper handling for insufficient data

### Step 4: Implement validation gate
- Complete `validation_gate()` method (already partially implemented)
- Add `validate_strategy()` method:
  - Run backtest on IS data
  - Run backtest on OOS data
  - Calculate Trinity Score for both
  - Apply validation gate (70% threshold)
  - Return result with REJECT or ACCEPT status

### Step 5: Run tests to verify they pass
- Execute `python -m pytest ai_trading/tests/test_backtest_manager.py -v`
- Fix any remaining issues

✅ **COMPLETED**: All 16 tests pass

### Step 6: Commit with proper message
- Commit message: "Implement IS/OOS splitter and validation gate for backtesting"
- Include Co-Authored-By line

✅ **COMPLETED**: Changes committed

## Acceptance Criteria
- [ ] All 8 test cases pass
- [ ] Data splitter works with OHLCV data
- [ ] IS and OOS metrics stored separately
- [ ] Final Trinity Score calculated from OOS performance
- [ ] Validation gate rejects overfitted strategies (OOS < 70% IS)
- [ ] Code passes type checking

## Files Modified/Created
- Modified: `ai_trading/core/backtest_manager.py`
- Created: `ai_trading/tests/test_backtest_manager.py`
