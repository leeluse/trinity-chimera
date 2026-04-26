"use client";

import { FiBook } from "react-icons/fi";
import { Trade } from "@/types/backtest";

interface ExecutionLogProps {
  trades: Trade[];
  totalTradesCount: number;
  isLight?: boolean;
  fmtMoney: (v: number) => string;
}

export default function ExecutionLog({
  trades,
  totalTradesCount,
  isLight = false,
  fmtMoney,
}: ExecutionLogProps) {
  return (
    <>
      <div className={`p-4 border-b ${isLight ? "border-zinc-200" : "border-white/[0.06]"} flex justify-between items-center`}>
        <h3 className="text-sm font-bold text-purple-500 uppercase tracking-wider">Execution Log</h3>
        <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${isLight ? "bg-zinc-100" : "bg-black/40"} ${isLight ? "text-zinc-500" : "text-zinc-500"}`}>
          {trades.length > 0 ? `${totalTradesCount} TRADES` : "READY"}
        </span>
      </div>

      <div className={`flex-grow overflow-y-auto p-4 space-y-3 custom-scrollbar`}>
        {trades.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full opacity-30">
            <FiBook className="w-8 h-8 mb-2" />
            <p className="text-xs italic">No history available</p>
          </div>
        ) : (
          trades.slice().reverse().map((t, idx) => {
            const isProfit = Number(t.profitPct) >= 0;
            return (
              <div
                key={`${t.time}-${idx}`}
                className={`${isLight ? "bg-white/50" : "bg-white/[0.02]"} border border-white/[0.04] border-l-4 rounded-lg p-3 transition-colors hover:bg-white/[0.05] ${isProfit ? "border-l-green-500" : "border-l-red-500"}`}
              >
                <div className="flex justify-between items-center mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${t.type === "LONG" ? "bg-indigo-500/20 text-indigo-500" : "bg-orange-500/20 text-orange-500"}`}>
                      {t.type}
                    </span>
                    <span className={`text-[9px] font-mono ${isLight ? "text-zinc-400" : "text-zinc-500"}`}>{t.time.split(' ')[0]}</span>
                  </div>
                  <span className={`text-xs font-bold ${isProfit ? "text-green-500" : "text-red-500"}`}>
                    {isProfit ? "+" : ""}{Number(t.profitPct).toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between text-[10px] items-end">
                  <div className={`font-mono leading-tight ${isLight ? "text-zinc-500" : "text-zinc-400"}`}>
                    IN: ${t.entry.toLocaleString()}
                    <br />
                    OUT: ${t.exit.toLocaleString()}
                  </div>
                  <div className="text-right">
                    <span className={`text-[9px] font-mono ${isLight ? "text-zinc-500" : "text-zinc-500"}`}>
                      {t.exitReason}
                    </span>
                    <div className={`font-bold mt-0.5 ${isProfit ? "text-green-500" : "text-red-500"}`}>
                      {fmtMoney(t.profitAmt)}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </>
  );
}
