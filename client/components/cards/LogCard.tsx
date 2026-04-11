"use client";

import React from "react";

interface LogCardProps {
  agentName: string;
  avatar: string;
  avatarBg: string;
  color: string;
  time: string;
  analysis: string;
  reason: string;
  onClick?: () => void;
  isActive?: boolean;
  params?: Array<{
    name: string;
    oldVal: string;
    newVal: string;
    trend?: "up" | "down" | "neutral";
  }>;
}

export default function LogCard({
  agentName,
  avatar,
  avatarBg,
  color,
  time,
  analysis,
  reason,
  onClick,
  isActive,
  params,
}: LogCardProps) {
  return (
    <div 
      onClick={onClick}
      className={`bg-white/[0.03] backdrop-blur-md border rounded-2xl overflow-hidden shrink-0 shadow-xl group cursor-pointer ${
        isActive ? 'border-white/20 bg-white/[0.08]' : 'border-white/[0.05]'
      }`}
    >
      <div className="flex items-center justify-between px-4 py-3 sm:py-4">
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-sm font-bold"
            style={{ background: avatarBg, color }}
          >
            {avatar}
          </div>
          <span className="text-sm font-semibold" style={{ color }}>{agentName}</span>
        </div>
        <span className="text-[11px] text-[#4a5a7a] font-mono">{time}</span>
      </div>

      <div className="flex flex-col px-4 pb-4 gap-2 sm:gap-4">
        <div className="flex flex-col gap-2">
          <div className="text-[10px] font-bold tracking-widest uppercase text-[#5a6b8c] border-b border-white/[0.03] pb-2">현재 전략 분석</div>
          <p className="text-[12.5px] leading-relaxed text-[#94a3b8] [&_span]:text-white [&_span]:font-semibold pt-1" dangerouslySetInnerHTML={{ __html: analysis }} />
        </div>

        {params && params.length > 0 && (
          <div className="flex flex-col gap-3 pt-3 sm:pt-4 border-t border-white/[0.03]">
            <div className="flex items-center gap-2">
              <div className="w-1 h-3.5 bg-purple-400/50 rounded-full" />
              <div className="text-[10px] font-bold tracking-widest uppercase text-[#5a6b8c]">파라미터 변경 내역</div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {params.map((p, idx) => (
                <div key={idx} className="bg-white/[0.04] rounded-lg py-1.5 px-2.5 hover:bg-white/[0.07] transition-colors flex flex-col gap-1">
                  <div className="text-[10px] font-bold text-[#4a5a7a] font-mono tracking-tight">{p.name}</div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <span className="text-[#4a5a7a]/60 line-through decoration-[#fc8181]/30">{p.oldVal}</span>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-[#4a5a7a]/40">
                        <path d="M5 12h14m-7-7l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span className={`font-bold ${p.trend === 'up' ? 'text-[#4ade80]' :
                        p.trend === 'down' ? 'text-[#f87171]' :
                          'text-[#bd93f9]'
                        }`}>{p.newVal}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
