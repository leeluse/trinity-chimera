"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useTerminalStore } from "./terminalStore";
import {
  mountHunterRuntime,
  type HunterLeaderboardItem,
  type HunterRow,
  type HunterRuntimeSnapshot,
  type HunterSortMode,
} from "./hunterRuntime";
import { mergeRows, isCompositeSignal } from "./compositeSignal";
import type { EnrichedRow }  from "./compositeSignal";
import { useCrimeStore } from "@/store/useCrimeStore";

type HunterTab = "lb" | "rg" | "pre";

function FuelBlocks({ value }: { value: number }) {
  const BLOCKS = 5;
  const filled = Math.round((value / 100) * BLOCKS);
  const color =
    value >= 80 ? "bg-violet-400 shadow-[0_0_3px_rgba(167,139,250,0.6)]" :
    value >= 60 ? "bg-indigo-400" :
    "bg-white/20";
  return (
    <div className="flex gap-[2px] items-center ml-1">
      {Array.from({ length: BLOCKS }).map((_, i) => (
        <div key={i} className={`w-[3px] h-[7px] rounded-[1px] ${i < filled ? color : "bg-white/[0.06]"}`} />
      ))}
    </div>
  );
}

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
  const { setSelectedSymbol, setHunterRows, setHunterRegime, setHunterAlert } = useTerminalStore();
  const [tab, setTab] = useState<HunterTab>("lb");
  const [state, setState] = useState<HunterRuntimeSnapshot>(INITIAL);
  const runtimeRef = useRef<ReturnType<typeof mountHunterRuntime> | null>(null);
  const prevRowsRef = useRef<HunterRow[]>([]);

  const crimeResults = useCrimeStore((s) => s.results);
  const enrichedRows = useMemo(
    () => mergeRows(state.rows, crimeResults),
    [state.rows, crimeResults]
  );
  
  const { setCompositeAlert } = useTerminalStore();
  const prevCompositeRef = useRef<Set<string>>(new Set());

  const sortedRows = useMemo(() => {
    if (state.sortMode !== 'combo') return enrichedRows;
    return [...enrichedRows].sort((a, b) => b.compositeScore - a.compositeScore);
  }, [enrichedRows, state.sortMode]);

  useEffect(() => {
    const runtime = mountHunterRuntime((snapshot) => {
      setState(snapshot);
      setHunterRows(snapshot.rows);
      setHunterRegime(snapshot.regime);

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
  }, []);

  useEffect(() => {
    const next = new Set<string>();
    for (const row of enrichedRows) {
      if (isCompositeSignal(row)) {
        next.add(row.full);
        if (!prevCompositeRef.current.has(row.full)) {
          setCompositeAlert({
            sym:            row.sym,
            full:           row.full,
            crimeStage:     row.crimeStage,
            hunterStage:    row.stage,
            squeezeFuel:    row.squeezeFuel,
            compositeScore: row.compositeScore,
            ts:             Date.now(),
          });
        }
      }
    }
    prevCompositeRef.current = next;
  }, [enrichedRows, setCompositeAlert]);

  const onStart = () => { void runtimeRef.current?.api.startSystem(); };
  const onStop = () => { runtimeRef.current?.api.stopSystem(); };
  const onToggleFreeze = () => { runtimeRef.current?.api.toggleFreeze(); };
  const onToggleFocus = () => { runtimeRef.current?.api.toggleFocus(); };
  const onToggleMute = () => { runtimeRef.current?.api.toggleMute(); };
  const onSetSort = (mode: HunterSortMode) => { runtimeRef.current?.api.setSort(mode); };

  const wsTagClass = (on: boolean) =>
    cn(
      "rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-widest",
      on ? "border-blue-400/70 text-blue-300 bg-blue-400/10" : "border-white/[0.12] text-slate-600",
    );

  const biasColor = state.summary.bias.includes("ALT강세")
    ? "text-blue-400"
    : state.summary.bias.includes("ALT약세")
      ? "text-rose-400"
      : "text-slate-400";

  return (
    <div className="flex h-full flex-col bg-[#030508]/60 backdrop-blur-xl border-l border-white/5">
      {/* ── Header ── */}
      <div className="border-b border-white/10 px-3 py-2.5 bg-gradient-to-r from-black/40 to-cyan-950/20">
        <div className="flex items-center gap-2">
          <div className="text-[12px] font-black uppercase tracking-[0.2em] text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-400 drop-shadow-[0_0_10px_rgba(34,211,238,0.5)]">
            ◈ TRINITY FUSION ENGINE
          </div>
          <span className="rounded border border-violet-500/30 bg-violet-500/10 px-1.5 py-0.5 text-[7px] font-bold text-violet-300">
            HUNTER × CRIME
          </span>
        </div>
        <div className="mt-1 text-[8px] text-slate-500 tracking-widest">
          Stage Gate + Latch + Multi-WS
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className={wsTagClass(state.ws.bn)}>BN</span>
          <span className={wsTagClass(state.ws.okx)}>OKX</span>
          <span className={wsTagClass(state.ws.bybit)}>BYB</span>
          <span className={wsTagClass(state.ws.bitget)}>BIT</span>
          <button type="button" onClick={onToggleFreeze}
            className={cn("ml-auto rounded border px-2 py-0.5 text-[9px] font-bold transition-colors",
              state.frozen ? "border-sky-400/60 bg-sky-400/10 text-sky-300 shadow-[0_0_10px_rgba(56,189,248,0.2)]" : "border-white/10 text-slate-500 hover:text-cyan-300 hover:border-cyan-400/30"
            )}>
            {state.frozen ? "▶ 재개" : "⏸ 정지"}
          </button>
          <button type="button" onClick={onToggleFocus}
            className={cn("rounded border px-2 py-0.5 text-[9px] font-bold transition-colors",
              state.focusMode ? "border-violet-400/60 bg-violet-400/10 text-violet-300 shadow-[0_0_10px_rgba(167,139,250,0.2)]" : "border-white/10 text-slate-500 hover:text-cyan-300 hover:border-cyan-400/30"
            )}>
            🎯 포커스
          </button>
          <button type="button" onClick={onToggleMute}
            className={cn("rounded border px-2 py-0.5 text-[9px] font-bold transition-colors",
              state.muted ? "border-rose-400/60 bg-rose-400/10 text-rose-300 shadow-[0_0_10px_rgba(251,113,133,0.2)]" : "border-white/10 text-slate-500 hover:text-white"
            )}>
            {state.muted ? "🔇" : "🔊"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <button type="button" onClick={onStart} disabled={state.running}
            className={cn("rounded border px-3 py-1 text-[10px] font-black uppercase tracking-wider transition-all",
              state.running ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-300 animate-pulse shadow-[0_0_15px_rgba(34,211,238,0.2)]" : "border-cyan-400/30 text-cyan-300 hover:bg-cyan-400/10 hover:shadow-[0_0_15px_rgba(34,211,238,0.2)]"
            )}>
            {state.running ? "■ 감시중" : "▶ 가동"}
          </button>
          {state.running && (
            <button type="button" onClick={onStop}
              className="rounded border border-rose-500/60 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-rose-300 hover:bg-rose-500/10">
              STOP
            </button>
          )}
          <span className="ml-auto text-[9px] text-slate-400 font-mono tracking-widest">{state.statusText}</span>
        </div>
      </div>

      {/* ── Summary 5-box ── */}
      <div className="flex border-b border-white/10 bg-black/20">
        <SumBox label="스나이퍼" value={String(state.summary.snipers)} tone="text-cyan-400" />
        <SumBox label="S2+ 진입" value={String(state.summary.s2plus)} tone="text-blue-400" />
        <SumBox label="S1 대기" value={String(state.summary.s1)} tone="text-orange-400" />
        <SumBox label="레짐 편향" value={state.summary.bias} tone={biasColor} small />
        <SumBox label="선행" value={String(state.summary.pre)} tone="text-cyan-400" last />
      </div>

      {/* ── Tabs ── */}
      <div className="flex border-b border-white/10 bg-black/40">
        <TabBtn active={tab === "lb"} onClick={() => setTab("lb")}>🏆 리더보드</TabBtn>
        <TabBtn active={tab === "rg"} onClick={() => setTab("rg")}>📊 레짐</TabBtn>
        <TabBtn active={tab === "pre"} onClick={() => setTab("pre")}>🔮 선행</TabBtn>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto no-scrollbar">

        {/* ── Leaderboard tab ── */}
        {tab === "lb" && (
          <div>
            {/* Sort bar */}
            <div className="flex border-b border-white/10 bg-black/40">
              {(["total","cross","sqz","whale"] as HunterSortMode[]).map((m) => {
                const label = m === "total" ? "🔥전체" : m === "cross" ? "⚡크로스" : m === "sqz" ? "💥스퀴즈" : "🐋고래";
                return (
                  <button key={m} type="button" onClick={() => onSetSort(m)}
                    className={cn("flex-1 py-1.5 text-[9px] font-bold border-r border-white/5 last:border-r-0 transition-colors",
                      state.sortMode === m ? "text-cyan-300 bg-white/[0.08] shadow-[inset_0_-1px_0_rgba(34,211,238,0.5)]" : "text-slate-500 hover:text-slate-300"
                    )}>
                    {label}
                  </button>
                );
              })}
              <button onClick={() => onSetSort('combo')}
                className={cn("text-[9px] uppercase px-1.5 py-0.5 rounded border",
                  state.sortMode === 'combo'
                    ? "border-violet-400/70 text-violet-300 bg-violet-400/10"
                    : "border-white/10 text-slate-500 hover:text-white/40")}>
                COMBO
              </button>
            </div>

            {/* Sniper targets header */}
            <div className="flex items-center justify-between border-b border-white/5 bg-black/60 px-3 py-1.5">
              <span className="text-[9px] font-bold text-cyan-400 tracking-[0.1em]">🎯 FUSION TARGETS</span>
            </div>
            <div className="flex border-b border-white/5 bg-black/40 text-[8px] text-slate-500 uppercase tracking-widest">
              <div className="w-[100px] px-2 py-1">Symbol</div>
              <div className="w-[110px] px-2 py-1">Hunter Stage</div>
              <div className="w-[130px] px-2 py-1">CRIME Phase</div>
              <div className="flex-1 px-2 py-1">Composite & Signals</div>
            </div>

            {/* Sniper rows */}
            {sortedRows.length === 0 && (
              <div className="flex flex-col items-center justify-center py-10 opacity-70">
                <div className="relative flex h-12 w-12 items-center justify-center rounded-full border border-cyan-500/20 bg-cyan-500/5">
                  <div className={cn("absolute inset-0 rounded-full border border-cyan-500/40", state.running && "animate-ping")} />
                  <span className="text-cyan-500 text-[18px]">⚡</span>
                </div>
                <div className="mt-3 text-center">
                  <p className="text-[11px] font-bold uppercase tracking-widest text-cyan-400">
                    {state.running ? "Engine Scanning" : "System Standby"}
                  </p>
                  <p className="mt-1 text-[9px] uppercase tracking-widest text-slate-500">
                    {state.running ? "Searching for signals..." : "Waiting for initialization"}
                  </p>
                </div>
              </div>
            )}
            {sortedRows.map((row) => (
              <SniperRow key={row.full} row={row as EnrichedRow} onSelect={() => setSelectedSymbol(row.full)} focusMode={state.focusMode} />
            ))}

            {/* Leaderboard (sigHist) */}
            <div className="mt-1 border-t border-white/5 bg-black/40 px-3 py-1.5 text-[9px] font-bold uppercase tracking-widest text-slate-500">
              🏆 FUSION LEADERBOARD (30 MIN)
            </div>
            {state.leaderboard.length === 0 && (
              <div className="px-3 py-4 text-center text-[10px] italic text-slate-600">시그널 대기중...</div>
            )}
            {state.leaderboard.slice(0, 12).map((lb, idx) => (
              <LeaderboardCard key={lb.sym} lb={lb} idx={idx} onSelect={() => setSelectedSymbol(lb.sym)} />
            ))}
          </div>
        )}

        {/* ── Regime tab ── */}
        {tab === "rg" && (
          <div className="space-y-px bg-white/5">
            <RegimeCell
              label="BTC vs ALT 상대강도"
              value={`${state.regime.btcAltDelta >= 0 ? "+" : ""}${state.regime.btcAltDelta.toFixed(2)}%`}
              sub={state.regime.btcAltDelta > 0.5 ? "BTC 우세 — ALT 약세" : state.regime.btcAltDelta < -0.5 ? "ALT 우세" : "혼조"}
              tone={state.regime.btcAltDelta > 0.5 ? "text-rose-400" : state.regime.btcAltDelta < -0.5 ? "text-cyan-400" : "text-slate-400"}
              bar={clamp((state.regime.btcAltDelta + 5) / 10, 0, 1)}
            />
            <RegimeCell
              label="평균 펀딩(스나이퍼)"
              value={`${state.regime.avgFunding >= 0 ? "+" : ""}${state.regime.avgFunding.toFixed(4)}%`}
              sub={Math.abs(state.regime.avgFunding) > 0.05 ? "극단 수준" : Math.abs(state.regime.avgFunding) > 0.03 ? "높음" : "정상"}
              tone={Math.abs(state.regime.avgFunding) > 0.03 ? "text-cyan-400" : "text-slate-400"}
              bar={clamp((state.regime.avgFunding + 0.2) / 0.4, 0, 1)}
            />
            <RegimeCell
              label="OI 확장 비율"
              value={`${state.regime.oiExpansionRate.toFixed(1)}%`}
              sub={state.regime.oiExpansionRate > 60 ? "과열" : "정상"}
              tone={state.regime.oiExpansionRate > 60 ? "text-cyan-400" : "text-slate-400"}
              bar={clamp(state.regime.oiExpansionRate / 100, 0, 1)}
            />
            <RegimeCell
              label="시그널 롱/숏 흐름"
              value={`${state.regime.longFlowRatio.toFixed(0)}%`}
              sub={state.regime.longFlowRatio > 60 ? "롱 우세" : state.regime.longFlowRatio < 40 ? "숏 우세" : "균형"}
              tone={state.regime.longFlowRatio > 60 ? "text-cyan-400" : state.regime.longFlowRatio < 40 ? "text-rose-400" : "text-slate-400"}
              bar={clamp(state.regime.longFlowRatio / 100, 0, 1)}
            />
          </div>
        )}

        {/* ── Pre-signals tab ── */}
        {tab === "pre" && (
          <div>
            {state.preSignals.length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] italic text-slate-500">선행 시그널 감시중...</div>
            )}
            {state.preSignals.slice(0, 30).map((p, idx) => (
              <button
                key={`${p.sym}-${p.type}-${idx}`}
                type="button"
                onClick={() => setSelectedSymbol(p.sym)}
                className={cn(
                  "w-full border-b border-[#2a2000] px-3 py-2 text-left hover:bg-amber-500/[0.06]",
                  p.dir > 0 ? "border-l-2 border-l-blue-500/60 bg-blue-500/[0.03]" : "border-l-2 border-l-rose-500/60 bg-rose-500/[0.03]"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-black text-slate-200">{p.sym.replace("USDT", "")}</span>
                  <span className={cn("text-[10px] font-bold", p.dir > 0 ? "text-blue-400" : "text-rose-400")}>
                    {p.dir > 0 ? "▲" : "▼"} {p.score > 0 ? "+" : ""}{p.score}
                  </span>
                </div>
                <div className="mt-0.5 text-[10px] text-slate-300">{p.title}</div>
                <div className="mt-0.5 text-[9px] text-slate-500">{p.desc}</div>
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
  row: EnrichedRow;
  onSelect: () => void;
  focusMode: boolean;
}) {
  if (focusMode && row.stage < 2 && !row.pinned) return null;

  const pct = Math.min(Math.abs(row.score) / 180, 1) * 50;
  const isBull = row.latchDir >= 0;
  const opacity = row.stage > 0 ? Math.max(0.4, 0.4 + 0.6 * row.latchRatio) : 1;

  // Row background class
  const rowBg = row.aGradeActive
    ? (row.aGradeDir > 0
        ? "border-t border-b border-blue-500/60 bg-blue-500/[0.12] animate-pulse"
        : "border-t border-b border-rose-500/60 bg-rose-500/[0.12] animate-pulse")
    : row.pinned
      ? "border-t border-dashed border-amber-500/40 bg-amber-500/[0.06]"
      : row.stage >= 2 && row.score >= 60 ? "bg-blue-500/[0.10]"
      : row.stage >= 2 && row.score <= -60 ? "bg-rose-500/[0.10]"
      : row.stage >= 1 && row.score >= 30 ? "bg-blue-500/[0.04]"
      : row.stage >= 1 && row.score <= -30 ? "bg-rose-500/[0.04]"
      : "";

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "group w-full border-b border-white/[0.02] px-0 py-0 text-left transition-colors hover:bg-cyan-500/[0.06] cursor-pointer",
        rowBg,
        isCompositeSignal(row) && "ring-1 ring-violet-500/40 bg-violet-500/[0.05]"
      )}
    >
      <div className="flex items-center">
        {/* Symbol Column */}
        <div className="w-[100px] shrink-0 px-2 py-2">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-1">
              <span className="text-[10px]">{row.stage >= 2 ? "🚀" : row.stage === 1 ? "⚡" : "·"}</span>
              <span className="font-mono text-[13px] font-black text-slate-200">{row.sym}</span>
              {row.pinned && <span className="text-[9px] text-cyan-400">📌</span>}
            </div>
            {row.aGradeCount > 0 && (
              <span className={cn(
                "w-fit rounded px-1 py-0.5 text-[7px] font-black leading-3",
                row.aGradeActive
                  ? (row.aGradeDir > 0
                      ? "bg-blue-500 text-white shadow-[0_0_6px_rgba(59,130,246,0.6)]"
                      : "bg-rose-500 text-white shadow-[0_0_6px_rgba(244,63,94,0.6)]")
                  : (row.aGradeDir > 0
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/30"
                      : "bg-rose-500/10 text-rose-400 border border-rose-500/30")
              )}>
                👑 A급 {row.aGradeDir > 0 ? "매수" : "매도"}
              </span>
            )}
          </div>
        </div>

        {/* Hunter Stage Column */}
        <div className="w-[110px] shrink-0 px-1 py-2 border-l border-white/5">
          <div className="flex flex-col gap-1 w-full max-w-[90px]">
            <div className="flex items-center justify-between">
              <div
                className={cn("relative rounded px-1 pt-0.5 pb-0.5 text-[8px] font-black font-mono overflow-hidden border", stageBadgeCls(row.stage, row.latchDir))}
                style={{ opacity }}
              >
                S{row.stage}
                <div className="absolute bottom-0 left-0 h-[2px] bg-current transition-all" style={{ width: `${row.latchRatio * 100}%` }} />
              </div>
              <span className={cn("text-[8px] font-mono font-bold", isBull ? "text-cyan-400" : "text-rose-400")}>
                {row.score > 0 ? "+" : ""}{row.score}
              </span>
            </div>
            {/* Center Bar */}
            <div className="relative h-[4px] rounded-full bg-black/50 border border-white/10 overflow-hidden">
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/20 z-10" />
              <div
                className={cn("absolute top-0 bottom-0 transition-all duration-300", isBull
                  ? "left-1/2 bg-gradient-to-r from-cyan-800/80 to-cyan-400"
                  : "right-1/2 bg-gradient-to-l from-rose-800/80 to-rose-400"
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>

        {/* CRIME Phase Column */}
        <div className="w-[130px] shrink-0 px-2 py-2 border-l border-white/5">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <span className={cn(
                "text-[8px] font-bold px-1.5 py-0.5 rounded border tracking-widest",
                (row as EnrichedRow).crimeStage === "IGNITION"
                  ? "border-violet-500/60 text-violet-300 bg-violet-500/10 shadow-[0_0_8px_rgba(139,92,246,0.3)]"
                  : (row as EnrichedRow).crimeStage === "PRE_IGNITION"
                  ? "border-indigo-400/60 text-indigo-300 bg-indigo-400/10"
                  : (row as EnrichedRow).crimeStage === "SPRING"
                  ? "border-emerald-400/60 text-emerald-300 bg-emerald-400/10"
                  : "border-white/10 text-white/30"
              )}>
                {(row as EnrichedRow).crimeStage === "NONE" ? "STANDBY" : (row as EnrichedRow).crimeStage}
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="text-[7px] text-slate-500 uppercase">Fuel</span>
              <FuelBlocks value={(row as EnrichedRow).squeezeFuel} />
              <span className="text-[8px] font-mono text-slate-400 ml-1">{(row as EnrichedRow).squeezeFuel}%</span>
            </div>
          </div>
        </div>

        {/* Composite & Signals Column */}
        <div className="flex-1 min-w-0 px-2 py-2 border-l border-white/5">
          <div className="flex items-center justify-between">
            <div className="flex flex-wrap gap-0.5">
              {row.sig.slice(0, 4).map((s, i) => (
                <span key={i} className={cn(
                  "inline-block rounded border px-1 py-0.5 text-[7px] font-bold leading-3",
                  s.cat === "setup"
                    ? "text-cyan-300 border-cyan-500/40 bg-cyan-500/10"
                    : s.d > 0
                      ? "text-blue-400 border-blue-500/40 bg-blue-500/10"
                      : "text-rose-400 border-rose-500/40 bg-rose-500/10"
                )}>
                  {s.n}
                </span>
              ))}
            </div>
            {/* Composite Score Highlight */}
            {(row as EnrichedRow).compositeScore > 0 && (
              <div className="flex items-center gap-1 ml-2 bg-violet-500/10 border border-violet-500/30 rounded px-1.5 py-0.5">
                <span className="text-[7px] text-violet-400 font-bold">CMP</span>
                <span className="font-mono text-[10px] font-black text-violet-300">
                  {(row as EnrichedRow).compositeScore}
                </span>
              </div>
            )}
          </div>
          <div className="mt-1.5 flex gap-2 text-[8px] text-slate-500 font-mono">
            <span>CVD {row.cvd >= 0 ? "+" : ""}{(row.cvd / 1000).toFixed(1)}k</span>
            {row.mult > 0.1 && <span>×{row.mult.toFixed(1)}</span>}
          </div>
        </div>
      </div>
    </button>
  );
}

/* ─────────────────────────────────────────────────────────
   Leaderboard Card (sigHist-based)
───────────────────────────────────────────────────────── */
function LeaderboardCard({ lb, idx, onSelect }: {
  lb: HunterLeaderboardItem;
  idx: number;
  onSelect: () => void;
}) {
  const isBuy = lb.scoreSum >= 0;
  return (
    <button
      type="button"
      onClick={onSelect}
      className="group w-full border-b border-white/[0.02] px-3 py-2 text-left transition-colors hover:bg-cyan-500/[0.06] cursor-pointer"
    >
      <div className="flex items-center justify-between gap-1">
        {/* Left: rank + sym + badges */}
        <div className="flex items-center gap-1 flex-wrap min-w-0">
          <span className="text-[9px] text-slate-500">{idx + 1}.</span>
          <span className="font-mono text-[12px] font-black text-slate-200">
            {lb.sym.replace("USDT", "")}
          </span>
          {/* A급 badge */}
          {lb.aGradeCount > 0 && (
            <span className={cn(
              "inline-block rounded px-1 py-0 text-[8px] font-black leading-4",
              lb.aGradeDir > 0
                ? "bg-blue-500/10 text-blue-400 border border-blue-500/60"
                : "bg-rose-500/10 text-rose-400 border border-rose-500/60"
            )}>
              👑 A급 {lb.aGradeDir > 0 ? "매수" : "매도"} {lb.aGradeCount}회
            </span>
          )}
          {/* Stage badge */}
          {lb.stage > 0 && (
            <span className={cn("rounded border px-1 text-[7px] font-black font-mono", stageBadgeCls(lb.stage, lb.aGradeDir))}>
              S{lb.stage}
            </span>
          )}
        </div>
        {/* Right: dir badge + score */}
        <div className="flex items-center gap-1 shrink-0">
          {lb.scoreSum >= 30
            ? <span className="rounded px-1 py-0 text-[8px] font-black bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">▲매수</span>
            : lb.scoreSum <= -30
              ? <span className="rounded px-1 py-0 text-[8px] font-black bg-rose-500/20 text-rose-400 border border-rose-500/30">▼매도</span>
              : <span className="rounded px-1 py-0 text-[8px] font-black bg-slate-500/10 text-slate-400 border border-white/10">⚡혼조</span>
          }
          <span className={cn("font-mono text-[11px] font-bold", isBuy ? "text-blue-400" : "text-rose-400")}>
            {lb.scoreSum > 0 ? "+" : ""}{lb.scoreSum}
          </span>
        </div>
      </div>
      {/* Signal tags */}
      {Object.keys(lb.tags).length > 0 && (
        <div className="mt-1 flex flex-wrap gap-0.5">
          {Object.entries(lb.tags).map(([name, count]) => (
            <span key={name} className={cn(
              "inline-block rounded border bg-black/40 px-1 text-[8px] font-bold leading-4 shadow-sm",
              isBuy ? "text-cyan-400 border-cyan-500/30" : "text-rose-400 border-rose-500/30"
            )}>
              {name}{count > 1 ? ` ${count}` : ""}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

/* ─────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────── */
function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function stageBadgeCls(stage: number, dir: number): string {
  if (stage === 3) return "text-cyan-400 border-cyan-500/70 bg-cyan-500/15 shadow-[0_0_8px_rgba(34,211,238,0.3)]";
  if (stage === 2) return dir >= 0
    ? "text-blue-400 border-blue-500/70 bg-blue-500/15"
    : "text-rose-400 border-rose-500/70 bg-rose-500/15";
  if (stage === 1) return "text-slate-300 border-slate-500/70 bg-slate-500/10";
  return "text-slate-500 border-white/10";
}

function stageGateLabel(score: number, stage: number, dir: number): string {
  const sign = score >= 0 ? "+" : "";
  if (stage === 0) return `— ${score}`;
  if (stage === 1) return `⊙ 대기 ${sign}${score}`;
  if (stage === 2) return `${dir >= 0 ? "▲ 매수" : "▼ 매도"} ${sign}${score}`;
  return `${dir >= 0 ? "▲▲ 강매수" : "▼▼ 강매도"} ${sign}${score}`;
}

/* ─────────────────────────────────────────────────────────
   Sub-components
───────────────────────────────────────────────────────── */
function SumBox({ label, value, tone, small, last }: {
  label: string; value: string; tone: string; small?: boolean; last?: boolean;
}) {
  return (
    <div className={cn(
      "group relative flex-1 flex flex-col items-center py-2.5 gap-1 overflow-hidden transition-colors hover:bg-white/[0.04]",
      !last && "border-r border-white/5"
    )}>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-500/0 to-transparent opacity-0 transition-opacity duration-300 group-hover:via-cyan-500/50 group-hover:opacity-100" />
      <div className="text-[8px] uppercase tracking-[0.2em] text-slate-500 transition-colors group-hover:text-slate-300">{label}</div>
      <div className={cn("font-mono font-black drop-shadow-[0_0_5px_currentColor]", tone, small ? "text-[11px]" : "text-[14px]")}>{value}</div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" onClick={onClick}
      className={cn("relative flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-all duration-200 overflow-hidden",
        active 
          ? "text-cyan-400 bg-cyan-500/[0.08]" 
          : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
      )}>
      {active && (
        <div className="absolute bottom-0 left-0 h-[2px] w-full bg-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.8)]" />
      )}
      {children}
    </button>
  );
}

function RegimeCell({ label, value, sub, tone, bar }: {
  label: string; value: string; sub: string; tone: string; bar: number;
}) {
  const colorMap: Record<string, string> = {
    "text-rose-300": "#fca5a5",
    "text-blue-300": "#93c5fd",
    "text-cyan-400": "#22d3ee",
    "text-rose-400": "#fb7185",
    "text-slate-400": "#94a3b8",
  };
  const barColor = colorMap[tone] ?? "#94a3b8";

  return (
    <div className="group relative bg-black/20 px-4 py-4 flex flex-col gap-1.5 border-b border-white/5 overflow-hidden transition-colors hover:bg-white/[0.04]">
      <div className="absolute left-0 top-0 h-full w-[2px] bg-gradient-to-b from-transparent via-cyan-500/30 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      <div className="text-[9px] uppercase tracking-[0.2em] font-bold text-slate-500 transition-colors group-hover:text-slate-400">{label}</div>
      <div className={cn("font-mono text-[22px] font-black leading-none drop-shadow-md", tone)}>{value}</div>
      <div className="text-[10px] text-slate-500/70">{sub}</div>
      <div className="mt-2 h-[4px] w-full rounded-full bg-black/40 overflow-hidden border border-white/5">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out shadow-[0_0_10px_currentColor]"
          style={{ width: `${Math.round(bar * 100)}%`, backgroundColor: barColor, color: barColor }}
        />
      </div>
    </div>
  );
}
