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
    if (v === undefined || v === 0) return "text-white/60";
    return v > 0 ? "text-emerald-400" : "text-rose-400";
  };

  return (
    <div className="bg-[#0b0f1a]/60 border border-white/10 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl h-full flex flex-col">
      <div className="px-6 py-4 border-b border-white/[0.08] bg-white/[0.02] flex items-center gap-3 h-[60px]">
        <Activity size={16} className="text-blue-400" />
        <h3 className="text-sm font-black text-white/90 uppercase tracking-[0.2em] mb-0">Performance Analysis</h3>
      </div>

      <div className="p-6">
        {/* Internal Horizontal Grid - 2 columns within the component */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-6">
          <MetricCell 
            icon={<TrendingUp size={12} className="text-emerald-400/70" />} 
            label="총 수익률" value={fmtPct(results.totalReturnNum)} valueClass={colorClass(results.totalReturnNum)} 
          />
          <MetricCell 
            icon={<Shield size={12} className="text-slate-500" />} 
            label="매수 보유" value={fmtPct(results.buyHoldReturn)} valueClass="text-slate-300"
          />
          <MetricCell 
            icon={<Zap size={12} className="text-amber-400/70" />} 
            label="초과 성과" value={fmtPct(results.alphaReturn)} valueClass={colorClass(results.alphaReturn)} 
          />
          <MetricCell 
            icon={<DollarSign size={12} className="text-rose-400/70" />} 
            label="전체 수수료" value={fmtVal(results.totalFees)} valueClass="text-rose-400/80"
          />
          <MetricCell 
            icon={<TrendingDown size={12} className="text-rose-400/70" />}
            label="최대 낙폭" value={fmtPct(results.mddPct)} valueClass="text-rose-400"
          />
          <MetricCell 
            icon={<Zap size={12} className="text-blue-400/70" />}
            label="샤프 비율" value={results.sharpeRatio.toFixed(2)} valueClass="text-blue-400"
          />
          <MetricCell 
            icon={<BarChart3 size={12} className="text-indigo-400/70" />}
            label="소르티노" value={results.sortinoRatio?.toFixed(2) || "0.00"} valueClass="text-indigo-400"
          />
          <MetricCell 
            icon={<Target size={12} className="text-emerald-400/70" />}
            label="기댓값 (EV)" value={fmtPct(results.expectedReturn)} valueClass={colorClass(results.expectedReturn)}
          />
        </div>

        {/* Dynamic L/S side tags condensed */}
        <div className="mt-8 flex gap-4 pt-6 border-t border-white/5">
           <SideBadge label="LONG" value={fmtPct(results.longReturn)} pf={results.longPF} color="emerald" />
           <SideBadge label="SHORT" value={fmtPct(results.shortReturn)} pf={results.shortPF} color="rose" />
        </div>
      </div>
    </div>
  );
};

function MetricCell({ icon, label, value, valueClass }: any) {
  return (
    <div className="flex flex-col gap-1.5 group">
      <div className="flex items-center gap-2 opacity-60 group-hover:opacity-100 transition-opacity">
         {icon}
         <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex items-baseline gap-2 pl-5">
         <span className={`text-base font-black tracking-tighter ${valueClass}`}>{value}</span>
         <div className="h-px flex-1 bg-white/5" />
      </div>
    </div>
  );
}

function SideBadge({ label, value, pf, color }: any) {
  const isEmerald = color === "emerald";
  return (
    <div className="flex-1 flex items-center justify-between bg-white/[0.02] border border-white/[0.05] rounded-xl px-4 py-2.5">
       <div className="flex flex-col">
          <span className={`text-[9px] font-black uppercase ${isEmerald ? 'text-emerald-500/50' : 'text-rose-500/50'}`}>{label}</span>
          <span className="text-sm font-black text-white">{value}</span>
       </div>
       <div className="flex flex-col items-end">
          <span className="text-[8px] font-bold text-slate-600 uppercase">PF</span>
          <span className="text-xs font-black text-white/80">{pf?.toFixed(2) || "0.00"}</span>
       </div>
    </div>
  );
}

function TrendingDown({ size, className }: { size: number; className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"></polyline><polyline points="16 17 22 17 22 11"></polyline></svg>
  );
}

export default PerformanceDetails;
