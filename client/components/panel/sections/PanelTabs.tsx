"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Zap, History, FileSearch } from "lucide-react";

const PanelTabsContent = () => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();

  const isBacktestPage = pathname === "/backtest";
  const isDashboardPage = pathname === "/";
  
  // 탭 활성화 상태 판별 (경로와 뷰를 모두 고려)
  const isLogsActive = isDashboardPage && (view === "logs" || view === "");
  const isEvolutionActive = isDashboardPage && view === "evolution";
  const isBacktestActive = isBacktestPage;

  return (
    <div className="sticky top-0 z-[220] flex p-1 bg-[#10141d] border-b border-white/[0.08] gap-1 shrink-0 pointer-events-auto">
      <Link
        href="/?view=logs"
        className={`flex-1 flex flex-row items-center justify-center gap-2 py-2.5 text-[10px] font-bold transition-all relative uppercase cursor-pointer pointer-events-auto group ${
          isLogsActive 
          ? 'bg-[#1e1a35] text-indigo-400' 
          : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
        }`}
      >
        <FileSearch size={14} className={isLogsActive ? "text-indigo-400" : "text-slate-600"} />
        LOGS
        {isLogsActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500" />}
      </Link>
      
      <Link
        href="/?view=evolution"
        className={`flex-1 flex flex-row items-center justify-center gap-2 py-2.5 text-[10px] font-bold transition-all relative uppercase cursor-pointer pointer-events-auto group ${
          isEvolutionActive 
          ? 'bg-[#1e1a35] text-indigo-400' 
          : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
        }`}
      >
        <Zap size={14} className={isEvolutionActive ? "text-indigo-400" : "text-slate-600"} />
        EVOLUTION
        {isEvolutionActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500" />}
      </Link>

      <Link
        href="/backtest"
        className={`flex-1 flex flex-row items-center justify-center gap-2 py-2.5 text-[10px] font-bold transition-all relative uppercase cursor-pointer pointer-events-auto group ${
          isBacktestActive 
          ? 'bg-[#1e1a35] text-indigo-400' 
          : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
        }`}
      >
        <History size={14} className={isBacktestActive ? "text-indigo-400" : "text-slate-600"} />
        BACKTEST
        {isBacktestActive && <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-indigo-500" />}
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
