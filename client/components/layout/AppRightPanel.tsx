"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { RightPanelShell } from "@/components/panel/RightPanelShell";
import ChatInterface, { type LinePatch } from "@/components/features/chat/ChatInterface";
import AgentFilter from "@/components/panel/sections/AgentFilter";
import { useDashboardStore } from "@/store/useDashboardStore";
import { Trophy } from "lucide-react";

interface AppRightPanelProps {
  agentIds?: string[];
  names?: string[];
  backtestContext?: any;
  onBacktestGenerated?: (data: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
  onApplyPatch?: (patches: LinePatch[], title?: string) => void;
  botTrades?: any[];
}

export function AppRightPanel({
  agentIds = [],
  names = [],
  backtestContext = null,
  onBacktestGenerated,
  onApplyCode,
  onApplyPatch,
  botTrades = [],
}: AppRightPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();
  const { logActiveBot: activeBot, setLogActiveBot: setActiveBot } = useDashboardStore();

  const isBacktestPage = pathname === "/backtest";
  const isTerminalPage = pathname === "/terminal";
  const isDashboardPage = pathname === "/";

  const isLogsView = (view === "logs" || (view === "" && isDashboardPage)) && false; 
  const isBacktestView = isBacktestPage && view === "";
  const isTerminalView = isTerminalPage;

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

      {/* Chat / Backtest Interface */}
      {isBacktestView && !!backtestContext && (
        <ChatInterface
          context={backtestContext}
          onBacktestGenerated={onBacktestGenerated}
          onApplyCode={onApplyCode}
          onApplyPatch={onApplyPatch}
        />
      )}

      {/* Terminal View */}
      {isTerminalView && (
        <div className="flex h-full flex-col bg-[#06070d] items-center justify-center p-8 text-center">
           <Trophy size={32} className="text-violet-500/20 mb-4" />
           <div className="text-[11px] font-black uppercase tracking-[0.22em] text-slate-500">
             Terminal Active
           </div>
           <div className="mt-2 text-[9px] font-bold uppercase tracking-[0.16em] text-slate-600">
             Performance metrics streaming...
           </div>
        </div>
      )}
    </RightPanelShell>
  );
}
