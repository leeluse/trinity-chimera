"use client";

import AgentCard from "@/components/cards/AgentCard";
import { NAMES, COLORS } from "@/constants";

interface AgentsListProps {
  activeAgent: string;
  setActiveAgent: (id: string) => void;
  names?: string[];
  metrics?: {
    [agentId: string]: {
      current_score: number;
      current_return: number;
      current_sharpe: number;
      current_mdd: number;
      current_win_rate: number;
    };
  };
}

export const AgentsList = ({ activeAgent, setActiveAgent, names, metrics }: AgentsListProps) => {
  const getName = (idx: number, fallback: string) => names && names[idx] ? names[idx] : fallback;
  const getAvatar = (idx: number, fallback: string) => names && names[idx] ? names[idx].charAt(0) : fallback;
  const normalizeRatio = (value: number): number => (Math.abs(value) > 1 ? value / 100 : value);
  const formatPercent = (value: number, digits = 1): string => `${(normalizeRatio(value) * 100).toFixed(digits)}%`;

  const agentIds = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-2">
      {agentIds.map((id, idx) => {
        const m = metrics?.[id];
        return (
          <AgentCard
            key={id}
            id={id}
            name={getName(idx, id)}
            avatar={getAvatar(idx, id.charAt(0).toUpperCase())}
            strategy={
              id === 'momentum_hunter' ? 'Donchian Breakout' :
              id === 'mean_reverter' ? 'Grid + Mean Rev' :
              id === 'macro_trader' ? 'Trend Following' : 'Scalping ATR'
            }
            sharpe={m ? m.current_sharpe.toFixed(2) : '0.00'}
            mdd={m ? formatPercent(m.current_mdd, 1) : '0.0%'}
            winRate={m ? formatPercent(m.current_win_rate, 1) : '0.0%'}
            color={COLORS[idx]}
            isActive={activeAgent === id}
            onClick={() => setActiveAgent(id)}
          />
        );
      })}
    </div>
  );
};

export default AgentsList;
