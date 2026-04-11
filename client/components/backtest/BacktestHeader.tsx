"use client";

import { ChevronDown, Play, Zap, Save, Copy } from "lucide-react";
import { SYMBOLS } from "@/constants";

interface BacktestHeaderProps {
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
  activeTab: string;
  onTabChange: (tab: string) => void;
  loading?: boolean;
}

export default function BacktestHeader({
  symbol, setSymbol,
  timeframe, setTimeframe,
  startDate, setStartDate,
  endDate, setEndDate,
  strategy,
  strategies,
  setStrategy,
  onRun,
  activeTab,
  onTabChange,
  loading
}: BacktestHeaderProps) {
  const currentStrategyLabel = strategies.find(s => s.key === strategy)?.label || strategy;
  const TABS = ["코드", "지표", "거래 내역"];

  return (
    <div className="flex flex-col gap-3 p-3 border-b border-white/[0.05] relative z-20">
      {/* ... (rest of the component remains the same for the top row) */}
      {/* Top Row: Parameters & Primary Actions */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Strategy Selector */}
        <div className="relative group">
          <select 
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="appearance-none bg-white/[0.03] border border-white/10 rounded-xl px-4 py-2 pr-10 text-xs font-bold text-white/90 cursor-pointer focus:ring-1 focus:ring-purple-500/50 outline-none hover:bg-white/10 transition-all"
          >
            {strategies.map(s => <option key={s.key} value={s.key} className="bg-[#0d0d1a]">{s.label}</option>)}
          </select>
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none flex items-center gap-2">
            <ChevronDown size={14} className="text-slate-500" />
          </div>
        </div>

        {/* Symbol */}
        <DropdownSelect 
          value={symbol} 
          options={SYMBOLS} 
          onChange={setSymbol} 
          width="w-28" 
        />

        {/* Timeframe */}
        <DropdownSelect 
          value={timeframe} 
          options={["1m", "5m", "15m", "1h", "4h", "1d"]} 
          onChange={setTimeframe} 
          width="w-24" 
        />

        {/* Date Range Group */}
        <div className="flex items-center gap-2 px-4 py-2 bg-white/[0.03] border border-white/10 rounded-xl">
          <input 
            type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            className="bg-transparent border-none p-0 text-[11px] font-bold text-white/80 focus:ring-0 cursor-pointer [color-scheme:dark]"
          />
          <span className="text-slate-600 text-[10px] font-black mx-1">→</span>
          <input 
            type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            className="bg-transparent border-none p-0 text-[11px] font-bold text-white/80 focus:ring-0 cursor-pointer [color-scheme:dark]"
          />
        </div>

        <div className="flex-1" />

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button 
            onClick={onRun}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#9f7aea]/10 border border-[#9f7aea]/20 rounded-xl text-xs font-bold text-[#9f7aea] hover:bg-[#9f7aea]/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play size={14} className={`${loading ? 'animate-pulse' : 'fill-current'}`} />
            {loading ? "작업 중..." : "백테스트 실행"}
          </button>
          <button className="flex items-center gap-2 px-5 py-2.5 bg-[#90d579ff] text-[#060912] rounded-xl text-xs font-black hover:brightness-110 transition-all shadow-lg shadow-[#90d579ff]/20 active:scale-95">
            <Zap size={14} className="fill-current" />
            배포
          </button>
        </div>
      </div>

      {/* Bottom Row: Tabs & Tools */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 bg-white/[0.02] border border-white/5 rounded-xl">
          {TABS.map((tab) => (
            <button 
              key={tab} 
              onClick={() => onTabChange(tab)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold tracking-tight transition-all ${activeTab === tab ? 'bg-[#9f7aea]/20 text-[#a78bfa] shadow-md border border-[#9f7aea]/30' : 'text-slate-600 hover:text-slate-400'}`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4 text-slate-500">
          <button className="flex items-center gap-1.5 hover:text-purple-400 transition-colors group">
            <Save size={14} className="group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-black uppercase tracking-widest">저장</span>
          </button>
          <button className="flex items-center gap-1.5 hover:text-purple-400 transition-colors group">
            <Copy size={14} className="group-hover:scale-110 transition-transform" />
            <span className="text-[10px] font-black uppercase tracking-widest">복사</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function DropdownSelect({ value, options, onChange, width }: any) {
  return (
    <div className={`relative group ${width}`}>
      <select 
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none w-full bg-white/[0.03] border border-white/10 rounded-xl px-4 py-2 pr-10 text-xs font-bold text-white/90 cursor-pointer focus:ring-1 focus:ring-purple-500/50 outline-none hover:bg-white/10 transition-all"
      >
        {options.map((opt: string) => <option key={opt} value={opt} className="bg-[#0d0d1a]">{opt}</option>)}
      </select>
      <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none group-hover:text-white" />
    </div>
  );
}
