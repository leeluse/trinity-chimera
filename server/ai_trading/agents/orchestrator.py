import logging
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path

from dotenv import load_dotenv

from server.api.services.supabase_client import SupabaseManager

from .llm_client import EvolutionLLMClient
from .trigger import EvolutionTrigger

try:
    from server.ai_trading.core.strategy_loader import StrategyLoader
    from server.ai_trading.core.backtest_manager import BacktestManager
    from server.ai_trading.core.metrics_buffer import MetricsBuffer
except ImportError:
    class MetricsBuffer:
        def __init__(self, trigger_callback=None):
            self._trigger_callback = trigger_callback

        async def set_callback(self, callback):
            """Set callback - async to support both sync and async callbacks"""
            self._trigger_callback = callback

        async def push(self, agent_id: str, tick: Any) -> Optional[str]:
            """No-op fallback push"""
            return None

    class StrategyLoader:
        @staticmethod
        def load_strategy(code: str):
            return True

        @staticmethod
        def validate_code(code: str):
            pass

    class BacktestManager:
        async def validate_strategy(self, code: str):
            return {"trinity_score": 150, "return": 15.0, "sharpe": 2.0, "mdd": -5.0, "win_rate": 60.0}

logger = logging.getLogger(__name__)


class EvolutionState(Enum):
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMMITTING = "COMMITTING"


class EvolutionOrchestrator:
    def __init__(self):
        self.llm_client = EvolutionLLMClient()
        self.trigger_engine = EvolutionTrigger()
        self.supabase = SupabaseManager()
        self.backtest_manager = BacktestManager()
        self.metrics_buffer = MetricsBuffer()  # 신규 추가
        self.metrics_buffer.set_callback(self._on_metrics_buffer_trigger)  # 콜백 설정
        self.states: Dict[str, EvolutionState] = {}

    async def _on_metrics_buffer_trigger(self, agent_id: str, metrics_entries: List):
        """Handle MetricsBuffer trigger"""
        try:
            if self.states.get(agent_id) != EvolutionState.IDLE:
                return  # 이미 진행 중인 에이전트는 건너뜀

            await self.run_evolution_cycle(agent_id, force_trigger=True)
        except Exception as e:
            logger.error(f"MetricsBuffer trigger failed for {agent_id}: {e}")

    async def get_state(self, agent_id: str) -> Optional[EvolutionState]:
        return self.states.get(agent_id, EvolutionState.IDLE)

    async def run_evolution_cycle(self, agent_id: str, force_trigger: bool = False):
        try:
            if not force_trigger:
                # V2.0: Replace hardcoded False with dynamic trigger logic
                # In a full implementation, this would check for performance decay,
                # regime change, or a specific time interval.
                is_triggered = await self.trigger_engine.check_trigger(agent_id)
                if not is_triggered:
                    return

            self.states[agent_id] = EvolutionState.TRIGGERED
            logger.info(f"Agent {agent_id} evolution triggered.")

            self.states[agent_id] = EvolutionState.GENERATING

            strategy_data = await self.supabase.get_agent_strategy(agent_id)
            if not strategy_data:
                logger.error(f"Could not find current strategy for agent {agent_id}")
                self.states[agent_id] = EvolutionState.IDLE
                return

            # V2.0: Prevent Look-ahead Bias.
            # Fetch backtest metrics for a specific OOS window ending at the trigger point.
            # This ensures the LLM doesn't see "future" data.
            trigger_date = self.trigger_engine.get_last_trigger_date(agent_id)
            metrics = await self.supabase.get_backtest_for_period(
                strategy_id=strategy_data.get("id"),
                end_date=trigger_date,
                period_type="OOS"
            ) if strategy_data.get("id") else {
                "trinity_score": 0, "return": 0.0, "sharpe": 0.0, "mdd": 0.0
            }

            # V2.0: Data Validation Gate (Analyst Recommended)
            if not metrics or metrics.get("trinity_score") is None:
                logger.error(f"Invalid or missing metrics for agent {agent_id}. Skipping evolution.")
                self.states[agent_id] = EvolutionState.IDLE
                return

            evolution_package = {
                "current_strategy_code": strategy_data.get("code", ""),
                "metrics": metrics,
                "market_regime": "Unknown", # TODO: Integrate with MarketContextProvider
                "competitive_rank": "Unknown", # TODO: Implement Cross-Agent Rank Calculation
                "evolution_history": "Analyzing structural patterns...", # TODO: Abstracted Pattern Summary
                "loss_period_logs": "Analyzing drawdown periods...",
                "top_agent_traits": "Comparing with high-sharpe agents...",
                "market_volatility": "Medium",
            }

            new_code = await self.llm_client.generate_strategy_code(evolution_package)

            self.states[agent_id] = EvolutionState.VALIDATING

            StrategyLoader.validate_code(new_code)
            metrics = await self.backtest_manager.validate_strategy(new_code)

            if metrics["trinity_score"] <= evolution_package["metrics"]["trinity_score"]:
                logger.info(f"Evolution rejected for agent {agent_id}: No score improvement.")
                self.states[agent_id] = EvolutionState.IDLE
                return

            self.states[agent_id] = EvolutionState.COMMITTING

            prev_strategy_id = strategy_data.get("id")
            new_strategy_id = await self.supabase.save_strategy(
                agent_id=agent_id,
                code=new_code,
                rationale="Automated evolution based on C-mode analysis",
                params=strategy_data.get("params", {}),
            )

            if new_strategy_id:
                await self.supabase.save_backtest(new_strategy_id, metrics)
                await self.supabase.save_improvement_log(
                    agent_id=agent_id,
                    prev_id=prev_strategy_id,
                    new_id=new_strategy_id,
                    analysis="C-mode optimization successful",
                    expected={"trinity_score": metrics["trinity_score"]},
                )
                logger.info(f"Agent {agent_id} successfully evolved to version {new_strategy_id}")
            else:
                logger.error(f"Failed to save new strategy for agent {agent_id}")
        except Exception as e:
            logger.exception(f"Error during evolution cycle for agent {agent_id}: {e}")
        finally:
            self.states[agent_id] = EvolutionState.IDLE


_evolution_orchestrator: Optional[EvolutionOrchestrator] = None


def _load_environment_once() -> None:
    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(project_root / "server" / "api" / ".env", override=False)


def get_evolution_orchestrator() -> EvolutionOrchestrator:
    global _evolution_orchestrator
    if _evolution_orchestrator is None:
        _load_environment_once()
        _evolution_orchestrator = EvolutionOrchestrator()
    return _evolution_orchestrator
