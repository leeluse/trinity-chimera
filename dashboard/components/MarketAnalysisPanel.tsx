/**
 * MarketAnalysisPanel Component
 * Phase 3: 실시간 시장 분석 패널
 */

import React from 'react';
import type { MarketAnalysis, MarketRegime } from '../types';

interface MarketAnalysisPanelProps {
  analysis: MarketAnalysis | null;
}

const regimeIcons: Record<MarketRegime, string> = {
  bull: '🐂',
  bear: '🐻',
  sideways: '📊',
  volatile: '🌊',
  unknown: '❓',
};

const regimeColors: Record<MarketRegime, { bg: string; text: string; border: string }> = {
  bull: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  bear: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  sideways: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
  volatile: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  unknown: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
};

const sentimentIcons: Record<string, string> = {
  bullish: '📈',
  bearish: '📉',
  neutral: '➡️',
};

export const MarketAnalysisPanel: React.FC<MarketAnalysisPanelProps> = ({ analysis }) => {
  if (!analysis) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex h-48 items-center justify-center text-gray-500 dark:text-gray-400">
          Waiting for market analysis data...
        </div>
      </div>
    );
  }

  const regime = analysis.regime as MarketRegime;
  const regimeStyle = regimeColors[regime] || regimeColors.unknown;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500">
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">
              Market Analysis
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Phase 3 AI-Powered Analysis
            </p>
          </div>
        </div>
        <div className={`rounded-lg border px-4 py-2 ${regimeStyle.bg} ${regimeStyle.border}`}>
          <span className="text-lg">{regimeIcons[regime]}</span>
          <span className={`ml-2 font-semibold capitalize ${regimeStyle.text}`}>
            {regime} Market
          </span>
        </div>
      </div>

      {/* 주요 메트릭 */}
      <div className="mb-6 grid grid-cols-4 gap-4">
        <MetricCard
          title="Volatility"
          value={`${(analysis.volatility * 100).toFixed(2)}%`}
          color={analysis.volatility > 0.3 ? 'text-red-500' : analysis.volatility > 0.15 ? 'text-yellow-500' : 'text-emerald-500'}
        />
        <MetricCard
          title="Trend Strength"
          value={`${(analysis.trend_strength * 100).toFixed(1)}%`}
          color={analysis.trend_strength > 0.7 ? 'text-emerald-500' : 'text-gray-500'}
        />
        <MetricCard
          title="Sentiment"
          value={`${sentimentIcons[analysis.sentiment] || '➡️'} ${analysis.sentiment}`}
          color={
            analysis.sentiment === 'bullish' ? 'text-emerald-500' :
            analysis.sentiment === 'bearish' ? 'text-red-500' : 'text-gray-500'
          }
        />
        <MetricCard
          title="Regime"
          value={regime}
          color={`${regimeStyle.text}`}
        />
      </div>

      {/* Key Levels */}
      <div className="mb-6 rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
          Key Levels
        </h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">Support</p>
            <div className="flex flex-wrap gap-2">
              {analysis.key_levels.support.map((level, i) => (
                <span key={i} className="rounded bg-blue-100 px-2 py-1 text-sm font-medium text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                  ${level.toLocaleString()}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs text-gray-500 dark:text-gray-400">Resistance</p>
            <div className="flex flex-wrap gap-2">
              {analysis.key_levels.resistance.map((level, i) => (
                <span key={i} className="rounded bg-red-100 px-2 py-1 text-sm font-medium text-red-700 dark:bg-red-900 dark:text-red-300">
                  ${level.toLocaleString()}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Correlation Matrix Preview */}
      {Object.keys(analysis.correlation_matrix).length > 0 && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
            Agent Correlation Matrix
          </h3>
          <CorrelationMatrix data={analysis.correlation_matrix} />
        </div>
      )}
    </div>
  );
};

interface MetricCardProps {
  title: string;
  value: string;
  color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, color }) => (
  <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700/50">
    <p className="mb-1 text-xs text-gray-500 dark:text-gray-400">{title}</p>
    <p className={`text-lg font-semibold ${color}`}>{value}</p>
  </div>
);

interface CorrelationMatrixProps {
  data: Record<string, Record<string, number>>;
}

const CorrelationMatrix: React.FC<CorrelationMatrixProps> = ({ data }) => {
  const agents = Object.keys(data);

  const getCorrelationColor = (value: number) => {
    if (value > 0.7) return 'bg-emerald-500';
    if (value > 0.3) return 'bg-emerald-300';
    if (value > -0.3) return 'bg-gray-300';
    if (value > -0.7) return 'bg-red-300';
    return 'bg-red-500';
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="p-2"></th>
            {agents.map((agent) => (
              <th key={agent} className="p-2 text-xs font-medium text-gray-500 dark:text-gray-400">
                {agent.slice(0, 4)}..
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {agents.map((agent1) => (
            <tr key={agent1}>
              <td className="p-2 text-xs font-medium text-gray-700 dark:text-gray-300">
                {agent1.slice(0, 8)}..
              </td>
              {agents.map((agent2) => {
                const value = data[agent1][agent2];
                return (
                  <td key={agent2} className="p-2">
                    <div
                      className={`h-6 w-full rounded ${getCorrelationColor(value)} relative`}
                      title={`${agent1} ↔ ${agent2}: ${value.toFixed(2)}`}
                    >
                      <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white">
                        {value.toFixed(1)}
                      </span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MarketAnalysisPanel;
