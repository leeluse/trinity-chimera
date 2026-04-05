/**
 * HMMRegimeVisualizer Component
 * HMM Regime 분류 결과 시각화
 * - Regime 전환 타임라인
 * - Regime별 성과 비교
 * - 예측 정확도 모니터링
 */

import React, { useState, useMemo } from 'react';
import type { MarketRegime } from '../types';

interface RegimeData {
  timestamp: string;
  regime: MarketRegime;
  confidence: number;
  duration?: number; // 해당 regime 지속 시간 (시간)
}

interface RegimePerformance {
  regime: MarketRegime;
  avgReturn: number;
  volatility: number;
  frequency: number; // 현재까지 등장 횟수
  avgDuration: number; // 평균 지속 시간
}

interface HMMRegimeVisualizerProps {
  regimeHistory: RegimeData[];
  performance?: RegimePerformance[];
  predictions?: {
    timestamp: string;
    predicted: MarketRegime;
    actual: MarketRegime;
    confidence: number;
  }[];
  height?: number;
}

type ViewMode = 'timeline' | 'distribution' | 'accuracy';

export const HMMRegimeVisualizer: React.FC<HMMRegimeVisualizerProps> = ({
  regimeHistory,
  performance,
  predictions,
  height = 300,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('timeline');
  const [selectedTimeRange, setSelectedTimeRange] = useState<'24h' | '7d' | '30d' | 'all'>('7d');

  // Regime 색상 정의
  const regimeColors: Record<MarketRegime, string> = {
    bull: '#10B981',      // emerald-500
    bear: '#EF4444',      // red-500
    sideways: '#F59E0B',  // amber-500
    volatile: '#8B5CF6',  // violet-500
    unknown: '#6B7280',   // gray-500
  };

  const regimeLabels: Record<MarketRegime, string> = {
    bull: 'Bull Market',
    bear: 'Bear Market',
    sideways: 'Sideways',
    volatile: 'Volatile',
    unknown: 'Unknown',
  };

  const regimeIcons: Record<MarketRegime, string> = {
    bull: '📈',
    bear: '📉',
    sideways: '➡️',
    volatile: '📊',
    unknown: '❓',
  };

  // 샘플 데이터 (실제로는 props로 전달)
  const sampleRegimeData: RegimeData[] = useMemo(() => {
    const regimes: MarketRegime[] = ['bull', 'sideways', 'bear', 'volatile', 'bull'];
    return Array.from({ length: 50 }, (_, i) => ({
      timestamp: new Date(Date.now() - (50 - i) * 3600000).toISOString(),
      regime: regimes[Math.floor(i / 10)],
      confidence: 0.7 + Math.random() * 0.25,
      duration: Math.floor(Math.random() * 12) + 4,
    }));
  }, []);

  const data = regimeHistory.length > 0 ? regimeHistory : sampleRegimeData;

  // 시간 필터링
  const filteredData = useMemo(() => {
    const now = new Date();
    let cutoff: Date;

    switch (selectedTimeRange) {
      case '24h':
        cutoff = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        break;
      case '7d':
        cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case '30d':
        cutoff = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      default:
        cutoff = new Date(0);
    }

    return data.filter((d) => new Date(d.timestamp) >= cutoff);
  }, [data, selectedTimeRange]);

  // 현재 Regime
  const currentRegime = filteredData[filteredData.length - 1]?.regime || 'unknown';
  const currentConfidence = filteredData[filteredData.length - 1]?.confidence || 0;

  // Regime 통계
  const regimeStats = useMemo(() => {
    const stats: Record<MarketRegime, { count: number; totalConfidence: number }> = {
      bull: { count: 0, totalConfidence: 0 },
      bear: { count: 0, totalConfidence: 0 },
      sideways: { count: 0, totalConfidence: 0 },
      volatile: { count: 0, totalConfidence: 0 },
      unknown: { count: 0, totalConfidence: 0 },
    };

    filteredData.forEach((d) => {
      stats[d.regime].count++;
      stats[d.regime].totalConfidence += d.confidence;
    });

    return Object.entries(stats).map(([regime, s]) => ({
      regime: regime as MarketRegime,
      count: s.count,
      percentage: filteredData.length > 0 ? (s.count / filteredData.length) * 100 : 0,
      avgConfidence: s.count > 0 ? s.totalConfidence / s.count : 0,
    }));
  }, [filteredData]);

  // 예측 정확도 계산
  const accuracy = useMemo(() => {
    if (!predictions || predictions.length === 0) return null;

    const correct = predictions.filter((p) => p.predicted === p.actual).length;
    const accuracy = (correct / predictions.length) * 100;

    const byRegime: Record<MarketRegime, { total: number; correct: number }> = {
      bull: { total: 0, correct: 0 },
      bear: { total: 0, correct: 0 },
      sideways: { total: 0, correct: 0 },
      volatile: { total: 0, correct: 0 },
      unknown: { total: 0, correct: 0 },
    };

    predictions.forEach((p) => {
      byRegime[p.actual].total++;
      if (p.predicted === p.actual) {
        byRegime[p.actual].correct++;
      }
    });

    return { overall: accuracy, byRegime };
  }, [predictions]);

  // SVG 계산
  const svgConfig = useMemo(() => {
    const svgWidth = 700;
    const svgHeight = height;
    const padding = { top: 20, right: 40, bottom: 60, left: 80 };
    const chartWidth = svgWidth - padding.left - padding.right;
    const chartHeight = svgHeight - padding.top - padding.bottom;
    return { svgWidth, svgHeight, padding, chartWidth, chartHeight };
  }, [height]);

  const { svgWidth, svgHeight, padding, chartWidth, chartHeight } = svgConfig;

  // 타임라인 차트 계산
  const timelineData = useMemo(() => {
    if (filteredData.length === 0) return [];

    const minTime = Math.min(...filteredData.map((d) => new Date(d.timestamp).getTime()));
    const maxTime = Math.max(...filteredData.map((d) => new Date(d.timestamp).getTime()));
    const timeRange = maxTime - minTime || 1;

    return filteredData.map((d, i) => ({
      ...d,
      x: padding.left + ((new Date(d.timestamp).getTime() - minTime) / timeRange) * chartWidth,
      y: padding.top + chartHeight / 2,
      prevRegime: i > 0 ? filteredData[i - 1].regime : d.regime,
    }));
  }, [filteredData, padding.left, chartWidth, chartHeight]);

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
            HMM Regime Detection
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Hidden Markov Model regime classification
          </p>
        </div>

        {/* 현재 상태 */}
        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-2 rounded-lg px-4 py-2"
            style={{ backgroundColor: `${regimeColors[currentRegime]}20` }}
          >
            <span className="text-2xl">{regimeIcons[currentRegime]}</span>
            <div>
              <p className="text-sm font-medium" style={{ color: regimeColors[currentRegime] }}>
                {regimeLabels[currentRegime]}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Confidence: {(currentConfidence * 100).toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 뷰 모드 선택 */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
          {(['timeline', 'distribution', 'accuracy'] as ViewMode[]).map((mode) => (
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

        {/* 시간 범위 선택 */}
        <div className="flex rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-800">
          {(['24h', '7d', '30d', 'all'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setSelectedTimeRange(range)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors
                        ${selectedTimeRange === range
                  ? 'bg-gray-800 text-white dark:bg-white dark:text-gray-900'
                  : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700'
                }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* 차트 영역 */}
      <div className="overflow-hidden" style={{ height }}>
        {viewMode === 'timeline' && (
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full">
            {/* Y축 라벨 */}
            <text
              x={20}
              y={padding.top + chartHeight / 2}
              textAnchor="middle"
              className="fill-gray-400 text-xs"
              transform={`rotate(-90, 20, ${padding.top + chartHeight / 2})`}
            >
              Regime
            </text>

            {/* Regime 구간 표시 */}
            {(() => {
              const segments: { start: number; end: number; regime: MarketRegime }[] = [];
              let currentStart = 0;
              let currentRegime: MarketRegime = filteredData[0]?.regime || 'unknown';

              timelineData.forEach((d, i) => {
                if (d.regime !== currentRegime || i === timelineData.length - 1) {
                  segments.push({
                    start: timelineData[currentStart].x,
                    end: d.x,
                    regime: currentRegime,
                  });
                  currentStart = i;
                  currentRegime = d.regime;
                }
              });

              return segments.map((seg, i) => (
                <rect
                  key={i}
                  x={seg.start}
                  y={padding.top}
                  width={seg.end - seg.start}
                  height={chartHeight}
                  fill={regimeColors[seg.regime]}
                  opacity={0.1}
                />
              ));
            })()}

            {/* 데이터 포인트 */}
            {timelineData.map((d, i) => (
              <g key={i}>
                {/* Regime 변경 시 선 */}
                {i > 0 && d.regime !== timelineData[i - 1].regime && (
                  <line
                    x1={d.x}
                    y1={padding.top}
                    x2={d.x}
                    y2={padding.top + chartHeight}
                    stroke={regimeColors[d.regime]}
                    strokeDasharray="4"
                    opacity={0.5}
                  />
                )}

                {/* 데이터 포인트 */}
                <circle
                  cx={d.x}
                  cy={d.y}
                  r={6}
                  fill={regimeColors[d.regime]}
                  stroke="white"
                  strokeWidth={2}
                />

                {/* Confidence 링 */}
                <circle
                  cx={d.x}
                  cy={d.y}
                  r={8 + d.confidence * 4}
                  fill="none"
                  stroke={regimeColors[d.regime]}
                  strokeWidth={1}
                  opacity={0.3}
                />
              </g>
            ))}

            {/* Regime 라벨 */}
            {Array.from(new Set(filteredData.map((d) => d.regime))).map((regime, i) => (
              <text
                key={regime}
                x={padding.left - 10}
                y={padding.top + (chartHeight / 5) * i + 20}
                textAnchor="end"
                className="text-xs"
                fill={regimeColors[regime as MarketRegime]}
              >
                {regimeLabels[regime as MarketRegime]}
              </text>
            ))}

            {/* X축 시간 라벨 */}
            {timelineData.filter((_, i) => i % Math.ceil(timelineData.length / 5) === 0).map((d) => (
              <text
                key={d.timestamp}
                x={d.x}
                y={padding.top + chartHeight + 20}
                textAnchor="middle"
                className="fill-gray-400 text-xs"
              >
                {formatTime(d.timestamp)}
              </text>
            ))}
          </svg>
        )}

        {viewMode === 'distribution' && (
          <div className="h-full p-4">
            <div className="space-y-4">
              {regimeStats
                .filter((s) => s.count > 0)
                .sort((a, b) => b.count - a.count)
                .map((stat) => (
                  <div key={stat.regime}>
                    <div className="mb-1 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>{regimeIcons[stat.regime]}</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-white">
                          {regimeLabels[stat.regime]}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-semibold text-gray-900 dark:text-white">
                          {formatPercent(stat.percentage)}
                        </span>
                        <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                          ({stat.count} samples)
                        </span>
                      </div>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${stat.percentage}%`,
                          backgroundColor: regimeColors[stat.regime],
                        }}
                      />
                    </div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Avg Confidence: {(stat.avgConfidence * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {viewMode === 'accuracy' && accuracy && (
          <div className="h-full p-4">
            <div className="mb-4 text-center">
              <p className="text-sm text-gray-500 dark:text-gray-400">Overall Accuracy</p>
              <p className={`text-3xl font-bold ${
                accuracy.overall >= 70 ? 'text-emerald-500' :
                accuracy.overall >= 50 ? 'text-yellow-500' : 'text-red-500'
              }`}>
                {accuracy.overall.toFixed(1)}%
              </p>
            </div>

            <div className="space-y-3">
              {Object.entries(accuracy.byRegime)
                .filter(([_, data]) => data.total > 0)
                .map(([regime, data]) => {
                  const reg = regime as MarketRegime;
                  const regAccuracy = (data.correct / data.total) * 100;

                  return (
                    <div key={regime} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span>{regimeIcons[reg]}</span>
                        <span className="text-sm text-gray-700 dark:text-gray-300">
                          {regimeLabels[reg]}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {data.correct}/{data.total}
                        </span>
                        <span className={`text-sm font-semibold ${
                          regAccuracy >= 70 ? 'text-emerald-500' :
                          regAccuracy >= 50 ? 'text-yellow-500' : 'text-red-500'
                        }`}>
                          {regAccuracy.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>

      {/* 범례 */}
      <div className="mt-4 flex flex-wrap justify-center gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
        {(['bull', 'bear', 'sideways', 'volatile'] as MarketRegime[]).map((regime) => (
          <div key={regime} className="flex items-center gap-2">
            <div
              className="h-3 w-3 rounded-full"
              style={{ backgroundColor: regimeColors[regime] }}
            />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              {regimeIcons[regime]} {regimeLabels[regime]}
            </span>
          </div>
        ))}
      </div>

      {/* 통계 요약 */}
      <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Total Samples</p>
          <p className="font-semibold text-gray-900 dark:text-white">{filteredData.length}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Current Regime</p>
          <p className="font-semibold" style={{ color: regimeColors[currentRegime] }}>
            {regimeIcons[currentRegime]} {currentRegime}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Avg Confidence</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {(filteredData.reduce((sum, d) => sum + d.confidence, 0) / filteredData.length * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Regimes Detected</p>
          <p className="font-semibold text-gray-900 dark:text-white">
            {new Set(filteredData.map((d) => d.regime)).size}
          </p>
        </div>
      </div>
    </div>
  );
};

export default HMMRegimeVisualizer;
