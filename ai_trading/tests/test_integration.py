"""
통합 테스트 - Arena, Portfolio, BaseAgent 연동
"""
import sys
import numpy as np
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

from ai_trading.agents import MomentumHunter, MeanReverter, MacroTrader, ChaosAgent, AgentConfig
from ai_trading.battle import Arena, Portfolio


def test_agent_initialization():
    """테스트 1: 4개 에이전트 초기화"""
    print("\n=== 테스트 1: 에이전트 초기화 ===")

    configs = [
        AgentConfig(name="momentum_hunter", algorithm="PPO"),
        AgentConfig(name="mean_reverter", algorithm="SAC"),
        AgentConfig(name="macro_trader", algorithm="PPO"),
        AgentConfig(name="chaos_agent", algorithm="SAC"),
    ]

    agents = [
        MomentumHunter(configs[0]),
        MeanReverter(configs[1]),
        MacroTrader(configs[2]),
        ChaosAgent(configs[3]),
    ]

    for agent in agents:
        print(f"  ✓ {agent.name}: {agent.ALGORITHM}, Persona={agent.PERSONA[:20]}...")

    return agents


def test_arena_registration(agents):
    """테스트 2: Arena에 에이전트 등록"""
    print("\n=== 테스트 2: Arena 에이전트 등록 ===")

    arena = Arena()

    for agent in agents:
        arena.register_agent(agent)

    print(f"  ✓ 등록된 에이전트: {list(arena.agents.keys())}")

    # 초기 배분 확인
    for name, ratio in arena.allocations.items():
        print(f"    {name}: {ratio:.2%}")

    return arena


def test_portfolio_tracking(arena):
    """테스트 3: Portfolio 자본 추적"""
    print("\n=== 테스트 3: Portfolio 자본 추적 ===")

    portfolio = arena.portfolio

    # 에이전트 계좌 확인
    for name in arena.agents.keys():
        account = portfolio.get_agent_account(name)
        if account:
            print(f"  ✓ {account.name}: "
                  f"초기={account.initial_capital:.2f}, "
                  f"배분비율={account.allocation_ratio:.2%}")

    # 총 자본 확인
    total = portfolio.total_capital
    print(f"  ✓ 총 자본: {total} units")


def test_arena_step(arena):
    """테스트 4: Arena step() - 가중 투표"""
    print("\n=== 테스트 4: Arena step() 실행 ===")

    # 샘플 시장 데이터
    market_obs = {
        "regime": "bull",
        "p_long": 0.65,
        "p_short": 0.25,
        "confidence": 0.70,
        "roc_10": 0.02,
        "adx": 30.0,
        "price_vs_52w_high": 0.7,
        "ema_fast": 51000,
        "ema_slow": 50000,
        "rsi": 45.0,
        "bb_deviation": 0.5,
        "volume_spike": 1.2,
        "realized_vol": 0.15,
        "regime_prob": 0.75,
        "open_interest_change": 0.05,
        "fear_greed_index": 65.0,
        "trend_4h": 0.3,
        "trend_1d": 0.5,
        "trend_1w": 0.2,
        "funding_rate": 0.01,
    }

    # Step 실행
    result = arena.step(market_obs, current_prices={"BTC/USDT": 51000})

    print(f"  ✓ Step {arena.portfolio.step_count} 완료")
    print(f"    Net Action: {result['net_action']:.4f}")
    print(f"    개별 액션:")
    for name, data in result['actions'].items():
        print(f"      {name}: action={data['action']:.2f}, confidence={data['confidence']:.2f}")

    return result


