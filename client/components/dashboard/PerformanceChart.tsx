"use client";

import { RefObject, useState } from "react";
import { MetricKey } from "@/types";

interface PerformanceChartProps {
  chartRef: RefObject<HTMLCanvasElement | null>;
  labelPositions: any[];
  currentMetric: MetricKey;
}

export const PerformanceChart = ({ chartRef, labelPositions, currentMetric }: PerformanceChartProps) => {
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);

  return (
    <div className="relative w-full h-[520px]">
      <div className="absolute inset-0 bg-transparent overflow-visible px-8 py-4">
        <canvas ref={chartRef} className="w-full h-full z-10 relative"></canvas>
        {labelPositions.map((pos, i) => (
          <div 
            key={i} 
            className="absolute z-30 transition-all duration-300 pointer-events-none" 
            style={{ 
              left: pos.x, 
              top: pos.y, 
              transform: 'translate(12px, -50%)'
            }}
          >
            <div className="flex items-center gap-3">
              <div 
                className="relative shrink-0 pointer-events-auto cursor-pointer" 
                onMouseEnter={() => setHoveredLabel(pos.label)} 
                onMouseLeave={() => setHoveredLabel(null)}
              >
                <div 
                  className={`w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-black transition-transform duration-300 ${hoveredLabel === pos.label ? 'scale-110' : ''}`} 
                  style={{ 
                    backgroundColor: 'rgba(6, 9, 18, 0.9)', 
                    color: pos.color, 
                  }}
                >
                  {pos.avatar}
                </div>
              </div>
              {hoveredLabel === pos.label && (
                <div className="bg-[#0b0f1a]/95 backdrop-blur-3xl border border-white/10 rounded-[8px] py-1.5 px-2.5 shadow-2xl min-w-[90px] flex flex-col gap-0.5 animate-in fade-in zoom-in-95 duration-200">
                  <div className="text-[8px] font-bold text-slate-500 uppercase tracking-tighter">{currentMetric.toUpperCase()}</div>
                  <div className="text-[12px] font-bold tracking-tight text-white leading-none my-0.5">{pos.value.toFixed(1)}</div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PerformanceChart;
