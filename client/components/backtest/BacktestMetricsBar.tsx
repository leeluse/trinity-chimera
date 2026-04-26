"use client";

import { Results } from "@/types/backtest";

interface BacktestMetricsBarProps {
  results: Results | null;
}

export default function BacktestMetricsBar({ results }: BacktestMetricsBarProps) {
  const stats = [
    { 
      label: "총 수익률", 
      value: results ? `+${results.totalReturnNum.toFixed(2)}%` : "+76.61%", 
      sub: results ? `${results.totalTradesCount} 거래 내역` : "30 거래 내역", 
      color: "text-[#4ade80]" 
    },
    { 
      label: "최대 낙폭", 
      value: results ? `${results.mddPct.toFixed(2)}%` : "15.92%", 
      color: "text-white/90" 
    },
    { 
      label: "승률", 
      value: results ? `${results.winRateNum.toFixed(2)}%` : "46.67%", 
      sub: results ? `${results.winCount}W ${results.lossCount}L` : "14W 16L" 
    },
    { 
      label: "수익 팩터", 
      value: results ? results.profitFactor.toFixed(2) : "2.71" 
    },
    { 
      label: "샤프 비율", 
      value: results ? results.sharpeRatio.toFixed(2) : "2.22" 
    },
  ];

  return (
    <div className="grid grid-cols-5 gap-3 p-5">
      {stats.map((stat, i) => (
        <div 
          key={i} 
          className="bg-background/40 border border-white/[0.05] rounded-xl p-5 space-y-2 shadow-lg backdrop-blur-sm group hover:border-white/10 hover:bg-background/60 transition-all duration-300"
        >
          <div className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] leading-none mb-1">
            {stat.label}
          </div>
          <div className={`text-[20px] font-black tracking-tighter ${stat.color || 'text-white/95'} group-hover:scale-[1.03] transition-transform origin-left`}>
            {stat.value}
          </div>
          {stat.sub && (
            <div className="text-[10px] font-bold text-slate-600 tracking-tight">
              {stat.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