def test_multiple_steps(arena, num_steps=5):
    """테스트 5: 여러 스텝 실행 및 PnL 추적"""
    print(f"\n=== 테스트 5: {num_steps} 스텝 실행 ===")

    # 다양한 시장 시나리오
    scenarios = [
        {"regime": "bull", "p_long": 0.70, "p_short": 0.20, "confidence": 0.75, "adx": 35},
        {"regime": "bull", "p_long": 0.65, "p_short": 0.30, "confidence": 0.60, "adx": 28},
        {"regime": "sideways", "p_long": 0.45, "p_short": 0.45, "confidence": 0.40, "adx": 15},
        {"regime": "bear", "p_long": 0.25, "p_short": 0.65, "confidence": 0.55, "adx": 22},
        {"regime": "bear", "p_long": 0.20, "p_short": 0.70, "confidence": 0.70, "adx": 30},
    ]

    prices = [50000, 50500, 50200, 49500, 49000]

    for i, (scenario, price) in enumerate(zip(scenarios[:num_steps], prices)):
        market_obs = {
            "regime": scenario["regime"],
            "p_long": scenario["p_long"],
            "p_short": scenario["p_short"],
            "confidence": scenario["confidence"],
            "adx": scenario["adx"],
            "roc_10": np.random.uniform(-0.02, 0.02),
            "price_vs_52w_high": 0.7,
            "ema_fast": price,
            "ema_slow": price * 0.99,
            "rsi": np.random.uniform(30, 70),
            "bb_deviation": 0.0,
            "volume_spike": np.random.uniform(0.8, 1.5),
            "realized_vol": 0.15,
            "regime_prob": 0.7,
            "open_interest_change": 0.05,
            "fear_greed_index": 50.0,
            "trend_4h": 0.0,
            "trend_1d": 0.1 if scenario["regime"] == "bull" else -0.1,
            "trend_1w": 0.2,
            "funding_rate": 0.01,
        }

        result = arena.step(market_obs, current_prices={"BTC/USDT": price})

        if i == 0:
            print(f"  스텝 진행:")
        print(f"    Step {i+1}: regime={scenario['regime']}, net_action={result['net_action']:.3f}")

    print(f"\n  ✓ {num_steps} 스텝 완료")


def test_portfolio_history(arena):
    """테스트 6: 포트폴리오 히스토리 및 메트릭"""
    print("\n=== 테스트 6: Portfolio 메트릭 계산 ===")

    metrics = arena.portfolio.get_metrics()

    print("  에이전트별 메트릭:")
    for name, m in metrics.items():
        print(f"    {name}:")
        print(f"      alloc={m['allocation']:.2%}, sharpe={m['sharpe_7d']:.2f}, "
              f"trades={m['trade_count']}")


def test_rebalance(arena):
    """테스트 7: 재배분 기능"""
    print("\n=== 테스트 7: 재배분 기능 ===")

    # 현재 배분
    print(f"  현재 배분:")
    for name, ratio in arena.allocations.items():
        print(f"    {name}: {ratio:.2%}")

    # 재배분 시도
    new_allocations = {
        "momentum_hunter": 0.35,
        "mean_reverter": 0.25,
        "macro_trader": 0.30,
        "chaos_agent": 0.10,
    }

    arena.update_allocations(new_allocations)

    print(f"  새 배분:")
    for name, ratio in arena.allocations.items():
        print(f"    {name}: {ratio:.2%}")


def test_simple_callable_agent():
    """테스트 8: 단순 callable 에이전트 지원"""
    print("\n=== 테스트 8: Callable 에이전트 지원 ===")

    def simple_agent(obs):
        """간단한 랜덤 에이전트"""
        return np.random.uniform(-0.5, 0.5)

    arena = Arena()
    arena.register_agent(simple_agent, name="simple_random")

    result = arena.step({"regime": "sideways", "p_long": 0.5, "p_short": 0.5})

    print(f"  ✓ Callable 에이전트 등록 완료: simple_random")
    print(f"    Net action: {result['net_action']:.3f}")


if __name__ == "__main__":
    print("=" * 60)
    print("AI Trading System - 통합 테스트")
    print("=" * 60)

    try:
        # 순차 실행
        agents = test_agent_initialization()
        arena = test_arena_registration(agents)
        test_portfolio_tracking(arena)
        test_arena_step(arena)
        test_multiple_steps(arena, num_steps=5)
        test_portfolio_history(arena)
        test_rebalance(arena)
        test_simple_callable_agent()

        print("\n" + "=" * 60)
        print("✓ 모든 통합 테스트 통과!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
