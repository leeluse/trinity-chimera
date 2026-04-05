"""
Text-based Dashboard for AI Trading System (Phase 2 MVP)

MVP 기능:
- 에이전트별 PnL 콘솔 출력
- 포트폴리오 배분 상태 로깅
- 텍스트 기반 모니터링 (웹 UI 없음)

Integration with battle/arena.py:
- ArenaDashboardMixin: Arena 클래스에 대시보드 기능 주입
- PortfolioStateAdapter: Portfolio 객체를 대시보드 포맷으로 변환
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

# battle 시스템 import (Tailor가 구현)
from ai_trading.battle.arena import Arena
from ai_trading.battle.portfolio import Portfolio, AgentAccount


@dataclass
class AgentMetrics:
    """개별 에이전트 성과 지표"""
    name: str
    allocation: float  # 현재 배분 비율 (0.0 ~ 1.0)
    pnl_24h: float = 0.0     # 24시간 PnL
    pnl_7d: float = 0.0      # 7일 PnL
    pnl_total: float = 0.0   # 누적 PnL
    sharpe: float = 0.0      # 샤프 비율
    max_drawdown: float = 0.0  # 최대 낙폭
    win_rate: float = 0.0    # 승률
    open_positions: int = 0  # 현재 보중 포지션 수
    regime: str = "unknown"         # 현재 감지된 레짐
    trade_count: int = 0  # 거래 횟수

    @classmethod
    def from_account(cls, account: AgentAccount) -> "AgentMetrics":
        """AgentAccount로부터 AgentMetrics 생성"""
        metrics = account.get_metrics()
        return cls(
            name=metrics.get("name", account.name),
            allocation=metrics.get("allocation", account.allocation_ratio),
            pnl_total=metrics.get("total_pnl", 0.0),
            sharpe=metrics.get("sharpe_7d", 0.0),
            max_drawdown=metrics.get("max_drawdown", 0.0),
            win_rate=metrics.get("win_rate", 0.0),
            trade_count=metrics.get("trade_count", 0)
        )


@dataclass
class PortfolioState:
    """전체 포트폴리오 상태"""
    total_capital: float
    total_pnl_24h: float
    total_pnl_7d: float
    total_pnl_total: float
    agent_metrics: Dict[str, AgentMetrics]
    timestamp: datetime

    @classmethod
    def from_portfolio(cls, portfolio: Portfolio) -> "PortfolioState":
        """Portfolio 객체로부터 PortfolioState 생성"""
        agent_metrics = {}
        for name, account in portfolio.accounts.items():
            agent_metrics[name] = AgentMetrics.from_account(account)

        return cls(
            total_capital=portfolio.total_capital,
            total_pnl_24h=0.0,  # TODO: 계산 필요
            total_pnl_7d=0.0,
            total_pnl_total=portfolio.get_total_pnl(),
            agent_metrics=agent_metrics,
            timestamp=datetime.utcnow()
        )


class TextDashboard:
    """텍스트 기반 대시보드"""

    def __init__(self, log_path: str = None):
        """
        Args:
            log_path: 포트폴리오 상태 로그 저장 경로 (없으면 stdout 만)
        """
        self.log_path = log_path
        if log_path:
            logging.basicConfig(
                filename=log_path,
                level=logging.INFO,
                format='%(asctime)s - %(message)s'
            )
            self.logger = logging.getLogger('dashboard')
        else:
            self.logger = None

    def log_portfolio_state(self, state: PortfolioState) -> None:
        """
        포트폴리오 배분 상태를 로깅
        콘솔 출력 + 파일 로깅 (설정된 경우)
        """
        lines = []
        lines.append("\n" + "=" * 80)
        lines.append(f" PORTFOLIO SNAPSHOT - {state.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC ")
        lines.append("=" * 80)
        lines.append(f"\nTotal Capital: {state.total_capital:,.2f} units")
        lines.append(f"Total PnL (24h): {state.total_pnl_24h:+.2f}%")
        lines.append(f"Total PnL (7d):  {state.total_pnl_7d:+.2f}%")
        lines.append(f"Total PnL (All): {state.total_pnl_total:+.2f}%")
        lines.append("\n" + "-" * 80)
        lines.append(" AGENT ALLOCATION & PnL ")
        lines.append("-" * 80)
        lines.append(f"{'Agent':<15} {'Alloc%':>8} {'PnL(24h)':>10} {'PnL(7d)':>10} {'Sharpe':>8} {'MDD%':>8} {'Win%':>8} {'Pos':>4}")
        lines.append("-" * 80)

        for agent_name, metrics in state.agent_metrics.items():
            lines.append(
                f"{metrics.name:<15} "
                f"{metrics.allocation*100:>7.1f}% "
                f"{metrics.pnl_24h:>+9.2f}% "
                f"{metrics.pnl_7d:>+9.2f}% "
                f"{metrics.sharpe:>8.2f} "
                f"{metrics.max_drawdown*100:>7.1f}% "
                f"{metrics.win_rate*100:>7.1f}% "
                f"{metrics.open_positions:>4d}"
            )

        lines.append("-" * 80)
        lines.append("\n")

        output = "\n".join(lines)
        print(output)

        if self.logger:
            self.logger.info(output)

    def log_agent_pnl(self, agent_name: str, metrics: AgentMetrics) -> None:
        """
        개별 에이전트 PnL 콘솔 출력
        """
        lines = []
        lines.append(f"\n{'─' * 60}")
        lines.append(f" Agent: {agent_name} ")
        lines.append(f"{'─' * 60}")
        lines.append(f"  Allocation:    {metrics.allocation*100:.1f}%")
        lines.append(f"  PnL (24h):     {metrics.pnl_24h:+.2f}%")
        lines.append(f"  PnL (7d):      {metrics.pnl_7d:+.2f}%")
        lines.append(f"  PnL (Total):   {metrics.pnl_total:+.2f}%")
        lines.append(f"  Sharpe:        {metrics.sharpe:.2f}")
        lines.append(f"  Max Drawdown:  {metrics.max_drawdown*100:.1f}%")
        lines.append(f"  Win Rate:      {metrics.win_rate*100:.1f}%")
        lines.append(f"  Open Pos:      {metrics.open_positions}")
        lines.append(f"  Current Regime: {metrics.regime}")
        lines.append(f"{'─' * 60}\n")

        output = "\n".join(lines)
        print(output)

        if self.logger:
            self.logger.info(output)

    def log_arbiter_decision(self, old_allocations: Dict[str, float],
                              new_allocations: Dict[str, float],
                              reasoning: str) -> None:
        """
        Arbiter 재배분 결정 로깅
        """
        lines = []
        lines.append("\n" + "=" * 80)
        lines.append(" ARBITER REALLOCATION ")
        lines.append("=" * 80)
        lines.append(f"\nTimestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append("\nAllocation Changes:")
        lines.append(f"{'Agent':<15} {'Before':>10} {'After':>10} {'Delta':>10}")
        lines.append("-" * 50)

        for agent in old_allocations.keys():
            old_pct = old_allocations[agent] * 100
            new_pct = new_allocations.get(agent, 0) * 100
            delta = new_pct - old_pct
            lines.append(f"{agent:<15} {old_pct:>9.1f}% {new_pct:>9.1f}% {delta:>+9.1f}%")

        lines.append("\nReasoning:")
        lines.append(reasoning)
        lines.append("\n" + "=" * 80 + "\n")

        output = "\n".join(lines)
        print(output)

        if self.logger:
            self.logger.info(output)

    def log_battle_step(self, step: int, market_obs: dict,
                        agent_actions: Dict[str, float],
                        net_signal: float) -> None:
        """
        배틀 스텝별 행동 로깅 (디버깅용)
        """
        lines = []
        lines.append(f"\n{'─' * 60}")
        lines.append(f" Battle Step {step} ")
        lines.append(f"{'─' * 60}")
        lines.append(f"  Market: {market_obs.get('regime', 'unknown')}")
        lines.append(f"  Agent Actions:")
        for agent, action in agent_actions.items():
            lines.append(f"    {agent:<15}: {action:+.2f}")
        lines.append(f"  Net Signal: {net_signal:+.4f}")
        lines.append(f"{'─' * 60}\n")

        output = "\n".join(lines)
        print(output)

        if self.logger:
            self.logger.info(output)


class ArenaDashboardMixin:
    """
    Arena 클래스에 대시보드 기능을 주입하는 Mixin

    Usage in arena.py:
        class Arena(ArenaDashboardMixin):
            def __init__(self, ...):
                super().__init__(...)
                self._init_dashboard()
    """

    def _init_dashboard(self, log_path: Optional[str] = None):
        """대시보드 초기화"""
        self.dashboard = TextDashboard(log_path=log_path)
        self._last_dashboard_step = 0
        self._dashboard_interval = 100  # 100 스텝마다 출력

    def log_step_to_dashboard(self, step_result: dict, market_obs: dict):
        """스텝 결과를 대시보드에 로깅"""
        if not hasattr(self, 'dashboard'):
            return

        step = getattr(self.portfolio, 'step_count', 0)

        # 주기적 포트폴리오 상태 출력
        if step - self._last_dashboard_step >= self._dashboard_interval:
            portfolio_state = PortfolioState.from_portfolio(self.portfolio)
            self.dashboard.log_portfolio_state(portfolio_state)
            self._last_dashboard_step = step

        # 디버그 모드에서만 스텝별 로깅
        if getattr(self, 'debug_mode', False):
            self.dashboard.log_battle_step(
                step=step,
                market_obs=market_obs,
                agent_actions=step_result.get("actions", {}),
                net_signal=step_result.get("net_action", 0.0)
            )

    def log_reallocation(self, old_alloc: Dict[str, float],
                          new_alloc: Dict[str, float],
                          reasoning: str = "Periodic rebalancing"):
        """재배분 로깅"""
        if hasattr(self, 'dashboard'):
            self.dashboard.log_arbiter_decision(old_alloc, new_alloc, reasoning)

    def get_dashboard_summary(self) -> dict:
        """현재 대시보드 요약 반환"""
        if not hasattr(self, 'portfolio'):
            return {}

        summary = self.portfolio.get_metrics()
        summary['step'] = getattr(self.portfolio, 'step_count', 0)
        summary['total_pnl'] = self.portfolio.get_total_pnl()
        return summary

    def print_agent_report(self, agent_name: Optional[str] = None):
        """에이전트별 보고서 출력"""
        if not hasattr(self, 'portfolio'):
            return

        if agent_name:
            account = self.portfolio.get_agent_account(agent_name)
            if account:
                metrics = AgentMetrics.from_account(account)
                self.dashboard.log_agent_pnl(agent_name, metrics)
        else:
            # 모든 에이전트 출력
            for name in self.portfolio.accounts.keys():
                account = self.portfolio.get_agent_account(name)
                if account:
                    metrics = AgentMetrics.from_account(account)
                    self.dashboard.log_agent_pnl(name, metrics)


class DashboardLogger:
    """
    간단한 로거 클래스 - dashboard 모듈용
    arena.py 등에서 간단히 사용
    """

    def __init__(self, name: str = "dashboard"):
        self.name = name

    def log_agent_performance(self, agent_performance: Dict) -> None:
        """
        에이전트 성과 간단 로깅
        """
        print(f"\n[{self.name}] Agent Performance Update:")
        for agent, perf in agent_performance.items():
            print(f"  {agent}: PnL={perf.get('pnl', 0):+.2f}%, "
                  f"Alloc={perf.get('allocation', 0)*100:.1f}%")

    def log_portfolio_summary(self, capital: float, pnl: float,
                               agent_count: int) -> None:
        """
        포트폴리오 요약 로깅
        """
        print(f"\n[{self.name}] Portfolio: "
              f"Capital={capital:,.2f}, "
              f"PnL={pnl:+.2f}%, "
              f"Agents={agent_count}")


# 사용 예시
if __name__ == "__main__":
    # 테스트용 더미 데이터
    dashboard = TextDashboard(log_path="/tmp/dashboard.log")

    agents = {
        "momentum": AgentMetrics(
            name="momentum",
            allocation=0.30,
            pnl_24h=2.5,
            pnl_7d=8.2,
            pnl_total=15.3,
            sharpe=1.85,
            max_drawdown=-0.12,
            win_rate=0.65,
            open_positions=2,
            regime="bull"
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
            regime="sideways"
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
            regime="bull"
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
            regime="unknown"
        )
    }

    state = PortfolioState(
        total_capital=100.0,
        total_pnl_24h=1.6,
        total_pnl_7d=18.0,
        total_pnl_total=41.2,
        agent_metrics=agents,
        timestamp=datetime.utcnow()
    )

    # 전체 포트폴리오 상태 출력
    dashboard.log_portfolio_state(state)

    # 개별 에이전트 PnL 출력
    for agent_name, metrics in agents.items():
        dashboard.log_agent_pnl(agent_name, metrics)

    # Arbiter 결정 로깅 예시
    old_alloc = {"momentum": 0.30, "mean_reverter": 0.30,
                 "macro_trader": 0.25, "chaos_agent": 0.15}
    new_alloc = {"momentum": 0.35, "mean_reverter": 0.25,
                 "macro_trader": 0.30, "chaos_agent": 0.10}
    reasoning = "Bull regime detected. Increasing momentum/macro allocation."
    dashboard.log_arbiter_decision(old_alloc, new_alloc, reasoning)

    # 배틀 스텝 로깅 예시
    dashboard.log_battle_step(
        step=100,
        market_obs={"regime": "bull", "close": 45000},
        agent_actions={
            "momentum": 0.8,
            "mean_reverter": -0.3,
            "macro_trader": 0.5,
            "chaos_agent": -0.6
        },
        net_signal=0.035
    )
