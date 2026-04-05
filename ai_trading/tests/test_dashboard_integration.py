"""
Dashboard Integration Test

Tests:
1. Dashboard displays battle system data correctly
2. Agent PnL console output works
3. Portfolio allocation logging works
"""

import sys
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_trading.battle.arena import Arena
from ai_trading.battle.portfolio import Portfolio, AgentAccount
from ai_trading.agents.base_agent import BaseAgent, AgentConfig
from dashboard import TextDashboard, AgentMetrics, PortfolioState, ArenaDashboardMixin


class MockAgent(BaseAgent):
    """Test agent that returns random actions"""

    PERSONA = "Test agent for dashboard integration"
    ALGORITHM = "PPO"

    def __init__(self, name: str, action_pattern: str = "random"):
        config = AgentConfig(name=name, algorithm="PPO", observation_dim=8)
        super().__init__(config)
        self.action_pattern = action_pattern
        self._counter = 0

    def build_observation(self, market_obs: dict, portfolio_state: dict) -> np.ndarray:
        """Build observation vector"""
        return np.random.randn(8).astype(np.float32)

    def act(self, observation: np.ndarray) -> float:
        """Return action based on pattern"""
        self._counter += 1
        if self.action_pattern == "long":
            return 0.8
        elif self.action_pattern == "short":
            return -0.8
        elif self.action_pattern == "oscillate":
            return np.sin(self._counter * 0.1) * 0.9
        else:
            return np.random.uniform(-1.0, 1.0)

    def compute_reward(self, action, prev_state, curr_state) -> float:
        return np.random.randn() * 0.1


