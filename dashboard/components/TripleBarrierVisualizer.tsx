/**
 * TripleBarrierVisualizer Component
 * Triple Barrier 레이블링 결과 시각화
 * - 레이블 분포 차트
 * - 샘플 가중치 분포
 * - 레이블 타임라인
 * - 메타라벨 품질 지표
 */

import React, { useState, useMemo } from 'react';

// Triple Barrier 레이블 타입
export type TripleBarrierLabel = -1 | 0 | 1; // -1: Sell, 0: Hold/No Decision, 1: Buy
export type MetaLabel = 'take_profit' | 'stop_loss' | 'touch_vertical' | 'no_hit';

interface TripleBarrierData {
  timestamp: string;
  close: number;
  label: TripleBarrierLabel;
  meta_label: MetaLabel;
  sample_weight: number;
  profit_taking?: number; // 수익실현 배리어
  stop_loss?: number;     // 손절 배리어
  vertical_barrier?: string; // 수직 배리어 시간
  is_touched?: boolean;   // 배리어 터치 여부
}

interface TripleBarrierStats {
  total_samples: number;
  buy_count: number;
  sell_count: number;
  hold_count: number;
  avg_sample_weight: number;
  touched_barriers: number;
  quality_score: number; // 레이블 품질 점수 (0-1)
}

interface TripleBarrierVisualizerProps {
  data: TripleBarrierData[];
  stats?: TripleBarrierStats;
  height?: number;
}

type ViewMode = 'distribution' | 'timeline' | 'weights' | 'detail';

