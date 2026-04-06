/**
 * BattleMonitor Component
 * 에이전트 배틀 실시간 모니터링 컴포넌트
 */

import React, { useMemo } from 'react';
import type { BattleStep, AgentMetrics } from '../types';

interface BattleMonitorProps {
  battleSteps: BattleStep[];
  agents: Record<string, AgentMetrics>;
  maxSteps?: number;
}

interface AgentActionTimelineProps {
  steps: BattleStep[];
  agentName: string;
  agentColor: string;
}

const AGENT_COLORS: Record<string, string> = {
  momentum_hunter: '#3b82f6',
  mean_reverter: '#10b981',
  macro_trader: '#8b5cf6',
  chaos_agent: '#f59e0b',
};

const AGENT_ICONS: Record<string, string> = {
  momentum_hunter: '🔥',
  mean_reverter: '🔄',
  macro_trader: '🌍',
  chaos_agent: '🌀',
};

export const BattleMonitor: React.FC<BattleMonitorProps> = ({
  battleSteps,
  agents,
  maxSteps = 50,
}) => {
  const recentSteps = useMemo(() => {
    return battleSteps.slice(-maxSteps);
  }, [battleSteps, maxSteps]);

  const latestStep = recentSteps[recentSteps.length - 1];

  const formatNumber = (num: number, decimals: number = 2) => {
    return num.toFixed(decimals);
  };

  const getSignalColor = (value: number) => {
    if (value > 0.3) return 'text-emerald-500';
    if (value > 0) return 'text-emerald-400';
    if (value < -0.3) return 'text-red-500';
    if (value < 0) return 'text-red-400';
    return 'text-gray-500';
  };

  const getSignalBg = (value: number) => {
    if (value > 0.3) return 'bg-emerald-500';
    if (value > 0) return 'bg-emerald-400';
    if (value < -0.3) return 'bg-red-500';
    if (value < 0) return 'bg-red-400';
    return 'bg-gray-400';
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-red-500">
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Agent Battle Monitor
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Real-time strategy competition
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-500 dark:text-gray-400">Current Step</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            #{latestStep?.step || 0}
          </p>
        </div>
      </div>

      {/* Current Market State */}
      {latestStep && (
        <div className="mb-6 grid grid-cols-3 gap-4 rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Market Regime</p>
            <p className="text-lg font-semibold capitalize text-gray-900 dark:text-white">
              {latestStep.market_obs.regime}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Price</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">
              ${latestStep.market_obs.close.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Net Signal</p>
            <p className={`text-lg font-semibold ${getSignalColor(latestStep.net_signal)}`}>
              {latestStep.net_signal > 0 ? '+' : ''}{formatNumber(latestStep.net_signal)}
            </p>
          </div>
        </div>
      )}

      {/* Agent Actions */}
      <div className="mb-6">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
          Current Agent Actions
        </h3>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {latestStep && Object.entries(latestStep.agent_actions).map(([name, action]) => (
            <div key={name} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
              <div className="mb-2 flex items-center gap-2">
                <span className="text-lg">{AGENT_ICONS[name] || '🤖'}</span>
                <span className="text-sm font-medium capitalize text-gray-700 dark:text-gray-300">
                  {name.replace(/_/g, ' ')}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`h-2 flex-1 rounded-full bg-gray-200 dark:bg-gray-700`}>
                  <div
                    className={`h-full rounded-full ${getSignalBg(action)}`}
                    style={{ width: `${Math.abs(action) * 100}%`, marginLeft: action < 0 ? 'auto' : 0 }}
                  />
                </div>
                <span className={`text-sm font-semibold ${getSignalColor(action)}`}>
                  {action > 0 ? '+' : ''}{formatNumber(action)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Mini Signal Chart */}
      {recentSteps.length > 1 && (
        <div className="mb-4">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Net Signal History (Last {recentSteps.length} steps)
          </h3>
          <div className="h-32 w-full">
            <svg viewBox="0 0 100 40" className="h-full w-full" preserveAspectRatio="none">
              {/* Grid lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
                <line
                  key={tick}
                  x1="0"
                  x2="100"
                  y1={tick * 40}
                  y2={tick * 40}
                  stroke="currentColor"
                  className="text-gray-200 dark:text-gray-700"
                  strokeWidth="0.2"
                />
              ))}

              {/* Zero line */}
              <line
                x1="0"
                x2="100"
                y1="20"
                y2="20"
                stroke="currentColor"
                className="text-gray-400 dark:text-gray-500"
                strokeWidth="0.3"
                strokeDasharray="2"
              />

              {/* Net Signal Line */}
              <polyline
                fill="none"
                stroke="#3b82f6"
                strokeWidth="0.5"
                points={recentSteps.map((step, i) => {
                  const x = (i / (recentSteps.length - 1)) * 100;
                  const y = 20 - step.net_signal * 18; // Scale to fit
                  return `${x},${y}`;
                }).join(' ')}
              />

              {/* Current point */}
              {latestStep && (
                <circle
                  cx="100"
                  cy={20 - latestStep.net_signal * 18}
                  r="1.5"
                  fill="#3b82f6"
                />
              )}
            </svg>
          </div>
          <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>-1.0</span>
            <span>0</span>
            <span>+1.0</span>
          </div>
        </div>
      )}

      {/* Battle Steps Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                Step
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                Regime
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                Net Signal
              </th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                Price
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {recentSteps.slice(-5).reverse().map((step) => (
              <tr key={step.step} className="bg-white dark:bg-gray-800">
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300">
                  #{step.step}
                </td>
                <td className="px-3 py-2 capitalize text-gray-700 dark:text-gray-300">
                  {step.market_obs.regime}
                </td>
                <td className={`px-3 py-2 text-right font-medium ${getSignalColor(step.net_signal)}`}>
                  {step.net_signal > 0 ? '+' : ''}{formatNumber(step.net_signal)}
                </td>
                <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                  ${step.market_obs.close.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default BattleMonitor;
