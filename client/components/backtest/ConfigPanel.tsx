"use client";

import { SYMBOLS, LEVERAGES } from "@/constants";
import { FiBook } from "react-icons/fi";

interface ConfigPanelProps {
  symbol: string;
  setSymbol: (v: string) => void;
  startDate: string;
  setStartDate: (v: string) => void;
  endDate: string;
  setEndDate: (v: string) => void;
  leverage: number;
  setLeverage: (v: number) => void;
  framework: string;
  setFramework: (v: string) => void;
  strategy: string;
  setStrategy: (v: string) => void;
  strategies: any[];
  handleStartTest: () => void;
  runAiAnalysis: () => void;
  results: any;
  cardClass: string;
  inputClass: string;
}

export const ConfigPanel = ({
  symbol, setSymbol,
  startDate, setStartDate,
  endDate, setEndDate,
  leverage, setLeverage,
  framework, setFramework,
  strategy, setStrategy,
  strategies,
  handleStartTest,
  runAiAnalysis,
  results,
  cardClass,
  inputClass
}: ConfigPanelProps) => {
  return (
    <div className="p-0 bg-transparent">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6 mb-8 border-t border-white/[0.05] pt-6">
        <Field label="Symbol">
          <select value={symbol} onChange={e => setSymbol(e.target.value)} className={inputClass}>
            {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Start Date">
          <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className={inputClass} />
        </Field>
        <Field label="End Date">
          <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Leverage">
          <select value={leverage} onChange={e => setLeverage(Number(e.target.value))} className={inputClass}>
            {LEVERAGES.map(l => <option key={l} value={l}>{l}x</option>)}
          </select>
        </Field>
        <Field label="Framework">
          <select value={framework} onChange={e => setFramework(e.target.value)} className={`${inputClass} text-cyan-500`}>
            <option value="freqtrade_adapter">freqtrade_adapter</option>
          </select>
        </Field>
        <Field label="Strategy">
          <select value={strategy} onChange={e => setStrategy(e.target.value)} className={`${inputClass} text-purple-500`}>
            {strategies.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </Field>
      </div>
      <div className="flex gap-4">
        <button 
          onClick={handleStartTest} 
          className="flex-grow bg-purple-600 hover:bg-purple-700 text-white font-black py-3 rounded-xl transition-all active:scale-[0.98] shadow-lg shadow-purple-600/20"
        >
          START BACKTEST
        </button>
        {results && (
          <button 
            onClick={runAiAnalysis} 
            className="px-8 bg-cyan-600 hover:bg-cyan-700 text-white font-black py-3 rounded-xl flex items-center gap-2 transition-all active:scale-[0.98] shadow-lg shadow-cyan-600/20"
          >
            <FiBook /> AI ANALYSIS
          </button>
        )}
      </div>
    </div>
  );
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-[10px] font-black text-zinc-500 uppercase tracking-[0.2em]">{label}</label>
      {children}
    </div>
  );
}

export default ConfigPanel;
