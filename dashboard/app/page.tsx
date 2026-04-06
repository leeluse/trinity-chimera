/**
 * TRINITY-CHIMERY Dashboard - Main Page
 * 메인 대시보드 페이지
 */

'use client';

import React, { useEffect, useState } from 'react';
import { AgentCard } from '../components/AgentCard';
import { PortfolioSummaryPanel } from '../components/PortfolioSummaryPanel';
import { PortfolioValueChart } from '../components/PortfolioValueChart';
import { RealtimeIndicator } from '../components/RealtimeIndicator';
import { TradeHistoryTable } from '../components/TradeHistoryTable';
import { ArbiterDecisionLog } from '../components/ArbiterDecisionLog';
import { useDashboardStore } from '../store/useDashboardStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { AgentMetrics, PortfolioState, Trade, ArbiterDecision, WebSocketEvent } from '../types';

// Mock data for initial development
const mockAgents: Record<string, AgentMetrics> = {
  momentum_hunter: {
    name: 'Momentum Hunter',
    allocation: 0.4,
    pnl_24h: 2.5,
    pnl_7d: 8.3,
    pnl_total: 15.2,
    sharpe: 1.8,
    max_drawdown: 0.12,
    win_rate: 0.68,
    open_positions: 3,
    regime: 'bull',
    trade_count: 145,
  },
  mean_reverter: {
    name: 'Mean Reverter',
    allocation: 0.35,
    pnl_24h: -0.8,
    pnl_7d: 3.2,
    pnl_total: 8.7,
    sharpe: 1.2,
    max_drawdown: 0.08,
    win_rate: 0.62,
    open_positions: 2,
    regime: 'sideways',
    trade_count: 98,
  },
};

const mockPortfolio: PortfolioState = {
  total_capital: 125000,
  total_pnl_24h: 1.7,
  total_pnl_7d: 11.5,
  total_pnl_total: 23.9,
  agent_metrics: mockAgents,
  timestamp: new Date().toISOString(),
};

const mockPortfolioHistory: PortfolioState[] = [
  { ...mockPortfolio, timestamp: new Date(Date.now() - 86400000 * 30).toISOString(), total_capital: 100000 },
  { ...mockPortfolio, timestamp: new Date(Date.now() - 86400000 * 20).toISOString(), total_capital: 108000 },
  { ...mockPortfolio, timestamp: new Date(Date.now() - 86400000 * 10).toISOString(), total_capital: 115000 },
  { ...mockPortfolio, timestamp: new Date(Date.now() - 86400000).toISOString(), total_capital: 122000 },
  mockPortfolio,
];

const mockTrades: Trade[] = [
  { id: '1', agent_name: 'momentum_hunter', action: 1, pnl: 250, timestamp: new Date().toISOString(), symbol: 'BTC/USDT', entry_price: 65000, exit_price: 66000 },
  { id: '2', agent_name: 'mean_reverter', action: -0.5, pnl: -120, timestamp: new Date(Date.now() - 3600000).toISOString(), symbol: 'ETH/USDT', entry_price: 3500, exit_price: 3450 },
];

