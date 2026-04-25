"use client";

import { NAMES, COLORS } from "@/constants";

interface ChartLegendProps {
  names?: string[];
}

export const ChartLegend = ({ names }: ChartLegendProps) => {
  const displayNames = names || NAMES;
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      {displayNames.map((name, i) => {
        const itemColor = name === "BTC BnH" ? "#64748b" : COLORS[i % COLORS.length];
        return (
          <div key={name} className="flex items-center gap-2 px-3 py-1 rounded-lg bg-white/[0.02] border border-white/[0.04] backdrop-blur-sm">
            <div className="w-1.5 h-1.5 rounded-full shadow-[0_0_8px_currentColor]" style={{ background: itemColor, color: itemColor }}></div>
            <span className="text-[10px] font-black text-slate-400 tracking-widest uppercase">{name}</span>
          </div>
        );
      })}
    </div>
  );
};

export default ChartLegend;
