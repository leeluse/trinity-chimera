"use client";

import LogCard from "@/components/cards/LogCard";
import { DashboardMetrics, DashboardProgress, EvolutionLogEvent, DecisionLogEvent } from "@/lib/api";

// Extracted Sections
import PanelTabs from "./sections/PanelTabs";
import AgentFilter from "./sections/AgentFilter";
import EvolutionLogPanel from "./sections/EvolutionLogPanel";

import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useMemo } from "react";

import { useDashboardStore } from "@/store/useDashboardStore";

interface DashboardRightPanelProps {
  agentIds: string[];
  names: string[];
  metricsData?: DashboardMetrics;
  progress?: DashboardProgress;
  evolutionEvents?: EvolutionLogEvent[];
  decisionLogs?: DecisionLogEvent[];
  botTrades?: any[];
  automationStatus?: {
    enabled: boolean;
    status: string;
    next_run_time?: string | null;
  } | null;
  onToggleAutomation?: (enabled: boolean) => void;
}

const PHASE_LABEL_MAP: Record<string, string> = {
  loop: "루프",
  triggered: "트리거",
  generating: "생성",
  generated: "생성완료",
  baseline: "기준로딩",
  validation: "검증",
  decision: "결정",
  committing: "반영",
  completed: "완료",
  failed: "실패",
  retry: "재시도",
  skipped: "스킵",
};

// --- Mock Data ---
const MOCK_LOGS = [
  {
    id: "mock-1",
    agentId: "bot_1",
    agentName: "Momentum Hunter",
    avatar: "M",
    avatarBg: "rgba(16, 185, 129, 0.1)",
    color: "#10b981",
    time: "14:32:45",
    analysis: "LONG_SIGNAL 롱 진입 @ $67,450 (BTCUSDT)",
    reason: "진입가: $67,450\n청산가: $67,890\n수익금: $285.50 (4.24%)",
    params: [],
    meta: {}
  },
  {
    id: "mock-2",
    agentId: "bot_2",
    agentName: "Mean Reverter",
    avatar: "R",
    avatarBg: "rgba(239, 68, 68, 0.1)",
    color: "#ef4444",
    time: "14:28:12",
    analysis: "SHORT_SIGNAL 숏 진입 @ $67,520 (BTCUSDT)",
    reason: "진입가: $67,520\n청산가: $67,280\n수익금: $192.40 (2.85%)",
    params: [],
    meta: {}
  },
  {
    id: "mock-3",
    agentId: "bot_1",
    agentName: "Momentum Hunter",
    avatar: "M",
    avatarBg: "rgba(16, 185, 129, 0.1)",
    color: "#10b981",
    time: "14:15:08",
    analysis: "LONG_SIGNAL 롱 진입 @ $67,120 (BTCUSDT)",
    reason: "진입가: $67,120\n청산가: $66,890\n수익금: -$115.80 (-1.72%)",
    params: [],
    meta: {}
  },
  {
    id: "mock-4",
    agentId: "bot_3",
    agentName: "Macro Trader",
    avatar: "T",
    avatarBg: "rgba(59, 130, 246, 0.1)",
    color: "#3b82f6",
    time: "13:52:33",
    analysis: "SHORT_SIGNAL 숏 진입 @ $67,680 (BTCUSDT)",
    reason: "진입가: $67,680\n청산가: $67,850\n수익금: -$108.50 (-1.60%)",
    params: [],
    meta: {}
  }
];

export default function DashboardRightPanel(props: DashboardRightPanelProps) {
  return (
    <Suspense fallback={<div className="flex-1 bg-[#060912]/30 animate-pulse" />}>
      <DashboardRightPanelContent {...props} />
    </Suspense>
  );
}

