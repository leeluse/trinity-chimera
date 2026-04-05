"""
Portfolio - 가상 자본 및 PnL 추적
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np


@dataclass
class AgentAccount:
    """개별 에이전트의 가상 계좌"""
    name: str
    initial_capital: float = 25.0  # units
    current_capital: float = 25.0
    allocation_ratio: float = 0.25  # 현재 배분 비율 (0~1)

    # PnL 추적
    trades: List[dict] = field(default_factory=list)
    daily_pnl: List[float] = field(default_factory=list)
    portfolio_history: List[dict] = field(default_factory=list)

    def __post_init__(self):
        """초기화 후 history 설정"""
        self.current_capital = self.initial_capital

    def update_allocation(self, new_ratio: float):
        """새로운 배분 비율 적용 (min 5%, max 50%)"""
        self.allocation_ratio = np.clip(new_ratio, 0.05, 0.50)

    def record_trade(self, action: float, pnl: float, timestamp=None):
        """거래 기록"""
        self.trades.append({
            "action": action,
            "pnl": pnl,
            "timestamp": timestamp
        })
        self.current_capital += pnl

    def record_portfolio_state(self, state: Dict[str, Any]):
        """포트폴리오 상태 기록 (BaseAgent.compute_metrics용)"""
        self.portfolio_history.append(state)
        if len(self.portfolio_history) > 1000:
            self.portfolio_history = self.portfolio_history[-1000:]

    def record_daily_pnl(self, pnl: float):
        """일별 PnL 기록"""
        self.daily_pnl.append(pnl)

    def compute_sharpe(self, window: int = 7, risk_free_rate: float = 0.0) -> float:
        """Sharpe ratio 계산"""
        if len(self.daily_pnl) < 2:
            return 0.0
        returns = np.array(self.daily_pnl[-window:])
        if len(returns) < 2 or returns.std() < 1e-8:
            return 0.0
        return (returns.mean() - risk_free_rate) / (returns.std() + 1e-8)

    def compute_max_drawdown(self) -> float:
        """최대 낙폭 계산"""
        if not self.portfolio_history:
            return 0.0
        pnl_series = [p.get("pnl", 0.0) for p in self.portfolio_history]
        if not pnl_series:
            return 0.0
        cumulative = np.cumsum([0] + pnl_series)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (running_max - cumulative) / (running_max + 1e-8)
        return float(drawdowns.max())

    def compute_win_rate(self) -> float:
        """승률 계산"""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.get("pnl", 0) > 0)
        return wins / len(self.trades)

    def get_metrics(self) -> dict:
        """성과 메트릭 반환 (BaseAgent.compute_metrics 호환)"""
        return {
            "name": self.name,
            "allocation": self.allocation_ratio,
            "sharpe_7d": self.compute_sharpe(7),
            "max_drawdown": self.compute_max_drawdown(),
            "win_rate": self.compute_win_rate(),
            "total_pnl": self.current_capital - self.initial_capital,
            "trade_count": len(self.trades),
            "current_capital": self.current_capital,
        }


class Portfolio:
    """전체 포트폴리오 관리"""

    def __init__(self, total_capital: float = 100.0):
        self.total_capital = total_capital
        self.accounts: Dict[str, AgentAccount] = {}
        self.step_count = 0
        self.last_rebalance_step = 0
        self.allocation_history: List[dict] = []

    def add_agent(self, name: str, initial_allocation: float):
        """에이전트 추가"""
        capital = self.total_capital * initial_allocation
        self.accounts[name] = AgentAccount(
            name=name,
            initial_capital=capital,
            current_capital=capital,
            allocation_ratio=initial_allocation
        )

    def get_agent_account(self, name: str) -> Optional[AgentAccount]:
        """에이전트 계좌 조회"""
        return self.accounts.get(name)

    def get_allocation(self, name: str) -> float:
        """특정 에이전트 배분 비율 조회"""
        if name in self.accounts:
            return self.accounts[name].allocation_ratio
        return 0.25

    def set_allocation(self, allocations: Dict[str, float]):
        """배분 비율 업데이트"""
        total = sum(allocations.values())
        if abs(total - 1.0) > 0.01:
            allocations = {k: v / total for k, v in allocations.items()}

        for name, ratio in allocations.items():
            if name in self.accounts:
                self.accounts[name].update_allocation(ratio)

    def record_portfolio_state(self, agent_name: str, state: dict):
        """에이전트 포트폴리오 상태 기록"""
        if agent_name in self.accounts:
            self.accounts[agent_name].record_portfolio_state(state)

    def record_pnl(self, agent_name: str, pnl: float):
        """에이전트별 PnL 기록"""
        if agent_name in self.accounts:
            self.accounts[agent_name].record_daily_pnl(pnl)

    def get_total_pnl(self) -> float:
        """전체 포트폴리오 PnL"""
        total = sum(
            acc.current_capital - acc.initial_capital
            for acc in self.accounts.values()
        )
        return total

    def get_metrics(self) -> Dict[str, dict]:
        """모든 에이전트 메트릭 반환"""
        return {name: acc.get_metrics() for name, acc in self.accounts.items()}

    def should_rebalance(self, rebalance_interval: int = 7) -> bool:
        """재배분 필요 여부 확인"""
        return (self.step_count - self.last_rebalance_step) >= rebalance_interval

    def mark_rebalanced(self, new_allocations: Dict[str, float]):
        """재배분 완료 기록"""
        self.last_rebalance_step = self.step_count
        self.allocation_history.append({
            "step": self.step_count,
            "allocations": new_allocations.copy()
        })

    def step(self):
        """스텝 카운터 증가"""
        self.step_count += 1
