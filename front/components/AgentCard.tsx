"use client";

import React from "react";

interface AgentCardProps {
  id: string;
  name: string;
  avatar: string;
  strategy: string;
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
  sharpe,
  mdd,
  winRate,
  color,
  isActive,
  onClick,
}: AgentCardProps) {
  const isPositiveSharpe = !sharpe.startsWith("-");

  return (
    <div
      onClick={onClick}
      className={`relative overflow-hidden cursor-pointer rounded-2xl transition-all duration-500 hover:-translate-y-1 p-4 ${
        isActive 
          ? "bg-white/[0.08] backdrop-blur-2xl border-white/20 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.3)]" 
          : "bg-white/[0.02] backdrop-blur-md border-white/[0.05] hover:bg-white/[0.06] hover:border-white/10"
      } border`}
      style={{ 
        boxShadow: isActive ? `0 15px 35px -5px color-mix(in srgb, ${color}, transparent 80%)` : 'none'
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
        <span className="text-[13px] font-bold tracking-tight" style={{ color }}>{name}</span>
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