export function DashboardRightPanelContent({
  agentIds,
  names,
  metricsData,
  evolutionEvents = [],
  decisionLogs = [],
  botTrades = [],
  automationStatus,
  onToggleAutomation,
}: DashboardRightPanelProps) {
  const { logActiveAgent: activeAgent, setLogActiveAgent: setActiveAgent } = useDashboardStore();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();

  const isEvolutionView = pathname === "/" && view === "evolution";
  const isLogsView = pathname === "/" && (view === "" || view === "logs");

  const visibleAgentIds = useMemo(
    () => (agentIds.length > 0 ? agentIds : ["momentum_hunter"]),
    [agentIds]
  );
  const formatMetricDisplay = (metric: string, value: number | undefined): string => {
    if (typeof value !== "number" || Number.isNaN(value)) return "-";
    if (metric === "total_trades") return String(Math.round(value));
    if (metric === "total_return" || metric === "win_rate" || metric === "max_drawdown") {
      return `${(value * 100).toFixed(2)}%`;
    }
    return value.toFixed(3);
  };
  const agentNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    visibleAgentIds.forEach((id, idx) => {
      map[id] = names[idx] || metricsData?.agents?.[id]?.name || id;
    });
    return map;
  }, [visibleAgentIds, names, metricsData]);

  const dbLogsData = useMemo(() => {
    // 봇 정보 기반 로그 (BotTrades)
    const tradeLogs = (botTrades || []).map((trade: any, idx: number) => {
      const isLong = trade.direction === "LONG";
      const signalType = isLong ? "LONG_SIGNAL" : "SHORT_SIGNAL";
      const signalText = isLong ? "롱 진입" : "숏 진입";

      return {
        id: `trade-${idx}-${trade.close_time}`,
        agentId: trade.bot_id,
        agentName: trade.bot_name || "Bot",
        avatar: (trade.bot_name || "B").charAt(0),
        avatarBg: isLong ? "rgba(16, 185, 129, 0.1)" : "rgba(239, 68, 68, 0.1)",
        color: isLong ? "#10b981" : "#ef4444",
        time: new Date(trade.close_time).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
        analysis: `${signalType} ${signalText} @ $${trade.close_price.toLocaleString()} (${trade.symbol})`,
        reason: `진입가: $${trade.entry_price.toLocaleString()}\n청산가: $${trade.close_price.toLocaleString()}\n수익금: $${trade.pnl.toFixed(2)} (${trade.pnl_pct.toFixed(2)}%)`,
        params: [],
        meta: {}
      };
    });

    const systemLogs = (decisionLogs || [])
      .map((event) => {
        const decision = event.meta?.decision || {};
        const improvements = Array.isArray(decision.improvement_summary) ? decision.improvement_summary : [];
        const resultLabel = decision.result ? String(decision.result) : event.phase;
        const phaseLabel = PHASE_LABEL_MAP[String(event.phase || "").toLowerCase()] || event.phase || "log";
        const agentId = event.agent_id || "system";
        const agentName = event.agent_label || agentNameMap[agentId] || metricsData?.agents?.[agentId]?.name || agentId;
        const colorIdx = Math.max(0, visibleAgentIds.indexOf(agentId));

        const isRejected = (decision.result || "").toLowerCase().includes("reject");
        const isAccepted = (decision.result || "").toLowerCase() === "accepted";

        const detailLines: string[] = [];
        if (decision.reason) detailLines.push(`사유: ${decision.reason}`);
        if (improvements.length > 0) {
          detailLines.push("개선 상세:");
          improvements.slice(0, 5).forEach((item) => {
            const metricName = String(item.label || item.metric || "metric");
            const baselineDisplay = item.baseline_display || formatMetricDisplay(String(item.metric), Number(item.baseline));
            const candidateDisplay = item.candidate_display || formatMetricDisplay(String(item.metric), Number(item.candidate));
            detailLines.push(`- ${metricName}: ${baselineDisplay} → ${candidateDisplay}`);
          });
        }

        return {
          id: event.id,
          agentId,
          agentName,
          avatar: (agentName || "A").charAt(0),
          avatarBg: isRejected ? "rgba(239, 68, 68, 0.1)" : "rgba(255,255,255,0.05)",
          color: isRejected ? "#ef4444" : (isAccepted ? "#10b981" : `var(--agent-${(colorIdx % 4) + 1})`),
          time: new Date(event.created_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
          analysis: isRejected ? `[거절] ${decision.reason || resultLabel}` : `[${phaseLabel}] ${resultLabel}`,
          reason: detailLines.length > 0 ? detailLines.join("\n") : event.message,
          params: improvements.slice(0, 6).map((item) => {
            const delta = Number(item.delta || 0);
            return {
              name: String(item.label || item.metric || "metric"),
              oldVal: String(item.baseline_display || "-"),
              newVal: String(item.candidate_display || "-"),
              trend: delta > 0 ? "up" as const : delta < 0 ? "down" as const : "neutral" as const,
            };
          }),
          meta: event.meta || {},
        };
      });

    return [...MOCK_LOGS, ...tradeLogs, ...systemLogs];
  }, [decisionLogs, botTrades, visibleAgentIds, metricsData, agentNameMap]);

  const logsData = dbLogsData;
  const activeAgentName = useMemo(
    () => agentNameMap[activeAgent] || metricsData?.agents?.[activeAgent]?.name || activeAgent,
    [activeAgent, agentNameMap, metricsData]
  );

  const isAllFilter = !activeAgent ||
    activeAgent === "전체" ||
    activeAgent === "ALL" ||
    activeAgent === "all";

  const filteredLogs = useMemo(() => (isAllFilter
    ? logsData
    : logsData.filter(
      (log) =>
        log.agentId === activeAgent ||
        log.agentName === activeAgent ||
        log.agentName === activeAgentName ||
        (log.meta?.decision?.agent_alias === activeAgent)
    )), [isAllFilter, logsData, activeAgent, activeAgentName]);

  const displayLogs = (filteredLogs.length === 0 && logsData.length > 0 && isAllFilter)
    ? logsData
    : filteredLogs;

  return (
    <>
      <PanelTabs />

      {isLogsView && (
        <AgentFilter
          agentIds={visibleAgentIds}
          names={names}
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
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
        <div className="flex-1 overflow-y-auto min-h-0 bg-[#060912]/30 no-scrollbar flex flex-col">
          <div className="flex flex-col gap-4 p-4">
            {displayLogs.map((log) => (
              <LogCard
                key={log.id}
                {...log}
                onClick={() => setActiveAgent(log.agentId)}
                isActive={activeAgent === log.agentId}
              />
            ))}
            {displayLogs.length === 0 && (
              <div className="py-20 text-center opacity-30">
                <p className="text-xs italic">해당 에이전트의 최근 로그가 없습니다.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
