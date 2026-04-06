/**
 * PortfolioSummaryPanel Component
 * 포트폴리오 전체 상태 요약 패널
 */

import React from 'react';
import type { PortfolioState } from '../types';

interface PortfolioSummaryPanelProps {
  totalCapital: number;
  totalPnl24h: number;
  totalPnl7d: number;
  totalPnlTotal: number;
  agentCount?: number;
  activeAgents?: number;
  timestamp?: string;
}

export const PortfolioSummaryPanel: React.FC<PortfolioSummaryPanelProps> = ({
  totalCapital,
  totalPnl24h,
  totalPnl7d,
  totalPnlTotal,
  agentCount = 2,
  activeAgents = 2,
  timestamp = new Date().toISOString(),
}) => {
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);

  const formatPercent = (value: number) =>
    `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

  const formatTimestamp = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const getTrendIcon = (value: number) => {
    if (value > 0) return '▲';
    if (value < 0) return '▼';
    return '•';
  };

  const getTrendColor = (value: number) => {
    if (value > 0) return 'text-emerald-500';
    if (value < 0) return 'text-red-500';
    return 'text-gray-500';
  };

  const getTrendBg = (value: number) => {
    if (value > 0) return 'bg-emerald-50 dark:bg-emerald-900/20';
    if (value < 0) return 'bg-red-50 dark:bg-red-900/20';
    return 'bg-gray-50 dark:bg-gray-800/50';
  };

  // activeAgents는 props로 받은 값을 사용
  const actualActiveAgents = activeAgents;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-500">
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Portfolio Summary
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Last updated: {formatTimestamp(timestamp)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 animate-pulse rounded-full bg-emerald-500"></span>
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {actualActiveAgents} Active
          </span>
        </div>
      </div>

      {/* 총 자본 */}
      <div className="mb-6">
        <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">Total Capital</p>
        <p className="text-4xl font-bold text-gray-900 dark:text-white">
          {formatCurrency(totalCapital)}
        </p>
      </div>

      {/* PnL 카드 그리드 */}
      <div className="grid grid-cols-3 gap-4">
        {/* 24h PnL */}
        <div className={`rounded-lg border p-4 ${getTrendBg(totalPnl24h)} dark:border-gray-700/50`}>
          <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">PnL (24h)</p>
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold ${getTrendColor(totalPnl24h)}`}>
              {formatPercent(totalPnl24h)}
            </span>
            <span className={`text-lg ${getTrendColor(totalPnl24h)}`}>
              {getTrendIcon(totalPnl24h)}
            </span>
          </div>
        </div>

        {/* 7d PnL */}
        <div className={`rounded-lg border p-4 ${getTrendBg(totalPnl7d)} dark:border-gray-700/50`}>
          <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">PnL (7d)</p>
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold ${getTrendColor(totalPnl7d)}`}>
              {formatPercent(totalPnl7d)}
            </span>
            <span className={`text-lg ${getTrendColor(totalPnl7d)}`}>
              {getTrendIcon(totalPnl7d)}
            </span>
          </div>
        </div>

        {/* Total PnL */}
        <div className={`rounded-lg border p-4 ${getTrendBg(totalPnlTotal)} dark:border-gray-700/50`}>
          <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">PnL (Total)</p>
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold ${getTrendColor(totalPnlTotal)}`}>
              {formatPercent(totalPnlTotal)}
            </span>
            <span className={`text-lg ${getTrendColor(totalPnlTotal)}`}>
              {getTrendIcon(totalPnlTotal)}
            </span>
          </div>
        </div>
      </div>

      {/* 푸터: 번외 정보 */}
      <div className="mt-6 border-t border-gray-100 pt-4 dark:border-gray-700">
        <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
          <div className="flex items-center gap-4">
            <span className="text-gray-500 dark:text-gray-400">
              Active Agents: <span className="font-medium text-gray-900 dark:text-white">{actualActiveAgents}</span>
            </span>
            <span className="text-gray-500 dark:text-gray-400">
              Allocation: <span className="font-medium text-gray-900 dark:text-white">100%</span>
            </span>
          </div>

          {/* 변화율 (이전 데이터와 비교) */}
          {/* 이전 상태 비교는 구현되지 않음 */}
        </div>
      </div>
    </div>
  );
};

/** Skeleton 로딩 상태 */
export const PortfolioSummaryPanelSkeleton: React.FC = () => (
  <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
    <div className="mb-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-xl bg-gray-200 dark:bg-gray-700"></div>
        <div>
          <div className="mb-2 h-6 w-40 rounded bg-gray-200 dark:bg-gray-700"></div>
          <div className="h-4 w-32 rounded bg-gray-200 dark:bg-gray-700"></div>
        </div>
      </div>
    </div>
    <div className="mb-6">
      <div className="mb-2 h-4 w-20 rounded bg-gray-200 dark:bg-gray-700"></div>
      <div className="h-10 w-48 rounded bg-gray-200 dark:bg-gray-700"></div>
    </div>
    <div className="grid grid-cols-3 gap-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-lg border p-4 dark:border-gray-700">
          <div className="mb-2 h-4 w-16 rounded bg-gray-200 dark:bg-gray-700"></div>
          <div className="h-8 w-24 rounded bg-gray-200 dark:bg-gray-700"></div>
        </div>
      ))}
    </div>
  </div>
);

export default PortfolioSummaryPanel;