const mockDecisions: ArbiterDecision[] = [
  {
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    old_allocations: { momentum_hunter: 0.3, mean_reverter: 0.4 },
    new_allocations: { momentum_hunter: 0.4, mean_reverter: 0.35 },
    reasoning: 'Momentum Hunter shows superior performance in current bull regime with 1.8 Sharpe ratio. Increased allocation to capture trend.',
  },
];

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'agents' | 'trades' | 'arbiter'>('overview');
  const { setPortfolio, setAgents } = useDashboardStore();

  // WebSocket connection
  const { status, lastEvent, latency, lastUpdate } = useWebSocket({
    url: 'ws://localhost:8000/ws/dashboard',
    autoConnect: true,
  });

  const isConnected = status === 'connected';

  // Handle WebSocket events
  useEffect(() => {
    if (lastEvent) {
      const event = lastEvent as WebSocketEvent;
      switch (event.type) {
        case 'portfolio':
          setPortfolio(event.data as PortfolioState);
          break;
        case 'agent_update':
          const agentMetrics = event.data as AgentMetrics;
          setAgents({ [agentMetrics.name]: agentMetrics });
          break;
      }
    }
  }, [lastEvent, setPortfolio, setAgents]);

  // Initialize with mock data (for development)
  useEffect(() => {
    setPortfolio(mockPortfolio);
    setAgents(mockAgents);
  }, [setPortfolio, setAgents]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md dark:border-gray-700 dark:bg-gray-900/80">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo & Title */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600">
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">
                  TRINITY-CHIMERY
                </h1>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  AI Trading Dashboard
                </p>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="hidden md:flex items-center gap-1">
              {[
                { id: 'overview', label: 'Overview', icon: '📊' },
                { id: 'agents', label: 'Agents', icon: '🤖' },
                { id: 'trades', label: 'Trades', icon: '💱' },
                { id: 'arbiter', label: 'Arbiter', icon: '⚖️' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === tab.id
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
            </nav>

            {/* Right Side: Connection Status */}
            <RealtimeIndicator
              status={isConnected ? 'connected' : 'disconnected'}
              latency={24}
              lastUpdate={new Date().toISOString()}
            />
          </div>
        </div>
      </header>

      {/* Mobile Navigation */}
      <div className="border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900 md:hidden">
        <div className="mx-auto max-w-7xl px-4">
          <div className="flex overflow-x-auto py-2 gap-2">
            {[
              { id: 'overview', label: 'Overview' },
              { id: 'agents', label: 'Agents' },
              { id: 'trades', label: 'Trades' },
              { id: 'arbiter', label: 'Arbiter' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-fade-in">
            {/* Portfolio Summary */}
            <PortfolioSummaryPanel
              totalCapital={mockPortfolio.total_capital}
              totalPnl24h={mockPortfolio.total_pnl_24h}
              totalPnl7d={mockPortfolio.total_pnl_7d}
              totalPnlTotal={mockPortfolio.total_pnl_total}
              agentCount={Object.keys(mockPortfolio.agent_metrics).length}
              activeAgents={Object.values(mockPortfolio.agent_metrics).filter(a => a.open_positions > 0).length}
            />

            {/* Portfolio Chart & Agent Cards */}
            <div className="grid gap-6 lg:grid-cols-3">
              {/* Chart - takes 2 columns */}
              <div className="lg:col-span-2">
                <PortfolioValueChart data={mockPortfolioHistory} height={350} />
              </div>

              {/* Agent Cards */}
              <div className="space-y-4">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Active Agents
                </h2>
                {Object.values(mockAgents).map((agent) => (
                  <AgentCard key={agent.name} metrics={agent} isActive={agent.open_positions > 0} />
                ))}
              </div>
            </div>

            {/* Recent Activity */}
            <div className="grid gap-6 md:grid-cols-2">
              <TradeHistoryTable trades={mockTrades.slice(0, 5)} pageSize={5} />
              <ArbiterDecisionLog decisions={mockDecisions} maxEntries={3} />
            </div>
          </div>
        )}

        {/* Agents Tab */}
        {activeTab === 'agents' && (
          <div className="space-y-6 animate-fade-in">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Agent Performance</h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {Object.values(mockAgents).map((agent) => (
                <AgentCard key={agent.name} metrics={agent} isActive={true} />
              ))}
            </div>
          </div>
        )}

        {/* Trades Tab */}
        {activeTab === 'trades' && (
          <div className="space-y-6 animate-fade-in">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Trade History</h2>
            <TradeHistoryTable trades={mockTrades} />
          </div>
        )}

        {/* Arbiter Tab */}
        {activeTab === 'arbiter' && (
          <div className="space-y-6 animate-fade-in">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">LLM Arbiter Decisions</h2>
            <ArbiterDecisionLog decisions={mockDecisions} showReasoning={true} />
          </div>
        )}
      </main>
    </div>
  );
}
