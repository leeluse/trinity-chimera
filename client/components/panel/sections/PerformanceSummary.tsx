"use client";

import { PerformanceRow } from "@/types";

interface PerformanceSummaryProps {
  performanceData: PerformanceRow[];
  onAgentClick?: (agentId: string) => void;
  activeAgent?: string;
}

export const PerformanceSummary = ({ performanceData, onAgentClick, activeAgent }: PerformanceSummaryProps) => {
  return (
    <div className="p-4 border-t border-white/[0.04] bg-[#060912]/90 shrink-0 backdrop-blur-lg">
      <div className="text-[10px] font-bold text-[#475569] uppercase tracking-[0.14em] mb-4 flex items-center justify-between">
        <span>성과 요약</span>
        <div className="flex gap-2">
          <div className="w-1 h-1 rounded-full bg-blue-400"></div>
          <div className="w-1 h-1 rounded-full bg-blue-400/40"></div>
          <div className="w-1 h-1 rounded-full bg-blue-400/20"></div>
        </div>
      </div>
      <div className="overflow-x-auto no-scrollbar">
        <table className="w-full text-left border-collapse min-w-[320px]">
          <thead>
            <tr className="text-[9px] text-[#475569] uppercase tracking-wider border-b border-white/[0.04]">
              <th className="pb-2.5 pt-1 font-bold px-3">Agent</th>
              <th className="pb-2.5 pt-1 font-bold text-center px-2">Return</th>
              <th className="pb-2.5 pt-1 font-bold text-center px-2">Sharpe</th>
              <th className="pb-2.5 pt-1 font-bold text-right px-3">MDD</th>
            </tr>
          </thead>
          <tbody className="text-[12px] font-mono">
            {performanceData.map((row) => (
              <tr 
                key={row.name} 
                className={`group transition-colors ${
                  (row.agentId && activeAgent === row.agentId) ? 'bg-white/[0.03]' : ''
                }`}
                onClick={() => row.agentId && onAgentClick?.(row.agentId)}
              >
                <td className="py-2.5 px-3 font-medium tracking-tighter border-b border-white/[0.02]" style={{ color: row.color }}>{row.name}</td>
                <td className={`py-2.5 px-2 text-center border-b border-white/[0.02] font-semibold ${row.pos ? 'text-[#4ade80]' : 'text-[#fb7185]'}`}>{row.ret}</td>
                <td className="py-2.5 px-2 text-center border-b border-white/[0.02] text-[#94a3b8] font-medium">{row.sh}</td>
                <td className="py-2.5 px-3 text-right border-b border-white/[0.02] text-[#fb7185] opacity-90 font-medium">{row.mdd}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PerformanceSummary;
