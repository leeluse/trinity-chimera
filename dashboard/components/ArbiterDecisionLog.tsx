/**
 * ArbiterDecisionLog Component
 * LLM Arbiter 재배분 결정 로그 뷰어
 */

import React, { useState } from 'react';
import type { ArbiterDecision } from '../types';

interface ArbiterDecisionLogProps {
  decisions: ArbiterDecision[];
  maxEntries?: number;
  showReasoning?: boolean;
}

export const ArbiterDecisionLog: React.FC<ArbiterDecisionLogProps> = ({
  decisions,
  maxEntries = 10,
  showReasoning = true,
}) => {
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);

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

  const formatTimeAgo = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  const getChangeColor = (delta: number) => {
    if (delta > 0) return 'text-emerald-600 dark:text-emerald-400';
    if (delta < 0) return 'text-red-600 dark:text-red-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  const getChangeIcon = (delta: number) => {
    if (delta > 0) return '▲';
    if (delta < 0) return '▼';
    return '•';
  };

  const getAgentIcon = (name: string) => {
    const icons: Record<string, string> = {
      momentum_hunter: '🔥',
      mean_reverter: '🔄',
      macro_trader: '🌍',
      chaos_agent: '🌀',
    };
    return icons[name.toLowerCase()] || '🤖';
  };

  const displayedDecisions = decisions.slice(0, maxEntries);

  return (
    <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="border-b border-gray-200 p-4 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 to-pink-500">
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548 5.478a1 1 0 01-.994.905h-4.164a1 1 0 01-.994-.905L7.3 14.645z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Arbiter Decisions
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              AI-driven capital reallocation log
            </p>
          </div>
        </div>
      </div>

      {/* 결정 목록 */}
      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {displayedDecisions.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
            No decisions recorded yet
          </div>
        ) : (
          displayedDecisions.map((decision, index) => {
            const isExpanded = expandedEntry === decision.timestamp;
            const agents = Object.keys(decision.old_allocations).sort();

            return (
              <div
                key={decision.timestamp}
                className={`transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50
                           ${isExpanded ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}
              >
                {/* 요약 행 */}
                <div
                  onClick={() => setExpandedEntry(isExpanded ? null : decision.timestamp)}
                  className="cursor-pointer px-4 py-3"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-xs
                                       font-medium text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                        #{displayedDecisions.length - index}
                      </span>
                      <div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          Reallocation Executed
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {formatTimestamp(decision.timestamp)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {formatTimeAgo(decision.timestamp)}
                      </span>
                      <svg
                        className={`h-4 w-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>

                  {/* Allocation Changes Preview */}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {agents.slice(0, 4).map((agent) => {
                      const oldPct = decision.old_allocations[agent] * 100;
                      const newPct = decision.new_allocations[agent] * 100;
                      const delta = newPct - oldPct;
                      if (Math.abs(delta) < 0.1) return null;

                      return (
                        <span
                          key={agent}
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs
                                     ${delta > 0
                              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                              : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            }`}
                        >
                          {getAgentIcon(agent)} {agent.replace(/_/g, ' ')}
                          <span className={getChangeColor(delta)}>
                            {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                          </span>
                        </span>
                      );
                    })}
                    {agents.length > 4 && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        +{agents.length - 4} more
                      </span>
                    )}
                  </div>
                </div>

                {/* 확장 상세 정보 */}
                {isExpanded && (
                  <div className="border-t border-gray-100 bg-gray-50/50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900/30">
                    {/* Reasoning */}
                    {showReasoning && decision.reasoning && (
                      <div className="mb-4">
                        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                          Reasoning
                        </h4>
                        <p className="text-sm text-gray-700 dark:text-gray-300">
                          {decision.reasoning}
                        </p>
                      </div>
                    )}

                    {/* Allocation Changes Table */}
                    <div className="mb-4">
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
                        Allocation Changes
                      </h4>
                      <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-100 dark:bg-gray-800">
                            <tr>
                              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                                Agent
                              </th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                                Before
                              </th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                                After
                              </th>
                              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                                Δ
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                            {agents.map((agent) => {
                              const oldPct = decision.old_allocations[agent] * 100;
                              const newPct = (decision.new_allocations[agent] || 0) * 100;
                              const delta = newPct - oldPct;

                              return (
                                <tr key={agent} className="bg-white dark:bg-gray-800">
                                  <td className="px-3 py-2">
                                    <div className="flex items-center gap-2">
                                      <span>{getAgentIcon(agent)}</span>
                                      <span className="capitalize text-gray-900 dark:text-white">
                                        {agent.replace(/_/g, ' ')}
                                      </span>
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-400">
                                    {oldPct.toFixed(1)}%
                                  </td>
                                  <td className="px-3 py-2 text-right">
                                    <span className={`font-medium ${
                                      newPct > oldPct ? 'text-emerald-600' : newPct < oldPct ? 'text-red-600' : 'text-gray-600'
                                    } dark:text-gray-300`}>
                                      {newPct.toFixed(1)}%
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 text-right">
                                    <span className={`font-medium ${getChangeColor(delta)}`}>
                                      {getChangeIcon(delta)} {Math.abs(delta).toFixed(1)}%
                                    </span>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Warnings */}
                    {decision.warnings && decision.warnings.length > 0 && (
                      <div>
                        <h4 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-600">
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          Warnings
                        </h4>
                        <ul className="space-y-1">
                          {decision.warnings.map((warning, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-300">
                              <span className="mt-1">•</span>
                              <span>{warning}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 푸터 */}
      {decisions.length > maxEntries && (
        <div className="border-t border-gray-200 p-3 text-center dark:border-gray-700">
          <button className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400
                           dark:hover:text-blue-300">
            View all {decisions.length} decisions
          </button>
        </div>
      )}
    </div>
  );
};

export default ArbiterDecisionLog;
