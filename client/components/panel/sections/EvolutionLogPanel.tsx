"use client";

import { EvolutionLogEvent } from "@/lib/api";
import { FiActivity, FiTerminal, FiCpu, FiAlertTriangle, FiCheckCircle } from "react-icons/fi";
import type { IconType } from "react-icons";
import { COLORS } from "@/constants";

interface EvolutionLogPanelProps {
  events: EvolutionLogEvent[];
  activeAgent: string;
  isLoopRunning?: boolean;
  automationEnabled?: boolean;
  onToggleAutomation?: () => void;
}

const PHASE_CONFIG: Record<string, { color: string; icon: IconType; label: string }> = {
  boot: { color: "#61afef", icon: FiCpu, label: "부팅" },
  loop: { color: "#d19a66", icon: FiActivity, label: "루프" },
  queued: { color: "#d19a66", icon: FiActivity, label: "대기" },
  triggered: { color: "#d19a66", icon: FiActivity, label: "트리거" },
  context: { color: "#61afef", icon: FiCpu, label: "맥락" },
  baseline: { color: "#56b6c2", icon: FiActivity, label: "기준" },
  generating: { color: "#c678dd", icon: FiTerminal, label: "생성" },
  generated: { color: "#c678dd", icon: FiTerminal, label: "코드" },
  backtesting: { color: "#56b6c2", icon: FiActivity, label: "검증" },
  validation: { color: "#56b6c2", icon: FiActivity, label: "검증" },
  retry: { color: "#e5c07b", icon: FiAlertTriangle, label: "재시도" },
  committing: { color: "#98c379", icon: FiCheckCircle, label: "반영" },
  completed: { color: "#98c379", icon: FiCheckCircle, label: "완료" },
  success: { color: "#98c379", icon: FiCheckCircle, label: "성공" },
  skipped: { color: "#abb2bf", icon: FiAlertTriangle, label: "건너뜀" },
  failed: { color: "#e06c75", icon: FiAlertTriangle, label: "실패" },
  error: { color: "#e06c75", icon: FiAlertTriangle, label: "오류" },
};

const formatEventTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

const AGENT_COLOR_MAP: Record<string, string> = {
  momentum_hunter: COLORS[0],
  mean_reverter: COLORS[1],
  macro_trader: COLORS[2],
  chaos_agent: COLORS[3],
};

const AGENT_FALLBACK_PALETTE = [COLORS[0], COLORS[1], COLORS[2], COLORS[3], "#61afef", "#e5c07b"];

const colorFromAgentId = (agentId?: string | null) => {
  if (!agentId) return "#8b93a7";
  if (AGENT_COLOR_MAP[agentId]) return AGENT_COLOR_MAP[agentId];

  const key = String(agentId);
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return AGENT_FALLBACK_PALETTE[hash % AGENT_FALLBACK_PALETTE.length];
};

const withAlpha = (hex: string, alpha: string) => {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) return hex;
  return `#${normalized}${alpha}`;
};

export default function EvolutionLogPanel({
  events,
  activeAgent,
  isLoopRunning = false,
  automationEnabled = false,
  onToggleAutomation,
}: EvolutionLogPanelProps) {
  const filtered = (activeAgent === "ALL" || activeAgent === "전체")
    ? events
    : events.filter((event) => event.agent_id === activeAgent);

  return (
    <div className="flex-1 flex flex-col overflow-hidden relative group">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.08] bg-white/[0.02]">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <FiTerminal className="text-purple-400 w-4 h-4" />
            <div className="absolute -top-1 -right-1 w-1.5 h-1.5 bg-purple-400 rounded-full animate-ping" />
          </div>
          <h3 className="text-[11px] font-black tracking-[0.2em] text-white uppercase">
            진화 로그 모니터
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleAutomation}
            className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-all ${
              automationEnabled
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                : "bg-slate-500/10 border-slate-500/30 text-slate-400 hover:bg-slate-500/20"
            }`}
          >
            <div className={`w-1.5 h-1.5 rounded-full ${automationEnabled ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-[9px] font-black tracking-widest uppercase">
              {automationEnabled ? "Auto Live" : "Auto Paused"}
            </span>
          </button>
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
              const agentColor = colorFromAgentId(event.agent_id);
              return (
                <div
                  key={event.id}
                  className="group/item font-mono border-l-2 transition-all pl-3"
                  style={{ borderLeftColor: withAlpha(agentColor, "66") }}
                >
                  {/* Header Line: [LOG] Agent_Name (Time) */}
                  <div className="flex items-center gap-2 text-[10px]">
                    <span className="font-black" style={{ color: config.color }}>
                      [{config.label}]
                    </span>
                    {event.agent_label && (
                      <span className="font-bold" style={{ color: agentColor }}>
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