export const TripleBarrierVisualizer: React.FC<TripleBarrierVisualizerProps> = ({
  data,
  stats,
  height = 300,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('distribution');
  const [selectedLabel, setSelectedLabel] = useState<TripleBarrierLabel | null>(null);

  // 샘플 데이터 (실제로는 props로 전달)
  const sampleData: TripleBarrierData[] = useMemo(() => {
    const labels: TripleBarrierLabel[] = [1, 0, -1];
    const metaLabels: MetaLabel[] = ['take_profit', 'stop_loss', 'touch_vertical', 'no_hit'];

    return Array.from({ length: 100 }, (_, i) => ({
      timestamp: new Date(Date.now() - (100 - i) * 3600000).toISOString(),
      close: 45000 + Math.random() * 5000,
      label: labels[Math.floor(Math.random() * 3)],
      meta_label: metaLabels[Math.floor(Math.random() * 4)],
      sample_weight: 0.5 + Math.random() * 0.5,
      profit_taking: 0.02,
      stop_loss: -0.01,
      vertical_barrier: new Date(Date.now() - (100 - i) * 3600000 + 86400000).toISOString(),
      is_touched: Math.random() > 0.3,
    }));
  }, []);

  const displayData = data.length > 0 ? data : sampleData;

  // 통계 계산
  const computedStats = useMemo<TripleBarrierStats>(() => {
    const total = displayData.length;
    const buy = displayData.filter((d) => d.label === 1).length;
    const sell = displayData.filter((d) => d.label === -1).length;
    const hold = total - buy - sell;
    const avgWeight = displayData.reduce((sum, d) => sum + d.sample_weight, 0) / total;
    const touched = displayData.filter((d) => d.is_touched).length;

    // 품질 점수: 가중치 분포 균일성 + 터치 비율
    const weightVariance = displayData.reduce((sum, d) =>
      sum + Math.pow(d.sample_weight - avgWeight, 2), 0
    ) / total;
    const touchRate = touched / total;
    const quality = Math.min(1, (1 - weightVariance) * 0.5 + touchRate * 0.5);

    return {
      total_samples: total,
      buy_count: buy,
      sell_count: sell,
      hold_count: hold,
      avg_sample_weight: avgWeight,
      touched_barriers: touched,
      quality_score: quality,
    };
  }, [displayData]);

  const displayStats = stats || computedStats;

  // SV
  // 색상 정의
  const labelColors: Record<TripleBarrierLabel, string> = {
    1: '#10B981',   // Buy - emerald
    0: '#6B7280',   // Hold - gray
    '-1': '#EF4444' // Sell - red
  };

  const labelNames: Record<TripleBarrierLabel, string> = {
    1: 'Buy',
    0: 'Hold',
    '-1': 'Sell'
  };

  const metaLabelColors: Record<MetaLabel, string> = {
    'take_profit': '#059669',
    'stop_loss': '#DC2626',
    'touch_vertical': '#D97706',
    'no_hit': '#6B7280'
  };

  const metaLabelNames: Record<MetaLabel, string> = {
    'take_profit': 'Take Profit',
    'stop_loss': 'Stop Loss',
    'touch_vertical': 'Time Barrier',
    'no_hit': 'No Hit'
  };

  // 필터링된 데이터
  const filteredData = useMemo(() => {
    if (selectedLabel === null) return displayData;
    return displayData.filter((d) => d.label === selectedLabel);
  }, [displayData, selectedLabel]);

  // SVG 계산
  const svgConfig = useMemo(() => {
    const svgWidth = 700;
    const svgHeight = height;
    const padding = { top: 20, right: 40, bottom: 60, left: 60 };
    const chartWidth = svgWidth - padding.left - padding.right;
    const chartHeight = svgHeight - padding.top - padding.bottom;
    return { svgWidth, svgHeight, padding, chartWidth, chartHeight };
  }, [height]);

  const { svgWidth, svgHeight, padding, chartWidth, chartHeight } = svgConfig;

  // 분포 데이터
  const distributionData = useMemo(() => {
    const total = displayStats.total_samples;
    return [
      { label: 1 as TripleBarrierLabel, count: displayStats.buy_count, percent: (displayStats.buy_count / total) * 100 },
      { label: 0 as TripleBarrierLabel, count: displayStats.hold_count, percent: (displayStats.hold_count / total) * 100 },
      { label: -1 as TripleBarrierLabel, count: displayStats.sell_count, percent: (displayStats.sell_count / total) * 100 },
    ];
  }, [displayStats]);

  // 타임라인 데이터
  const timelineData = useMemo(() => {
    const minTime = Math.min(...displayData.map((d) => new Date(d.timestamp).getTime()));
    const maxTime = Math.max(...displayData.map((d) => new Date(d.timestamp).getTime()));
    const timeRange = maxTime - minTime || 1;

    return displayData.map((d, i) => ({
      ...d,
      x: padding.left + ((new Date(d.timestamp).getTime() - minTime) / timeRange) * chartWidth,
      y: padding.top + (1 - (d.close - 40000) / 15000) * chartHeight,
    }));
  }, [displayData, padding.left, chartWidth, chartHeight]);

  // 가중치 히스토그램 데이터
  const weightBins = useMemo(() => {
    const bins = [
      { range: '0.0-0.2', min: 0, max: 0.2, count: 0, color: '#FEE2E2' },
      { range: '0.2-0.4', min: 0.2, max: 0.4, count: 0, color: '#FED7AA' },
      { range: '0.4-0.6', min: 0.4, max: 0.6, count: 0, color: '#FEF3C7' },
      { range: '0.6-0.8', min: 0.6, max: 0.8, count: 0, color: '#D1FAE5' },
      { range: '0.8-1.0', min: 0.8, max: 1.0, count: 0, color: '#A7F3D0' },
    ];

    displayData.forEach((d) => {
      const bin = bins.find((b) => d.sample_weight >= b.min && d.sample_weight < b.max) || bins[4];
      bin.count++;
    });

    const maxCount = Math.max(...bins.map((b) => b.count));
    return bins.map((b) => ({ ...b, height: (b.count / maxCount) * chartHeight }));
  }, [displayData, chartHeight]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  const formatPercent = (value: number) => `${value.toFixed(1)}%`;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Triple Barrier Labeling
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Financial sample labeling with meta-labeling
          </p>
        </div>

        {/* 품질 점수 */}
        <div className="flex items-center gap-2 rounded-lg bg-gray-100 px-4 py-2 dark:bg-gray-700">
          <span className="text-sm text-gray-600 dark:text-gray-400">Quality Score:</span>
          <span className={`text-lg font-bold ${
            displayStats.quality_score >= 0.8 ? 'text-emerald-500' :
            displayStats.quality_score >= 0.6 ? 'text-yellow-500' : 'text-red-500'
          }`}>
            {(displayStats.quality_score * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* 뷰 모드 선택 */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
          {(['distribution', 'timeline', 'weights', 'detail'] as ViewMode[]).map((mode) => (
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

        {/* 레이블 필터 */}
        {viewMode !== 'distribution' && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Filter:</span>
            {([1, 0, -1] as TripleBarrierLabel[]).map((label) => (
              <button
                key={label}
                onClick={() => setSelectedLabel(selectedLabel === label ? null : label)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors
                          ${selectedLabel === label
                    ? 'bg-gray-800 text-white dark:bg-white dark:text-gray-900'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300'
                  }`}
                style={{ backgroundColor: selectedLabel === label ? labelColors[label] : undefined }}
              >
                {labelNames[label]}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 차트 영역 */}
      <div className="overflow-hidden" style={{ height }}>
        {viewMode === 'distribution' && (
          <div className="h-full p-4">
            <div className="flex h-full items-end justify-around gap-8">
              {distributionData.map((item) => (
                <div key={item.label} className="flex flex-col items-center">
                  <div className="mb-2 text-center">
                    <p className="text-2xl font-bold" style={{ color: labelColors[item.label] }}>
                      {item.count}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {formatPercent(item.percent)}
                    </p>
                  </div>
                  <div className="relative w-20 overflow-hidden rounded-t-lg bg-gray-200 dark:bg-gray-700">
                    <div
                      className="w-full rounded-t-lg transition-all duration-500"
                      style={{
                        height: `${item.percent * 2}px`,
                        backgroundColor: labelColors[item.label],
                        minHeight: '20px',
                        maxHeight: '200px',
                      }}
                    />
                  </div>
                  <p className="mt-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                    {labelNames[item.label]}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {viewMode === 'timeline' && (
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full">
            {/* 가격 라인 */}
            <polyline
              fill="none"
              stroke="#6B7280"
              strokeWidth={1}
              points={timelineData.map((d) => `${d.x},${d.y}`).join(' ')}
              opacity={0.3}
            />

            {/* 레이블 포인트 */}
            {timelineData.map((d, i) => {
              const isHighlighted = selectedLabel === null || d.label === selectedLabel;
              return (
                <g key={i}>
                  <circle
                    cx={d.x}
                    cy={d.y}
                    r={isHighlighted ? 5 : 3}
                    fill={labelColors[d.label]}
                    opacity={isHighlighted ? 1 : 0.3}
                  />
                  {/* 메타라벨 표시 */}
                  {d.is_touched && (
                    <circle
                      cx={d.x}
                      cy={d.y}
                      r={8}
                      fill="none"
                      stroke={metaLabelColors[d.meta_label]}
                      strokeWidth={1}
                      opacity={isHighlighted ? 0.5 : 0.1}
                    />
                  )}
                </g>
              );
            })}

            {/* X축 라벨 */}
            {timelineData
              .filter((_, i) => i % Math.ceil(timelineData.length / 5) === 0)
              .map((d) => (
                <text
                  key={d.timestamp}
                  x={d.x}
                  y={svgHeight - 10}
                  textAnchor="middle"
                  className="fill-gray-400 text-xs"
                >
                  {formatTime(d.timestamp)}
                </text>
              ))}
          </svg>
        )}

        {viewMode === 'weights' && (
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full">
            {weightBins.map((bin, i) => {
              const barWidth = chartWidth / weightBins.length * 0.8;
              const barX = padding.left + i * (chartWidth / weightBins.length) + barWidth * 0.1;

              return (
                <g key={bin.range}>
                  {/* 바 */}
                  <rect
                    x={barX}
                    y={padding.top + chartHeight - bin.height}
                    width={barWidth}
                    height={bin.height}
                    fill={bin.color}
                    rx={4}
                  />
                  {/* 카운트 */}
                  <text
                    x={barX + barWidth / 2}
                    y={padding.top + chartHeight - bin.height - 5}
                    textAnchor="middle"
                    className="fill-gray-700 text-xs"
                  >
                    {bin.count}
                  </text>
                  {/* 범위 라벨 */}
                  <text
                    x={barX + barWidth / 2}
                    y={svgHeight - 10}
                    textAnchor="middle"
                    className="fill-gray-500 text-xs"
                  >
                    {bin.range}
                  </text>
                </g>
              );
            })}
          </svg>
        )}

        {viewMode === 'detail' && (
          <div className="h-full overflow-auto p-2">
            <div className="space-y-1">
              {filteredData.slice(-20).reverse().map((d, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-gray-100 p-2 dark:border-gray-700"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: labelColors[d.label] }}
                    />
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {formatTime(d.timestamp)}
                    </span>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      ${d.close.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs"
                      style={{
                        backgroundColor: `${metaLabelColors[d.meta_label]}20`,
                        color: metaLabelColors[d.meta_label],
                      }}
                    >
                      {metaLabelNames[d.meta_label]}
                    </span>
                    <span className="text-xs text-gray-500">
                      w: {d.sample_weight.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 범례 */}
      <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-700">
        {viewMode === 'distribution' && (
          <div className="flex flex-wrap justify-center gap-4">
            {([1, 0, -1] as TripleBarrierLabel[]).map((label) => (
              <div key={label} className="flex items-center gap-2">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: labelColors[label] }}
                />
                <span className="text-xs text-gray-600 dark:text-gray-400">
                  {labelNames[label]}: {distributionData.find((d) => d.label === label)?.count}
                </span>
              </div>
            ))}
          </div>
        )}

        {viewMode === 'timeline' && (
          <div className="flex flex-wrap justify-center gap-4">
            {(Object.keys(metaLabelNames) as MetaLabel[]).map((meta) => (
              <div key={meta} className="flex items-center gap-2">
                <div
                  className="h-3 w-3 rounded"
                  style={{ backgroundColor: metaLabelColors[meta] }}
                />
                <span className="text-xs text-gray-600 dark:text-gray-400">
                  {metaLabelNames[meta]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 통계 요약 */}
      <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Total Samples</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {displayStats.total_samples}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Buy Ratio</p>
          <p className="font-semibold text-emerald-500">
            {formatPercent(displayStats.buy_count / displayStats.total_samples)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Sell Ratio</p>
          <p className="font-semibold text-red-500">
            {formatPercent(displayStats.sell_count / displayStats.total_samples)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Avg Weight</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {displayStats.avg_sample_weight.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
};

export default TripleBarrierVisualizer;
