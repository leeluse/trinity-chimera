/**
 * AgentPerformanceChart Component
 * 에이전트별 성과 비교 차트
 */

import React, { useState, useMemo } from 'react';
import type { AgentMetrics, MetricType, ChartType } from '../types';

interface AgentPerformanceChartProps {
  agents: AgentMetrics[];
  height?: number;
}

type ViewMode = 'comparison' | 'timeline' | 'radar';

export const AgentPerformanceChart: React.FC<AgentPerformanceChartProps> = ({
  agents,
  height = 300,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('comparison');
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('pnl_7d');
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(
    new Set(agents.map((a) => a.name))
  );

  // SVG 계산
  const svgConfig = useMemo(() => {
    const svgWidth = 700;
    const svgHeight = height;
    const padding = { top: 20, right: 40, bottom: 60, left: 60 };
    const chartWidth = svgWidth - padding.left - padding.right;
    const chartHeight = svgHeight - padding.top - padding.bottom;
    return { svgWidth, svgHeight, padding, chartWidth, chartHeight };
  }, [height]);

  // 필터링된 에이전트
  const filteredAgents = useMemo(() => {
    // 샘플 타임라인 데이터 생성 (실제로는 백엔드에서 제공)
    return agents.map((agent) => ({
      ...agent,
      history: Array.from({ length: 20 }, (_, i) => ({
        day: i,
        pnl: agent.pnl_total * (0.5 + Math.random() * 0.5) * (i / 20),
      })),
    }));
  }, [agents]);

  // 메트릭 레이블
  const metricLabels: Record<MetricType, string> = {
    pnl_24h: 'PnL (24h) %',
    pnl_7d: 'PnL (7d) %',
    pnl_total: 'PnL Total %',
    sharpe: 'Sharpe Ratio',
    win_rate: 'Win Rate %',
    max_drawdown: 'Max Drawdown %',
    allocation: 'Allocation %',
  };

  const agentColors: Record<string, string> = {
    momentum_hunter: '#F97316',
    mean_reverter: '#06B6D4',
    macro_trader: '#8B5CF6',
    chaos_agent: '#EC4899',
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

  // 비교 차트 데이터 계산
  const comparisonData = useMemo(() => {
    const activeAgents = agents.filter((a) => selectedAgents.has(a.name));
    if (!activeAgents.length) return [];

    const values = activeAgents.map((a) => {
      switch (selectedMetric) {
        case 'pnl_24h': return a.pnl_24h;
        case 'pnl_7d': return a.pnl_7d;
        case 'pnl_total': return a.pnl_total;
        case 'sharpe': return a.sharpe;
        case 'win_rate': return a.win_rate * 100;
        case 'max_drawdown': return a.max_drawdown * 100;
        case 'allocation': return a.allocation * 100;
        default: return a.pnl_7d;
      }
    });

    const minValue = Math.min(...values, 0);
    const maxValue = Math.max(...values, 0);
    const range = maxValue - minValue || 1;

    return activeAgents.map((agent, i) => ({
      agent,
      value: values[i],
      x: i,
      color: agentColors[agent.name] || '#6B7280',
    }));
  }, [agents, selectedAgents, selectedMetric]);

  // 비교 차트 SVG 계산
  const { padding, chartWidth, chartHeight, svgWidth, svgHeight } = svgConfig;

  const barScale = comparisonData.length ? chartHeight / (Math.max(...comparisonData.map((d) => Math.abs(d.value))) * 2 || 1) : 1;

  // 포맷 함수
  const formatValue = (value: number, metric: MetricType): string => {
    if (metric === 'sharpe') return value.toFixed(2);
    if (metric === 'win_rate' || metric.includes('drawdown') || metric.includes('allocation') || metric.includes('pnl')) {
      return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
    }
    return value.toFixed(2);
  };

  const getTrendColor = (value: number, metric: MetricType = selectedMetric) => {
    // For metrics where negative is bad
    if (['pnl_24h', 'pnl_7d', 'pnl_total', 'sharpe', 'win_rate'].includes(metric)) {
      return value >= 0 ? '#10B981' : '#EF4444';
    }
    // For max_drawdown where lower is better
    if (metric === 'max_drawdown') {
      return value <= 15 ? '#10B981' : value <= 25 ? '#F59E0B' : '#EF4444';
    }
    return '#6B7280';
  };

  // 레이더 차트 데이터
  const radarMetrics: MetricType[] = ['pnl_7d', 'sharpe', 'win_rate', 'max_drawdown', 'allocation'];
  const radarData = useMemo(() => {
    const activeAgents = agents.filter((a) => selectedAgents.has(a.name));
    const angleStep = (2 * Math.PI) / radarMetrics.length;

    return activeAgents.map((agent) => {
      const values = radarMetrics.map((metric) => {
        switch (metric) {
          case 'pnl_7d': return Math.max(0, Math.min(1, (agent.pnl_7d + 20) / 40));
          case 'sharpe': return Math.max(0, Math.min(1, agent.sharpe / 3));
          case 'win_rate': return agent.win_rate;
          case 'max_drawdown': return Math.max(0, Math.min(1, 1 - agent.max_drawdown / 0.5));
          case 'allocation': return agent.allocation;
          default: return 0.5;
        }
      });

      const points = values.map((v, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const r = v * Math.min(chartWidth, chartHeight) / 2 * 0.8;
        return {
          x: svgConfig.svgWidth / 2 + r * Math.cos(angle),
          y: svgConfig.svgHeight / 2 + r * Math.sin(angle),
        };
      });

      return { agent, values, points };
    });
  }, [agents, selectedAgents, radarMetrics, svgConfig]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Agent Performance
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Compare agent metrics across the portfolio
          </p>
        </div>

        {/* 뷰 모드 선택 */}
        <div className="flex rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
          {(['comparison', 'radar'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors
                        ${viewMode === mode
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* 필터 바 */}
      <div className="mb-4 flex flex-wrap items-center gap-4">
        {viewMode === 'comparison' && (
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600 dark:text-gray-400">Metric:</label>
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value as MetricType)}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm
                         focus:border-blue-500 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              {Object.entries(metricLabels).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
        )}

        {/* 에이전트 토글 */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">Agents:</span>
          {agents.map((agent) => (
            <button
              key={agent.name}
              onClick={() => {
                const newSelected = new Set(selectedAgents);
                if (newSelected.has(agent.name)) {
                  newSelected.delete(agent.name);
                } else {
                  newSelected.add(agent.name);
                }
                setSelectedAgents(newSelected);
              }}
              className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium transition-colors
                        ${selectedAgents.has(agent.name)
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                }`}
            >
              <span>{getAgentIcon(agent.name)}</span>
              <span className="max-w-[60px] truncate">{agent.name.split('_')[0]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 차트 영역 */}
      <div className="overflow-hidden" style={{ height }}>
        {viewMode === 'comparison' && (
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full">
            {/* 그리드 라인 (0축) */}
            <line
              x1={padding.left}
              x2={padding.left + chartWidth}
              y1={padding.top + chartHeight / 2}
              y2={padding.top + chartHeight / 2}
              stroke="#E5E7EB"
              strokeDasharray="4"
              className="dark:stroke-gray-700"
            />

            {/* 바 차트 */}
            {comparisonData.map((d, i) => {
              const barWidth = chartWidth / comparisonData.length * 0.6;
              const barX = padding.left + (i + 0.5) * (chartWidth / comparisonData.length) - barWidth / 2;
              const isPositive = d.value >= 0;
              const barHeight = Math.abs(d.value) * barScale * chartHeight / 2 / (Math.max(comparisonData.map(x => Math.abs(x.value))) || 1);
              const barY = isPositive
                ? padding.top + chartHeight / 2 - barHeight
                : padding.top + chartHeight / 2;

              return (
                <g key={d.agent.name}>
                  {/* 바 */}
                  <rect
                    x={barX}
                    y={barY}
                    width={barWidth}
                    height={barHeight || 1}
                    fill={d.color}
                    rx={4}
                    opacity={selectedAgents.has(d.agent.name) ? 1 : 0.3}
                  />
                  {/* 값 라벨 */}
                  <text
                    x={barX + barWidth / 2}
                    y={isPositive ? barY - 8 : barY + barHeight + 16}
                    textAnchor="middle"
                    className="text-xs fill-gray-700 dark:fill-gray-300"
                    style={{ fontSize: '10px' }}
                  >
                    {formatValue(d.value, selectedMetric)}
                  </text>
                  {/* 에이전트 라벨 */}
                  <text
                    x={barX + barWidth / 2}
                    y={padding.top + chartHeight + 15}
                    textAnchor="middle"
                    transform={`rotate(-30, ${barX + barWidth / 2}, ${padding.top + chartHeight + 15})`}
                    className="text-xs fill-gray-500 dark:fill-gray-400"
                  >
                    {getAgentIcon(d.agent.name)} {d.agent.name.split('_')[0]}
                  </text>
                </g>
              );
            })}

            {/* Y축 라벨 */}
            <text
              x={10}
              y={padding.top + 10}
              className="text-xs fill-gray-400"
            >
              {metricLabels[selectedMetric]}
            </text>
          </svg>
        )}

        {viewMode === 'radar' && (
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full">
            {/* 배경 원 */}
            {[0.2, 0.4, 0.6, 0.8, 1].map((ratio) => (
              <circle
                key={ratio}
                cx={svgWidth / 2}
                cy={svgHeight / 2}
                r={Math.min(chartWidth, chartHeight) / 2 * 0.8 * ratio}
                fill="none"
                stroke="#E5E7EB"
                strokeDasharray="2"
                className="dark:stroke-gray-700"
              />
            ))}

            {/* 축선 */}
            {radarMetrics.map((metric, i) => {
              const angle = i * ((2 * Math.PI) / radarMetrics.length) - Math.PI / 2;
              const r = Math.min(chartWidth, chartHeight) / 2 * 0.8;
              const x2 = svgWidth / 2 + r * Math.cos(angle);
              const y2 = svgHeight / 2 + r * Math.sin(angle);

              return (
                <g key={metric}>
                  <line
                    x1={svgWidth / 2}
                    y1={svgHeight / 2}
                    x2={x2}
                    y2={y2}
                    stroke="#E5E7EB"
                    className="dark:stroke-gray-700"
                  />
                  <text
                    x={x2 + Math.cos(angle) * 20}
                    y={y2 + Math.sin(angle) * 20}
                    textAnchor="middle"
                    alignmentBaseline="middle"
                    className="text-xs fill-gray-500 dark:fill-gray-400"
                  >
                    {metricLabels[metric].split(' ')[0]}
                  </text>
                </g>
              );
            })}

            {/* 에이전트 데이터 */}
            {radarData.map(({ agent, points }, agentIndex) => {
              if (!selectedAgents.has(agent.name)) return null;

              const color = agentColors[agent.name] || '#6B7280';
              const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ') + ' Z';

              return (
                <g key={agent.name}>
                  <path
                    d={pathD}
                    fill={color}
                    fillOpacity={0.1}
                    stroke={color}
                    strokeWidth={2}
                  />
                  {points.map((p, i) => (
                    <circle
                      key={i}
                      cx={p.x}
                      cy={p.y}
                      r={3}
                      fill={color}
                    />
                  ))}
                </g>
              );
            })}
          </svg>
        )}
      </div>

      {/* 범례 */}
      <div className="mt-4 flex flex-wrap justify-center gap-4">
        {agents
          .filter((a) => selectedAgents.has(a.name))
          .map((agent) => (
            <div key={agent.name} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: agentColors[agent.name] || '#6B7280' }}
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {getAgentIcon(agent.name)} {agent.name.replace(/_/g, ' ')}
              </span>
            </div>
          ))}
      </div>

      {/* 통계 요약 */}
      <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
        {selectedMetric !== 'allocation' && (
          <>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Best</p>
              <p className={`font-medium ${
                comparisonData.length && comparisonData.reduce((max, d) => d.value > max.value ? d : max, comparisonData[0])?.value >= 0
                  ? 'text-emerald-600' : 'text-red-600'
              }`}>
                {comparisonData.length
                  ? formatValue(comparisonData.reduce((max, d) => d.value > max.value ? d : max, comparisonData[0]).value, selectedMetric)
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Worst</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {comparisonData.length
                  ? formatValue(comparisonData.reduce((min, d) => d.value < min.value ? d : min, comparisonData[0]).value, selectedMetric)
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Average</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {comparisonData.length
                  ? formatValue(comparisonData.reduce((sum, d) => sum + d.value, 0) / comparisonData.length, selectedMetric)
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 dark:text-gray-400">Active</p>
              <p className="font-medium text-gray-900 dark:text-white">
                {selectedAgents.size}/{agents.length}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AgentPerformanceChart;
