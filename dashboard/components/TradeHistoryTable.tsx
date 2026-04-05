/**
 * TradeHistoryTable Component
 * 거래 실행 이력 테이블
 */

import React, { useState, useMemo } from 'react';
import type { Trade } from '../types';

interface TradeHistoryTableProps {
  trades: Trade[];
  pageSize?: number;
  filterable?: boolean;
  sortable?: boolean;
  agentFilter?: string[];
  dateRange?: { start: string; end: string };
}

type SortField = 'timestamp' | 'agent_name' | 'pnl' | 'action';
type SortDirection = 'asc' | 'desc';

export const TradeHistoryTable: React.FC<TradeHistoryTableProps> = ({
  trades,
  pageSize = 10,
  filterable = true,
  sortable = true,
  agentFilter,
}) => {
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [agentFilterInput, setAgentFilterInput] = useState<string>('all');
  const [resultFilter, setResultFilter] = useState<string>('all');

  // 에이전트 목록
  const agents = useMemo(() => {
    const unique = new Set(trades.map((t) => t.agent_name));
    return Array.from(unique).sort();
  }, [trades]);

  // 필터링 및 정렬된 데이터
  const filteredAndSortedTrades = useMemo(() => {
    let filtered = [...trades];

    // 에이전트 필터
    if (agentFilterInput !== 'all') {
      filtered = filtered.filter((t) => t.agent_name === agentFilterInput);
    }

    // 결과 필터
    if (resultFilter === 'profit') {
      filtered = filtered.filter((t) => t.pnl > 0);
    } else if (resultFilter === 'loss') {
      filtered = filtered.filter((t) => t.pnl < 0);
    } else if (resultFilter === 'neutral') {
      filtered = filtered.filter((t) => t.pnl === 0);
    }

    // 정렬
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'timestamp':
          comparison = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case 'agent_name':
          comparison = a.agent_name.localeCompare(b.agent_name);
          break;
        case 'pnl':
          comparison = a.pnl - b.pnl;
          break;
        case 'action':
          comparison = a.action - b.action;
          break;
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [trades, agentFilterInput, resultFilter, sortField, sortDirection]);

  // 페이지네이션
  const totalPages = Math.ceil(filteredAndSortedTrades.length / pageSize);
  const paginatedTrades = filteredAndSortedTrades.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // 정렬 핸들러
  const handleSort = (field: SortField) => {
    if (!sortable) return;
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
    setCurrentPage(1);
  };

  // 포맷 도우미
  const formatCurrency = (value: number) =>
    `$${Math.abs(value).toFixed(2)}`;

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

  const formatAction = (action: number) => {
    if (action > 0) return { text: `LONG ${(action * 100).toFixed(0)}%`, color: 'text-emerald-600' };
    if (action < 0) return { text: `SHORT ${(Math.abs(action) * 100).toFixed(0)}%`, color: 'text-red-600' };
    return { text: 'NEUTRAL', color: 'text-gray-500' };
  };

  // CSV 내보내기
  const exportCSV = () => {
    const headers = ['ID', 'Time', 'Agent', 'Action', 'Entry Price', 'Exit Price', 'PnL', 'PnL %'];
    const rows = filteredAndSortedTrades.map((t) => [
      t.id,
      t.timestamp,
      t.agent_name,
      t.action,
      t.entry_price?.toFixed(2) || 'N/A',
      t.exit_price?.toFixed(2) || 'N/A',
      t.pnl.toFixed(4),
      (t.pnl * 100).toFixed(2) + '%',
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trades_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  // 정렬 아이콘
  const SortIcon = ({ field }: { field: SortField }) => {
    if (!sortable || sortField !== field) {
      return <span className="ml-1 text-gray-300">↕</span>;
    }
    return (
      <span className="ml-1 text-blue-500">
        {sortDirection === 'asc' ? '↑' : '↓'}
      </span>
    );
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="border-b border-gray-200 p-4 dark:border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Trade History
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {filteredAndSortedTrades.length} trades total
            </p>
          </div>
          <button
            onClick={exportCSV}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700
                       transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300
                       dark:hover:bg-gray-700"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* 필터 바 */}
      {filterable && (
        <div className="border-b border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-900/50">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600 dark:text-gray-400">Agent:</label>
              <select
                value={agentFilterInput}
                onChange={(e) => {
                  setAgentFilterInput(e.target.value);
                  setCurrentPage(1);
                }}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm
                           focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                           dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="all">All Agents</option>
                {agents.map((agent) => (
                  <option key={agent} value={agent}>
                    {agent}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600 dark:text-gray-400">Result:</label>
              <select
                value={resultFilter}
                onChange={(e) => {
                  setResultFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm
                           focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                           dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="all">All</option>
                <option value="profit">Profit</option>
                <option value="loss">Loss</option>
                <option value="neutral">Neutral</option>
              </select>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Showing {Math.min(filteredAndSortedTrades.length, (currentPage - 1) * pageSize + 1)}-
                {Math.min(filteredAndSortedTrades.length, currentPage * pageSize)} of{' '}
                {filteredAndSortedTrades.length}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 테이블 */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-900/50">
            <tr>
              <th
                onClick={() => handleSort('timestamp')}
                className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
                           text-gray-500 dark:text-gray-400"
              >
                Time <SortIcon field="timestamp" />
              </th>
              <th
                onClick={() => handleSort('agent_name')}
                className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
                           text-gray-500 dark:text-gray-400"
              >
                Agent <SortIcon field="agent_name" />
              </th>
              <th
                onClick={() => handleSort('action')}
                className="cursor-pointer px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
                           text-gray-500 dark:text-gray-400"
              >
                Action <SortIcon field="action" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
                             text-gray-500 dark:text-gray-400">
                Entry
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider
                             text-gray-500 dark:text-gray-400">
                Exit
              </th>
              <th
                onClick={() => handleSort('pnl')}
                className="cursor-pointer px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider
                           text-gray-500 dark:text-gray-400"
              >
                PnL <SortIcon field="pnl" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {paginatedTrades.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                  No trades found
                </td>
              </tr>
            ) : (
              paginatedTrades.map((trade, index) => {
                const action = formatAction(trade.action);
                return (
                  <tr
                    key={trade.id}
                    className={`transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50
                               ${index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50/50 dark:bg-gray-900/20'}`}
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900 dark:text-white">
                      {formatTimestamp(trade.timestamp)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs
                                       font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                        {trade.agent_name}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm">
                      <span className={`font-medium ${action.color}`}>
                        {action.text}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      {trade.entry_price ? `$${trade.entry_price.toFixed(2)}` : '-'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                      {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '-'}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm">
                      <span className={trade.pnl > 0 ? 'text-emerald-600' : trade.pnl < 0 ? 'text-red-600' : 'text-gray-600'}>
                        {trade.pnl > 0 ? '+' : ''}{formatPercent(trade.pnl)}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 p-4 dark:border-gray-700">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700
                       disabled:cursor-not-allowed disabled:opacity-50
                       hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Previous
          </button>

          <div className="flex items-center gap-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors
                          ${currentPage === page
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700'
                  }`}
              >
                {page}
              </button>
            ))}
          </div>

          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700
                       disabled:cursor-not-allowed disabled:opacity-50
                       hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default TradeHistoryTable;
