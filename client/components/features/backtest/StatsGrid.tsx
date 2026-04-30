"use client";

import { Results } from "@/types/backtest";

interface StatsGridProps {
  results: Results | null;
  fmtMoney: (v: number) => string;
}

export const StatsGrid = ({ results, fmtMoney }: StatsGridProps) => {
  const stats = [
    { 
      label: "총 수익률", 
      value: results 
        ? `${results.totalReturnNum >= 0 ? "+" : ""}${results.totalReturnNum.toFixed(2)}%` 
        : "0.00%", 
      sub: results ? `${results.totalTradesCount} 거래 내역` : "0 거래 내역", 
      color: results 
        ? (results.totalReturnNum >= 0 ? "text-[#4ade80]" : "text-[#fb7185]")
        : "text-slate-500" 
    },
    { 
      label: "최대 낙폭", 
      value: results ? `${results.mddPct.toFixed(2)}%` : "0.00%", 
      color: results ? "text-white/90" : "text-slate-500"
    },
    { 
      label: "승률", 
      value: results ? `${results.winRateNum.toFixed(2)}%` : "0.00%", 
      sub: results ? `${results.winCount}W ${results.lossCount}L` : "0W 0L",
      color: results ? "text-white/90" : "text-slate-500"
    },
    { 
      label: "수익 팩터", 
      value: results ? results.profitFactor.toFixed(2) : "0.00",
      color: results ? "text-white/90" : "text-slate-500"
    },
    { 
      label: "샤프 비율", 
      value: results ? results.sharpeRatio.toFixed(2) : "0.00",
      color: results ? "text-white/90" : "text-slate-500"
    },
  ];

  return (
    <div className="grid grid-cols-5 gap-2 py-2">
      {stats.map((stat, i) => (
        <div 
          key={i} 
          className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-3 space-y-2 shadow-xl hover:bg-white/[0.04] transition-all group"
        >
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none mb-1">
            {stat.label}
          </div>
          <div className={`text-[20px] font-black tracking-tight ${stat.color || 'text-white/90'} group-hover:scale-105 transition-transform origin-left duration-300`}>
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

export default StatsGrid;
