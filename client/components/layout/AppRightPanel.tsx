"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { RightPanelShell } from "@/components/panel/RightPanelShell";

import ChatInterface from "@/components/features/chat/ChatInterface";
import AgentFilter from "@/components/panel/sections/AgentFilter";
import TerminalHunterPanel from "@/components/features/terminal/TerminalHunterPanel";
import { useDashboardStore } from "@/store/useDashboardStore";
import { useMemo } from "react";

interface AppRightPanelProps {
  agentIds?: string[];
  names?: string[];

  automationStatus?: unknown;
  onToggleAutomation?: () => void;
  backtestContext?: unknown;
  onBacktestGenerated?: (data: unknown) => void;
  onApplyCode?: (code: string, name?: string, payload?: unknown) => void;

  botTrades?: unknown[];
  scannerContent?: React.ReactNode;
}

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

  const isBacktestPage = pathname === "/backtest";
  const isScannerPage = pathname === "/scanner";
  const isTerminalPage = pathname === "/terminal";
  const isDashboardPage = pathname === "/";

  // const isEvolutionView = view === "evolution"; // REmoved
  const isLogsView = (view === "logs" || (view === "" && isDashboardPage)) && false; // Disabled logs for now as they were agent-specific
  const isBacktestView = isBacktestPage && view === "";
  const isScannerView = isScannerPage;
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

      {/* 2. Main Content Slots */}
      


      {/* Chat / Backtest Interface */}
      {isBacktestView && backtestContext && (
        <ChatInterface
          context={backtestContext}
          onBacktestGenerated={onBacktestGenerated}
          onApplyCode={onApplyCode}
        />
      )}

      {/* Scanner Sidebar Content */}
      {isScannerView && scannerContent && (
        <div className="flex-1 overflow-y-auto no-scrollbar">
          {scannerContent}
        </div>
      )}

      {/* Terminal Hunter Fusion Content */}
      {isTerminalView && <TerminalHunterPanel />}

      {/* Decision Logs (Standard Terminal List) - Hidden for now */}
      {isLogsView && (
        <div className="flex flex-col gap-4 p-4">
          {/* ... */}
        </div>
      )}
    </RightPanelShell>
  );
}
