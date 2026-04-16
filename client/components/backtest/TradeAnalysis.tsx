"use client";

import { Results } from "@/types/backtest";
import { PieChart, BarChart3, Repeat, ShieldCheck, AlertCircle } from "lucide-react";

interface TradeAnalysisProps {
  results: Results | null;
}

export const TradeAnalysis = ({ results }: TradeAnalysisProps) => {
  if (!results) return null;

  const winRate = results.winRateNum;
  const fmtPct = (v: number | undefined) => {
    if (v === undefined) return "+0.00%";
    return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  };

  return (
    <div className="bg-[#0b0f1a]/60 border border-white/10 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/[0.08] bg-white/[0.02] flex items-center gap-3 h-[60px]">
        <PieChart size={16} className="text-emerald-400" />
        <h3 className="text-sm font-black text-white/90 uppercase tracking-[0.2em] mb-0">Trade Intelligence</h3>
      </div>

      <div className="p-6">
        {/* Top Win Rate Gauge area (Horizontal align inside) */}
        <div className="flex items-center gap-8 mb-10 pb-6 border-b border-white/5">
           <div className="flex flex-col">
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Win Probability</span>
              <span className="text-3xl font-black text-white tracking-tighter leading-none">{winRate.toFixed(1)}%</span>
           </div>
           <div className="flex-1 flex flex-col gap-2">
              <div className="flex justify-between text-[9px] font-black uppercase text-slate-600">
                 <span>{results.winCount} Wins</span>
                 <span>{results.lossCount} Losses</span>
              </div>
              <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden flex">
                 <div className="h-full bg-emerald-500" style={{ width: `${winRate}%` }} />
                 <div className="h-full bg-rose-500" style={{ width: `${100-winRate}%` }} />
              </div>
           </div>
        </div>

        {/* 2-Column Mesh Grid for detailed stats */}
        <div className="grid grid-cols-2 gap-x-10 gap-y-6">
           <StatCell icon={<ShieldCheck size={12}/>} label="Best Trade" value={fmtPct(results.bestTradeFinal)} color="text-emerald-400" />
           <StatCell icon={<AlertCircle size={12}/>} label="Worst Trade" value={fmtPct(results.worstTradeFinal)} color="text-rose-400" />
           <StatCell icon={<BarChart3 size={12}/>} label="Profit Factor" value={results.profitFactor.toFixed(2)} color="text-blue-400" />
           <StatCell icon={<Repeat size={12}/>} label="Avg. Hold" value={`${results.avgHoldBars?.toFixed(0) || 0} Bars`} />
           <StatCell icon={<BarChart3 size={12} className="opacity-40"/>} label="Max Wins" value={String(results.maxConsecutiveWins || 0)} color="text-emerald-500/80" />
           <StatCell icon={<AlertCircle size={12} className="opacity-40"/>} label="Max Losses" value={String(results.maxConsecutiveLosses || 0)} color="text-rose-500/80" />
        </div>
      </div>
    </div>
  );
};

function StatCell({ icon, label, value, color = "text-white/90" }: any) {
  return (
    <div className="flex flex-col gap-1.5 group">
       <div className="flex items-center gap-2 opacity-60 group-hover:opacity-100 transition-opacity">
          <div className="text-slate-500">{icon}</div>
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</span>
       </div>
       <div className="flex items-baseline gap-2 pl-5">
          <span className={`text-base font-black tracking-tighter ${color}`}>{value}</span>
          <div className="h-px flex-1 bg-white/5" />
       </div>
    </div>
  );
}

export default TradeAnalysis;
