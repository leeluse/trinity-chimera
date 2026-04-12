import os
from typing import Optional, Dict
from datetime import datetime, timedelta


class EvolutionTrigger:
    """
    Evaluates trigger levels to determine if a strategy evolution is required.

    Trigger Levels:
    - L1 (Regime-Shift): Market regime change detected.
    - L2 (Performance Decay): Strategy performance drops significantly.
    - L3 (Competitive Pressure): Strategy is lagging behind the top performer.
    - L4 (Heartbeat): Regular periodic update.
    """

    def __init__(self):
        self._last_trigger_at: Dict[str, datetime] = {}

    @staticmethod
    def _heartbeat_minutes() -> int:
        try:
            minutes = int(os.getenv("EVOLUTION_HEARTBEAT_MINUTES", "60"))
        except ValueError:
            minutes = 60
        return max(1, min(minutes, 24 * 60))

    def check_regime_shift(self, current_regime: str, prev_regime: str) -> bool:
        """L1: Return True if the market regime has changed."""
        return current_regime != prev_regime

    def check_performance_decay(self, current_score: float, avg_score: float, threshold: float = 0.8) -> bool:
        """L2: Return True if current Trinity Score is <= 80% of the historical average."""
        return current_score <= (avg_score * threshold)

    def check_competitive_pressure(self, agent_rank: int, top_score: float, current_score: float, gap_threshold: float = 0.2) -> bool:
        """L3: Return True if the gap between the top score and current score is significant."""
        if agent_rank == 1:
            return False

        if top_score <= 0:
            return False

        gap = (top_score - current_score) / top_score
        return gap >= gap_threshold

    def check_heartbeat(self, last_evolution_at: Optional[datetime], days: int = 14) -> bool:
        """Legacy day-based heartbeat helper."""
        if last_evolution_at is None:
            return True

        return datetime.now() - last_evolution_at >= timedelta(days=days)

    async def check_trigger(self, agent_id: str) -> bool:
        """
        Runtime trigger used by orchestrator scheduled polling.
        Returns True when heartbeat interval has elapsed.
        """
        now = datetime.utcnow()
        interval = timedelta(minutes=self._heartbeat_minutes())
        last_at = self._last_trigger_at.get(agent_id)

        if last_at is None or (now - last_at) >= interval:
            self._last_trigger_at[agent_id] = now
            return True
        return False

    def mark_trigger(self, agent_id: str, when: Optional[datetime] = None) -> None:
        self._last_trigger_at[agent_id] = when or datetime.utcnow()

    def get_last_trigger_date(self, agent_id: str) -> datetime:
        return self._last_trigger_at.get(agent_id, datetime.utcnow())

    def get_intensity(self, trigger_level: str) -> str:
        """
        Maps trigger level to evolution intensity.
        L1, L2 -> HIGH (Pivot)
        L3, L4 -> LOW (Tuning)
        """
        high_triggers = {"L1", "L2"}
        low_triggers = {"L3", "L4"}

        if trigger_level in high_triggers:
            return "HIGH (Pivot)"
        elif trigger_level in low_triggers:
            return "LOW (Tuning)"

        return "LOW (Tuning)"
