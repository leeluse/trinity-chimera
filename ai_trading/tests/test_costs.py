import pytest
import numpy as np
from ai_trading.core.backtest_manager import BacktestManager

def test_apply_trading_costs_buy():
    bm = BacktestManager(fee=0.0005, slippage_min=0.0001, slippage_max=0.0001) # fixed slippage for test
    price = 100.0
    # Expect: 100 * (1 + 0.0005 + 0.0001) = 100.06
    result = bm.apply_trading_costs(price, 1)
    assert result == pytest.approx(100.06)

def test_apply_trading_costs_sell():
    bm = BacktestManager(fee=0.0005, slippage_min=0.0001, slippage_max=0.0001)
    price = 100.0
    # Expect: 100 * (1 - (0.0005 + 0.0001)) = 99.94
    result = bm.apply_trading_costs(price, -1)
    assert result == pytest.approx(99.94)
