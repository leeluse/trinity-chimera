"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowDownNarrowWide,
  Database,
  Search,
  Shield,
  TrendingUp,
  X,
  Zap,
} from "lucide-react";
import { useTerminalStore } from "./terminalStore";
import { mountTerminalV4 } from "./terminalRuntimeV4";
import { cn } from "@/lib/utils";
import { PageLayout, PageHeader, AppRightPanel } from "@/components";

const FILTERS = [
  { id: "ALL", label: "ALL" },
  { id: "SHORT_SQUEEZE", label: "🔥숏스퀴즈" },
  { id: "VWAP_BREAK", label: "⚡VWAP 돌파" },
  { id: "BREAKOUT_MOMENTUM", label: "🚀모멘텀" },
  { id: "BOTTOM_ABSORPTION", label: "💎흡수" },
] as const;

const COLUMNS = [
  { key: "symbol", label: "Symbol" },
  { key: "setupTag", label: "Setup" },
  { key: "alphaScore", label: "Alpha" },
  { key: "wyckoffScore", label: "L1 WYC" },
  { key: "vwapScore", label: "VWAP" },
  { key: "rsScore", label: "RS" },
  { key: "mtfScore", label: "MTF" },
  { key: "cvdScore", label: "CVD" },
  { key: "realLiqScore", label: "LIQ" },
  { key: "bbScore", label: "BB" },
  { key: "atrScore", label: "ATR" },
  { key: "brkScore", label: "BRK" },
  { key: "flowScore", label: "Flow" },
  { key: "surgeScore", label: "Surge" },
  { key: "kimchiScore", label: "Kimchi" },
  { key: "fr", label: "FR%" },
  { key: "oiChangePct", label: "OI Δ" },
  { key: "pricePct", label: "Price Δ" },
] as const;

