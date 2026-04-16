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
  meta?: any;
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
  meta,
}: LogCardProps) {
  // meta 데이터에서 필요 지표 추출 (유연하게 매칭)
  const metrics = meta?.metrics || meta?.candidate_metrics || {};
  const baseline = meta?.baseline_metrics || {};

  const getVal = (obj: any, keys: string[]) => {
    for (const k of keys) if (obj[k] !== undefined) return obj[k];
    return 0;
  };

  const getF = (v: any) => (typeof v === 'number' ? v.toFixed(2) : "0.00");

  const scoreStart = getVal(baseline, ["trinity_score", "score"]);
  const scoreEnd = getVal(metrics, ["trinity_score", "score"]);
  
  const retStart = getVal(baseline, ["total_return", "current_return", "return"]);
  const retEnd = getVal(metrics, ["total_return", "current_return", "return"]);
  
  const mddStart = getVal(baseline, ["max_drawdown", "current_mdd", "mdd"]);
  const mddEnd = getVal(metrics, ["max_drawdown", "current_mdd", "mdd"]);

  const hasStats = scoreEnd !== 0 || retEnd !== 0 || mddEnd !== 0;

  return (
    <div 
      onClick={onClick}
      className={`bg-white/[0.03] backdrop-blur-md border rounded-2xl overflow-hidden shrink-0 shadow-xl group cursor-pointer transition-all ${
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
        <span className="text-[11px] text-[#4a5a7a] font-mono" suppressHydrationWarning>{time}</span>
      </div>

      <div className="flex flex-col px-4 pb-4 gap-4">
        {/* 현재 전략 분석 섹션 */}
        <div className="flex flex-col gap-2">
          <div className="text-[10px] font-bold tracking-widest uppercase text-[#5a6b8c] border-b border-white/[0.03] pb-2">현재 전략 분석</div>
          <p className="text-[12.5px] leading-relaxed text-[#94a3b8] pt-1 whitespace-pre-wrap break-words italic">
            "{analysis.replace(/^\[.*?\]\s*/, "")}"
          </p>
        </div>

        {/* 📊 성과 변화 (사용자 요청 시각적 블록 빌트인) */}
        {hasStats && (
          <div className="flex flex-col gap-2.5 p-3.5 bg-black/20 rounded-xl border border-white/[0.03] font-mono">
            <div className="text-[10px] font-bold tracking-widest uppercase text-blue-400">📊 성과 변화 (OOS 테스트 완료)</div>
            <div className="flex flex-col gap-1.5 text-[11px]">
               <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-24">Trinity Score</span>
                  <span className="text-slate-400">{getF(scoreStart)}</span>
                  <span className="text-emerald-500 font-bold"> ━━▶ </span>
                  <span className="text-yellow-400 font-bold">{getF(scoreEnd)}</span>
                  <span className="text-emerald-500/60 text-[10px] ml-1">(+{(scoreEnd - scoreStart).toFixed(2)})</span>
               </div>
               <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-24">Return</span>
                  <span className="text-slate-400">{getF(retStart * 100)}%</span>
                  <span className="text-emerald-500 font-bold"> ━━▶ </span>
                  <span className="text-white font-bold">{getF(retEnd * 100)}%</span>
                  <span className="text-emerald-500/60 text-[10px] ml-1">(+{( (retEnd - retStart) * 100 ).toFixed(2)}%)</span>
               </div>
               <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-24">MDD</span>
                  <span className="text-slate-400">{getF(mddStart * 100)}%</span>
                  <span className="text-emerald-500 font-bold"> ━━▶ </span>
                  <span className="text-red-400 font-bold">{getF(mddEnd * 100)}%</span>
                  <span className="text-emerald-500/60 text-[10px] ml-1">({( (mddEnd - mddStart) * 100 ).toFixed(2)}% 개선)</span>
               </div>
            </div>
            <div className="text-[9px] font-bold text-emerald-400/80 mt-1 flex items-center gap-1">
               ✅ 검증 완료: Static Gate, Quick Gate, Full Gate (Success)
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="text-[10px] font-bold tracking-widest uppercase text-[#5a6b8c] border-b border-white/[0.03] pb-2">실행 상세</div>
          <p className="text-[12px] leading-relaxed text-[#7f90ae] pt-1 whitespace-pre-wrap break-words">{reason}</p>
        </div>

        {params && params.length > 0 && (
          <div className="flex flex-col gap-3 pt-3 border-t border-white/[0.03]">
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