class DashboardArena(Arena, ArenaDashboardMixin):
    """Arena with dashboard integration"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_dashboard(log_path="/tmp/dashboard_test.log")

    def step(self, observation: dict, current_prices: dict = None) -> dict:
        """Step with dashboard logging"""
        result = super().step(observation, current_prices)
        self.log_step_to_dashboard(result, observation)
        return result


def test_1_agent_metrics_conversion():
    """Test 1: AgentAccount -> AgentMetrics conversion"""
    print("\n" + "="*60)
    print(" TEST 1: AgentAccount -> AgentMetrics Conversion ")
    print("="*60)

    account = AgentAccount(
        name="test_agent",
        initial_capital=25.0,
        current_capital=30.5,
        allocation_ratio=0.25
    )

    # Simulate trades
    for i in range(10):
        pnl = np.random.randn() * 2.0
        account.record_trade(action=0.5, pnl=pnl, timestamp=f"step_{i}")
        account.record_daily_pnl(pnl)

    metrics = AgentMetrics.from_account(account)

    print(f"\nAgent: {metrics.name}")
    print(f"  Allocation: {metrics.allocation*100:.1f}%")
    print(f"  PnL Total: {metrics.pnl_total:+.2f} units")
    print(f"  Sharpe: {metrics.sharpe:.2f}")
    print(f"  Win Rate: {metrics.win_rate*100:.1f}%")
    print(f"  Trade Count: {metrics.trade_count}")

    assert metrics.name == "test_agent"
    assert metrics.allocation == 0.25
    assert metrics.trade_count == 10
    print("\n✓ Test 1 PASSED")


def test_2_portfolio_state_conversion():
    """Test 2: Portfolio -> PortfolioState conversion"""
    print("\n" + "="*60)
    print(" TEST 2: Portfolio -> PortfolioState Conversion ")
    print("="*60)

    portfolio = Portfolio(total_capital=100.0)

    # Add agents
    agents = [
        ("momentum_hunter", 0.30),
        ("mean_reverter", 0.30),
        ("macro_trader", 0.25),
        ("chaos_agent", 0.15)
    ]

    for name, alloc in agents:
        portfolio.add_agent(name, alloc)

    # Simulate trading
    for name in portfolio.accounts:
        for i in range(20):
            pnl = np.random.randn() * 1.5
            portfolio.accounts[name].record_trade(action=0.5, pnl=pnl)
            portfolio.accounts[name].record_daily_pnl(pnl)

    state = PortfolioState.from_portfolio(portfolio)

    print(f"\nPortfolio Summary:")
    print(f"  Total Capital: {state.total_capital:.2f}")
    print(f"  Total PnL: {state.total_pnl_total:+.2f}")
    print(f"  Agent Count: {len(state.agent_metrics)}")

    print("\n  Agent Details:")
    for name, metrics in state.agent_metrics.items():
        print(f"    {name:<15}: Alloc={metrics.allocation*100:>5.1f}%  "
              f"PnL={metrics.pnl_total:>+6.2f}  Sharpe={metrics.sharpe:>5.2f}")

    assert state.total_capital == 100.0
    assert len(state.agent_metrics) == 4
    print("\n✓ Test 2 PASSED")


def test_3_text_dashboard_output():
    """Test 3: TextDashboard console output"""
    print("\n" + "="*60)
    print(" TEST 3: TextDashboard Console Output ")
    print("="*60)

    dashboard = TextDashboard(log_path=None)  # stdout only

    # Create test data
    agents = {
        "momentum_hunter": AgentMetrics(
            name="momentum_hunter",
            allocation=0.30,
            pnl_24h=2.5,
            pnl_7d=8.2,
            pnl_total=15.3,
            sharpe=1.85,
            max_drawdown=-0.12,
            win_rate=0.65,
            open_positions=2,
            regime="bull",
            trade_count=45
        ),
        "mean_reverter": AgentMetrics(
            name="mean_reverter",
            allocation=0.30,
            pnl_24h=-1.2,
            pnl_7d=3.5,
            pnl_total=8.7,
            sharpe=1.12,
            max_drawdown=-0.18,
            win_rate=0.58,
            open_positions=1,
            regime="sideways",
            trade_count=32
        ),
        "macro_trader": AgentMetrics(
            name="macro_trader",
            allocation=0.25,
            pnl_24h=0.8,
            pnl_7d=5.1,
            pnl_total=12.4,
            sharpe=1.45,
            max_drawdown=-0.15,
            win_rate=0.62,
            open_positions=1,
            regime="bull",
            trade_count=28
        ),
        "chaos_agent": AgentMetrics(
            name="chaos_agent",
            allocation=0.15,
            pnl_24h=-0.5,
            pnl_7d=1.2,
            pnl_total=4.8,
            sharpe=0.85,
            max_drawdown=-0.22,
            win_rate=0.52,
            open_positions=2,
            regime="unknown",
            trade_count=56
        )
    }

    from datetime import datetime
    state = PortfolioState(
        total_capital=100.0,
        total_pnl_24h=1.6,
        total_pnl_7d=18.0,
        total_pnl_total=41.2,
        agent_metrics=agents,
        timestamp=datetime.utcnow()
    )

    print("\n--- Portfolio State Output ---")
    dashboard.log_portfolio_state(state)

    print("\n--- Individual Agent PnL Output ---")
    dashboard.log_agent_pnl("momentum_hunter", agents["momentum_hunter"])
    dashboard.log_agent_pnl("mean_reverter", agents["mean_reverter"])

    print("\n--- Arbiter Reallocation Output ---")
    old_alloc = {"momentum_hunter": 0.30, "mean_reverter": 0.30,
                 "macro_trader": 0.25, "chaos_agent": 0.15}
    new_alloc = {"momentum_hunter": 0.35, "mean_reverter": 0.25,
                 "macro_trader": 0.30, "chaos_agent": 0.10}
    reasoning = "Bull regime detected. Momentum performing well."
    dashboard.log_arbiter_decision(old_alloc, new_alloc, reasoning)

    print("\n--- Battle Step Output ---")
    dashboard.log_battle_step(
        step=100,
        market_obs={"regime": "bull", "close": 45000},
        agent_actions={
            "momentum_hunter": 0.8,
            "mean_reverter": -0.3,
            "macro_trader": 0.5,
            "chaos_agent": -0.6
        },
        net_signal=0.035
    )

    print("\n✓ Test 3 PASSED")


def test_4_arena_dashboard_integration():
    """Test 4: Arena + Dashboard integration"""
    print("\n" + "="*60)
    print(" TEST 4: Arena + Dashboard Integration ")
    print("="*60)

    # Create agents
    agents = [
        MockAgent("momentum_hunter", "long"),
        MockAgent("mean_reverter", "oscillate"),
        MockAgent("macro_trader", "short"),
        MockAgent("chaos_agent", "random")
    ]

    # Create arena with dashboard
    arena = DashboardArena(
        agents=agents,
        total_capital=100.0,
        rebalance_interval=7
    )

    # Run simulation steps
    print("\nRunning 200 simulation steps...")
    for i in range(200):
        market_obs = {
            "close": 45000 + np.random.randn() * 500,
            "regime": np.random.choice(["bull", "sideways", "bear"]),
            "ml_signal": np.random.randn()
        }

        result = arena.step(market_obs, {"BTC": market_obs["close"]})

        # Simulate PnL based on signal
        for name in arena.portfolio.accounts:
            pnl = result["actions"][name]["action"] * np.random.randn() * 0.5
            arena.portfolio.record_pnl(name, pnl)

    print("\nSimulation complete!")
    print(f"\nTotal Steps: {arena.portfolio.step_count}")
    print(f"Total PnL: {arena.portfolio.get_total_pnl():+.2f} units")

    # Print dashboard summary
    summary = arena.get_dashboard_summary()
    print(f"\nDashboard Summary: {summary}")

    # Print individual agent reports
    print("\n")
    arena.print_agent_report()

    print("\n✓ Test 4 PASSED")


def test_5_portfolio_allocation_logging():
    """Test 5: Portfolio allocation tracking"""
    print("\n" + "="*60)
    print(" TEST 5: Portfolio Allocation Logging ")
    print("="*60)

    arena = DashboardArena(
        agents=[
            MockAgent("momentum_hunter"),
            MockAgent("mean_reverter")
        ],
        total_capital=100.0
    )

    print("\nInitial Allocations:")
    for name in arena.agents:
        alloc = arena.portfolio.get_allocation(name)
        print(f"  {name}: {alloc*100:.1f}%")

    # Run for a bit
    for i in range(20):
        arena.step({"close": 45000, "regime": "bull"}, {"BTC": 45000})

    # Simulate reallocation
    print("\nSimulating Arbiter reallocation...")
    old_alloc = arena.allocations.copy()
    new_alloc = {
        "momentum_hunter": 0.50,
        "mean_reverter": 0.50
    }
    arena.log_reallocation(old_alloc, new_alloc, "Rebalancing for better spread")

    print("\nAfter Reallocation:")
    print(f"  Allocation History: {len(arena.portfolio.allocation_history)} entries")
    for entry in arena.portfolio.allocation_history:
        print(f"    Step {entry['step']}: {entry['allocations']}")

    assert len(arena.portfolio.allocation_history) >= 1
    print("\n✓ Test 5 PASSED")


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "#"*60)
    print("#" + " "*58 + "#")
    print("#" + "  Dashboard Integration Test Suite  ".center(58) + "#")
    print("#" + " "*58 + "#")
    print("#"*60)

    try:
        test_1_agent_metrics_conversion()
        test_2_portfolio_state_conversion()
        test_3_text_dashboard_output()
        test_4_arena_dashboard_integration()
        test_5_portfolio_allocation_logging()

        print("\n" + "#"*60)
        print("#" + " "*58 + "#")
        print("#" + "  ALL TESTS PASSED  ".center(58) + "#")
        print("#" + " "*58 + "#")
        print("#"*60 + "\n")

        return True

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
