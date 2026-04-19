"use client";

import { HINT_MAP } from "@/constants";
import { MetricKey } from "@/types";
import { useDashboardStore } from "@/store/useDashboardStore";

interface MetricSelectorProps {}

export const MetricSelector = ({}: MetricSelectorProps) => {
  const { currentMetric, setCurrentMetric } = useDashboardStore();
  return (
    <div className="flex items-center justify-between border-b border-white/[0.05] pb-2">
      <div className="flex gap-1 overflow-x-auto no-scrollbar">
        {(Object.keys(HINT_MAP) as MetricKey[]).map((m) => (
          <button
            key={m}
            className={`px-3 py-1 text-[11px] font-bold tracking-tight transition-all rounded-lg whitespace-nowrap border ${
              currentMetric === m 
              ? 'bg-indigo-600/20 text-indigo-400 border-indigo-500/30' 
              : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
            onClick={() => setCurrentMetric(m)}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="ml-auto hidden md:flex items-center gap-2 bg-indigo-500/5 border border-indigo-500/10 py-1 px-3 rounded-lg">
        <span className="text-[10px] text-indigo-400/80 font-mono italic">
          {HINT_MAP[currentMetric]}
        </span>
      </div>
    </div>
  );
};

export default MetricSelector;
