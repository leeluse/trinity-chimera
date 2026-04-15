"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

const PanelTabsContent = () => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();

  const isBacktest = pathname === "/backtest";
  const isDashboard = pathname === "/" && (view === "" || view === "logs");
  const isEvolution = pathname === "/" && view === "evolution";

  return (
    <div className="sticky top-0 z-[220] flex p-2 bg-[#060912]/95 border-b border-white/[0.04] gap-1 shrink-0 pointer-events-auto backdrop-blur-xl">
      <Link
        href="/?view=logs"
        aria-pressed={isDashboard}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border text-center cursor-pointer pointer-events-auto ${isDashboard ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        LOGS
      </Link>
      <Link
        href="/?view=evolution"
        aria-pressed={isEvolution}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border text-center cursor-pointer pointer-events-auto ${isEvolution ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        EVOLUTION
      </Link>
      <Link
        href="/backtest"
        aria-pressed={isBacktest}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border text-center cursor-pointer pointer-events-auto ${isBacktest ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        BACKTEST
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
