"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useTerminalStore } from "./terminalStore";
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
  const { setSelectedSymbol, setHunterRows, setHunterRegime, setHunterAlert } = useTerminalStore();
  const [tab, setTab] = useState<HunterTab>("lb");
  const [state, setState] = useState<HunterRuntimeSnapshot>(INITIAL);
  const runtimeRef = useRef<ReturnType<typeof mountHunterRuntime> | null>(null);
  const prevRowsRef = useRef<HunterRow[]>([]);

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
    <div className="flex h-full flex-col bg-[#060400]">
      {/* ── Header ── */}
      <div className="border-b border-[#2a2000] px-3 py-2.5">
        <div className="text-[11px] font-black uppercase tracking-[0.2em] text-amber-400">
          ◈ ALPHA HUNTER V16
        </div>
        <div className="mt-0.5 text-[8px] text-[#604828]">
          Stage Gate + Latch + Multi-WS
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className={wsTagClass(state.ws.bn)}>BN</span>
          <span className={wsTagClass(state.ws.okx)}>OKX</span>
          <span className={wsTagClass(state.ws.bybit)}>BYB</span>
          <span className={wsTagClass(state.ws.bitget)}>BIT</span>
          <button type="button" onClick={onToggleFreeze}
            className={cn("ml-auto rounded border px-2 py-0.5 text-[9px] font-bold",
              state.frozen ? "border-sky-400/60 bg-sky-400/10 text-sky-300" : "border-[#2a2000] text-[#604828] hover:text-amber-300"
            )}>
            {state.frozen ? "▶ 재개" : "⏸ 정지"}
          </button>
          <button type="button" onClick={onToggleFocus}
            className={cn("rounded border px-2 py-0.5 text-[9px] font-bold",
              state.focusMode ? "border-violet-400/60 bg-violet-400/10 text-violet-300" : "border-[#2a2000] text-[#604828] hover:text-amber-300"
            )}>
            🎯 포커스
          </button>
          <button type="button" onClick={onToggleMute}
            className={cn("rounded border px-2 py-0.5 text-[9px] font-bold",
              state.muted ? "border-rose-400/60 bg-rose-400/10 text-rose-300" : "border-[#2a2000] text-[#604828]"
            )}>
            {state.muted ? "🔇" : "🔊"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <button type="button" onClick={onStart} disabled={state.running}
            className={cn("rounded border px-3 py-1 text-[10px] font-black uppercase tracking-wider",
              state.running ? "border-blue-400/50 bg-blue-400/10 text-blue-300 animate-pulse" : "border-amber-400/60 text-amber-300 hover:bg-amber-400/10"
            )}>
            {state.running ? "■ 감시중" : "▶ 가동"}
          </button>
          {state.running && (
            <button type="button" onClick={onStop}
              className="rounded border border-rose-500/60 px-3 py-1 text-[10px] font-black uppercase tracking-wider text-rose-300 hover:bg-rose-500/10">
              STOP
            </button>
          )}
          <span className="ml-auto text-[9px] text-[#604828]">{state.statusText}</span>
        </div>
      </div>

      {/* ── Summary 5-box ── */}
      <div className="flex border-b border-[#2a2000]">
        <SumBox label="스나이퍼" value={String(state.summary.snipers)} tone="text-amber-400" />
        <SumBox label="S2+ 진입" value={String(state.summary.s2plus)} tone="text-blue-400" />
        <SumBox label="S1 대기" value={String(state.summary.s1)} tone="text-orange-400" />
        <SumBox label="레짐 편향" value={state.summary.bias} tone={biasColor} small />
        <SumBox label="선행" value={String(state.summary.pre)} tone="text-cyan-400" last />
      </div>

      {/* ── Tabs ── */}
      <div className="flex border-b border-[#2a2000] bg-[#0c0800]">
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
            <div className="flex border-b border-[#2a2000] bg-[#0c0800]">
              {(["total","cross","sqz","whale"] as HunterSortMode[]).map((m) => {
                const label = m === "total" ? "🔥전체" : m === "cross" ? "⚡크로스" : m === "sqz" ? "💥스퀴즈" : "🐋고래";
                return (
                  <button key={m} type="button" onClick={() => onSetSort(m)}
                    className={cn("flex-1 py-1.5 text-[9px] font-bold border-r border-[#2a2000] last:border-r-0",
                      state.sortMode === m ? "text-amber-300 bg-white/[0.08]" : "text-[#604828] hover:text-[#bba383]"
                    )}>
                    {label}
                  </button>
                );
              })}
            </div>

            {/* Sniper targets header */}
            <div className="flex items-center justify-between border-b border-[#2a2000] bg-[#130d00] px-3 py-1.5">
              <span className="text-[9px] font-bold text-amber-300">🎯 SNIPER TARGETS — ANTI-FLICKER GATE</span>
            </div>
            <div className="flex border-b border-[#2a2000] bg-[#0c0800] text-[8px] text-[#604828]">
              <div className="flex-1 px-2 py-1">종목</div>
              <div className="w-[140px] px-2 py-1">Stage Gate 판정</div>
              <div className="flex-1 px-2 py-1">시그널</div>
            </div>

            {/* Sniper rows */}
            {state.rows.length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] italic text-[#604828]">시스템 가동 대기중...</div>
            )}
            {state.rows.map((row) => (
              <SniperRow key={row.full} row={row} onSelect={() => setSelectedSymbol(row.full)} focusMode={state.focusMode} />
            ))}

            {/* Leaderboard (sigHist) */}
            <div className="mt-1 border-t border-[#2a2000] bg-[#0c0800] px-3 py-1.5 text-[9px] font-bold uppercase tracking-widest text-[#604828]">
              리더보드 (30분)
            </div>
            {state.leaderboard.length === 0 && (
              <div className="px-3 py-4 text-center text-[10px] italic text-[#604828]">시그널 대기중...</div>
            )}
            {state.leaderboard.slice(0, 12).map((lb, idx) => (
              <LeaderboardCard key={lb.sym} lb={lb} idx={idx} onSelect={() => setSelectedSymbol(lb.sym)} />
            ))}
          </div>
        )}

        {/* ── Regime tab ── */}
        {tab === "rg" && (
          <div className="space-y-px bg-[#2a2000]">
            <RegimeCell
              label="BTC vs ALT 상대강도"
              value={`${state.regime.btcAltDelta >= 0 ? "+" : ""}${state.regime.btcAltDelta.toFixed(2)}%`}
              sub={state.regime.btcAltDelta > 0.5 ? "BTC 우세 — ALT 약세" : state.regime.btcAltDelta < -0.5 ? "ALT 우세" : "혼조"}
              tone={state.regime.btcAltDelta > 0.5 ? "text-rose-300" : state.regime.btcAltDelta < -0.5 ? "text-blue-300" : "text-[#bba383]"}
              bar={clamp((state.regime.btcAltDelta + 5) / 10, 0, 1)}
            />
            <RegimeCell
              label="평균 펀딩(스나이퍼)"
              value={`${state.regime.avgFunding >= 0 ? "+" : ""}${state.regime.avgFunding.toFixed(4)}%`}
              sub={Math.abs(state.regime.avgFunding) > 0.05 ? "극단 수준" : Math.abs(state.regime.avgFunding) > 0.03 ? "높음" : "정상"}
              tone={Math.abs(state.regime.avgFunding) > 0.03 ? "text-amber-400" : "text-[#bba383]"}
              bar={clamp((state.regime.avgFunding + 0.2) / 0.4, 0, 1)}
            />
            <RegimeCell
              label="OI 확장 비율"
              value={`${state.regime.oiExpansionRate.toFixed(1)}%`}
              sub={state.regime.oiExpansionRate > 60 ? "과열" : "정상"}
              tone={state.regime.oiExpansionRate > 60 ? "text-amber-400" : "text-[#bba383]"}
              bar={clamp(state.regime.oiExpansionRate / 100, 0, 1)}
            />
            <RegimeCell
              label="시그널 롱/숏 흐름"
              value={`${state.regime.longFlowRatio.toFixed(0)}%`}
              sub={state.regime.longFlowRatio > 60 ? "롱 우세" : state.regime.longFlowRatio < 40 ? "숏 우세" : "균형"}
              tone={state.regime.longFlowRatio > 60 ? "text-blue-300" : state.regime.longFlowRatio < 40 ? "text-rose-300" : "text-[#bba383]"}
              bar={clamp(state.regime.longFlowRatio / 100, 0, 1)}
            />
          </div>
        )}

        {/* ── Pre-signals tab ── */}
        {tab === "pre" && (
          <div>
            {state.preSignals.length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] italic text-[#604828]">선행 시그널 감시중...</div>
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
                  <span className="font-mono text-[11px] font-black text-[#ffe0a0]">{p.sym.replace("USDT", "")}</span>
                  <span className={cn("text-[10px] font-bold", p.dir > 0 ? "text-blue-400" : "text-rose-400")}>
                    {p.dir > 0 ? "▲" : "▼"} {p.score > 0 ? "+" : ""}{p.score}
                  </span>
                </div>
                <div className="mt-0.5 text-[10px] text-[#ffe0a0]">{p.title}</div>
                <div className="mt-0.5 text-[9px] text-[#bba383]">{p.desc}</div>
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
      className={cn("w-full border-b border-[#2a2000]/50 px-0 py-0 text-left hover:bg-amber-500/[0.06] cursor-pointer", rowBg)}
    >
      <div className="flex items-start">
        {/* 종목 column */}
        <div className="flex-1 min-w-0 px-2 py-1.5">
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-[10px]">{row.stage >= 2 ? "🚀" : row.stage === 1 ? "⚡" : "·"}</span>
            <span className="font-mono text-[12px] font-black text-[#ffe0a0]">{row.sym}</span>
            {row.pinned && <span className="text-[9px] text-amber-400">📌</span>}
            {row.aGradeCount > 0 && (
              <span className={cn(
                "inline-block rounded px-1 py-0 text-[8px] font-black leading-4",
                row.aGradeActive
                  ? (row.aGradeDir > 0
                      ? "bg-blue-500 text-white border border-blue-400 shadow-[0_0_6px_rgba(0,136,255,0.6)]"
                      : "bg-rose-500 text-white border border-rose-400 shadow-[0_0_6px_rgba(255,51,85,0.6)]")
                  : (row.aGradeDir > 0
                      ? "bg-blue-500/10 text-blue-400 border border-blue-500/60"
                      : "bg-rose-500/10 text-rose-400 border border-rose-500/60")
              )}>
                👑 A급 {row.aGradeDir > 0 ? "매수" : "매도"} {row.aGradeCount}회
              </span>
            )}
          </div>
        </div>

        {/* Stage Gate 판정 column */}
        <div className="w-[148px] shrink-0 px-1 py-1.5">
          <div className="flex items-center gap-1">
            {/* sg-ind: stage badge with aging bar */}
            <div
              className={cn("relative rounded px-1 pt-0.5 pb-1 text-[8px] font-black font-mono shrink-0 overflow-hidden border", stageBadgeCls(row.stage, row.latchDir))}
              style={{ opacity }}
            >
              S{row.stage}
              <div className="absolute bottom-0 left-0 h-[2px] bg-current" style={{ width: `${row.latchRatio * 100}%` }} />
            </div>

            {/* jb-bar: centered bar with label */}
            <div className="relative flex-1 h-[18px] rounded bg-[#1a1400] border border-[#2a2000] overflow-hidden">
              <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#604828] z-10" />
              <div
                className={cn("absolute top-0 bottom-0", isBull
                  ? "left-1/2 bg-gradient-to-r from-blue-800/40 to-blue-500/80"
                  : "right-1/2 bg-gradient-to-l from-rose-800/40 to-rose-500/80"
                )}
                style={{ width: `${pct}%` }}
              />
              <div className="absolute inset-0 flex items-center justify-center z-20 text-[8px] font-black text-white font-mono" style={{ textShadow: "0 0 3px #000, 0 0 3px #000" }}>
                {stageGateLabel(row.score, row.stage, row.latchDir)}
              </div>
            </div>
          </div>
        </div>

        {/* 시그널 column */}
        <div className="flex-1 min-w-0 px-1 py-1.5">
          <div className="flex flex-wrap gap-0.5">
            {row.sig.slice(0, 5).map((s, i) => (
              <span key={i} className={cn(
                "inline-block rounded border px-1 text-[8px] font-bold leading-4",
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
          <div className="mt-0.5 flex gap-2 text-[8px] text-[#604828]">
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
      className="w-full border-b border-[#2a2000] px-3 py-2 text-left hover:bg-amber-500/[0.06] cursor-pointer"
    >
      <div className="flex items-center justify-between gap-1">
        {/* Left: rank + sym + badges */}
        <div className="flex items-center gap-1 flex-wrap min-w-0">
          <span className="text-[9px] text-[#604828]">{idx + 1}.</span>
          <span className="font-mono text-[12px] font-black text-[#ffe0a0]">
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
            ? <span className="rounded px-1 py-0 text-[8px] font-black bg-blue-500/20 text-blue-400">▲매수</span>
            : lb.scoreSum <= -30
              ? <span className="rounded px-1 py-0 text-[8px] font-black bg-rose-500/20 text-rose-400">▼매도</span>
              : <span className="rounded px-1 py-0 text-[8px] font-black bg-amber-500/10 text-amber-400">⚡혼조</span>
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
              "inline-block rounded border bg-[#0c0800] px-1 text-[8px] font-bold leading-4",
              isBuy ? "text-blue-400 border-blue-500/50" : "text-rose-400 border-rose-500/50"
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
  if (stage === 3) return "text-amber-400 border-amber-500/70 bg-amber-500/15";
  if (stage === 2) return dir >= 0
    ? "text-blue-400 border-blue-500/70 bg-blue-500/15"
    : "text-rose-400 border-rose-500/70 bg-rose-500/15";
  if (stage === 1) return "text-orange-400 border-orange-500/70 bg-orange-500/10";
  return "text-[#604828] border-[#604828]/50";
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
    <div className={cn("flex-1 flex flex-col items-center py-2 gap-0.5", !last && "border-r border-[#2a2000]")}>
      <div className="text-[7px] uppercase tracking-wider text-[#604828]">{label}</div>
      <div className={cn("font-mono font-black", tone, small ? "text-[10px]" : "text-[13px]")}>{value}</div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" onClick={onClick}
      className={cn("flex-1 py-2 text-[10px] font-bold",
        active ? "text-amber-400 bg-amber-500/[0.08] border-b-2 border-amber-400" : "text-[#604828] hover:text-[#bba383]"
      )}>
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
    "text-amber-400": "#fbbf24",
    "text-[#bba383]": "#bba383",
  };
  const barColor = colorMap[tone] ?? "#bba383";

  return (
    <div className="bg-[#0c0800] px-4 py-4 flex flex-col gap-1.5 border-b border-[#2a2000]">
      <div className="text-[9px] uppercase tracking-wider font-bold text-[#604828]">{label}</div>
      <div className={cn("font-mono text-[20px] font-black leading-none", tone)}>{value}</div>
      <div className="text-[10px] text-[#bba383]">{sub}</div>
      <div className="mt-1 h-[4px] rounded bg-[#1a1400]">
        <div
          className="h-full rounded transition-all"
          style={{ width: `${Math.round(bar * 100)}%`, backgroundColor: barColor }}
        />
      </div>
    </div>
  );
}
