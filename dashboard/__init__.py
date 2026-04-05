"""
Dashboard Module - Text-based Monitoring System for AI Trading

MVP for Phase 2:
- Agent PnL console output
- Portfolio allocation logging
- Text-based monitoring (no web UI)

Usage:
    from dashboard import TextDashboard, AgentMetrics, PortfolioState
    dashboard = TextDashboard()
    dashboard.log_portfolio_state(portfolio_state)
"""

from .text_dashboard import (
    TextDashboard,
    DashboardLogger,
    AgentMetrics,
    PortfolioState
)

__all__ = [
    'TextDashboard',
    'DashboardLogger',
    'AgentMetrics',
    'PortfolioState',
    'ArenaDashboardMixin'
]
