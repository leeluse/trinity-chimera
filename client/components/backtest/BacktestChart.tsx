"use client";

import { RefObject } from "react";
import CandlestickChart from "@/components/charts/CandleStickChart";

interface BacktestChartProps {
  chartContainerRef: RefObject<HTMLDivElement | null>;
  results: any;
  loading: boolean;
  symbol: string;
  timeFrame: string;
  cardClass: string;
}

export const BacktestChart = ({
  chartContainerRef,
  results,
  loading,
  symbol,
  timeFrame,
  cardClass
}: BacktestChartProps) => {
  return (
    <div className="relative overflow-hidden h-[450px] shrink-0 w-full bg-[#060912]/40 backdrop-blur-sm border border-white/[0.05] rounded-xl">
      {!results && (
        <div className="absolute inset-0 z-10 h-[450px]">
          <CandlestickChart 
            pair={symbol.replace("USDT", "/USDT")} 
            timeFrame={timeFrame as any} 
            isActive 
            onClick={() => { }} 
            compact={false} 
          />
        </div>
      )}
      <div 
        ref={chartContainerRef} 
        className={`w-full h-[450px] ${results ? "opacity-100" : "opacity-0 pointer-events-none"}`} 
      />
      {loading && (
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-primary/30 border-l-primary animate-spin mb-4" />
          <p className="text-primary font-semibold text-sm tracking-widest uppercase">Simulating Markets...</p>
        </div>
      )}
    </div>
  );
};

export default BacktestChart;
