"use client";

import { useRouter, usePathname } from "next/navigation";

export const PanelTabs = () => {
  const router = useRouter();
  const pathname = usePathname();

  const isBacktest = pathname === "/backtest";
  const isDashboard = pathname === "/";

  return (
    <div className="flex p-2 bg-white/[0.02] border-b border-white/[0.03] gap-1 shrink-0">
      <button
        onClick={() => router.push("/")}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${isDashboard ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        Logs
      </button>
      <button
        onClick={() => router.push("/backtest")}
        className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${isBacktest ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
      >
        Backtest
      </button>
    </div>
  );
};

export default PanelTabs;