export default function TerminalMigrated() {
  const {
    results,
    filteredResults,
    globalMetrics,
    summaryStats,
    isRunning,
    progress,
    statusMessage,
    activeFilter,
    searchQuery,
    selectedSymbol,
    sort,
    engineApi,
    setEngineApi,
    setFilter,
    setSearchQuery,
    setSort,
    setSelectedSymbol,
  } = useTerminalStore();

  const hunterRows = useTerminalStore((s) => s.hunterRows);
  const hunterMap = useMemo(
    () => new Map(hunterRows.map((r) => [r.full, r])),
    [hunterRows],
  );

  const hunterRegime = useTerminalStore((s) => s.hunterRegime);

  const regimeHint = useMemo((): string | null => {
    if (!hunterRegime?.ready) return null;
    if (hunterRegime.btcAltDelta < -0.5 && hunterRegime.longFlowRatio < 45) return "SHORT_SQUEEZE";
    if (hunterRegime.longFlowRatio > 60 && hunterRegime.oiExpansionRate > 55) return "BREAKOUT_MOMENTUM";
    if (hunterRegime.avgFunding > 0.03) return "BOTTOM_ABSORPTION";
    return null;
  }, [hunterRegime]);

  const [scanMode, setScanMode] = useState<"topn" | "custom">("topn");

  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  useEffect(() => {
    const engine = mountTerminalV4();
    setEngineApi(engine.api);
    return () => {
      engine.cleanup();
      setEngineApi(null);
    };
  }, [setEngineApi]);

  useEffect(() => {
    if (!selectedSymbol || !tbodyRef.current) return;
    const row = tbodyRef.current.querySelector<HTMLElement>(
      `[data-symbol="${selectedSymbol}"]`,
    );
    if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedSymbol]);

  const selected = useMemo(
    () => results.find((r) => r.symbol === selectedSymbol) ?? null,
    [results, selectedSymbol],
  );

  const callApi = (method: string, ...args: unknown[]) => {
    if (engineApi && typeof engineApi[method] === "function") {
      return engineApi[method](...args);
    }
    return undefined;
  };

  const onScanModeChange = (mode: "topn" | "custom") => {
    setScanMode(mode);
    callApi("setMode", mode);
  };

  return (
    <div className="h-screen w-full overflow-hidden bg-[#030508] text-slate-200">
      <PageLayout fullHeight={true}>
        <PageLayout.Side>
          <AppRightPanel />
        </PageLayout.Side>

        <PageLayout.Main>
          <PageHeader
            statusText="Terminal Engine Active"
            statusColor="blue"
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
                  <div className="font-mono font-bold text-cyan-400">
                    {filteredResults.length}
                  </div>
                </div>
              </div>
            }
          />

          <div className="relative flex-1 flex flex-col overflow-hidden">
            <div
              className="absolute inset-0 opacity-[0.04] pointer-events-none"
              style={{
                backgroundImage:
                  "radial-gradient(rgba(0,221,255,0.6) 0.5px, transparent 0.5px)",
                backgroundSize: "28px 28px",
              }}
            />

            <div className="relative z-10 flex h-full flex-col overflow-hidden">

        <section className="grid grid-cols-2 gap-3 border-b border-white/10 bg-[#050911]/70 px-6 py-3 md:grid-cols-4 lg:grid-cols-8">
          <MetricCard
            label="Short Liq"
            value={globalMetrics.globalShortLiq}
            tone="text-emerald-400"
          />
          <MetricCard
            label="Long Liq"
            value={globalMetrics.globalLongLiq}
            tone="text-rose-400"
          />
          <MetricCard
            label="Fear&Greed"
            value={String(globalMetrics.fearGreed)}
            sub={globalMetrics.fearGreedLabel}
            tone="text-amber-400"
          />
          <MetricCard
            label="USD/KRW"
            value={String(Math.round(globalMetrics.usdKrw).toLocaleString())}
            tone="text-cyan-400"
          />
          <MetricCard
            label="BTC TX"
            value={String(globalMetrics.btcTx?.toLocaleString() ?? "—")}
            sub={globalMetrics.btcTxLabel}
            tone="text-slate-300"
          />
          <MetricCard
            label="Fees"
            value={
              globalMetrics.mempoolFees ? `${globalMetrics.mempoolFees} sat` : "—"
            }
            tone="text-indigo-400"
          />
          <MetricCard
            label="Strong Bull"
            value={String(summaryStats.strongBull)}
            tone="text-emerald-400"
          />
          <MetricCard
            label="Strong Bear"
            value={String(summaryStats.strongBear)}
            tone="text-rose-400"
          />
        </section>

        <section className="border-b border-white/10 bg-[#04070d] px-6 py-3">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <div className="mb-1 text-[9px] uppercase tracking-widest text-slate-600">
                Mode
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => onScanModeChange("topn")}
                  className={cn(
                    "rounded border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider",
                    scanMode === "topn"
                      ? "border-cyan-400 bg-cyan-400/10 text-cyan-300"
                      : "border-white/10 text-slate-400",
                  )}
                >
                  TOP N
                </button>
                <button
                  type="button"
                  onClick={() => onScanModeChange("custom")}
                  className={cn(
                    "rounded border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider",
                    scanMode === "custom"
                      ? "border-cyan-400 bg-cyan-400/10 text-cyan-300"
                      : "border-white/10 text-slate-400",
                  )}
                >
                  CUSTOM
                </button>
              </div>
            </div>

            <div>
              <div className="mb-1 text-[9px] uppercase tracking-widest text-slate-600">
                Top N
              </div>
              <select
                id="topN"
                defaultValue="50"
                className="h-8 rounded border border-white/10 bg-black/40 px-2 text-[11px] text-slate-200 outline-none"
              >
                <option value="30">Top 30</option>
                <option value="50">Top 50</option>
                <option value="80">Top 80</option>
                <option value="100">Top 100</option>
              </select>
            </div>

            <div>
              <div className="mb-1 text-[9px] uppercase tracking-widest text-slate-600">
                Period
              </div>
              <select
                id="period"
                defaultValue="4h"
                className="h-8 rounded border border-white/10 bg-black/40 px-2 text-[11px] text-slate-200 outline-none"
              >
                <option value="1h">1H</option>
                <option value="4h">4H</option>
                <option value="1d">1D</option>
              </select>
            </div>

            <textarea id="sym-input" className="hidden" defaultValue="" />

            <button
              type="button"
              onClick={() => callApi("doScan")}
              disabled={isRunning}
              className="ml-auto inline-flex h-9 items-center gap-2 rounded border border-cyan-400/50 bg-cyan-400/10 px-5 text-[11px] font-black uppercase tracking-[0.2em] text-cyan-300 transition hover:bg-cyan-400/20 disabled:opacity-50"
            >
              <Zap size={13} className={isRunning ? "animate-pulse" : ""} />
              ALPHA SCAN
            </button>

            {isRunning && (
              <button
                type="button"
                onClick={() => callApi("doStop")}
                className="inline-flex h-9 items-center rounded border border-rose-500/50 bg-rose-500/10 px-4 text-[11px] font-black uppercase tracking-wider text-rose-300"
              >
                STOP
              </button>
            )}
          </div>

          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-[10px] text-slate-500">
              <span>{statusMessage}</span>
              <span className="font-mono">{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded bg-black/50">
              <div
                className="h-full bg-cyan-400 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-[#04070d]/80 px-6 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative mr-3 w-full max-w-xs">
              <Search
                size={14}
                className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-slate-600"
              />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search symbol..."
                className="h-8 w-full rounded border border-white/10 bg-black/40 pl-8 pr-2 text-[11px] text-slate-200 outline-none placeholder:text-slate-600"
              />
            </div>

            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                className={cn(
                  "relative rounded border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition-colors",
                  activeFilter === f.id
                    ? "border-cyan-400 bg-cyan-400/10 text-cyan-300"
                    : "border-white/10 text-slate-400 hover:border-white/20 hover:text-slate-300",
                )}
              >
                {f.label}
                {regimeHint === f.id && activeFilter !== f.id && (
                  <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                )}
              </button>
            ))}
          </div>
        </section>

        <main className="relative flex-1 overflow-auto px-6 py-4">
          {results.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-slate-600">
              <Activity size={26} />
              <p className="text-[12px] uppercase tracking-[0.3em]">Engine Standby</p>
            </div>
          ) : (
            <table className="min-w-[1900px] w-full border-separate border-spacing-y-1">
              <thead className="sticky top-0 z-20 bg-[#030508]/95 backdrop-blur">
                <tr>
                  {COLUMNS.map((h) => (
                    <th
                      key={h.key}
                      onClick={() => setSort(h.key)}
                      className={cn(
                        "cursor-pointer px-3 py-2 text-left text-[10px] uppercase tracking-[0.18em]",
                        sort.col === h.key ? "text-cyan-400" : "text-slate-500",
                      )}
                    >
                      <span className="inline-flex items-center gap-1">
                        {h.label}
                        {sort.col === h.key && (
                          <ArrowDownNarrowWide
                            size={11}
                            className={sort.dir === 1 ? "rotate-180" : ""}
                          />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody ref={tbodyRef}>
                {filteredResults.map((r) => {
                  const wkLabel =
                    r.layers?.wk?.pattern !== "NONE" ? r.layers?.wk?.label || "—" : "—";
                  const vwapLabel = r.layers?.vwap?.label || "—";
                  const rsLabel = r.layers?.rs?.label || "—";
                  const mtfLabel = r.layers?.mtf?.label || "—";
                  const cvdLabel = r.layers?.cvd?.absorption
                    ? "흡수"
                    : r.cvdScore > 0
                      ? "↑"
                      : r.cvdScore < 0
                        ? "↓"
                        : "—";
                  const liqLabel =
                    r.layers?.wsLiq?.shortLiq > 0
                      ? "WS발생"
                      : (r.layers?.rl?.label || "—").slice(0, 8);
                  const bbLabel = r.layers?.bb?.label || "—";
                  const atrLabel = (r.layers?.atr?.label || "—").slice(0, 7);
                  const brkLabel = r.layers?.brk?.label || "—";
                  const surgeLabel = `×${r.layers?.vs?.surgeFactor || 1}`;
                  const kimchiPremium = r.layers?.km?.premium;
                  const kimchiLabel =
                    kimchiPremium == null
                      ? "—"
                      : `${kimchiPremium > 0 ? "+" : ""}${kimchiPremium}%`;

                  return (
                    <tr
                      key={r.symbol}
                      data-symbol={r.symbol}
                      onClick={() => setSelectedSymbol(r.symbol)}
                      className={cn(
                        "cursor-pointer bg-white/[0.02] hover:bg-white/[0.05]",
                        selectedSymbol === r.symbol && "bg-cyan-500/10",
                      )}
                    >
                      <td className="rounded-l-md px-3 py-2 font-mono text-[12px] font-black text-white">
                        <span>{r.symbol.replace("USDT", "")}</span>
                        {(() => {
                          const h = hunterMap.get(r.symbol);
                          if (!h || h.stage < 1) return null;
                          return (
                            <span
                              className={cn(
                                "ml-1.5 text-[9px] font-bold",
                                hunterBadgeClass(h.stage, h.latchDir),
                                h.stage >= 2 && "animate-pulse",
                              )}
                            >
                              {hunterBadgeLabel(h.stage, h.latchDir)}
                            </span>
                          );
                        })()}
                      </td>

                      <td className="px-3 py-2 text-[10px] font-bold text-amber-300">
                        {r.setupTag === "NONE" ? "—" : r.setupTag}
                      </td>

                      <td
                        className={cn(
                          "px-3 py-2 font-mono text-[12px] font-black",
                          r.alphaScore >= 25
                            ? "text-cyan-400"
                            : r.alphaScore <= -25
                              ? "text-rose-400"
                              : "text-slate-300",
                        )}
                      >
                        {r.alphaScore > 0 ? "+" : ""}
                        {r.alphaScore}
                      </td>

                      <LayerScore score={r.wyckoffScore} label={wkLabel} />
                      <LayerScore score={r.vwapScore} label={vwapLabel} />
                      <LayerScore score={r.rsScore} label={rsLabel} />
                      <LayerScore score={r.mtfScore} label={mtfLabel} />
                      <LayerScore score={r.cvdScore} label={cvdLabel} />
                      <LayerScore score={r.realLiqScore} label={liqLabel} />
                      <LayerScore score={r.bbScore} label={bbLabel} />
                      <LayerScore score={r.atrScore} label={atrLabel} />
                      <LayerScore score={r.brkScore} label={brkLabel} />
                      <LayerScore score={r.flowScore} label="Flow" />
                      <LayerScore score={r.surgeScore} label={surgeLabel} />
                      <LayerScore score={r.kimchiScore} label={kimchiLabel} />

                      <td
                        className={cn(
                          "px-3 py-2 font-mono text-[11px]",
                          r.fr <= 0 ? "text-emerald-400" : "text-rose-400",
                        )}
                      >
                        {r.fr > 0 ? "+" : ""}
                        {r.fr.toFixed(4)}%
                        {r.extremeFR ? " ⚡" : ""}
                      </td>

                      <td
                        className={cn(
                          "px-3 py-2 font-mono text-[11px]",
                          r.oiChangePct >= 0 ? "text-emerald-400" : "text-rose-400",
                        )}
                      >
                        {r.oiChangePct > 0 ? "+" : ""}
                        {r.oiChangePct.toFixed(2)}%
                      </td>

                      <td
                        className={cn(
                          "rounded-r-md px-3 py-2 font-mono text-[11px]",
                          r.pricePct >= 0 ? "text-emerald-400" : "text-rose-400",
                        )}
                      >
                        {r.pricePct > 0 ? "+" : ""}
                        {r.pricePct.toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </main>
      </div>
            </div>
          </PageLayout.Main>
        </PageLayout>


      {selected && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-4xl rounded-2xl border border-white/10 bg-[#060b14] p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h2 className="font-mono text-2xl font-black text-white">
                  {selected.symbol.replace("USDT", "")}/USDT
                </h2>
                <p className="mt-1 text-[11px] uppercase tracking-widest text-slate-500">
                  {selected.verdict}
                </p>
              </div>
              <button
                onClick={() => setSelectedSymbol(null)}
                className="rounded border border-white/10 p-2 text-slate-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <DetailCard
                label="Alpha Score"
                value={`${selected.alphaScore}`}
                tone={selected.alphaScore >= 0 ? "text-cyan-400" : "text-rose-400"}
                icon={<Zap size={12} />}
              />
              <DetailCard
                label="Current Price"
                value={
                  selected.currentPrice
                    ? `${selected.currentPrice.toLocaleString()} USDT`
                    : "—"
                }
                tone="text-slate-200"
                icon={<TrendingUp size={12} />}
              />
              <DetailCard
                label="Funding Rate"
                value={`${selected.fr.toFixed(5)}%`}
                tone={selected.fr <= 0 ? "text-emerald-400" : "text-rose-400"}
                icon={<Shield size={12} />}
              />
              <DetailCard
                label="OI Change"
                value={`${selected.oiChangePct.toFixed(2)}%`}
                tone={selected.oiChangePct >= 0 ? "text-emerald-400" : "text-rose-400"}
                icon={<Database size={12} />}
              />
            </div>

            <div className="mt-5 rounded-lg border border-white/10 bg-black/30 p-4">
              <div className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">
                Engine Note
              </div>
              <p className="text-[12px] text-slate-300">{selected.note}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function hunterBadgeLabel(stage: number, dir: number): string {
  if (stage === 3) return dir >= 0 ? "▲▲S3" : "▼▼S3";
  if (stage === 2) return dir >= 0 ? "▲S2" : "▼S2";
  return "S1";
}

function hunterBadgeClass(stage: number, dir: number): string {
  if (stage === 3) return dir >= 0 ? "text-cyan-300" : "text-rose-400";
  if (stage === 2) return dir >= 0 ? "text-blue-300" : "text-orange-400";
  return "text-amber-400";
}

function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone: string;
}) {
  return (
    <div className="rounded border border-white/10 bg-black/30 px-3 py-2">
      <div className="text-[9px] uppercase tracking-widest text-slate-600">{label}</div>
      <div className={cn("mt-1 font-mono text-[14px] font-black", tone)}>{value}</div>
      {sub ? <div className="mt-0.5 text-[9px] text-slate-600">{sub}</div> : null}
    </div>
  );
}

function LayerScore({ score, label }: { score: number; label: string }) {
  return (
    <td className="px-3 py-2 font-mono text-[11px] text-slate-300">
      <span className="mr-2 text-slate-500">{label}</span>
      <span className={cn(score > 0 ? "text-emerald-400" : score < 0 ? "text-rose-400" : "text-slate-500")}>
        {score > 0 ? "+" : ""}
        {score}
      </span>
    </td>
  );
}

function DetailCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded border border-white/10 bg-black/30 p-3">
      <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-500">
        {icon}
        {label}
      </div>
      <div className={cn("font-mono text-[14px] font-black", tone)}>{value}</div>
    </div>
  );
}
