"use client";

import { useEffect, useState } from "react";
import { useSearchParams, usePathname } from "next/navigation";
import { EvolutionLogEvent, DecisionLogEvent } from "@/lib/api";
import { Results, TimeFrame } from "@/types/backtest";
import { FiPlay, FiSquare, FiClock, FiActivity } from "react-icons/fi";
import LogCard from "../cards/LogCard";
import EvolutionLogPanel from "./sections/EvolutionLogPanel";
import PanelTabs from "./sections/PanelTabs";
import ChatInterface from "../chat/ChatInterface";

interface BacktestRightPanelProps {
  activeAgent: string;
  setActiveAgent: (name: string) => void;
  symbol: string;
  timeframe: TimeFrame;
  startDate: string;
  endDate: string;
  currentStrategyCode?: string;
  currentStrategyName?: string;
  results: Results | null;
  onBacktestGenerated: (payload: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
  // Evolution related props
  evolutionEvents?: EvolutionLogEvent[];
  decisionLogs?: DecisionLogEvent[];
  automationStatus?: { 
    enabled: boolean; 
    status: string; 
    next_run_time?: string | null; 
  } | null;
  onToggleAutomation?: (enabled: boolean) => void;
}

export default function BacktestRightPanel({
  activeAgent,
  setActiveAgent,
  symbol,
  timeframe,
  startDate,
  endDate,
  currentStrategyCode,
  currentStrategyName,
  results,
  onBacktestGenerated,
  onApplyCode,
  evolutionEvents = [],
  decisionLogs = [],
  automationStatus,
  onToggleAutomation,
}: BacktestRightPanelProps) {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const isBacktestPage = pathname === "/backtest";
  const view = (searchParams.get("view") || "").toLowerCase();
  
  // LOGS is the default view for the Dashboard page when no view is specified
  const isLogsView = view === "logs" || (view === "" && !isBacktestPage);
  const isEvolutionView = view === "evolution";
  const isBacktestView = isBacktestPage && view === "";

  const automationEnabled = automationStatus?.enabled ?? false;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background/50">
      <PanelTabs />
      
      <div className="flex-1 overflow-y-auto min-h-0 flex flex-col no-scrollbar">
        {isBacktestView && (
          <ChatInterface
            context={{
              symbol,
              timeframe,
              start_date: startDate,
              end_date: endDate,
              netProfitAmt: results?.netProfitAmt,
              total_return: results?.totalReturnNum,
              winRate: results?.winRateNum,
              maxDrawdown: results?.mddPct,
              sharpe: results?.sharpeRatio,
              profitFactor: results?.profitFactor,
              trades: results?.totalTradesCount,
              strategy: currentStrategyName,
              strategy_title: currentStrategyName,
              editor_code: currentStrategyCode,
              current_strategy: {
                title: currentStrategyName,
                code: currentStrategyCode,
              },
            }}
            onBacktestGenerated={onBacktestGenerated}
            onApplyCode={onApplyCode}
          />
        )}

        {isEvolutionView && (
          <EvolutionLogPanel
            events={evolutionEvents}
            activeAgent={activeAgent}
            automationStatus={automationStatus}
            onToggleAutomation={onToggleAutomation}
          />
        )}

        {isLogsView && (
          <div className="flex flex-col gap-4 p-4">
             {decisionLogs.length > 0 ? (
               decisionLogs.map((log: any, idx) => (
                 <LogCard
                   key={idx}
                   agentName={log.agent_label || log.agent_id || "system"}
                   avatar={(log.agent_label || log.agent_id || "S")[0].toUpperCase()}
                   avatarBg="bg-purple-500/20"
                   time={new Date(log.created_at).toLocaleTimeString()}
                   analysis={log.message}
                   reason={log.meta?.decision?.reason || ""}
                   color="var(--agent-1)"
                   isActive={false}
                   meta={log.meta}
                 />
               ))
             ) : (
               <div className="py-20 text-center opacity-30">
                 <div className="mb-4 flex justify-center">
                   <FiActivity className="w-8 h-8 text-purple-500/50" />
                 </div>
                 <p className="text-xs italic tracking-widest uppercase">최근 개선 이력이 없습니다.</p>
                 {automationEnabled && (
                   <p className="text-[10px] text-emerald-500/50 mt-2 animate-pulse">
                     새로운 진화 사이클이 시작되면 여기에 기록됩니다.
                   </p>
                 )}
               </div>
             )}
          </div>
        )}
      </div>
    </div>
  );
}
