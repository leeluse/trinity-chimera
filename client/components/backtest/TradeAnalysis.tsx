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
    <div className="bg-[#12122b]/60 border border-[rgba(189,147,249,0.12)] rounded-xl overflow-hidden shadow-xl backdrop-blur-xl h-full flex flex-col">
      <div className="px-6 py-4 border-b border-[rgba(189,147,249,0.12)] bg-[rgba(189,147,249,0.02)] flex items-center gap-3">
        <PieChart size={14} className="text-[#50fa7b]" />
        <h3 className="text-[11px] font-black text-[#f8f8f2]/80 uppercase tracking-[0.2em] mb-0">Trade Intelligence</h3>
      </div>

      <div className="p-2 px-6">
        {/* Win Rate Segment - Using Project Green/Red with Bold Spacing */}
        <div className="space-y-6 py-2">
           <div className="flex items-center justify-between px-1">
              <div className="flex flex-col">
                 <span className="text-[9.5px] font-black text-[#6272a4] uppercase tracking-widest">Winning Probability</span>
                 <span className="text-xl font-black text-[#f8f8f2] tracking-tighter leading-none py-4">{winRate.toFixed(1)}%</span>
              </div>
              
              <div className="flex flex-col gap-3 items-end">
                 <div className="flex items-center gap-2">
                    <span className="text-[9px] font-bold text-[#6272a4] uppercase tracking-widest">Wins</span>
                    <span className="text-[14px] font-black text-[#50fa7b] leading-none">{results.winCount}</span>
                 </div>
                 <div className="flex items-center gap-2">
                    <span className="text-[9px] font-bold text-[#6272a4] uppercase tracking-widest">Losses</span>
                    <span className="text-[14px] font-black text-[#ff5555] leading-none">{results.lossCount}</span>
                 </div>
              </div>
           </div>
           
           <div className="flex flex-col gap-3 mt-4">
              <div className="h-2 w-full bg-[rgba(255,255,255,0.05)] rounded-full overflow-hidden flex shadow-inner">
                 <div className="h-full bg-gradient-to-r from-[#50fa7b]/80 to-[#50fa7b]" style={{ width: `${winRate}%` }} />
                 <div className="h-full bg-gradient-to-r from-[#ff5555]/80 to-[#ff5555]" style={{ width: `${100-winRate}%` }} />
              </div>
              <div className="flex justify-between text-[8px] font-black uppercase text-[#6272a4] tracking-[0.1em] px-1">
                 <span>{results.winCount} Successful Trades</span>
                 <span>{results.lossCount} Failed Trades</span>
              </div>
           </div>
        </div>

        <div className="h-px bg-white/5 mt-10 mb-8" />

        {/* 2-Column Mesh Grid - Project Palette */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-0 text-[#f8f8f2]">
           <StatRow icon={<ShieldCheck size={12}/>} label="Best Trade" value={fmtPct(results.bestTradeFinal)} color="text-[#50fa7b]" />
           <StatRow icon={<AlertCircle size={12}/>} label="Worst Trade" value={fmtPct(results.worstTradeFinal)} color="text-[#ff5555]" />
           <StatRow icon={<BarChart3 size={12}/>} label="Profit Factor" value={results.profitFactor.toFixed(2)} color="text-[#bd93f9]" />
           <StatRow icon={<Repeat size={12}/>} label="Avg. Hold" value={`${results.avgHoldBars?.toFixed(0) || 0}B`} />
           <StatRow icon={<BarChart3 size={12} className="opacity-40"/>} label="Max Wins" value={String(results.maxConsecutiveWins || 0)} color="text-[#50fa7b]/80" />
           <StatRow icon={<AlertCircle size={12} className="opacity-40"/>} label="Max Losses" value={String(results.maxConsecutiveLosses || 0)} color="text-[#ff5555]/80" />
        </div>
      </div>
    </div>
  );
};

function StatRow({ icon, label, value, color = "text-[#f8f8f2]/90" }: any) {
  return (
    <div className="flex items-center justify-between group py-3 border-b border-white/[0.03] hover:border-[#bd93f9]/20 transition-colors">
       <div className="flex items-center gap-2.5 min-w-0">
          <div className="text-[#6272a4] w-4 flex justify-center shrink-0">{icon}</div>
          <span className="text-[9.5px] font-bold text-[#6272a4] group-hover:text-[#aeb9e1] uppercase tracking-wider whitespace-nowrap">{label}</span>
       </div>
       <span className={`text-[12px] font-black tracking-tight ${color} shrink-0 ml-4`}>{value}</span>
    </div>
  );
}

export default TradeAnalysis;
