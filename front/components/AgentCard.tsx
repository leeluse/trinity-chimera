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
      case 'active': return 'text-green-400';
      case 'idle': return 'text-yellow-400';
      case 'error': return 'text-red-400';
      default: return 'text-slate-500';
    }
  };

  const formatTimeAgo = (timestamp?: string) => {
    if (!timestamp) return 'N/A';
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    return `${diffHours}h ago`;
  };

  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden cursor-pointer rounded-xl transition-all duration-300 hover:-translate-y-1 p-[14px] border ${isActive
          ? "bg-white/[0.08] backdrop-blur-2xl border-white/20"
          : "bg-white/[0.02] backdrop-blur-md border-white/[0.05] hover:bg-white/[0.06] hover:border-white/10"
        }`}
      style={{
        boxShadow: isActive ? `0 15px 35px -5px color-mix(in srgb, ${color}, transparent 80%), 0 20px 40px -15px rgba(0,0,0,0.3)` : 'none'
      }}
    >
      {/* Accent Glass Glow */}
      {isActive && (
        <div
          className="absolute inset-x-0 top-0 h-24 opacity-20 pointer-events-none blur-3xl rounded-full"
          style={{ background: `radial-gradient(circle at 50% 0%, ${color}, transparent 70%)` }}
        />
      )}

      <div className="flex items-center gap-2 mb-3">
        <div className="relative">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{
              backgroundColor: `color-mix(in srgb, ${color}, transparent 85%)`,
              color: color,
              border: `1px solid color-mix(in srgb, ${color}, transparent 80%)`
            }}
          >
            {avatar}
          </div>
          {status && (
            <div className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full ${getStatusColor(status)}`}>
              <div className={`w-full h-full rounded-full ${getStatusColor(status).replace('text-', 'bg-')} animate-pulse`} />
            </div>
          )}
        </div>
        <div className="flex flex-col">
          <span className="text-[13px] font-bold tracking-tight" style={{ color }}>{name}</span>
          {lastActive && (
            <span className="text-[8px] text-slate-500 font-mono">
              {formatTimeAgo(lastActive)}
            </span>
          )}
        </div>
      </div>

      <div className="text-[10px] text-[#4a5a7a] mb-2 font-mono truncate">{strategy}</div>

      <div className="flex justify-between mt-2 gap-2">
        <div className="text-center flex-1">
          <div className="text-[9px] text-[#4a5a7a] uppercase tracking-wider">Sharpe</div>
          <div className={`text-[11px] font-semibold font-mono ${isPositiveSharpe ? "text-[#68d391]" : "text-[#fc8181]"}`}>
            {sharpe}
          </div>
        </div>
        <div className="text-center flex-1">
          <div className="text-[9px] text-[#4a5a7a] uppercase tracking-wider">MDD</div>
          <div className="text-[11px] font-semibold font-mono text-[#fc8181]">{mdd}</div>
        </div>
        <div className="text-center flex-1">
          <div className="text-[9px] text-[#4a5a7a] uppercase tracking-wider">Win%</div>
          <div className="text-[11px] font-semibold font-mono text-[#8b9fc6]">{winRate}</div>
        </div>
      </div>
    </div>
  );
}
