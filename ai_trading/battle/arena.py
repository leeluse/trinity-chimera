"""
Arena - 배틀 오케스트레이션

BaseAgent 인터페이스와 통합된 배틀 시스템
"""

from typing import Dict, List, Optional, Any, Callable
import logging
import numpy as np

from .portfolio import Portfolio

logger = logging.getLogger(__name__)


class AgentVote:
    """개별 에이전트 투표 결과"""
    def __init__(self, name: str, action: float, confidence: float = 1.0):
        self.name = name
        self.action = action
        self.confidence = confidence


class Arena:
    """
    배틀 시스템 메인 오케스트레이터

    BaseAgent 인터페이스 통합:
    - BaseAgent.build_observation() -> RL input
    - BaseAgent.act() -> action 결정
    - BaseAgent.compute_metrics() -> 성과 평가
    """

    def __init__(
        self,
        agents: Optional[List] = None,
        total_capital: float = 100.0,
        rebalance_interval: int = 7,
        agent_allocations: Optional[Dict[str, float]] = None,
    ):
        self.agents: Dict[str, Any] = {}
        self.is_base_agent: Dict[str, bool] = {}
        self.portfolio = Portfolio(total_capital=total_capital)
        self.rebalance_interval = rebalance_interval

        default_allocations = {
            "momentum_hunter": 0.30,
            "mean_reverter": 0.30,
            "macro_trader": 0.25,
            "chaos_agent": 0.15,
        }
        self.allocations = agent_allocations or default_allocations
        self.agent_portfolio_states: Dict[str, dict] = {}

        if agents:
            for agent in agents:
                self.register_agent(agent)

        for name, ratio in self.allocations.items():
            if name not in self.portfolio.accounts:
                self.portfolio.add_agent(name, ratio)

        logger.info(f"Arena initialized with {len(self.agents)} agents")

    def step(
        self,
        observation: Dict[str, Any],
        current_prices: Optional[Dict[str, float]] = None,
    ) -> dict:
        """
        한 스텝 진행

        Args:
            observation: 시장 관찰값 (dict)
            current_prices: 현재 가격 (선택)

        Returns:
            step 결과 딕셔너리
        """
        votes: List[AgentVote] = []

        for name, agent in self.agents.items():
            try:
                if self.is_base_agent.get(name, False):
                    # BaseAgent 인터페이스
                    portfolio_state = self.agent_portfolio_states[name]
                    obs = agent.build_observation(observation, portfolio_state)
                    action = agent.act(obs)
                elif callable(agent):
                    # Callable 인터페이스
                    action = agent(observation)
                else:
                    action = 0.0

                action = float(np.clip(action, -1.0, 1.0))
                confidence = abs(action)
                votes.append(AgentVote(name, action, confidence))

            except Exception as e:
                logger.warning(f"Agent {name} failed: {e}")
                votes.append(AgentVote(name, 0.0, 0.0))

        # 가중 투표
        net_action = self._weighted_vote(votes)

        # 포트폴리오 업데이트
        self._update_portfolio_states(votes, current_prices)
        self.portfolio.step()

        return {
            "net_action": net_action,
            "actions": {v.name: {"action": v.action, "confidence": v.confidence}
                       for v in votes},
            "allocations": {name: self.portfolio.get_allocation(name)
                          for name in self.agents},
        }

    def _weighted_vote(self, votes: List[AgentVote]) -> float:
        """자본 가중 투표"""
        weighted_sum = 0.0
        total_weight = 0.0

        for vote in votes:
            allocation = self.portfolio.get_allocation(vote.name)
            weighted_sum += allocation * vote.action * vote.confidence
            total_weight += allocation * vote.confidence

        if total_weight < 1e-8:
            return 0.0

        return float(np.clip(weighted_sum / total_weight, -1.0, 1.0))

    def _update_portfolio_states(
        self,
        votes: List[AgentVote],
        current_prices: Optional[Dict[str, float]] = None,
    ):
        """포트폴리오 상태 업데이트"""
        for vote in votes:
            name = vote.name
            if name not in self.agent_portfolio_states:
                continue

            state = self.agent_portfolio_states[name]
            prev_state = state.copy()

            state["position"] = vote.action
            state["hold_bars"] = prev_state.get("hold_bars", 0) + 1 if vote.action != 0 else 0
            state["cash_ratio"] = 1.0 - abs(vote.action)

            # BaseAgent 업데이트
            agent = self.agents.get(name)
            if agent and self.is_base_agent.get(name, False):
                try:
                    agent.update_portfolio_history(state)
                except:
                    pass
            self.portfolio.record_portfolio_state(name, state)

    def update_allocations(self, new_allocations: Dict[str, float]):
        """재배분 실행 (min 5%, max 50%)"""
        constrained = {}
        for name, ratio in new_allocations.items():
            if name in self.agents:
                constrained[name] = np.clip(ratio, 0.05, 0.50)

        total = sum(constrained.values())
        if total > 0:
            constrained = {k: v / total for k, v in constrained.items()}
            self.allocations = constrained
            self.portfolio.set_allocation(constrained)
            self.portfolio.mark_rebalanced(constrained)
            logger.info(f"Allocations updated: {constrained}")

    def get_agent_metrics(self) -> Dict[str, dict]:
        """모든 에이전트 메트릭 (BaseAgent.compute_metrics 사용)"""
        from ai_trading.agents.base_agent import BaseAgent

        metrics = {}
        for name, agent in self.agents.items():
            account = self.portfolio.get_agent_account(name)
            portfolio_history = account.portfolio_history if account else []

            if isinstance(agent, BaseAgent) or hasattr(agent, "compute_metrics"):
                try:
                    metrics[name] = agent.compute_metrics(portfolio_history)
                except Exception as e:
                    logger.warning(f"Failed to get metrics for {name}: {e}")
                    metrics[name] = self._default_metrics(name)
            else:
                metrics[name] = self._default_metrics(name)

            metrics[name]["allocation"] = self.portfolio.get_allocation(name)
        return metrics

    def _default_metrics(self, name: str) -> dict:
        """기본 메트릭"""
        return {
            "sharpe_7d": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "avg_hold_bars": 0.0,
            "regime_fit": 0.5,
            "diversity_score": 0.5,
            "overfit_score": 0.0,
        }

    def get_summary(self) -> dict:
        """현재 상태 요약"""
        return {
            "step": self.portfolio.step_count,
            "agents": list(self.agents.keys()),
            "total_pnl": self.portfolio.get_total_pnl(),
            "metrics": self.portfolio.get_metrics(),
        }

    def get_net_position_size(self) -> float:
        """현재 순 포지션 크기"""
        from dataclasses import dataclass

        # No history, compute from current agents
        votes = []
        for name, agent in self.agents.items():
            try:
                if self.is_base_agent.get(name, False):
                    state = self.agent_portfolio_states.get(name, {})
                    action = state.get("position", 0.0)
                else:
                    action = 0.0
                confidence = abs(action)
                votes.append(AgentVote(name, action, confidence))
            except:
                votes.append(AgentVote(name, 0.0, 0.0))

        return self._weighted_vote(votes)
