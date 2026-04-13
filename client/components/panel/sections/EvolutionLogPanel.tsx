"use client";

import { EvolutionLogEvent } from "@/lib/api";
import { FiActivity, FiTerminal, FiCpu, FiAlertTriangle, FiCheckCircle } from "react-icons/fi";

interface EvolutionLogPanelProps {
  events: EvolutionLogEvent[];
  activeAgent: string;
  isLoopRunning?: boolean;
}

const PHASE_CONFIG: Record<string, { color: string; icon: any; label: string }> = {
  boot: { color: "#61afef", icon: FiCpu, label: "BOOT" },
  loop: { color: "#d19a66", icon: FiActivity, label: "LOOP" },
  generating: { color: "#c678dd", icon: FiTerminal, label: "GEN" },
  backtesting: { color: "#56b6c2", icon: FiActivity, label: "TEST" },
  validation: { color: "#56b6c2", icon: FiActivity, label: "VAL" },
  committing: { color: "#98c379", icon: FiCheckCircle, label: "COMMIT" },
  success: { color: "#98c379", icon: FiCheckCircle, label: "OK" },
  failed: { color: "#e06c75", icon: FiAlertTriangle, label: "FAIL" },
  error: { color: "#e06c75", icon: FiAlertTriangle, label: "ERR" },
};

const formatEventTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

export default function EvolutionLogPanel({
  events,
  activeAgent,
  isLoopRunning = false,
}: EvolutionLogPanelProps) {
  const filtered = (activeAgent === "ALL" || activeAgent === "전체")
    ? events
    : events.filter((event) => event.agent_id === activeAgent);

  return (
    <div className="flex-1 m-3 rounded-2xl border border-white/[0.05] bg-[#0c1221]/80 backdrop-blur-xl flex flex-col overflow-hidden shadow-2xl relative group">
      {/* Dynamic Background Glow */}
      <div className="absolute top-0 left-1/4 w-1/2 h-1/2 bg-purple-500/10 blur-[100px] -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.08] bg-white/[0.02]">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <FiTerminal className="text-purple-400 w-4 h-4" />
            <div className="absolute -top-1 -right-1 w-1.5 h-1.5 bg-purple-400 rounded-full animate-ping" />
          </div>
          <h3 className="text-[11px] font-black tracking-[0.2em] text-white uppercase">
            Evolution Monitor
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.03] border border-white/10">
            <div className={`w-1.5 h-1.5 rounded-full ${isLoopRunning ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-[9px] font-bold text-slate-300 uppercase tracking-wider">
              {isLoopRunning ? "Active" : "Idle"}
            </span>
          </div>
        </div>
      </div>

      {/* Log Feed */}
      <div className="flex-1 overflow-y-auto px-4 py-4 no-scrollbar space-y-3 font-mono">
        {filtered.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center opacity-20">
            <FiActivity className="w-8 h-8 mb-3 text-purple-400" />
            <p className="text-[10px] uppercase font-bold tracking-widest text-white">Awaiting System Pulse...</p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((event) => {
              const config = PHASE_CONFIG[event.phase?.toLowerCase()] || { color: "#abb2bf", icon: FiTerminal, label: "LOG" };
              return (
                <div
                  key={event.id}
                  className="group/item font-mono border-l-2 border-transparent hover:border-white/20 transition-all pl-3"
                >
                  {/* Header Line: [LOG] Agent_Name (Time) */}
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="font-black" style={{ color: config.color }}>
                      [{config.label}]
                    </span>
                    {event.agent_label && (
                      <span className="font-bold text-indigo-400">
                        {event.agent_label.replace(/\s/g, '_')}
                      </span>
                    )}
                    <span className="text-slate-500 text-[9px]" suppressHydrationWarning>
                      ({formatEventTime(event.created_at)})
                    </span>
                  </div>

                  {/* Message Line: Indented */}
                  <div className="pl-6 mt-1.5">
                    <p className="text-[11px] leading-relaxed text-slate-300 antialiased break-words tracking-tight group-hover/item:text-white transition-colors">
                      {event.message}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="h-20" /> {/* Bottom Spacing for scrolling */}
      </div>

      {/* Footer Info */}
      <div className="px-5 py-2 border-t border-white/[0.05] bg-black/20 flex justify-between items-center shrink-0">
        <span className="text-[9px] font-bold text-slate-600 tracking-widest flex items-center gap-2">
          <FiCpu className="w-3 h-3" /> TRINITY_ORCH_V1.1
        </span>
        <span className="text-[9px] font-mono text-slate-500">
          SEQ_{Math.max(0, ...filtered.map(e => e.id)).toString().padStart(4, '0')}
        </span>
      </div>
    </div>
  );
}
