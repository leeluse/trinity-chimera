"use client";

import { HINT_MAP } from "@/constants";
import { MetricKey } from "@/types";

interface MetricSelectorProps {
  currentMetric: MetricKey;
  setCurrentMetric: (metric: MetricKey) => void;
}

export const MetricSelector = ({ currentMetric, setCurrentMetric }: MetricSelectorProps) => {
  return (
    <div className="flex items-center justify-between bg-transparent overflow-hidden">
      <div className="flex p-1 rounded-xl overflow-x-auto no-scrollbar max-w-full">
        {(Object.keys(HINT_MAP) as MetricKey[]).map((m) => (
          <button
            key={m}
            className={`px-3 sm:px-4 py-1.5 rounded-lg text-[10px] sm:text-[11px] font-bold outline-none transition-none whitespace-nowrap border ${currentMetric === m ? 'bg-white/10 text-white border-white/20' : 'text-slate-500 hover:text-slate-400 border-transparent'}`}
            onClick={() => setCurrentMetric(m)}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>
      <div className="ml-auto hidden sm:flex items-center gap-2 px-3 py-1.5 bg-transparent shrink-0">
        <span className="text-[10px] text-slate-500 font-mono italic tracking-tight">{HINT_MAP[currentMetric]}</span>
      </div>
    </div>
  );
};

export default MetricSelector;
