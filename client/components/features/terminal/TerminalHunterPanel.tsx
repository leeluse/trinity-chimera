"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useTerminalStore } from "./terminalStore";
import {
  Play, Square, Pause, Target, Volume2, VolumeX, Activity, Cpu, Zap, Trophy,
  BarChart3, Binary, Flame, Crosshair, Rocket
} from "lucide-react";
import {
  mountHunterRuntime,
  type HunterLeaderboardItem,
  type HunterRow,
  type HunterRuntimeSnapshot,
  type HunterSortMode,
} from "./hunterRuntime";

type HunterTab = "lb" | "rg" | "pre";

const INITIAL: HunterRuntimeSnapshot = {
  running: false,
  muted: false,
  focusMode: false,
  frozen: false,
  sortMode: "total",
  statusText: "대기중",
  ws: { bn: false, okx: false, bybit: false, bitget: false },
  summary: { snipers: 0, s2plus: 0, s1: 0, bias: "—", pre: 0 },
  regime: {
    ready: false,
    btcAltDelta: 0,
    avgFunding: 0,
    oiExpansionRate: 0,
    longFlowRatio: 50,
  },
  rows: [],
  preSignals: [],
  leaderboard: [],
  updatedAt: Date.now(),
};

export default function TerminalHunterPanel() {
  const { setSelectedSymbol, setHunterRows, setHunterRegime, setHunterAlert, setHunterLeaderboard, setHunterSummary } = useTerminalStore();
  const [tab, setTab] = useState<HunterTab>("lb");
  const [state, setState] = useState<HunterRuntimeSnapshot>(INITIAL);
  const runtimeRef = useRef<ReturnType<typeof mountHunterRuntime> | null>(null);
  const prevRowsRef = useRef<HunterRow[]>([]);

  useEffect(() => {
    const runtime = mountHunterRuntime((snapshot) => {
      setState(snapshot);
      setHunterRows(snapshot.rows);
      setHunterRegime(snapshot.regime);
      setHunterLeaderboard(snapshot.leaderboard);
      setHunterSummary(snapshot.summary);

      // S2+ 신규 진입 감지 → alert
      const prevMap = new Map(prevRowsRef.current.map((r) => [r.full, r.stage]));
      for (const row of snapshot.rows) {
        const prev = prevMap.get(row.full) ?? 0;
        if (row.stage >= 2 && prev < 2) {
          setHunterAlert({ sym: row.sym, full: row.full, stage: row.stage, dir: row.latchDir, ts: Date.now() });
        }
      }
      prevRowsRef.current = snapshot.rows;
    });
    runtimeRef.current = runtime;
    return () => { runtime.cleanup(); runtimeRef.current = null; };
  }, [setHunterRows, setHunterRegime, setHunterAlert, setHunterLeaderboard, setHunterSummary]);

  const onStart = () => { void runtimeRef.current?.api.startSystem(); };
  const onStop = () => { runtimeRef.current?.api.stopSystem(); };
  const onToggleFreeze = () => { runtimeRef.current?.api.toggleFreeze(); };
  const onToggleFocus = () => { runtimeRef.current?.api.toggleFocus(); };
  const onToggleMute = () => { runtimeRef.current?.api.toggleMute(); };
  const onSetSort = (mode: HunterSortMode) => { runtimeRef.current?.api.setSort(mode); };

  const wsTagClass = (on: boolean) =>
    cn(
      "rounded-md border px-2.5 py-1 text-[9px] font-black uppercase tracking-widest transition-all",
      on
        ? "border-violet-400/50 bg-violet-500/12 text-violet-200 shadow-[0_0_10px_rgba(139,92,246,0.18)]"
        : "border-white/[0.07] bg-white/[0.025] text-slate-600",
    );

  return (
    <div className="flex h-full flex-col bg-[#06070d] text-slate-100">
      {/* ── Header ── */}
      <div className="relative border-b border-white/[0.07] bg-[#080910]/95 px-5 py-3 backdrop-blur-md">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-400/40 to-transparent" />

        <div className="relative z-10 flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.035] shadow-[0_0_18px_rgba(139,92,246,0.14)]">
              <Crosshair size={15} className="text-violet-200" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.9)]" />
                <div className="truncate text-[13px] font-black uppercase tracking-[0.22em] text-slate-100">
                  ALPHA HUNTER <span className="font-mono italic text-violet-300">V16</span>
                </div>
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[8px] font-bold uppercase tracking-[0.16em] text-slate-500">
                <Binary size={9} className="text-violet-300/45" />
                Stage-Gate Fusion Protocol Active
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <div className="flex items-center gap-1 rounded-lg border border-white/[0.07] bg-[#0d0e17] p-1">
              <span className={wsTagClass(state.ws.bn)}>BN</span>
              <span className={wsTagClass(state.ws.okx)}>OKX</span>
              <span className={wsTagClass(state.ws.bybit)}>BYB</span>
              <span className={wsTagClass(state.ws.bitget)}>BIT</span>
            </div>

            <div className="flex h-8 items-center gap-1 rounded-lg border border-white/[0.07] bg-[#0d0e17] p-1">
              <button
                type="button"
                onClick={onToggleFreeze}
                title="Toggle System Freeze"
                className={cn(
                  "flex h-full items-center gap-1.5 rounded-sm px-2 text-[9px] font-black uppercase transition-all",
                  state.frozen
                    ? "border border-violet-300/35 bg-violet-500/14 text-violet-100"
                    : "text-slate-500 hover:bg-white/[0.04] hover:text-slate-200",
                )}
              >
                {state.frozen ? <Play size={12} className="fill-current" /> : <Pause size={12} />}
                Freeze
              </button>

              <button
                type="button"
                onClick={onToggleFocus}
                title="Toggle Sniper Focus Mode"
                className={cn(
                  "flex h-full items-center gap-1.5 rounded-sm px-2 text-[9px] font-black uppercase transition-all",
                  state.focusMode
                    ? "border border-violet-300/35 bg-violet-500/14 text-violet-100"
                    : "text-slate-500 hover:bg-white/[0.04] hover:text-slate-200",
                )}
              >
                <Target size={12} />
                Focus
              </button>

              <button
                type="button"
                onClick={onToggleMute}
                title="Toggle Audio Notifications"
                className={cn(
                  "flex h-full items-center rounded-sm px-2 transition-all",
                  state.muted
                    ? "border border-pink-400/25 bg-pink-500/12 text-pink-300"
                    : "text-slate-500 hover:bg-white/[0.04] hover:text-slate-200",
                )}
              >
                {state.muted ? <VolumeX size={14} /> : <Volume2 size={14} />}
              </button>
            </div>
          </div>
        </div>

        <div className="relative z-10 mt-3 flex items-center justify-between gap-3 border-t border-white/[0.055] pt-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onStart}
              disabled={state.running}
              className={cn(
                "group relative flex h-8 items-center gap-2 overflow-hidden rounded-md border px-4 text-[10px] font-black uppercase tracking-[0.1em] transition-all",
                state.running
                  ? "border-violet-300/45 bg-violet-500/12 text-violet-100 shadow-[0_0_14px_rgba(139,92,246,0.14)]"
                  : "border-white/[0.08] bg-white/[0.035] text-slate-300 hover:border-violet-300/35 hover:bg-violet-500/10 hover:text-violet-100",
              )}
            >
              <div className="absolute inset-0 bg-white/[0.04] opacity-0 transition-opacity group-hover:opacity-100" />
              {state.running ? <Activity size={13} className="animate-pulse" /> : <Zap size={13} className="fill-current" />}
              {state.running ? "Active Monitoring" : "Initialize Engine"}
            </button>

            {state.running && (
              <button
                type="button"
                onClick={onStop}
                className="flex h-8 items-center gap-2 rounded-md border border-pink-400/25 bg-pink-500/8 px-4 text-[10px] font-black uppercase tracking-[0.1em] text-pink-300 transition-all hover:border-pink-300/45 hover:bg-pink-500/12"
              >
                <Square size={13} className="fill-current" />
                Shutdown
              </button>
            )}
          </div>

          <div className="flex h-8 min-w-[128px] items-center justify-between rounded-md border border-white/[0.07] bg-[#0d0e17] px-3">
            <div>
              <div className="text-[8px] font-black uppercase tracking-widest text-slate-500">Engine Status</div>
              <div className="font-mono text-[10px] font-bold uppercase tracking-widest text-violet-200">{state.statusText}</div>
            </div>
            <div className={cn("h-1.5 w-1.5 rounded-full", state.running ? "animate-pulse bg-violet-400 shadow-[0_0_8px_rgba(167,139,250,0.9)]" : "bg-pink-500")} />
          </div>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-white/[0.06] bg-[#080910] px-5 py-3 no-scrollbar">
        <TabBtn active={tab === "lb"} onClick={() => setTab("lb")} icon={<Trophy size={14} />}>리더보드</TabBtn>
        <TabBtn active={tab === "rg"} onClick={() => setTab("rg")} icon={<BarChart3 size={14} />}>레짐</TabBtn>
        <TabBtn active={tab === "pre"} onClick={() => setTab("pre")} icon={<Flame size={14} />}>선행</TabBtn>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto bg-[#06070d] no-scrollbar">
        {/* ── Leaderboard tab ── */}
        {tab === "lb" && (
          <div className="flex h-full flex-col">
            {/* Sort bar */}
            <div className="border-b border-white/[0.06] bg-[#080910] px-4 py-2">
              <div className="grid grid-cols-4 gap-1 rounded-lg border border-white/[0.06] bg-[#0d0e17] p-1">
              {(["total", "cross", "sqz", "whale"] as HunterSortMode[]).map((m) => {
                const label = m === "total" ? "🔥 TOTAL" : m === "cross" ? "⚡ CROSS" : m === "sqz" ? "💥 SQZ" : "🐋 WHALE";
                const Icon = m === "total" ? Flame : m === "cross" ? Zap : m === "sqz" ? Activity : Cpu;
                return (
                  <button key={m} type="button" onClick={() => onSetSort(m)}
                    className={cn("flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[9px] font-black tracking-widest transition-all",
                      state.sortMode === m ? "bg-violet-500/14 text-violet-100 shadow-[0_0_10px_rgba(139,92,246,0.12)]" : "text-slate-600 hover:bg-white/[0.035] hover:text-slate-300"
                    )}>
                    <Icon size={12} />
                    {label}
                  </button>
                );
              })}
              </div>
            </div>

            {/* Sniper targets header */}
            <div className="flex items-center justify-between border-b border-white/[0.06] bg-[#080910] px-5 py-2.5">
              <div className="flex items-center gap-3">
                <div className="flex h-5 w-5 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.035]">
                  <Crosshair size={12} className="text-violet-300" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-200">
                  SNIPER TARGETS <span className="mx-2 text-slate-700">|</span> <span className="text-violet-300/55">ACTIVE PROTOCOLS</span>
                </span>
              </div>
              <div className="flex items-center gap-4 text-[9px] font-bold uppercase tracking-widest text-violet-200/35">
                <span className="flex items-center gap-1.5"><div className="h-1.5 w-1.5 rounded-full bg-violet-300/70" /> S2+ Active</span>
                <span className="flex items-center gap-1.5"><div className="h-1.5 w-1.5 rounded-full bg-fuchsia-300/70" /> S1 Pending</span>
              </div>
            </div>

            <div className="flex border-b border-white/[0.06] bg-[#070812] text-[8px] font-black uppercase tracking-widest text-slate-600">
              <div className="flex-1 px-5 py-1.5">Asset</div>
              <div className="w-[150px] border-x border-violet-300/10 px-2 py-1.5 text-center">Stage</div>
              <div className="flex-1 px-5 py-1.5">Signals</div>
            </div>

            {/* Sniper rows */}
            <div className="flex-1">
              {state.rows.length === 0 && (
                <div className="flex flex-col items-center justify-center gap-4 py-24 opacity-40">
                  <div className="relative flex h-16 w-16 items-center justify-center">
                    <div className="absolute inset-0 animate-[spin_10s_linear_infinite] rounded-full border-2 border-dashed border-violet-300/30" />
                    <div className="relative flex h-9 w-9 items-center justify-center rounded-full border border-white/[0.06] bg-[#0d0e17]">
                      <Activity size={20} className="text-violet-300/65" />
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <div className="text-[11px] font-black uppercase tracking-[0.4em] text-violet-200">Synchronizing...</div>
                    <div className="text-[9px] font-bold uppercase tracking-widest text-violet-200/35">Awaiting Real-time Signal Stream</div>
                  </div>
                </div>
              )}
              {state.rows.map((row) => (
                <SniperRow key={row.full} row={row} onSelect={() => setSelectedSymbol(row.full)} focusMode={state.focusMode} />
              ))}
            </div>
          </div>
        )}

        {/* ── Regime tab ── */}
        {tab === "rg" && (
          <div className="space-y-3 p-4">
            <div className="mb-2 flex items-center gap-3">
              <BarChart3 size={18} className="text-violet-300" />
              <div className="text-[12px] font-black uppercase tracking-[0.2em] text-violet-50">Market Regime Matrix</div>
            </div>
            <RegimeCell
              label="BTC vs ALT Relative Strength"
              value={`${state.regime.btcAltDelta >= 0 ? "+" : ""}${state.regime.btcAltDelta.toFixed(2)}%`}
              sub={state.regime.btcAltDelta > 0.5 ? "Dominant Alpha in Majors" : state.regime.btcAltDelta < -0.5 ? "Alt-Season Rotation Active" : "Neutral Market Structure"}
              tone={state.regime.btcAltDelta > 0.5 ? "text-fuchsia-300" : state.regime.btcAltDelta < -0.5 ? "text-violet-300" : "text-violet-200/60"}
              bar={clamp((state.regime.btcAltDelta + 5) / 10, 0, 1)}
            />
            <RegimeCell
              label="Average Funding (Sniper Universe)"
              value={`${state.regime.avgFunding >= 0 ? "+" : ""}${state.regime.avgFunding.toFixed(4)}%`}
              sub={Math.abs(state.regime.avgFunding) > 0.05 ? "EXTREME SKEW" : Math.abs(state.regime.avgFunding) > 0.03 ? "ELEVATED BIAS" : "STANDARD RANGE"}
              tone={Math.abs(state.regime.avgFunding) > 0.03 ? "text-fuchsia-300" : "text-violet-200/60"}
              bar={clamp((state.regime.avgFunding + 0.2) / 0.4, 0, 1)}
            />
            <RegimeCell
              label="OI Expansion Velocity"
              value={`${state.regime.oiExpansionRate.toFixed(1)}%`}
              sub={state.regime.oiExpansionRate > 60 ? "Aggressive Position Loading" : "Organic Growth"}
              tone={state.regime.oiExpansionRate > 60 ? "text-violet-300" : "text-violet-200/60"}
              bar={clamp(state.regime.oiExpansionRate / 100, 0, 1)}
            />
            <RegimeCell
              label="Signal Flow Ratio (L/S)"
              value={`${state.regime.longFlowRatio.toFixed(0)}%`}
              sub={state.regime.longFlowRatio > 60 ? "Bullish Momentum Dominant" : state.regime.longFlowRatio < 40 ? "Bearish Pressure" : "Equilibrium"}
              tone={state.regime.longFlowRatio > 60 ? "text-violet-300" : state.regime.longFlowRatio < 40 ? "text-pink-300" : "text-violet-200/60"}
              bar={clamp(state.regime.longFlowRatio / 100, 0, 1)}
            />
          </div>
        )}

        {/* ── Pre-signals tab ── */}
        {tab === "pre" && (
          <div className="space-y-2 p-4">
            <div className="mb-2 flex items-center gap-3 px-1">
              <Flame size={18} className="text-fuchsia-300" />
              <div className="text-[12px] font-black uppercase tracking-[0.2em] text-violet-50">Anomaly Detection Stream</div>
            </div>
            {state.preSignals.length === 0 && (
              <div className="px-3 py-24 text-center">
                <Activity size={32} className="mx-auto mb-4 text-violet-950" />
                <div className="text-[11px] font-black uppercase tracking-[0.3em] text-violet-200/25">Awaiting Early Detection Triggers</div>
              </div>
            )}
            {state.preSignals.slice(0, 40).map((p, idx) => (
              <button
                key={`${p.sym}-${p.type}-${idx}`}
                type="button"
                onClick={() => setSelectedSymbol(p.sym)}
                className={cn(
                  "group relative w-full overflow-hidden rounded-xl border border-violet-300/10 px-5 py-4 text-left backdrop-blur-sm transition-all hover:border-violet-300/25 hover:bg-violet-400/[0.04]",
                  p.dir > 0 ? "bg-violet-500/[0.03]" : "bg-pink-500/[0.03]"
                )}
              >
                <div className="absolute bottom-0 left-0 top-0 w-1 opacity-60 transition-all group-hover:w-1.5"
                     style={{ backgroundColor: p.dir > 0 ? "#a78bfa" : "#f472b6" }} />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn("rounded-lg border p-1.5", p.dir > 0 ? "border-violet-300/25 bg-violet-500/10 text-violet-200" : "border-pink-300/25 bg-pink-500/10 text-pink-300")}>
                      {p.dir > 0 ? <Rocket size={14} /> : <Flame size={14} />}
                    </div>
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[16px] font-black uppercase text-violet-50 transition-colors group-hover:text-violet-200">{p.sym.replace("USDT", "")}</span>
                        <span className="text-[10px] font-bold uppercase text-violet-200/30">USDT</span>
                      </div>
                      <div className="mt-0.5 text-[11px] font-black uppercase tracking-wide text-violet-100">{p.title}</div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <span className={cn("rounded-md border px-2.5 py-1 font-mono text-[12px] font-black", p.dir > 0 ? "border-violet-300/30 bg-violet-500/10 text-violet-200" : "border-pink-300/30 bg-pink-500/10 text-pink-300")}>
                      {p.dir > 0 ? "▲ BULLISH" : "▼ BEARISH"}
                    </span>
                    <span className="mt-1 text-[9px] font-bold uppercase tracking-widest text-violet-200/35">{p.desc}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Sniper Row
 ───────────────────────────────────────────────────────── */
function SniperRow({ row, onSelect, focusMode }: {
  row: HunterRow;
  onSelect: () => void;
  focusMode: boolean;
}) {
  if (focusMode && row.stage < 2 && !row.pinned) return null;

  const pct = Math.min(Math.abs(row.score) / 180, 1) * 100;
  const isBull = row.latchDir >= 0;
  const coin = row.sym.replace("USDT", "");
  const priceText = row.price > 0
    ? row.price >= 100
      ? row.price.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : row.price.toLocaleString(undefined, { maximumFractionDigits: 5 })
    : "—";

  return (
    <div className="px-4 py-0.5">
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "group relative grid w-full grid-cols-[minmax(210px,0.85fr)_150px_minmax(180px,1fr)_72px] items-center gap-3 overflow-hidden rounded-lg border border-white/[0.06] bg-[#090a12] px-3 py-2 text-left transition-all hover:border-violet-300/22 hover:bg-[#0d0e18]",
          row.aGradeActive ? (isBull ? "ring-1 ring-violet-300/20" : "ring-1 ring-pink-300/20") : ""
        )}
      >
        <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-violet-300/20 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

        <div className="relative z-10 flex min-w-0 items-center gap-2">
          <div className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border font-mono text-[9px] font-black",
            isBull
              ? "border-violet-300/22 bg-violet-500/10 text-violet-100"
              : "border-pink-300/22 bg-pink-500/10 text-pink-100"
          )}>
            {coin.slice(0, 3)}
          </div>

          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="truncate font-mono text-[15px] font-black uppercase leading-none tracking-tight text-slate-100">
                {coin}
              </span>
              <span className="rounded-sm border border-white/[0.06] bg-white/[0.025] px-1 py-[1px] text-[8px] font-black uppercase tracking-wider text-slate-600">
                USDT
              </span>
              {row.pinned && <Target size={11} className="shrink-0 text-violet-300" />}
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="font-mono text-[9px] font-bold text-slate-500">${priceText}</span>
              {row.chg9 != null && (
                <span className={cn(
                  "rounded-sm border px-1.5 py-[1px] font-mono text-[8px] font-black",
                  row.chg9 >= 0
                    ? "border-violet-300/20 bg-violet-500/8 text-violet-200"
                    : "border-pink-300/20 bg-pink-500/8 text-pink-300"
                )}>
                  9AM {row.chg9 > 0 ? "+" : ""}{row.chg9.toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-center gap-2">
          <div className={cn(
            "rounded-md border px-2 py-1 text-center",
            isBull
              ? "border-violet-300/22 bg-violet-500/8"
              : "border-pink-300/22 bg-pink-500/8"
          )}>
            <div className={cn("text-[8px] font-black uppercase tracking-wider", isBull ? "text-violet-200/55" : "text-pink-200/55")}>
              {isBull ? "LONG" : "SHORT"}
            </div>
            <div className="mt-0.5 flex items-center justify-center gap-1">
              <span className={cn("text-[9px] font-black", isBull ? "text-violet-100" : "text-pink-300")}>{isBull ? "▲" : "▼"}</span>
              <span className={cn("font-mono text-[10px] font-black", stageLabelColor(row.stage))}>S{row.stage}</span>
            </div>
          </div>
          <div className={cn("w-[46px] text-right font-mono text-[16px] font-black leading-none", isBull ? "text-slate-100" : "text-pink-300")}>
            {row.score > 0 ? "+" : ""}{Math.round(row.score)}
          </div>
        </div>

        <div className="relative z-10 min-w-0">
          <div className="mb-1 flex items-center justify-between font-mono text-[8px] font-black uppercase tracking-wider text-slate-600">
            <span>Strength</span>
            <span>{Math.round(pct)}%</span>
          </div>
          <div className="relative h-1.5 w-full overflow-hidden rounded-sm border border-white/[0.06] bg-black/35">
            <div
              className={cn(
                "h-full rounded-sm transition-all duration-1000",
                isBull
                  ? "bg-gradient-to-r from-violet-700 via-violet-400 to-fuchsia-300"
                  : "bg-gradient-to-r from-pink-700 via-fuchsia-500 to-rose-300"
              )}
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap gap-1">
            {row.sig.slice(0, 4).map((s, i) => (
              <span
                key={i}
                className={cn(
                  "rounded-sm border px-1.5 py-[1px] text-[8px] font-black uppercase tracking-wider",
                  s.cat === "setup"
                    ? "border-violet-300/18 bg-violet-500/8 text-violet-200/62"
                    : s.cat === "trigger"
                      ? "border-fuchsia-300/18 bg-fuchsia-500/8 text-fuchsia-200/62"
                      : "border-pink-300/18 bg-pink-500/8 text-pink-200/62"
                )}
              >
                {s.n}
              </span>
            ))}
            {!row.sig.length && (
              <span className="rounded-sm border border-white/[0.06] bg-white/[0.025] px-1.5 py-[1px] text-[8px] font-black uppercase tracking-wider text-slate-700">
                No Trigger
              </span>
            )}
          </div>
        </div>

        <div className="relative z-10 flex flex-col items-end gap-1 font-mono text-[8px] font-black uppercase text-slate-600">
          <span>A {row.score > 0 ? "+" : ""}{Math.round(row.score * 0.3)}</span>
          <span>RM ×{row.regimeMult.toFixed(2)}</span>
        </div>
      </button>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Leaderboard Card
 ───────────────────────────────────────────────────────── */
export function LeaderboardCard({ lb, idx, onSelect }: {
  lb: HunterLeaderboardItem;
  idx: number;
  onSelect: () => void;
}) {
  const isBuy = lb.scoreSum >= 0;
  const pct = Math.min(Math.abs(lb.scoreSum) / 150, 1) * 100;
  const coin = lb.sym.replace("USDT", "");
  const topTags = Object.entries(lb.tags || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group relative mb-2 w-full overflow-hidden rounded-lg border border-white/[0.06] bg-[#090a12] px-3 py-2 text-left transition-all hover:border-violet-300/22 hover:bg-[#0d0e18]",
        lb.aGradeCount > 0 ? (isBuy ? "ring-1 ring-violet-300/20" : "ring-1 ring-pink-300/20") : ""
      )}
    >
      <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-violet-300/20 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div className="relative z-10 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md border font-mono text-[9px] font-black",
            isBuy
              ? "border-violet-300/22 bg-violet-500/10 text-violet-100"
              : "border-pink-300/22 bg-pink-500/10 text-pink-100"
          )}>
            {idx + 1}
          </div>

          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="truncate font-mono text-[15px] font-black uppercase leading-none tracking-tight text-slate-100">
                {coin}
              </span>
              <span className="rounded-sm border border-white/[0.06] bg-white/[0.025] px-1 py-[1px] text-[8px] font-black uppercase tracking-wider text-slate-600">
                USDT
              </span>
              {lb.aGradeCount > 0 && (
                <span className="rounded-sm border border-violet-300/18 bg-violet-500/8 px-1.5 py-[1px] text-[8px] font-black uppercase tracking-wider text-violet-200/65">
                  A×{lb.aGradeCount}
                </span>
              )}
            </div>

            <div className="mt-1 flex min-w-0 flex-wrap gap-1">
              {topTags.length > 0 ? topTags.map(([name, count]) => (
                <span
                  key={name}
                  className="rounded-sm border border-white/[0.06] bg-white/[0.025] px-1.5 py-[1px] text-[8px] font-black uppercase tracking-wider text-slate-500"
                >
                  {name} {count}
                </span>
              )) : (
                <span className="rounded-sm border border-white/[0.06] bg-white/[0.025] px-1.5 py-[1px] text-[8px] font-black uppercase tracking-wider text-slate-700">
                  No Tags
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-start gap-2">
          {lb.stage > 0 && (
            <div className={cn(
              "rounded-md border px-2 py-1 text-center",
              isBuy
                ? "border-violet-300/22 bg-violet-500/8"
                : "border-pink-300/22 bg-pink-500/8"
            )}>
              <div className={cn("text-[8px] font-black uppercase tracking-wider", isBuy ? "text-violet-200/55" : "text-pink-200/55")}>
                {isBuy ? "LONG" : "SHORT"}
              </div>
              <div className="mt-0.5 flex items-center justify-center gap-1">
                <span className={cn("text-[9px] font-black", isBuy ? "text-violet-100" : "text-pink-300")}>{isBuy ? "▲" : "▼"}</span>
                <span className={cn("font-mono text-[10px] font-black", stageLabelColor(lb.stage))}>S{lb.stage}</span>
              </div>
            </div>
          )}
          <div className={cn("w-[48px] text-right font-mono text-[16px] font-black leading-none", isBuy ? "text-slate-100" : "text-pink-300")}>
            {lb.scoreSum > 0 ? "+" : ""}{lb.scoreSum}
          </div>
        </div>
      </div>

      <div className="relative z-10 mt-2">
        <div className="mb-1 flex items-center justify-between font-mono text-[8px] font-black uppercase tracking-wider text-slate-600">
          <span>Aggregate Strength</span>
          <span>{Math.round(pct)}%</span>
        </div>
        <div className="relative h-1.5 w-full overflow-hidden rounded-sm border border-white/[0.06] bg-black/35">
          <div
            className={cn(
              "h-full rounded-sm transition-all duration-1000",
              isBuy
                ? "bg-gradient-to-r from-violet-700 via-violet-400 to-fuchsia-300"
                : "bg-gradient-to-r from-pink-700 via-fuchsia-500 to-rose-300"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="relative z-10 mt-1.5 flex items-center justify-between font-mono text-[8px] font-black uppercase text-slate-600">
        <span>Total {lb.total}</span>
        <span>Abs {Math.round(lb.absSum)}</span>
        <span>RM ×{(0.8 + (lb.stage * 0.15)).toFixed(2)}</span>
      </div>
    </button>
  );
}

function stageLabelColor(stage: number): string {
  if (stage === 3) return "text-violet-50";
  if (stage === 2) return "text-violet-100";
  if (stage === 1) return "text-fuchsia-300";
  return "text-violet-200/35";
}

function stageLabelText(stage: number): string {
  if (stage === 3) return "확신";
  if (stage === 2) return "진입";
  if (stage === 1) return "대기";
  return "관망";
}

/* ─────────────────────────────────────────────────────────
   Helpers
 ───────────────────────────────────────────────────────── */
function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

export function stageBadgeCls(stage: number, dir: number): string {
  if (stage === 3) return "border-violet-300/45 bg-violet-500/15 text-violet-100 shadow-[0_0_12px_rgba(167,139,250,0.18)]";
  if (stage === 2) return dir >= 0
    ? "border-violet-300/40 bg-violet-500/12 text-violet-200 shadow-[0_0_10px_rgba(167,139,250,0.14)]"
    : "border-pink-300/40 bg-pink-500/12 text-pink-300 shadow-[0_0_10px_rgba(244,114,182,0.14)]";
  if (stage === 1) return "border-fuchsia-300/40 bg-fuchsia-500/10 text-fuchsia-300 shadow-[0_0_10px_rgba(217,70,239,0.12)]";
  return "border-violet-300/10 bg-violet-950/20 text-violet-200/35";
}

function stageGateLabel(score: number, stage: number, dir: number): string {
  const sign = score >= 0 ? "+" : "";
  if (stage === 0) return `Standby Protocol ${sign}${score}`;
  if (stage === 1) return `Signal Accumulation ${sign}${score}`;
  if (stage === 2) return `${dir >= 0 ? "Bullish" : "Bearish"} Execution ${sign}${score}`;
  return `${dir >= 0 ? "Prime Long" : "Prime Short"} Focus ${sign}${score}`;
}

/* ─────────────────────────────────────────────────────────
   Sub-components
 ───────────────────────────────────────────────────────── */
function TabBtn({ active, onClick, children, icon }: { active: boolean; onClick: () => void; children: string; icon?: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={cn("flex items-center gap-1.5 rounded-md border px-4 py-1.5 text-[10px] font-black tracking-widest transition-all",
        active
          ? "border-violet-300/35 bg-violet-500/12 text-violet-100 shadow-[0_0_10px_rgba(139,92,246,0.1)]"
          : "border-white/[0.07] bg-white/[0.02] text-slate-600 hover:bg-white/[0.04] hover:text-slate-300"
      )}>
      {icon}
      {children}
    </button>
  );
}

function RegimeCell({ label, value, sub, tone, bar }: {
  label: string; value: string; sub: string; tone: string; bar: number;
}) {
  const colorMap: Record<string, string> = {
    "text-pink-300": "#f472b6",
    "text-fuchsia-300": "#f0abfc",
    "text-violet-300": "#c4b5fd",
    "text-violet-200/60": "rgba(221,214,254,0.6)",
  };
  const barColor = colorMap[tone] ?? "#c4b5fd";

  return (
    <div className="group mb-3 flex flex-col gap-2 rounded-lg border border-white/[0.06] bg-[#090a12] p-3 transition-all hover:border-violet-300/22 hover:bg-[#0d0e18]">
      <div className="text-[9px] font-black uppercase tracking-[0.18em] text-slate-600 transition-colors group-hover:text-slate-400">{label}</div>
      <div className="flex items-end justify-between gap-4">
        <div className={cn("font-mono text-[16px] font-black leading-none tracking-tight", tone)}>{value}</div>
        <div className="border-b border-violet-300/10 pb-0.5 text-[9px] font-black uppercase tracking-widest text-slate-500">{sub}</div>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-sm border border-white/[0.06] bg-black/35">
        <div
          className="h-full rounded-sm transition-all duration-1000"
          style={{ width: `${Math.round(bar * 100)}%`, backgroundColor: barColor }}
        />
      </div>
    </div>
  );
}
