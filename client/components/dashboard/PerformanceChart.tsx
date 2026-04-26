'use client';

import React, { RefObject, useState, memo } from "react";
import { MetricKey } from "@/types";

interface PerformanceChartProps {
  chartRef: RefObject<HTMLCanvasElement | null>;
  labelPositions: any[];
  currentMetric: MetricKey;
}

// React.memo로 감싸서 불필요한 부모의 렌더링에 의한 차트 영향 최소화
export const PerformanceChart = memo(({ chartRef, labelPositions, currentMetric }: PerformanceChartProps) => {
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);

  return (
    <div className="relative w-full h-[520px]">
      <div className="absolute inset-0 bg-transparent overflow-visible px-8 py-4">
        <canvas ref={chartRef} className="w-full h-full z-10 relative"></canvas>
        {labelPositions.map((pos, i) => {
          // 겹침 방지를 위해 더 큰 Y축 오프셋 부여 (20px 단위)
          const overlapOffset = (i * 20) - ((labelPositions.length - 1) * 10);
          
          return (
            <div 
              key={i} 
              className="absolute z-30 transition-all duration-500 pointer-events-none" 
              style={{ 
                left: pos.x, 
                top: `calc(${pos.y}px + ${overlapOffset}px)`, 
                transform: 'translate(14px, -50%)'
              }}
            >
              <div className="flex items-center gap-3">
                <div 
                  className="relative shrink-0 pointer-events-auto cursor-pointer" 
                  onMouseEnter={() => setHoveredLabel(pos.label)} 
                  onMouseLeave={() => setHoveredLabel(null)}
                >
                  <div 
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-black transition-all duration-300 shadow-[0_0_20px_rgba(0,0,0,0.5)] border-2 ${hoveredLabel === pos.label ? 'scale-125 z-50' : 'z-30'}`} 
                    style={{ 
                      backgroundColor: 'rgba(6, 9, 18, 0.98)', 
                      color: pos.color, 
                      borderColor: pos.color
                    }}
                  >
                    {pos.avatar.toUpperCase()}
                  </div>
                </div>
                {hoveredLabel === pos.label && (
                  <div className="bg-background/98 backdrop-blur-3xl border border-white/20 rounded-[10px] py-2 px-3 shadow-2xl min-w-[100px] flex flex-col gap-1 animate-in fade-in zoom-in-95 duration-200 z-50">
                    <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">{currentMetric.toUpperCase()}</div>
                    <div className="text-[13px] font-bold tracking-tight text-white leading-none tabular-nums">
                      {pos.value.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

PerformanceChart.displayName = "PerformanceChart";

export default PerformanceChart;
