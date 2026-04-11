"use client";

import AgentCard from "@/components/cards/AgentCard";
import { NAMES, COLORS } from "@/constants";

interface AgentsListProps {
  activeAgent: string;
  setActiveAgent: (id: string) => void;
  names?: string[];
}

export const AgentsList = ({ activeAgent, setActiveAgent, names }: AgentsListProps) => {
  const getName = (idx: number, fallback: string) => names && names[idx] ? names[idx] : fallback;
  const getAvatar = (idx: number, fallback: string) => names && names[idx] ? names[idx].charAt(0) : fallback;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-2">
      <AgentCard 
        id="momentum_hunter" name={getName(0, "momentum_hunter")} avatar={getAvatar(0, "M")} strategy="Donchian Breakout" 
        sharpe="2.41" mdd="-12.3%" winRate="67.4%" color={COLORS[0]} 
        isActive={activeAgent === "momentum_hunter"} 
        onClick={() => setActiveAgent("momentum_hunter")} 
      />
      <AgentCard 
        id="mean_reverter" name={getName(1, "mean_reverter")} avatar={getAvatar(1, "A")} strategy="Grid + Mean Rev" 
        sharpe="1.87" mdd="-8.1%" winRate="71.2%" color={COLORS[1]} 
        isActive={activeAgent === "mean_reverter"} 
        onClick={() => setActiveAgent("mean_reverter")} 
      />
      <AgentCard 
        id="macro_trader" name={getName(2, "macro_trader")} avatar={getAvatar(2, "N")} strategy="Trend Following" 
        sharpe="1.23" mdd="-18.9%" winRate="52.1%" color={COLORS[2]} 
        isActive={activeAgent === "macro_trader"} 
        onClick={() => setActiveAgent("macro_trader")} 
      />
      <AgentCard 
        id="chaos_agent" name={getName(3, "chaos_agent")} avatar={getAvatar(3, "C")} strategy="Scalping ATR" 
        sharpe="-0.31" mdd="-24.7%" winRate="44.8%" color={COLORS[3]} 
        isActive={activeAgent === "chaos_agent"} 
        onClick={() => setActiveAgent("chaos_agent")} 
      />
    </div>
  );
};

export default AgentsList;
