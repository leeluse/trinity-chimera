"use client";

import { Results } from "@/types/backtest";
import { TrendingUp, Shield, Zap, DollarSign, Activity, BarChart3, Target, TrendingDown } from "lucide-react";

interface PerformanceDetailsProps {
  results: Results | null;
}

export const PerformanceDetails = ({ results }: PerformanceDetailsProps) => {
  if (!results) return null;

  const fmtPct = (v: number | undefined) => {
    if (v === undefined) return "0.00%";
    return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  };

  const fmtVal = (v: number | undefined) => {
    if (v === undefined) return "$0.00";
    return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const colorClass = (v: number | undefined) => {
    if (v === undefined || v === 0) return "text-[#6272a4]";
    return v > 0 ? "text-[#50fa7b]" : "text-[#ff5555]";
  };

  return (
    <div className="bg-[#12122b]/60 border border-[rgba(189,147,249,0.12)] rounded-xl overflow-hidden shadow-xl backdrop-blur-xl h-full flex flex-col">
      <div className="px-6 py-4 border-b border-[rgba(189,147,249,0.12)] bg-[rgba(189,147,249,0.02)] flex items-center gap-3">
        <Activity size={14} className="text-[#bd93f9]" />
        <h3 className="text-[11px] font-black text-[#f8f8f2]/80 uppercase tracking-[0.2em] mb-0">Performance Analysis</h3>
      </div>

      <div className="p-2 px-6">
        {/* Core Return Segment - Restored Styled Layout */}
        <div className="space-y-2">
           <div className="flex flex-col">
              <span className="text-[9.5px] font-black text-[#6272a4] uppercase tracking-widest">Total Strategy Return</span>
              <span className={`text-xl font-black tracking-tighter leading-none pb-4 pt-2 ${colorClass(results.totalReturnNum)}`}>
                {fmtPct(results.totalReturnNum)}
              </span>
           </div>
        </div>

        <div className="h-px bg-white/5 mt-6" />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-0 text-[#f8f8f2]">
          <MetricRow 
            icon={<TrendingUp size={12} className="text-[#50fa7b]/70" />} 
            label="총 수익률" value={fmtPct(results.totalReturnNum)} valueClass={colorClass(results.totalReturnNum)} 
          />
          <MetricRow 
            icon={<Shield size={12} className="text-[#6272a4]" />} 
            label="매수 보유" value={fmtPct(results.buyHoldReturn)} valueClass="text-[#aeb9e1]"
          />
          <MetricRow 
            icon={<Zap size={12} className="text-[#ffb86c]/70" />} 
            label="초과 성과" value={fmtPct(results.alphaReturn)} valueClass={colorClass(results.alphaReturn)} 
          />
          <MetricRow 
            icon={<DollarSign size={12} className="text-[#ff5555]/70" />} 
            label="전체 수수료" value={fmtVal(results.totalFees)} valueClass="text-[#ff5555]/80"
          />
          <MetricRow 
            icon={<TrendingDown size={12} className="text-[#ff5555]/70" />}
            label="최대 낙폭" value={fmtPct(results.mddPct)} valueClass="text-[#ff5555]"
          />
          <MetricRow 
            icon={<Zap size={12} className="text-[#bd93f9]/70" />}
            label="샤프 비율" value={results.sharpeRatio.toFixed(2)} valueClass="text-[#bd93f9]"
          />
          <MetricRow 
            icon={<BarChart3 size={12} className="text-[#8be9fd]/70" />}
            label="소르티노" value={results.sortinoRatio?.toFixed(2) || "0.00"} valueClass="text-[#8be9fd]"
          />
          <MetricRow 
            icon={<Target size={12} className="text-[#50fa7b]/70" />}
            label="기댓값 (EV)" value={fmtPct(results.expectedReturn)} valueClass={colorClass(results.expectedReturn)}
          />
        </div>

        <div className="flex gap-4 pt-4 border-t border-[rgba(189,147,249,0.08)]">
           <SideBadge label="LONG" value={fmtPct(results.longReturn)} pf={results.longPF} color="green" />
           <SideBadge label="SHORT" value={fmtPct(results.shortReturn)} pf={results.shortPF} color="red" />
        </div>
      </div>
    </div>
  );
};

function MetricRow({ icon, label, value, valueClass }: any) {
  return (
    <div className="flex items-center justify-between group py-3 border-b border-white/[0.03] hover:border-[#bd93f9]/20 transition-colors">
      <div className="flex items-center gap-2.5 min-w-0">
         <div className="text-[#6272a4] w-4 flex justify-center shrink-0">{icon}</div>
         <span className="text-[9.5px] font-bold text-[#6272a4] group-hover:text-[#aeb9e1] transition-colors uppercase tracking-wider whitespace-nowrap">{label}</span>
      </div>
      <span className={`text-[12px] font-black tracking-tight ${valueClass} shrink-0 ml-4`}>{value}</span>
    </div>
  );
}

function SideBadge({ label, value, pf, color }: any) {
  const isGreen = color === "green";
  return (
    <div className="flex-1 flex items-center justify-between bg-[rgba(189,147,249,0.01)] border border-[rgba(189,147,249,0.05)] rounded-lg px-4 py-2">
       <div className="flex flex-col">
          <span className={`text-[8px] font-black uppercase ${isGreen ? 'text-[#50fa7b]/50' : 'text-[#ff5555]/50'}`}>{label}</span>
          <span className="text-xs font-black text-[#f8f8f2]">{value}</span>
       </div>
       <div className="flex flex-col items-end">
          <span className="text-[7px] font-bold text-[#6272a4] uppercase">PF</span>
          <span className="text-[10px] font-black text-[#f8f8f2]/80">{pf?.toFixed(2) || "0.00"}</span>
       </div>
    </div>
  );
}

export default PerformanceDetails;
