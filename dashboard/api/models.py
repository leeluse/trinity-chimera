"""
Dashboard API Models
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class AgentType(str, Enum):
    MOMENTUM = "momentum_hunter"
    MEAN = "mean_reverter"
    MACRO = "macro_trader"
    CHAOS = "chaos_agent"


class AgentPnL(BaseModel):
    """에이전트 PnL 데이터 포인트"""
    timestamp: datetime
    agent_id: str
    agent_name: str
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    sharpe_ratio: float
    win_rate: float
    drawdown: float


class AgentAllocation(BaseModel):
    """개별 에이전트 배분"""
    agent_id: str
    agent_name: str
    allocation_pct: float  # 퍼센트 (0.0 ~ 1.0)
    allocation_units: float  # 자본 단위
    color: str  # UI 색상


class PortfolioAllocation(BaseModel):
    """포트폴리오 배분 현황"""
    timestamp: datetime
    total_capital: float
    agents: List[AgentAllocation]


class BattleEvent(BaseModel):
    """배틀 이벤트 로그"""
    timestamp: datetime
    event_type: str  # trade, allocation_change, regime_change, etc
    agent_id: Optional[str] = None
    description: str
    metadata: Optional[Dict] = None


class RegimeState(BaseModel):
    """현재 시장 Regime"""
    regime: str  # bull, sideways, bear
    confidence: float
    since: datetime


class DashboardState(BaseModel):
    """대시보드 전체 상태"""
    timestamp: datetime
    regime: RegimeState
    allocations: PortfolioAllocation
    agent_pnl: Dict[str, AgentPnL]
    recent_events: List[BattleEvent]
    total_portfolio_pnl: float
    total_portfolio_sharpe: float
