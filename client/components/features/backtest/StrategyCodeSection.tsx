"use client";

import { Terminal, ShieldCheck, Cpu } from "lucide-react";
import CodeEditor from "../common/CodeEditor";

interface StrategyCodeSectionProps {
  strategyName: string;
  code: string;
  onChange?: (value: string) => void;
  loading?: boolean;
}

export default function StrategyCodeSection({ strategyName, code, onChange, loading }: StrategyCodeSectionProps) {
  if (!code && !loading) return null;

  return (
    <div className="w-full bg-background/50 border border-white/[0.05] rounded-2xl overflow-hidden mt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/[0.05] bg-white/[0.02] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-600/10 flex items-center justify-center">
            <Terminal size={16} className="text-purple-400" />
          </div>
          <div>
            <h3 className="text-[11px] font-black text-white uppercase tracking-wider">{strategyName} 로직</h3>
            <p className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">Strategy Implementation Source</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/5 border border-emerald-500/10">
            <ShieldCheck size={12} className="text-emerald-500" />
            <span className="text-[9px] font-black text-emerald-500/80 uppercase">Verified Logic</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-500/5 border border-purple-500/10">
            <Cpu size={12} className="text-purple-400" />
            <span className="text-[9px] font-black text-purple-400/80 uppercase">Optimization Active</span>
          </div>
        </div>
      </div>

      {/* Code Editor Area */}
      <div className="relative group">
        <div className="absolute inset-0 bg-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
        <CodeEditor 
          code={loading ? "// 전략 로직을 불러오는 중..." : code} 
          onChange={onChange}
        />
      </div>

      {/* Footer Info */}
      <div className="px-6 py-3 bg-white/[0.01] border-t border-white/[0.05] flex items-center justify-between text-[10px] font-medium text-slate-500">
        <div className="flex items-center gap-4">
          <span>FRAMEWORK: FREQTRADE ADAPTER</span>
          <span className="w-1 h-1 rounded-full bg-slate-700" />
          <span>LANGUAGE: PYTHON 3.10</span>
        </div>
        <div className="text-slate-600 italic">
          * 이 코드는 백테스트 엔진에 의해 실시간으로 해석됩니다.
        </div>
      </div>
    </div>
  );
}
