/**
 * AgentCard Component
 * 개별 에이전트 상태 요약 카드
 */

import React from 'react';
import type { AgentMetrics, MarketRegime } from '../types';

interface AgentCardProps {
  metrics: AgentMetrics;
  isActive?: boolean;
  trend?: 'up' | 'down' | 'neutral';
  onClick?: () => void;
}

const regimeIcons: Record<MarketRegime, string> = {
  bull: '🟢',
  bear: '🔴',
  sideways: '🟡',
  volatile: '🟣',
  unknown: '⚪',
};

const regimeLabels: Record<MarketRegime, string> = {
  bull: 'Bull',
  bear: 'Bear',
  sideways: 'Sideways',
  volatile: 'Volatile',
  unknown: 'Unknown',
};

const agentIcons: Record<string, string> = {
  momentum_hunter: '🔥',
  mean_reverter: '🔄',
  macro_trader: '🌍',
  chaos_agent: '🌀',
  default: '🤖',
};

export const AgentCard: React.FC<AgentCardProps> = ({
  metrics,
  isActive = false,
  trend = 'neutral',
  onClick,
}) => {
  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  const formatDecimal = (value: number, decimals: number = 2) => value.toFixed(decimals);

  const getTrendIcon = () => {
    if (trend === 'up') return '▲';
    if (trend === 'down') return '▼';
    return '•';
  };

  const getTrendColor = (value: number) => {
    if (value > 0) return 'text-emerald-500';
    if (value < 0) return 'text-red-500';
    return 'text-gray-500';
  };

  const agentIcon = agentIcons[metrics.name.toLowerCase().replace(' ', '_')] || agentIcons.default;
  const regime = (metrics.regime.toLowerCase() as MarketRegime) || 'unknown';

  return (
    <div
      onClick={onClick}
      className={`
        relative overflow-hidden rounded-xl border p-5 transition-all duration-200
        ${isActive
          ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/20'
          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-md dark:border-gray-700 dark:bg-gray-800'
        }
        cursor-pointer
      `}
    >
      {/* 상단: 에이전트 이름과 상태 */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{agentIcon}</span>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {metrics.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            </h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {regimeIcons[regime]} {regimeLabels[regime]}
            </span>
          </div>
        </div>
        <div className={`rounded-full px-2 py-1 text-xs font-medium ${
          isActive
            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
        }`}>
          {isActive ? 'LIVE' : 'IDLE'}
        </div>
      </div>

      {/* PnL 섹션 */}
      <div className="mb-4 grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-700/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">24h</p>
          <p className={`font-semibold ${getTrendColor(metrics.pnl_24h)}`}>
            {formatPercent(metrics.pnl_24h)} {getTrendIcon()}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-700/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">7d</p>
          <p className={`font-semibold ${getTrendColor(metrics.pnl_7d)}`}>
            {formatPercent(metrics.pnl_7d)} {getTrendIcon()}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-700/50">
          <p className="text-xs text-gray-500 dark:text-gray-400">Total</p>
          <p className={`font-semibold ${getTrendColor(metrics.pnl_total)}`}>
            {formatPercent(metrics.pnl_total)}
          </p>
        </div>
      </div>

      {/* 메트릭스 그리드 */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Allocation</span>
          <div className="flex items-center gap-2">
            <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className="h-full rounded-full bg-blue-500 transition-all duration-500"
                style={{ width: `${metrics.allocation * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {(metrics.allocation * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Sharpe</span>
          <span className={`text-sm font-medium ${
            metrics.sharpe > 1
              ? 'text-emerald-500'
              : metrics.sharpe > 0
                ? 'text-yellow-500'
                : 'text-red-500'
          }`}>
            {formatDecimal(metrics.sharpe)}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Win Rate</span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {(metrics.win_rate * 100).toFixed(1)}%
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Max DD</span>
          <span className="text-sm font-medium text-red-500">
            {(metrics.max_drawdown * 100).toFixed(1)}%
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Open Pos</span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {metrics.open_positions}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-500 dark:text-gray-400">Trades</span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {metrics.trade_count}
          </span>
        </div>
      </div>

      {/* 액션 버튼 */}
      <div className="mt-4 flex gap-2">
        <button
          onClick={(e) => {
            e.stopPropagation();
            // View details action
          }}
          className="flex-1 rounded-lg border border-gray-300 py-2 text-sm font-medium text-gray-700
                     transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300
                     dark:hover:bg-gray-700"
        >
          View Details
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            // Reallocate action
          }}
          className="flex-1 rounded-lg bg-blue-500 py-2 text-sm font-medium text-white
                     transition-colors hover:bg-blue-600 dark:bg-blue-600 dark:hover:bg-blue-700"
        >
          Reallocate
        </button>
      </div>
    </div>
  );
};

export default AgentCard;
