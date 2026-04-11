"use client";

import { Results } from "@/types/backtest";

interface TradeAnalysisProps {
  results: Results | null;
}

export const TradeAnalysis = ({ results }: TradeAnalysisProps) => {
  if (!results) return null;

  const winRate = results.winRateNum;
  const lossRate = 100 - winRate;

  const fmtPct = (v: number | undefined) => {
    if (v === undefined) return "+0.00%";
    return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
  };

  return (
    <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl overflow-hidden shadow-2xl backdrop-blur-md h-full">
      {/* Header */}
      <div className="px-5 py-3 border-b border-white/[0.05] bg-white/[0.01]">
        <h3 className="text-xs font-black text-slate-400 uppercase tracking-[0.2em]">거래 분석</h3>
      </div>

      <div className="p-6 space-y-6">
        {/* Win Rate Bar Section */}
        <div className="space-y-3">
          <div className="flex justify-between items-end">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-tight">{results.totalTradesCount} 거래 내역</span>
            <span className="text-[11px] font-black text-white/90 uppercase tracking-tight">승률 <span className="text-[#4ade80] ml-1">+{winRate.toFixed(2)}%</span></span>
          </div>
          
          <div className="h-2 w-full flex rounded-full overflow-hidden bg-white/5">
            <div 
              className="h-full bg-gradient-to-r from-[#4ade80] to-[#22c55e] transition-all duration-1000" 
              style={{ width: `${winRate}%` }} 
            />
            <div 
              className="h-full bg-gradient-to-r from-[#fb7185] to-[#e11d48] transition-all duration-1000" 
              style={{ width: `${lossRate}%` }} 
            />
          </div>

          <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
            <div className="flex gap-4">
              <span className="flex items-center gap-1.5 text-slate-400">
                <div className="w-1.5 h-1.5 rounded-full bg-[#4ade80]" />
                {results.winCount}W
              </span>
              <span className="flex items-center gap-1.5 text-slate-400">
                <div className="w-1.5 h-1.5 rounded-full bg-[#fb7185]" />
                {results.lossCount}L
              </span>
            </div>
            <div className="flex gap-4 text-slate-500">
               <span>{results.longCount}L</span>
               <span>{results.shortCount}S</span>
            </div>
          </div>
        </div>

        <div className="h-px bg-white/[0.05]" />

        {/* Primary Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-16 gap-y-4 px-1">
          <DetailRow label="가장 큰 승리" value={fmtPct(results.bestTradeFinal)} valueClass="text-[#4ade80]" />
          <DetailRow label="최대 손실" value={fmtPct(results.worstTradeFinal)} valueClass="text-[#fb7185]" />
          <DetailRow label="평균 수익" value={fmtPct(results.avgProfitPct)} valueClass="text-[#4ade80]" />
          <DetailRow label="평균 손실" value={fmtPct(results.avgLossPct)} valueClass="text-[#fb7185]" />
          <DetailRow label="수익 팩터" value={results.profitFactor.toFixed(2)} />
          <DetailRow label="평균 막대" value={results.avgHoldBars?.toFixed(2) || "0.00"} />
        </div>

        <div className="h-px bg-white/[0.05]" />

        {/* Streaks */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-16 px-1">
          <DetailRow label="최대 연속 승리" value={String(results.maxConsecutiveWins || 0)} valueClass="text-[#4ade80]" />
          <DetailRow label="최대 연속 손실 횟수" value={String(results.maxConsecutiveLosses || 0)} valueClass="text-[#fb7185]" />
        </div>
      </div>
    </div>
  );
};

function DetailRow({ label, value, valueClass = "text-white/90" }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between text-[10.5px] group gap-4">
      <span className="text-slate-500 font-bold group-hover:text-slate-300 transition-colors uppercase tracking-tight">{label}</span>
      <span className={`font-black tracking-tight ${valueClass}`}>{value}</span>
    </div>
  );
}

export default TradeAnalysis;
