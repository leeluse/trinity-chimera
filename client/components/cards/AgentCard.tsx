"use client";

import React from "react";

interface AgentCardProps {
  id: string;
  name: string;
  avatar: string;
  strategy: string;
  status?: string;
  lastActive?: string;
  sharpe: string;
  mdd: string;
  winRate: string;
  color: string;
  isActive?: boolean;
  onClick?: () => void;
}

export default function AgentCard({
  id,
  name,
  avatar,
  strategy,
  status,
  lastActive,
  sharpe,
  mdd,
  winRate,
  color,
  isActive,
  onClick,
}: AgentCardProps) {
  const isPositiveSharpe = !sharpe.startsWith("-");

  const getStatusColor = (status?: string) => {
    switch (status) {
      case "active":
        return "bg-[#50fa7b]"; // var(--accent-green)
      case "idle":
        return "bg-[#ffb86c]"; // var(--accent-orange)
      case "error":
        return "bg-[#ff5555]"; // var(--accent-red)
      default:
        return "bg-[#6272a4]"; // var(--text-muted)
    }
  };

  const statusLabel =
    status === "active" ? "Active" :
      status === "idle" ? "Idle" :
        status === "error" ? "Error" : "Unknown";

  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden cursor-pointer rounded-xl p-4 border transition-all duration-200 ${isActive
        ? "bg-[#181835] border-[#bd93f9]/40" // var(--bg-hover) + purple border
        : "bg-[#12122b]/60 border-[rgba(189,147,249,0.12)] hover:border-[rgba(189,147,249,0.25)]" // var(--bg-card) + var(--border)
        }`}
    >
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative shrink-0">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold"
              style={{
                backgroundColor: `color-mix(in srgb, ${color}, transparent 88%)`,
                color,
                border: `1px solid color-mix(in srgb, ${color}, transparent 80%)`,
              }}
            >
              {avatar}
            </div>
            {status && (
              <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#080812] ring-2 ring-[#080812]/90 flex items-center justify-center">
                <span className={`w-1.5 h-1.5 rounded-full ${getStatusColor(status)}`} />
              </div>
            )}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-[#f8f8f2] truncate">{name}</p>
            <p
              className="text-[10px] font-medium mt-1 border rounded-sm px-2 py-0.5 leading-normal inline-block"
              style={{ color, borderColor: `color-mix(in srgb, ${color}, transparent 75%)` }}
            >
              {strategy}
            </p>
          </div>
        </div>
        {status && (
          <span className="text-[9px] font-bold uppercase tracking-widest text-[#6272a4] border border-white/5 rounded-md px-2 py-0.5">
            {statusLabel}
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2 pt-3 border-t border-[rgba(189,147,249,0.08)]">
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-wider text-[#6272a4] font-semibold">Sharpe</span>
          <span className={`text-[13px] font-bold font-mono leading-none mt-1.5 ${isPositiveSharpe ? "text-[#50fa7b]" : "text-[#ff5555]"}`}>
            {sharpe}
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-wider text-[#6272a4] font-semibold">MDD</span>
          <span className="text-[13px] font-bold font-mono text-[#ff5555] leading-none mt-1.5">{mdd}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-wider text-[#6272a4] font-semibold">Win%</span>
          <span className="text-[13px] font-bold font-mono text-[#aeb9e1] leading-none mt-1.5">{winRate}</span>
        </div>
      </div>
    </div>
  );
}
