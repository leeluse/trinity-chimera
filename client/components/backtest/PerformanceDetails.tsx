"use client";

import { Results } from "@/types/backtest";

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
    if (v === undefined || v === 0) return "text-white/90";
    return v > 0 ? "text-[#4ade80]" : "text-[#fb7185]";
  };

  return (
    <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl overflow-hidden shadow-2xl backdrop-blur-md h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-white/[0.05] bg-white/[0.01]">
        <h3 className="text-xs font-black text-slate-400 uppercase tracking-[0.2em]">성능</h3>
      </div>

      <div className="p-2 space-y-8 ">
        {/* Section: Profit */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1 h-3 bg-blue-500 rounded-full" />
            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">수익</h4>
          </div>

          <div className="">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-16 gap-y-3 px-1">
            <MetricRow label="총 수익률" value={fmtPct(results.totalReturnNum)} valueClass={colorClass(results.totalReturnNum)} />
            <MetricRow label="매수 후 보유" value={fmtPct(results.buyHoldReturn)} valueClass={colorClass(results.buyHoldReturn)} />
            <MetricRow label="초과 성과" value={fmtPct(results.alphaReturn)} valueClass={colorClass(results.alphaReturn)} />
            <MetricRow label="수수료" value={fmtVal(results.totalFees)} />
            <MetricRow label="예상 수익" value={fmtVal(results.expectedReturn)} valueClass={colorClass(results.expectedReturn)} />
          </div>

            <div className="grid grid-cols-2 gap-6 mt-4">
              <SideTag label="Long" value={fmtPct(results.longReturn)} pf={results.longPF} color="text-[#4ade80]" />
              <SideTag label="Short" value={fmtPct(results.shortReturn)} pf={results.shortPF} color="text-[#4ade80]" />
            </div>
          </div>
        </section>

        {/* Section: Risk */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1 h-3 bg-red-500 rounded-full" />
            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">위험</h4>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-16 gap-y-3 px-1">
            <MetricRow label="최대 낙폭" value={fmtPct(results.mddPct)} />
            <MetricRow label="샤프 비율" value={results.sharpeRatio.toFixed(2)} />
            <MetricRow label="소르티노 비율" value={results.sortinoRatio?.toFixed(2) || "0.00"} />
            <MetricRow label="Calmar 비율" value={results.calmarRatio?.toFixed(2) || "0.00"} />
          </div>
        </section>
      </div>
    </div>
  );
};

function MetricRow({ label, value, valueClass = "text-white/90" }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between text-[10.5px] group gap-4">
      <span className="text-slate-500 font-bold group-hover:text-slate-300 transition-colors uppercase tracking-tight">{label}</span>
      <span className={`font-black tracking-tight ${valueClass}`}>{value}</span>
    </div>
  );
}

function SideTag({ label, value, pf, color }: { label: string; value: string; pf?: number; color: string }) {
  return (
    <div className="flex items-center justify-between bg-white/[0.03] border border-white/[0.05] rounded-xl px-4 py-2.5 hover:bg-white/[0.05] transition-all">
      <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.15em]">{label}</span>
      <div className="flex items-center gap-3">
        <span className={`text-[11px] font-black ${color}`}>{value}</span>
        <div className="w-px h-2 bg-white/10" />
        <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">PF <span className="text-white/90 ml-1">{pf?.toFixed(2) || "0.00"}</span></span>
      </div>
    </div>
  );
}

export default PerformanceDetails;
