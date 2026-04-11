"use client";

import { ChevronDown, Play, Zap, Save, Copy } from "lucide-react";
import { SYMBOLS } from "@/constants";

interface BacktestControlBarProps {
  symbol: string;
  setSymbol: (s: string) => void;
  timeframe: string;
  setTimeframe: (t: any) => void;
  startDate: string;
  setStartDate: (d: string) => void;
  endDate: string;
  setEndDate: (d: string) => void;
  strategy: string;
  strategies: any[];
  setStrategy: (s: string) => void;
  onRun: () => void;
}

export default function BacktestControlBar({
  symbol, setSymbol,
  timeframe, setTimeframe,
  startDate, setStartDate,
  endDate, setEndDate,
  strategy, strategies, setStrategy,
  onRun
}: BacktestControlBarProps) {
  const currentStrategyLabel = strategies.find(s => s.key === strategy)?.label || strategy;

  return (
    <div className="flex flex-col gap-4 p-4 bg-white/[0.02] border-b border-white/[0.05]">
      {/* Upper Row: Parameters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Strategy Dropdown */}
        <div className="flex items-center gap-2 px-4 py-2 bg-white/[0.03] border border-white/10 rounded-xl hover:bg-white/10 transition-all cursor-pointer group">
          <span className="text-xs font-bold text-white/90 truncate max-w-[150px]">{currentStrategyLabel}</span>
          <span className="text-xs font-bold text-[#4ade80]">+76.6%</span>
          <ChevronDown size={14} className="text-slate-500 group-hover:text-white transition-colors" />
        </div>

        {/* Symbol */}
        <Dropdown value={symbol} options={SYMBOLS} onChange={setSymbol} width="w-24" />

        {/* Timeframe */}
        <Dropdown value={timeframe} options={["1m", "5m", "15m", "1h", "4h", "1d"]} onChange={setTimeframe} width="w-20" />

        {/* Date Range */}
        <div className="flex items-center gap-2 px-4 py-2 bg-white/[0.03] border border-white/10 rounded-xl">
          <input 
            type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="bg-transparent border-none p-0 text-xs font-bold text-white/80 focus:ring-0 cursor-pointer"
          />
          <span className="text-slate-600 text-[10px] font-black">→</span>
          <input 
            type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="bg-transparent border-none p-0 text-xs font-bold text-white/80 focus:ring-0 cursor-pointer"
          />
        </div>

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button 
            onClick={onRun}
            className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-xs font-black text-slate-200 hover:bg-white/10 transition-all active:scale-95"
          >
            <Play size={14} className="fill-current capitalize" />
            백테스트 실행
          </button>
          <button className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 text-white rounded-xl text-xs font-black hover:bg-purple-500 transition-all shadow-lg shadow-purple-600/20 active:scale-95">
            <Zap size={14} className="fill-current" />
            배포
          </button>
        </div>
      </div>

      {/* Lower Row: Tabs & Tools */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 bg-white/[0.02] border border-white/5 rounded-xl">
          {["코드", "지표", "거래 내역"].map((tab, i) => (
            <button key={tab} className={`px-4 py-1.5 rounded-lg text-xs font-black tracking-tight transition-all ${i === 1 ? 'bg-white/10 text-white shadow-md' : 'text-slate-600 hover:text-slate-400'}`}>
              {tab}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4 text-slate-500">
          <button className="flex items-center gap-1.5 hover:text-purple-400 transition-colors">
            <Save size={14} />
            <span className="text-[10px] font-black uppercase tracking-widest">저장</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-purple-400 transition-colors">
            <Copy size={14} />
            <span className="text-[10px] font-black uppercase tracking-widest">복사</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function Dropdown({ value, options, onChange, width }: any) {
  return (
    <div className={`flex items-center justify-between px-4 py-2 bg-white/[0.03] border border-white/10 rounded-xl hover:bg-white/10 transition-all cursor-pointer group ${width}`}>
      <span className="text-xs font-bold text-white/90">{value}</span>
      <ChevronDown size={14} className="text-slate-500 group-hover:text-white" />
    </div>
  );
}
