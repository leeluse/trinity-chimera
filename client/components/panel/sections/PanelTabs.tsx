"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { History, FileSearch, Bot, Terminal as TerminalIcon, Skull } from "lucide-react";

const PanelTabsContent = () => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();

  const isBacktestPage = pathname === "/backtest";
  const isDashboardPage = pathname === "/";
  const isTerminalPage = pathname === "/terminal";
  const isScannerPage = pathname === "/scanner";

  // 탭 활성화 상태 판별
  const isLogsActive = isDashboardPage && (view === "logs" || view === "");
  const isScannerActive = isScannerPage;
  const isTerminalActive = isTerminalPage;
  const isCrimeActive = view === "crime";
  const isBacktestActive = isBacktestPage;

  return (
    <div className="sticky top-0 z-[220] flex h-11 bg-background border-b border-white/[0.05] shrink-0 pointer-events-auto">
      <Link
        href="/?view=logs"
        className={`flex-1 flex items-center justify-center gap-1.5 group transition-all relative uppercase cursor-pointer ${isLogsActive ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
          }`}
      >
        <FileSearch size={12} className={isLogsActive ? "text-indigo-400" : "text-slate-600 transition-colors group-hover:text-slate-400"} />
        <span className="text-[9px] font-bold tracking-wider leading-none">LOGS</span>
        {isLogsActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_-4px_10px_rgba(99,102,241,0.3)]" />}
      </Link>

      <Link
        href="/scanner"
        className={`flex-1 flex items-center justify-center gap-1.5 group transition-all relative uppercase cursor-pointer ${isScannerActive ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
          }`}
      >
        <Bot size={12} className={isScannerActive ? "text-indigo-400" : "text-slate-600 transition-colors group-hover:text-slate-400"} />
        <span className="text-[9px] font-bold tracking-wider leading-none">SCANNER</span>
        {isScannerActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_-4px_10px_rgba(99,102,241,0.3)]" />}
      </Link>

      <Link
        href="/terminal"
        className={`flex-1 flex items-center justify-center gap-1.5 group transition-all relative uppercase cursor-pointer ${isTerminalActive ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
          }`}
      >
        <TerminalIcon size={12} className={isTerminalActive ? "text-indigo-400" : "text-slate-600 transition-colors group-hover:text-slate-400"} />
        <span className="text-[9px] font-bold tracking-wider leading-none">TERMINAL</span>
        {isTerminalActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_-4px_10px_rgba(99,102,241,0.3)]" />}
      </Link>

      <Link
        href="/?view=crime"
        className={`flex-1 flex items-center justify-center gap-1.5 group transition-all relative uppercase cursor-pointer ${isCrimeActive ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
          }`}
      >
        <Skull size={12} className={isCrimeActive ? "text-indigo-400" : "text-slate-600 transition-colors group-hover:text-slate-400"} />
        <span className="text-[9px] font-bold tracking-wider leading-none">CRIME</span>
        {isCrimeActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_-4px_10px_rgba(99,102,241,0.3)]" />}
      </Link>

      <Link
        href="/backtest"
        className={`flex-1 flex items-center justify-center gap-1.5 group transition-all relative uppercase cursor-pointer ${isBacktestActive ? 'text-indigo-400 bg-indigo-500/5' : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
          }`}
      >
        <History size={12} className={isBacktestActive ? "text-indigo-400" : "text-slate-600 transition-colors group-hover:text-slate-400"} />
        <span className="text-[9px] font-bold tracking-wider leading-none">BACKTEST</span>
        {isBacktestActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500 shadow-[0_-4px_10px_rgba(99,102,241,0.3)]" />}
      </Link>
    </div>
  );
};

export const PanelTabs = () => {
  return (
    <Suspense fallback={<div className="h-14 bg-white/[0.02] border-b border-white/[0.03]" />}>
      <PanelTabsContent />
    </Suspense>
  );
};

export default PanelTabs;
