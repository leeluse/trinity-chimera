"use client";

import AgentCard from "@/components/cards/AgentCard";
import { COLORS } from "@/constants";

import { useDashboardStore } from "@/store/useDashboardStore";

interface AgentsListProps {
  agentIds: string[];
  names?: string[];
  metrics?: {
    [agentId: string]: {
      current_equity: number;
      current_return: number;
      current_sharpe: number;
      current_mdd: number;
      current_win_rate: number;
    };
  };
  strategies?: {
    [agentId: string]: string;
  };
}

export const AgentsList = ({ agentIds, names, metrics, strategies }: AgentsListProps) => {
  const { chartActiveAgent: activeAgent, setChartActiveAgent: setActiveAgent } = useDashboardStore();
  const getName = (idx: number, fallback: string) => names && names[idx] ? names[idx] : fallback;
  const getAvatar = (idx: number, fallback: string) => names && names[idx] ? names[idx].charAt(0) : fallback;
  const normalizeRatio = (value: number): number => (Math.abs(value) > 1 ? value / 100 : value);
  const formatPercent = (value: number, digits = 1): string => `${(normalizeRatio(value) * 100).toFixed(digits)}%`;
  const strategyLabelMap: Record<string, string> = {
    momentum_hunter: "Donchian Breakout",
    mean_reverter: "Grid + Mean Rev",
    macro_trader: "Trend Following",
    chaos_agent: "Scalping ATR",
  };
  const visibleIds = agentIds.length > 0 ? agentIds : ["momentum_hunter"];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 lg:gap-4 mt-6 mb-2">
      {visibleIds.map((id, idx) => {
        const m = metrics?.[id];
        return (
          <AgentCard
            key={id}
            id={id}
            name={getName(idx, id)}
            avatar={getAvatar(idx, id.charAt(0).toUpperCase())}
            strategy={strategies?.[id] || strategyLabelMap[id] || "Adaptive Strategy"}
            sharpe={m ? m.current_sharpe.toFixed(2) : '0.00'}
            mdd={m ? formatPercent(m.current_mdd, 1) : '0.0%'}
            winRate={m ? formatPercent(m.current_win_rate, 1) : '0.0%'}
            color={COLORS[idx % COLORS.length]}
            isActive={activeAgent === id}
            onClick={() => setActiveAgent(id)}
          />
        );
      })}
    </div>
  );
};

export default AgentsList;
