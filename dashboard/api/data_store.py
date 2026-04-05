"""
Dashboard Data Store
배틀 로그 데이터 관리 및 대시보드 상태 계산
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from dashboard.api.models import (
    AgentPnL, AgentAllocation, PortfolioAllocation,
    BattleEvent, RegimeState, DashboardState
)


class DataStore:
    """대시보드 데이터 관리"""

    def __init__(self, db_path: str = "data/battle_history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """SQLite 테이블 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_pnl (
                timestamp INTEGER,
                agent_id TEXT,
                unrealized REAL,
                realized REAL,
                sharpe REAL,
                win_rate REAL,
                drawdown REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allocations (
                timestamp INTEGER,
                agent_id TEXT,
                allocation_pct REAL,
                allocation_units REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                timestamp INTEGER,
                event_type TEXT,
                agent_id TEXT,
                description TEXT,
                metadata TEXT
            )
        """)

        conn.commit()
        conn.close()

    def get_agent_pnl_history(
        self,
        timeframe: str = "24h"
    ) -> Dict[str, List[AgentPnL]]:
        """에이전트별 PnL 히스토리 조회"""
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(timeframe, 24)
        since = int((datetime.now() - timedelta(hours=hours)).timestamp())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM agent_pnl
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        """, (since,))

        results = {}
        for row in cursor.fetchall():
            agent_id = row[1]
            pnl = AgentPnL(
                timestamp=datetime.fromtimestamp(row[0]),
                agent_id=agent_id,
                agent_name=self._get_agent_name(agent_id),
                unrealized_pnl=row[2],
                realized_pnl=row[3],
                total_pnl=row[2] + row[3],
                sharpe_ratio=row[4],
                win_rate=row[5],
                drawdown=row[6]
            )
            if agent_id not in results:
                results[agent_id] = []
            results[agent_id].append(pnl)

        conn.close()
        return results

    def get_current_allocation(self) -> PortfolioAllocation:
        """현재 포트폴리오 배분"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT timestamp, agent_id, allocation_pct, allocation_units
            FROM allocations
            ORDER BY timestamp DESC
        """)

        rows = cursor.fetchall()
        if not rows:
            return self._default_allocation()

        latest_ts = rows[0][0]
        agents = []
        total_capital = 0

        for row in rows:
            if row[0] == latest_ts:
                agents.append(AgentAllocation(
                    agent_id=row[1],
                    agent_name=self._get_agent_name(row[1]),
                    allocation_pct=row[2],
                    allocation_units=row[3],
                    color=self._get_agent_color(row[1])
                ))
                total_capital += row[3]

        conn.close()
        return PortfolioAllocation(
            timestamp=datetime.fromtimestamp(latest_ts),
            total_capital=total_capital,
            agents=agents
        )

    def get_allocation_history(self, days: int = 30) -> List[PortfolioAllocation]:
        """배분 히스토리"""
        since = int((datetime.now() - timedelta(days=days)).timestamp())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT timestamp, agent_id, allocation_pct, allocation_units
            FROM allocations
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        """, (since,))

        allocations_by_ts = {}
        for row in cursor.fetchall():
            ts = row[0]
            if ts not in allocations_by_ts:
                allocations_by_ts[ts] = []
            allocations_by_ts[ts].append(row[1:])

        conn.close()
        return [self._build_allocation(ts, data)
                for ts, data in allocations_by_ts.items()]

    def get_battle_events(
        self,
        limit: int = 100,
        agent_filter: Optional[str] = None
    ) -> List[BattleEvent]:
        """배틀 이벤트 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if agent_filter:
            cursor.execute("""
                SELECT * FROM events
                WHERE agent_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (agent_filter, limit))
        else:
            cursor.execute("""
                SELECT * FROM events
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

        events = []
        for row in cursor.fetchall():
            events.append(BattleEvent(
                timestamp=datetime.fromtimestamp(row[0]),
                event_type=row[1],
                agent_id=row[2],
                description=row[3],
                metadata=json.loads(row[4]) if row[4] else None
            ))

        conn.close()
        return events

    def get_current_state(self) -> DashboardState:
        """현재 대시보드 상태"""
        regime = RegimeState(
            regime="bull",
            confidence=0.75,
            since=datetime.now() - timedelta(hours=6)
        )

        allocation = self.get_current_allocation()
        agent_pnl_map = {
            agent.agent_id: AgentPnL(
                timestamp=datetime.now(),
                agent_id=agent.agent_id,
                agent_name=agent.agent_name,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                total_pnl=0.0,
                sharpe_ratio=0.0,
                win_rate=0.0,
                drawdown=0.0
            )
            for agent in allocation.agents
        }

        return DashboardState(
            timestamp=datetime.now(),
            regime=regime,
            allocations=allocation,
            agent_pnl=agent_pnl_map,
            recent_events=self.get_battle_events(limit=10),
            total_portfolio_pnl=0.0,
            total_portfolio_sharpe=0.0
        )

    def handle_freqtrade_update(self, payload: dict):
        """Freqtrade에서 수신한 실시간 업데이트 처리"""
        pass

    def _get_agent_name(self, agent_id: str) -> str:
        names = {
            "momentum_hunter": "Momentum Hunter",
            "mean_reverter": "Mean Reverter",
            "macro_trader": "Macro Trader",
            "chaos_agent": "Chaos Agent"
        }
        return names.get(agent_id, agent_id)

    def _get_agent_color(self, agent_id: str) -> str:
        colors = {
            "momentum_hunter": "#FF6B6B",
            "mean_reverter": "#4ECDC4",
            "macro_trader": "#45B7D1",
            "chaos_agent": "#96CEB4"
        }
        return colors.get(agent_id, "#888888")

    def _default_allocation(self) -> PortfolioAllocation:
        """기본 배분"""
        return PortfolioAllocation(
            timestamp=datetime.now(),
            total_capital=100.0,
            agents=[
                AgentAllocation(
                    agent_id="momentum_hunter",
                    agent_name="Momentum Hunter",
                    allocation_pct=0.30,
                    allocation_units=30.0,
                    color="#FF6B6B"
                ),
                AgentAllocation(
                    agent_id="mean_reverter",
                    agent_name="Mean Reverter",
                    allocation_pct=0.30,
                    allocation_units=30.0,
                    color="#4ECDC4"
                ),
                AgentAllocation(
                    agent_id="macro_trader",
                    agent_name="Macro Trader",
                    allocation_pct=0.25,
                    allocation_units=25.0,
                    color="#45B7D1"
                ),
                AgentAllocation(
                    agent_id="chaos_agent",
                    agent_name="Chaos Agent",
                    allocation_pct=0.15,
                    allocation_units=15.0,
                    color="#96CEB4"
                )
            ]
        )

    def _build_allocation(
        self,
        timestamp: int,
        data: list
    ) -> PortfolioAllocation:
        """그룹화된 데이터로 PortfolioAllocation 생성"""
        agents = []
        total = 0
        for row in data:
            agents.append(AgentAllocation(
                agent_id=row[0],
                agent_name=self._get_agent_name(row[0]),
                allocation_pct=row[1],
                allocation_units=row[2],
                color=self._get_agent_color(row[0])
            ))
            total += row[2]

        return PortfolioAllocation(
            timestamp=datetime.fromtimestamp(timestamp),
            total_capital=total,
            agents=agents
        )
