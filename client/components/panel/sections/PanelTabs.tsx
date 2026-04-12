"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

const PanelTabsContent = () => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = searchParams.get("view");

  const isBacktest = pathname === "/backtest";
  const isDashboard = pathname === "/" && !view;
  const isEvolution = pathname === "/" && view === "evolution";

  return (
    <div className="flex p-2 bg-white/[0.02] border-b border-white/[0.03] gap-1 shrink-0">
      <button
        onClick={() => router.push("/")}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${isDashboard ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        LOGS
      </button>
      <button
        onClick={() => router.push("/?view=evolution")}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${isEvolution ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        EVOLUTION
      </button>
      <button
        onClick={() => router.push("/backtest")}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${isBacktest ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        BACKTEST
      </button>
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
