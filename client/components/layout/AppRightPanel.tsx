"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { RightPanelShell } from "@/components/panel/RightPanelShell";
import EvolutionLogPanel from "@/components/panel/sections/EvolutionLogPanel";
import LogCard from "@/components/shared/LogCard";
import ChatInterface from "@/components/features/chat/ChatInterface";
import AgentFilter from "@/components/panel/sections/AgentFilter";
import { useDashboardStore } from "@/store/useDashboardStore";
import { useMemo } from "react";
import { FiActivity } from "react-icons/fi";

interface AppRightPanelProps {
  agentIds?: string[];
  names?: string[];
  evolutionEvents?: any[];
  decisionLogs?: any[];
  automationStatus?: any;
  onToggleAutomation?: () => void;
  backtestContext?: any;
  onBacktestGenerated?: (data: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
  metricsData?: any;
  botTrades?: any[];
  scannerContent?: React.ReactNode;
}

// This is a unified panel that handles all right-side content based on context
export function AppRightPanel({
  // Shared Props
  agentIds = [],
  names = [],
  evolutionEvents = [],
  decisionLogs = [],
  automationStatus = null,
  onToggleAutomation,
  
  // Backtest Props
  backtestContext = null,
  onBacktestGenerated,
  onApplyCode,
  
  // Dashboard Props
  metricsData,
  botTrades = [],
  
  // Scanner Props
  scannerContent = null,
}: AppRightPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();
  const { logActiveAgent: activeAgent, setLogActiveAgent: setActiveAgent } = useDashboardStore();

  const isBacktestPage = pathname === "/backtest";
  const isScannerPage = pathname === "/scanner";
  const isDashboardPage = pathname === "/";

  const isEvolutionView = view === "evolution";
  const isLogsView = view === "logs" || (view === "" && isDashboardPage);
  const isBacktestView = isBacktestPage && view === "";
  const isScannerView = isScannerPage;

  // Logic for filtering logs (borrowed from DashboardRightPanel)
  const agentNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    agentIds.forEach((id: string, idx: number) => {
      map[id] = names[idx] || metricsData?.agents?.[id]?.name || id;
    });
    return map;
  }, [agentIds, names, metricsData]);

  const filteredLogs = useMemo(() => {
    const isAll = !activeAgent || activeAgent === "ALL" || activeAgent === "전체";
    const logs = [...(decisionLogs || [])];
    if (isAll) return logs;
    return logs.filter(l => l.agent_id === activeAgent || l.agent_label === activeAgent);
  }, [decisionLogs, activeAgent]);

  return (
    <RightPanelShell>
      {/* 1. Specialized Filters */}
      {isLogsView && isDashboardPage && (
        <AgentFilter
          agentIds={agentIds}
          names={names}
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
        />
      )}

      {/* 2. Main Content Slots */}
      
      {/* Evolution Terminal */}
      {isEvolutionView && (
        <EvolutionLogPanel
          events={evolutionEvents}
          activeAgent={activeAgent}
          automationStatus={automationStatus}
          onToggleAutomation={onToggleAutomation}
        />
      )}

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

      {/* Decision Logs (Standard Terminal List) */}
      {isLogsView && (
        <div className="flex flex-col gap-4 p-4">
          {filteredLogs.length > 0 ? (
            filteredLogs.map((log: { id: string; agent_id?: string; agent_label?: string; created_at: string; message: string; meta?: any }, idx: number) => (
              <LogCard
                key={log.id || idx}
                agentId={log.agent_id || "system"}
                agentName={log.agent_label || agentNameMap[log.agent_id || ""] || "System"}
                avatar={(log.agent_label || "S")[0]}
                time={new Date(log.created_at).toLocaleTimeString()}
                analysis={log.message}
                reason={log.meta?.decision?.reason || ""}
                color={log.agent_id ? `var(--agent-${(agentIds.indexOf(log.agent_id) % 4) + 1})` : "var(--accent-blue)"}
                isActive={activeAgent === log.agent_id}
                onClick={() => log.agent_id && setActiveAgent(log.agent_id)}
                meta={log.meta}
              />
            ))
          ) : (
            <div className="py-20 text-center opacity-30">
              <FiActivity className="w-8 h-8 mx-auto mb-4 text-primary/50" />
              <p className="text-[10px] tracking-widest uppercase">활동 기록 없음</p>
            </div>
          )}
        </div>
      )}
    </RightPanelShell>
  );
}
