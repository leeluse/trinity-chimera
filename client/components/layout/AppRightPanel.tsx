"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { RightPanelShell } from "@/components/panel/RightPanelShell";

import ChatInterface from "@/components/features/chat/ChatInterface";
import AgentFilter from "@/components/panel/sections/AgentFilter";
import TerminalHunterPanel from "@/components/features/terminal/TerminalHunterPanel";
import { useDashboardStore } from "@/store/useDashboardStore";
import { useMemo } from "react";
import { Trophy } from "lucide-react";

interface AppRightPanelProps {
  agentIds?: string[];
  names?: string[];

  automationStatus?: any;
  onToggleAutomation?: () => void;
  backtestContext?: any;
  onBacktestGenerated?: (data: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;

  botTrades?: any[];
  scannerContent?: React.ReactNode;
}

import { useTerminalStore } from "@/components/features/terminal/terminalStore";
import { LeaderboardCard } from "@/components/features/terminal/TerminalHunterPanel";

// This is a unified panel that handles all right-side content based on context
export function AppRightPanel({
  // Shared Props
  agentIds = [],
  names = [],

  automationStatus = null,
  onToggleAutomation,
  
  // Backtest Props
  backtestContext = null,
  onBacktestGenerated,
  onApplyCode,
  

  botTrades = [],
  
  // Scanner Props
  scannerContent = null,
}: AppRightPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();
  const { logActiveBot: activeBot, setLogActiveBot: setActiveBot } = useDashboardStore();
  const { hunterLeaderboard, setSelectedSymbol } = useTerminalStore();

  const isBacktestPage = pathname === "/backtest";
  const isTerminalPage = pathname === "/terminal";
  const isDashboardPage = pathname === "/";

  // const isEvolutionView = view === "evolution"; // REmoved
  const isLogsView = (view === "logs" || (view === "" && isDashboardPage)) && false; // Disabled logs for now as they were agent-specific
  const isBacktestView = isBacktestPage && view === "";
  const isTerminalView = isTerminalPage;

  // Logic for filtering logs (borrowed from DashboardRightPanel)
  const agentNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    agentIds.forEach((id: string, idx: number) => {
      map[id] = names[idx] || id;
    });
    return map;
  }, [agentIds, names]);

  const filteredLogs = useMemo(() => {
    const isAll = !activeBot || activeBot === "ALL" || activeBot === "전체";
    const logs: unknown[] = []; // No logs for bots yet
    if (isAll) return logs;
    return logs;
  }, [activeBot]);

  return (
    <RightPanelShell>
      {/* 1. Specialized Filters */}
      {isLogsView && isDashboardPage && (
        <AgentFilter
          agentIds={agentIds}
          names={names}
          activeAgent={activeBot}
          setActiveAgent={setActiveBot}
        />
      )}

x      {/* Chat / Backtest Interface */}
      {isBacktestView && !!backtestContext && (
        <ChatInterface
          context={backtestContext}
          onBacktestGenerated={onBacktestGenerated}
          onApplyCode={onApplyCode}
        />
      )}


      {/* Terminal Leaderboard Sidebar */}
      {isTerminalView && (
        <div className="flex h-full flex-col bg-[#06070d]">
          <div className="relative border-b border-white/[0.07] bg-[#080910]/95 px-5 py-4 backdrop-blur-md">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-400/30 to-transparent" />
            <div className="flex items-center gap-2.5">
              <div className="flex h-6 w-6 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.03] shadow-[0_0_12px_rgba(139,92,246,0.12)]">
                <Trophy size={13} className="text-violet-300" />
              </div>
              <div>
                <div className="text-[11px] font-black uppercase tracking-[0.22em] text-slate-100">
                  PERFORMANCE INDEX
                </div>
                <div className="mt-0.5 text-[8px] font-bold uppercase tracking-[0.16em] text-slate-500">
                  30M Window Leaderboard
                </div>
              </div>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto no-scrollbar">
            {hunterLeaderboard.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3 opacity-20">
                <div className="h-8 w-8 border border-dashed border-cyan-500 rounded-full animate-spin" />
                <div className="text-[10px] font-bold uppercase tracking-widest">Collecting Signal Data...</div>
              </div>
            ) : (
              <div className="flex flex-col gap-2 p-3">
                {hunterLeaderboard.map((lb, idx) => (
                  <LeaderboardCard 
                    key={lb.sym} 
                    lb={lb} 
                    idx={idx} 
                    onSelect={() => setSelectedSymbol(lb.sym)} 
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Decision Logs (Standard Terminal List) - Hidden for now */}
      {isLogsView && (
        <div className="flex flex-col gap-4 p-4">
          {/* ... */}
        </div>
      )}
    </RightPanelShell>
  );
}
