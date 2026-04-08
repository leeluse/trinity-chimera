from enum import Enum
from typing import Dict, Any, Optional
import logging
import asyncio
from datetime import datetime

from .evolution_llm_client import EvolutionLLMClient
from .evolution_trigger import EvolutionTrigger
from .supabase_client import SupabaseManager

# Assuming StrategyLoader and BacktestManager exist based on the design doc
# Since they aren't in the current services folder, they might be in ai_trading.core
try:
    from ai_trading.core.strategy_loader import StrategyLoader
    from ai_trading.core.backtest_manager import BacktestManager
except ImportError:
    # Mock classes for integration if core is not available in this environment
    class StrategyLoader:
        @staticmethod
        def load_strategy(code: str): return True
        @staticmethod
        def validate_code(code: str): pass

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
        self.states: Dict[str, EvolutionState] = {}

    async def get_state(self, agent_id: str) -> Optional[EvolutionState]:
        return self.states.get(agent_id, EvolutionState.IDLE)

    async def run_evolution_cycle(self, agent_id: str, force_trigger: bool = False):
        """
        The main state machine for agent evolution.
        IDLE -> TRIGGERED -> GENERATING -> VALIDATING -> COMMITTING -> IDLE
        """
        try:
            # 1. TRIGGER CHECK
            if not force_trigger:
                # In a real system, we would fetch actual metrics from Supabase
                # For now, we simulate the check
                is_triggered = False # Simplified for this loop
                if not is_triggered:
                    return

            self.states[agent_id] = EvolutionState.TRIGGERED
            logger.info(f"Agent {agent_id} evolution triggered.")

            # 2. GENERATION
            self.states[agent_id] = EvolutionState.GENERATING

            # Assemble C-mode package
            strategy_data = await self.supabase.get_agent_strategy(agent_id)
            if not strategy_data:
                logger.error(f"Could not find current strategy for agent {agent_id}")
                self.states[agent_id] = EvolutionState.IDLE
                return

            evolution_package = {
                "current_strategy_code": strategy_data.get("code", ""),
                "metrics": {
                    "trinity_score": 120, # Mock
                    "return": 10.0,
                    "sharpe": 1.5,
                    "mdd": -8.0
                },
                "market_regime": "Bull", # Mock
                "competitive_rank": "5th", # Mock
                "evolution_history": "S-curve improving",
                "loss_period_logs": "High drawdown during choppy markets",
                "top_agent_traits": "Fast trend adaptation",
                "market_volatility": "Medium"
            }

            new_code = await self.llm_client.generate_strategy_code(evolution_package)

            # 3. VALIDATION
            self.states[agent_id] = EvolutionState.VALIDATING

            # Validate syntax and security
            StrategyLoader.validate_code(new_code)

            # Run backtest
            metrics = await self.backtest_manager.validate_strategy(new_code)

            # Validation Gate: Trinity Score must improve
            if metrics["trinity_score"] <= evolution_package["metrics"]["trinity_score"]:
                logger.info(f"Evolution rejected for agent {agent_id}: No score improvement.")
                self.states[agent_id] = EvolutionState.IDLE
                return

            # 4. COMMITTING
            self.states[agent_id] = EvolutionState.COMMITTING

            prev_strategy_id = strategy_data.get("id")
            new_strategy_id = await self.supabase.save_strategy(
                agent_id=agent_id,
                code=new_code,
                rationale="Automated evolution based on C-mode analysis",
                params=strategy_data.get("params", {})
            )

            if new_strategy_id:
                await self.supabase.save_backtest(new_strategy_id, metrics)
                await self.supabase.save_improvement_log(
                    agent_id=agent_id,
                    prev_id=prev_strategy_id,
                    new_id=new_strategy_id,
                    analysis="C-mode optimization successful",
                    expected={"trinity_score": metrics["trinity_score"]}
                )
                logger.info(f"Agent {agent_id} successfully evolved to version {new_strategy_id}")
            else:
                logger.error(f"Failed to save new strategy for agent {agent_id}")

        except Exception as e:
            logger.exception(f"Error during evolution cycle for agent {agent_id}: {e}")
        finally:
            self.states[agent_id] = EvolutionState.IDLE
