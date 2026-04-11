"use client";

interface AgentFilterProps {
  names: string[];
  activeAgent: string;
  setActiveAgent: (name: string) => void;
}

export const AgentFilter = ({ names, activeAgent, setActiveAgent }: AgentFilterProps) => {
  const filteredNames = ['ALL', ...names].filter(n => n !== 'BTC BnH');

  return (
    <div className="flex gap-2 p-4 border-b border-white/[0.02] overflow-x-auto shrink-0 no-scrollbar">
      {filteredNames.map(name => (
        <button
          key={name}
          className={`px-4 py-1.5 rounded-xl text-[10px] font-bold border transition-all whitespace-nowrap ${activeAgent === name ? 'bg-purple-400/20 border-purple-400/30 text-purple-200' : 'bg-white/[0.02] border-white/5 text-slate-500 hover:border-white/20'}`}
          onClick={() => setActiveAgent(name)}
        >
          {name}
        </button>
      ))}
    </div>
  );
};

export default AgentFilter;
