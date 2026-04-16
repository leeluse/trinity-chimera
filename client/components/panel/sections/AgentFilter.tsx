"use client";

interface AgentFilterProps {
  agentIds: string[];
  names: string[];
  activeAgent: string;
  setActiveAgent: (name: string) => void;
}

export const AgentFilter = ({ agentIds, names, activeAgent, setActiveAgent }: AgentFilterProps) => {
  const options = [{ value: "ALL", label: "ALL" }].concat(
    agentIds.map((agentId, idx) => ({
      value: agentId,
      label: names[idx] || agentId,
    }))
  );

  return (
    <div className="flex gap-2 p-4 border-b border-white/[0.02] overflow-x-auto shrink-0 no-scrollbar">
      {options.map((option) => (
        <button
          key={option.value}
          className={`px-4 py-1.5 rounded-xl text-[10px] font-bold border transition-all whitespace-nowrap ${activeAgent === option.value ? 'bg-purple-400/20 border-purple-400/30 text-purple-200' : 'bg-white/[0.02] border-white/5 text-slate-500 hover:border-white/20'}`}
          onClick={() => setActiveAgent(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
};

export default AgentFilter;
