"use client";

import LogCard from "@/components/cards/LogCard";
import { PerformanceRow } from "@/types";
import { DashboardMetrics, DashboardProgress, EvolutionLogEvent } from "@/lib/api";

// Extracted Sections
import PanelTabs from "./sections/PanelTabs";
import AgentFilter from "./sections/AgentFilter";
import PerformanceSummary from "./sections/PerformanceSummary";
import EvolutionLogPanel from "./sections/EvolutionLogPanel";

import { COLORS } from "@/constants";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

interface DashboardRightPanelProps {
  activeAgent: string;
  setActiveAgent: (name: string) => void;
  names: string[];
  metricsData?: DashboardMetrics;
  progress?: DashboardProgress;
  evolutionEvents?: EvolutionLogEvent[];
  isLoopRunning?: boolean;
}

export default function DashboardRightPanel(props: DashboardRightPanelProps) {
  return (
    <Suspense fallback={<div className="flex-1 bg-[#060912]/30 animate-pulse" />}>
      <DashboardRightPanelContent {...props} />
    </Suspense>
  );
}

function DashboardRightPanelContent({
  activeAgent,
  setActiveAgent,
  names,
  metricsData,
  progress,
  evolutionEvents = [],
  isLoopRunning = false,
}: DashboardRightPanelProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = searchParams.get("view");

  const isEvolutionView = pathname === "/" && view === "evolution";
  const isLogsView = pathname === "/" && !view;

  const agentIds = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];
  const normalizeRatio = (value: number): number => (Math.abs(value) > 1 ? value / 100 : value);
  const formatPercent = (value: number, digits = 2): string => `${(normalizeRatio(value) * 100).toFixed(digits)}%`;
  const statusLabelMap: Record<string, string> = {
    idle: "대기 중",
    triggered: "트리거 감지",
    generating: "전략 생성 중",
    backtesting: "백테스트/검증 중",
    committing: "전략 반영 중",
    completed: "개선 완료",
    failed: "개선 실패",
  };

  // Generate dynamic performance data from API metrics
  const performanceData: PerformanceRow[] = agentIds.map((id, idx) => {
    const m = metricsData?.agents[id];
    const normalizedReturn = m ? normalizeRatio(m.current_return) : 0;
    return {
      name: names && names[idx] ? names[idx] : id,
      color: COLORS[idx],
      ret: m ? formatPercent(m.current_return, 2) : '0.00%',
      sh: m ? m.current_sharpe.toFixed(2) : '0.00',
      mdd: m ? formatPercent(m.current_mdd, 1) : '0.0%',
      pos: normalizedReturn > 0,
    };
  });

  // Map API latest_improvements to LogCard format
  const logsData = (progress?.latest_improvements || []).map((imp) => {
    const agentName = names && names[agentIds.indexOf(imp.agent_id)] ? names[agentIds.indexOf(imp.agent_id)] : imp.agent_id;
    const colorIdx = agentIds.indexOf(imp.agent_id);
    const statusKey = (imp.status || "idle").toLowerCase();
    const statusLabel = statusLabelMap[statusKey] || imp.status;
    const detailText = imp.detail || `에이전트 ${imp.agent_id}의 자동 진화 프로세스가 실행되었습니다.`;

    return {
      agentId: imp.agent_id,
      agentName: agentName,
      avatar: (agentName || "A").charAt(0),
      avatarBg: "rgba(255,255,255,0.1)",
      color: `var(--agent-${colorIdx + 1})`,
      time: new Date(imp.created_at).toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' }) + ' · ' +
            new Date(imp.created_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }),
      analysis: `${statusLabel} (진행률 ${imp.progress}%)`,
      reason: detailText,
      params: []
    };
  });

  const filteredLogs = (activeAgent === "전체" || activeAgent === "ALL")
    ? logsData
    : logsData.filter(log => log.agentId === activeAgent || log.agentName === activeAgent);

  return (
    <>
      <PanelTabs />
      
      {isLogsView && (
        <AgentFilter names={names} activeAgent={activeAgent} setActiveAgent={setActiveAgent} />
      )}
      
      {isEvolutionView && (
        <EvolutionLogPanel events={evolutionEvents} activeAgent={activeAgent} isLoopRunning={isLoopRunning} />
      )}

      {isLogsView && (
        <div className="flex-1 overflow-y-auto min-h-0 bg-[#060912]/30 no-scrollbar flex flex-col">
          <div className="flex flex-col gap-4 p-4">
            {filteredLogs.map((log, idx) => (
              <LogCard
                key={idx}
                {...log}
                onClick={() => setActiveAgent(log.agentId)}
                isActive={activeAgent === log.agentId}
              />
            ))}
            {filteredLogs.length === 0 && (
              <div className="py-20 text-center opacity-30">
                <p className="text-xs italic">해당 에이전트의 최근 로그가 없습니다.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Show summary only on logs view */}
      {isLogsView && (
        <PerformanceSummary
          performanceData={performanceData}
          activeAgent={activeAgent}
          onAgentClick={(name) => {
            const idx = performanceData.findIndex(row => row.name === name);
            if (idx !== -1) setActiveAgent(agentIds[idx]);
          }}
        />
      )}
    </>
  );
}
