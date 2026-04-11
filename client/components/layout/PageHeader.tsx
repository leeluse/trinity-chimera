"use client";

import { ReactNode } from "react";

interface PageHeaderProps {
  statusText?: string;
  statusColor?: string;
  isLoading?: boolean;
  extra?: ReactNode;
}

export const PageHeader = ({
  statusText = "System Live",
  statusColor = "green",
  isLoading = false,
  extra
}: PageHeaderProps) => {
  const isGreen = statusColor === "green";
  const isBlue = statusColor === "blue";

  const getStatusStyles = () => {
    if (isGreen) return "bg-green-500/10 border-green-500/20 text-green-400 shadow-[0_0_8px_rgba(74,222,128,0.1)]";
    if (isBlue) return "bg-purple-500/10 border-purple-500/30 text-[#bd93f9] shadow-[0_0_10px_rgba(189,147,249,0.2)]";
    return "bg-slate-500/10 border-slate-500/20 text-slate-400";
  };

  const getDotStyles = () => {
    if (isGreen) return "bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)]";
    if (isBlue) return "bg-[#bd93f9] shadow-[0_0_10px_rgba(189,147,249,0.7)]";
    return "bg-slate-400";
  };

  return (
    <header className="flex items-center justify-between px-4 md:px-8 py-3 md:py-4 border-b border-white/[0.05] bg-white/[0.02] backdrop-blur-2xl sticky top-0 z-[100] shadow-2xl">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="relative w-9 h-9 flex items-center justify-center">
            <div className="absolute inset-0 bg-gradient-to-tr from-[#6366f1] via-[#8b5cf6] to-[#ec4899] rounded-lg rotate-45 blur-[8px] opacity-40 animate-pulse"></div>
            <div className="relative w-full h-full bg-[#0b0b1a] border border-white/20 rounded-lg rotate-45 flex items-center justify-center overflow-hidden">
              <div className="rotate-[-45deg] flex items-center justify-center">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L2 12L12 22L22 12L12 2ZM12 6L18 12L12 18L6 12L12 6Z" fill="white" fillOpacity="0.9" />
                  <rect x="11" y="11" width="2" height="2" fill="white" />
                </svg>
              </div>
            </div>
          </div>
          <div className="flex flex-col pl-2">
            <span className="text-lg font-black text-white tracking-[-0.02em] leading-tight">TRINITY<span className="text-[#8b5cf6]">CHIMERA</span></span>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-bold text-slate-500 tracking-[0.3em] uppercase leading-none">V2.4 Terminal</span>
              <div className="h-[1px] w-4 bg-slate-800"></div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-6">
        {extra}
        <div className={`flex items-center gap-2 px-3 py-1 rounded-full border transition-all duration-300 ${getStatusStyles()}`}>
          <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${getDotStyles()}`}></div>
          <span className="text-[10px] font-bold uppercase tracking-wider">
            {isLoading ? '로딩 중...' : statusText}
          </span>
        </div>
      </div>
    </header>
  );
};

export default PageHeader;
