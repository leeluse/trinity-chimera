"use client";

import React from "react";
import TerminalHunterPanel from "./TerminalHunterPanel";
import { PageLayout, PageHeader, AppRightPanel } from "@/components";
import { useTerminalStore } from "./terminalStore";
import { cn } from "@/lib/utils";

export default function TerminalMigrated() {
  const { hunterSummary: hSummary, filteredResults, globalMetrics } = useTerminalStore();

  return (
    <div className="h-screen w-full overflow-hidden bg-[#030508] text-slate-200">
      <PageLayout fullHeight={true}>
        <PageLayout.Side>
          <AppRightPanel />
        </PageLayout.Side>

        <PageLayout.Main>
          <PageHeader
            statusText="Terminal Engine Active"
            statusColor="purple"
            extra={
              <div className="mr-4 flex items-center gap-6 text-[10px] uppercase tracking-widest">
                <div className="text-right">
                  <div className="text-slate-600">WS</div>
                  <div
                    className={cn(
                      "font-mono font-bold",
                      globalMetrics.wsStatus === "LIVE"
                        ? "text-emerald-400"
                        : "text-rose-400",
                    )}
                  >
                    {globalMetrics.wsStatus}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-slate-600">Matches</div>
                  <div className="font-mono font-bold text-violet-400">
                    {filteredResults.length}
                  </div>
                </div>
              </div>
            }
          />
          <div className="flex-1 w-full overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-b from-violet-500/5 to-transparent pointer-events-none" />
            <TerminalHunterPanel />
          </div>
        </PageLayout.Main>
      </PageLayout>
    </div>
  );
}

