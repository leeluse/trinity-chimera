/**
 * PortfolioValueChart Component
 * 포트폴리오 가치 변화 라인/영역 차트
 */

import React, { useMemo } from 'react';
import type { PortfolioState, TimeRange } from '../types';

interface PortfolioValueChartProps {
  data: PortfolioState[];
  height?: number;
  showGrid?: boolean;
  timeRange?: TimeRange;
}

export const PortfolioValueChart: React.FC<PortfolioValueChartProps> = ({
  data,
  height = 300,
  showGrid = true,
  timeRange = '24h',
}) => {
  // 필터링 및 포맷팅된 데이터
  const chartData = useMemo(() => {
    if (!data.length) return [];

    const now = new Date(data[data.length - 1]?.timestamp || Date.now());
    let cutoff: Date;

    switch (timeRange) {
      case '1h':
        cutoff = new Date(now.getTime() - 60 * 60 * 1000);
        break;
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

    return data
      .filter((d) => new Date(d.timestamp) >= cutoff)
      .map((d, index, arr) => {
        const initial = arr[0]?.total_capital || 100;
        const pnl_pct = initial > 0 ? ((d.total_capital - initial) / initial) * 100 : 0;
        return {
          timestamp: d.timestamp,
          value: d.total_capital,
          pnl: d.total_pnl_total,
          pnl_pct,
          date: new Date(d.timestamp),
        };
      });
  }, [data, timeRange]);

  // SVG 계산
  const { svgWidth, svgHeight, padding, chartWidth, chartHeight } = useMemo(() => {
    const svgWidth = 800;
    const svgHeight = height;
    const padding = { top: 20, right: 40, bottom: 40, left: 60 };
    const chartWidth = svgWidth - padding.left - padding.right;
    const chartHeight = svgHeight - padding.top - padding.bottom;
    return { svgWidth, svgHeight, padding, chartWidth, chartHeight };
  }, [height]);

  // 스케일 계산
  const { xScale, yScale, yScalePercent } = useMemo(() => {
    if (!chartData.length) {
      return { xScale: () => 0, yScale: () => 0, yScalePercent: () => 0 };
    }

    const minTime = Math.min(...chartData.map((d) => d.date.getTime()));
    const maxTime = Math.max(...chartData.map((d) => d.date.getTime()));
    const minValue = Math.min(...chartData.map((d) => d.value));
    const maxValue = Math.max(...chartData.map((d) => d.value));
    const minPnl = Math.min(...chartData.map((d) => d.pnl_pct));
    const maxPnl = Math.max(...chartData.map((d) => d.pnl_pct));

    const valuePadding = (maxValue - minValue) * 0.1 || maxValue * 0.1;
    const pnlPadding = (maxPnl - minPnl) * 0.1 || 1;

    return {
      xScale: (time: number) => {
        if (maxTime === minTime) return padding.left + chartWidth / 2;
        return padding.left + ((time - minTime) / (maxTime - minTime)) * chartWidth;
      },
      yScale: (value: number) => {
        const yMax = maxValue + valuePadding;
        const yMin = minValue - valuePadding;
        return padding.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight;
      },
      yScalePercent: (pnl: number) => {
        const yMax = maxPnl + pnlPadding;
        const yMin = minPnl - pnlPadding;
        return padding.top + chartHeight - ((pnl - yMin) / (yMax - yMin)) * chartHeight;
      },
    };
  }, [chartData, padding, chartWidth, chartHeight]);

  // 선 경로 생성
  const linePath = useMemo(() => {
    if (!chartData.length) return '';
    return chartData
      .map((d, i) => {
        const x = xScale(d.date.getTime());
        const y = yScale(d.value);
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  }, [chartData, xScale, yScale]);

  // 영역 경로 생성
  const areaPath = useMemo(() => {
    if (!chartData.length) return '';
    const bottom = padding.top + chartHeight;
    const firstPoint = chartData[0];
    const lastPoint = chartData[chartData.length - 1];
    const startX = xScale(firstPoint.date.getTime());
    const endX = xScale(lastPoint.date.getTime());

    const line = chartData
      .map((d) => {
        const x = xScale(d.date.getTime());
        const y = yScale(d.value);
        return `L ${x} ${y}`;
      })
      .join(' ');

    return `M ${startX} ${bottom} ${line} L ${endX} ${bottom} Z`;
  }, [chartData, xScale, yScale, padding.top, chartHeight]);

  // 현재 값
  const currentValue = chartData[chartData.length - 1]?.value || 0;
  const currentPnl = chartData[chartData.length - 1]?.pnl || 0;
  const currentPnlPct = chartData[chartData.length - 1]?.pnl_pct || 0;

  // 포맷 도우미
  const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    switch (timeRange) {
      case '1h':
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      case '24h':
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
      case '7d':
      case '30d':
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      default:
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      {/* 헤더 */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Portfolio Value
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Real-time capital tracking
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            {formatCurrency(currentValue)}
          </p>
          <p className={`text-sm font-medium ${
            currentPnl >= 0 ? 'text-emerald-500' : 'text-red-500'
          }`}>
            {currentPnl >= 0 ? '+' : ''}{currentPnl.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* 차트 컨테이너 */}
      <div className="relative overflow-hidden" style={{ height }}>
        {!chartData.length ? (
          <div className="flex h-full items-center justify-center text-gray-400">
            No data available
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${svgWidth} ${svgHeight}`}
            className="h-full w-full"
            preserveAspectRatio="none"
          >
            {/* 그리드 라인 */}
            {showGrid && (
              <g className="text-gray-200 dark:text-gray-700">
                {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
                  <line
                    key={tick}
                    x1={padding.left}
                    x2={padding.left + chartWidth}
                    y1={padding.top + chartHeight * tick}
                    y2={padding.top + chartHeight * tick}
                    stroke="currentColor"
                    strokeWidth="1"
                    strokeDasharray="4"
                  />
                ))}
              </g>
            )}

            {/* 영역 (그라디언트) */}
            <defs>
              <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path
              d={areaPath}
              fill="url(#areaGradient)"
              className="transition-all duration-300"
            />

            {/* 선 */}
            <path
              d={linePath}
              fill="none"
              stroke="#3B82F6"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-all duration-300"
            />

            {/* Y축 라벨 - 가격 */}
            <g className="text-xs text-gray-500 dark:text-gray-400">
              {chartData.length > 0 && [
                Math.min(...chartData.map((d) => d.value)),
                (Math.min(...chartData.map((d) => d.value)) + Math.max(...chartData.map((d) => d.value))) / 2,
                Math.max(...chartData.map((d) => d.value)),
              ].map((value, i) => (
                <text
                  key={i}
                  x={padding.left - 10}
                  y={yScale(value)}
                  textAnchor="end"
                  alignmentBaseline="middle"
                >
                  {formatCurrency(value)}
                </text>
              ))}
            </g>

            {/* X축 라벨 */}
            <g className="text-xs text-gray-500 dark:text-gray-400">
              {[0, 0.33, 0.66, 1].map((tick) => {
                const index = Math.floor((chartData.length - 1) * tick);
                const d = chartData[index];
                if (!d) return null;
                return (
                  <text
                    key={tick}
                    x={xScale(d.date.getTime())}
                    y={svgHeight - 10}
                    textAnchor="middle"
                  >
                    {formatTime(d.timestamp)}
                  </text>
                );
              })}
            </g>

            {/* 현재 값 포인트 */}
            {chartData.length > 0 && (
              <g>
                <circle
                  cx={xScale(chartData[chartData.length - 1].date.getTime())}
                  cy={yScale(currentValue)}
                  r="5"
                  fill="#3B82F6"
                  stroke="#FFFFFF"
                  strokeWidth="2"
                />
              </g>
            )}
          </svg>
        )}
      </div>

      {/* 시간 범위 선택기 */}
      <div className="mt-4 flex items-center justify-center gap-2">
        {(['1h', '24h', '7d', '30d', 'all'] as TimeRange[]).map((range) => (
          <button
            key={range}
            className={`
              rounded-full px-3 py-1 text-xs font-medium transition-colors
              ${timeRange === range
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
              }
            `}
          >
            {range}
          </button>
        ))}
      </div>

      {/* 미니 통계 */}
      {chartData.length > 0 && (
        <div className="mt-4 grid grid-cols-4 gap-4 border-t border-gray-100 pt-4 dark:border-gray-700">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">High</p>
            <p className="font-medium text-gray-900 dark:text-white">
              {formatCurrency(Math.max(...chartData.map((d) => d.value)))}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Low</p>
            <p className="font-medium text-gray-900 dark:text-white">
              {formatCurrency(Math.min(...chartData.map((d) => d.value)))}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Change</p>
            <p className={`font-medium ${
              currentPnlPct >= 0 ? 'text-emerald-500' : 'text-red-500'
            }`}>
              {currentPnlPct >= 0 ? '+' : ''}{currentPnlPct.toFixed(2)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400">Points</p>
            <p className="font-medium text-gray-900 dark:text-white">
              {chartData.length}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioValueChart;
