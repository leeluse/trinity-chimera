"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useTerminalStore } from "./terminalStore";
import {
  mountHunterRuntime,
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

    return () => {
      runtime.cleanup();
      runtimeRef.current = null;
    };
  }, []);

  const onStart = () => {
    void runtimeRef.current?.api.startSystem();
  };

  const onStop = () => {
    runtimeRef.current?.api.stopSystem();
  };

  const onToggleFreeze = () => {
    runtimeRef.current?.api.toggleFreeze();
  };

  const onToggleFocus = () => {
    runtimeRef.current?.api.toggleFocus();
  };

  const onToggleMute = () => {
    runtimeRef.current?.api.toggleMute();
  };

  const onSetSort = (mode: HunterSortMode) => {
    runtimeRef.current?.api.setSort(mode);
  };

  const wsTagClass = (on: boolean) =>
    cn(
      "rounded border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-widest",
      on
        ? "border-cyan-400/70 text-cyan-300 bg-cyan-400/10"
        : "border-white/[0.12] text-slate-600",
    );

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/[0.06] px-3 py-3">
        <div className="text-[11px] font-black uppercase tracking-[0.2em] text-cyan-300">
          Hunter V16 Fusion
        </div>
        <div className="mt-1 text-[9px] text-slate-500">
          Stage Gate + Latch + Multi-WS
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className={wsTagClass(state.ws.bn)}>BN</span>
          <span className={wsTagClass(state.ws.okx)}>OKX</span>
          <span className={wsTagClass(state.ws.bybit)}>BYB</span>
          <span className={wsTagClass(state.ws.bitget)}>BIT</span>

          <button
            type="button"
            onClick={onToggleFreeze}
            className={cn(
              "ml-auto rounded border px-2 py-1 text-[9px] font-bold",
              state.frozen
                ? "border-sky-400/60 bg-sky-400/10 text-sky-300"
                : "border-white/[0.12] text-slate-400",
            )}
          >
            {state.frozen ? "▶ 재개" : "⏸ 정지"}
          </button>
          <button
            type="button"
            onClick={onToggleFocus}
            className={cn(
              "rounded border px-2 py-1 text-[9px] font-bold",
              state.focusMode
                ? "border-violet-400/60 bg-violet-400/10 text-violet-300"
                : "border-white/[0.12] text-slate-400",
            )}
          >
            🎯 포커스
          </button>
          <button
            type="button"
            onClick={onToggleMute}
            className={cn(
              "rounded border px-2 py-1 text-[9px] font-bold",
              state.muted
                ? "border-rose-400/60 bg-rose-400/10 text-rose-300"
                : "border-white/[0.12] text-slate-400",
            )}
          >
            {state.muted ? "🔇" : "🔊"}
          </button>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={onStart}
            disabled={state.running}
            className={cn(
              "rounded border px-3 py-1.5 text-[10px] font-black uppercase tracking-wider",
              state.running
                ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-300"
                : "border-amber-400/60 text-amber-300 hover:bg-amber-400/10",
            )}
          >
            {state.running ? "■ 감시중" : "▶ 가동"}
          </button>
          {state.running && (
            <button
              type="button"
              onClick={onStop}
              className="rounded border border-rose-500/60 px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-rose-300 hover:bg-rose-500/10"
            >
              STOP
            </button>
          )}
          <span className="ml-auto text-[9px] text-slate-500">{state.statusText}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 border-b border-white/[0.06] p-3">
        <SummaryBox label="스나이퍼" value={String(state.summary.snipers)} tone="text-amber-300" />
        <SummaryBox label="S2+" value={String(state.summary.s2plus)} tone="text-cyan-300" />
        <SummaryBox label="S1" value={String(state.summary.s1)} tone="text-orange-300" />
        <SummaryBox label="Pre" value={String(state.summary.pre)} tone="text-violet-300" />
      </div>

      <div className="border-b border-white/[0.06] px-3 py-2">
        <div className="text-[10px] uppercase tracking-widest text-slate-500">Bias</div>
        <div
          className={cn(
            "mt-1 text-[11px] font-bold",
            state.summary.bias.includes("ALT강세")
              ? "text-cyan-300"
              : state.summary.bias.includes("ALT약세")
                ? "text-rose-300"
                : "text-slate-300",
          )}
        >
          {state.summary.bias}
        </div>
      </div>

      <div className="flex border-b border-white/[0.06] px-2 py-2">
        <TabButton active={tab === "lb"} onClick={() => setTab("lb")}>리더보드</TabButton>
        <TabButton active={tab === "rg"} onClick={() => setTab("rg")}>레짐</TabButton>
        <TabButton active={tab === "pre"} onClick={() => setTab("pre")}>선행</TabButton>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-3">
        {tab === "lb" && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1.5">
              <SortButton label="전체" mode="total" current={state.sortMode} onClick={onSetSort} />
              <SortButton label="크로스" mode="cross" current={state.sortMode} onClick={onSetSort} />
              <SortButton label="스퀴즈" mode="sqz" current={state.sortMode} onClick={onSetSort} />
              <SortButton label="고래" mode="whale" current={state.sortMode} onClick={onSetSort} />
            </div>

            <div className="space-y-2">
              {state.rows.slice(0, 14).map((row, idx) => (
                <button
                  key={row.full}
                  type="button"
                  onClick={() => setSelectedSymbol(row.full)}
                  className="w-full rounded border border-white/[0.06] bg-black/30 px-2.5 py-2 text-left hover:bg-white/[0.03]"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-slate-600">{idx + 1}.</span>
                      <span className="font-mono text-[12px] font-black text-slate-100">{row.sym}</span>
                      {row.pinned && <span className="text-[10px] text-amber-300">📌</span>}
                    </div>
                    <span className={cn("font-mono text-[11px] font-bold", stageClass(row.stage, row.latchDir))}>
                      {stageLabel(row.stage, row.score, row.latchDir)}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded bg-white/[0.06]">
                    <div
                      className={cn(
                        "h-full rounded",
                        row.latchDir > 0
                          ? "bg-cyan-400/80"
                          : row.latchDir < 0
                            ? "bg-rose-400/80"
                            : "bg-slate-500/60",
                      )}
                      style={{ width: `${Math.round(row.latchRatio * 100)}%` }}
                    />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
                    <span>CVD {row.cvd >= 0 ? "+" : ""}{(row.cvd / 1000).toFixed(1)}k</span>
                    <span>Flow ×{row.mult > 0.1 ? row.mult.toFixed(1) : "—"}</span>
                  </div>
                </button>
              ))}
              {!state.rows.length && <EmptyText text="가동 후 실시간 스코어가 표시됩니다." />}
            </div>

            <div className="pt-1">
              <div className="mb-1 text-[9px] uppercase tracking-widest text-slate-500">Top Leaderboard</div>
              <div className="space-y-1.5">
                {state.leaderboard.slice(0, 8).map((lb, idx) => (
                  <button
                    key={lb.sym}
                    type="button"
                    onClick={() => setSelectedSymbol(lb.sym)}
                    className="w-full rounded border border-white/[0.06] bg-black/20 px-2 py-1.5 text-left hover:bg-white/[0.03]"
                  >
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-slate-500">{idx + 1}. <span className="font-mono text-slate-200">{lb.sym.replace("USDT", "")}</span></span>
                      <span className={cn("font-mono font-bold", lb.scoreSum >= 0 ? "text-cyan-300" : "text-rose-300")}>
                        {lb.scoreSum > 0 ? "+" : ""}{lb.scoreSum}
                      </span>
                    </div>
                  </button>
                ))}
                {!state.leaderboard.length && <EmptyText text="시그널 대기중..." />}
              </div>
            </div>
          </div>
        )}

        {tab === "rg" && (
          <div className="space-y-3">
            <RegimeItem
              label="BTC vs ALT"
              value={`${state.regime.btcAltDelta >= 0 ? "+" : ""}${state.regime.btcAltDelta.toFixed(2)}%`}
              tone={
                state.regime.btcAltDelta > 0.5
                  ? "text-cyan-300"
                  : state.regime.btcAltDelta < -0.5
                    ? "text-rose-300"
                    : "text-slate-300"
              }
              barValue={clamp((state.regime.btcAltDelta + 5) / 10, 0, 1)}
            />
            <RegimeItem
              label="평균 Funding"
              value={`${state.regime.avgFunding >= 0 ? "+" : ""}${state.regime.avgFunding.toFixed(4)}%`}
              tone={Math.abs(state.regime.avgFunding) > 0.03 ? "text-amber-300" : "text-slate-300"}
              barValue={clamp((state.regime.avgFunding + 0.2) / 0.4, 0, 1)}
            />
            <RegimeItem
              label="OI 확장 비율"
              value={`${state.regime.oiExpansionRate.toFixed(1)}%`}
              tone={state.regime.oiExpansionRate > 60 ? "text-amber-300" : "text-slate-300"}
              barValue={clamp(state.regime.oiExpansionRate / 100, 0, 1)}
            />
            <RegimeItem
              label="Long Flow"
              value={`${state.regime.longFlowRatio.toFixed(0)}%`}
              tone={
                state.regime.longFlowRatio > 60
                  ? "text-cyan-300"
                  : state.regime.longFlowRatio < 40
                    ? "text-rose-300"
                    : "text-slate-300"
              }
              barValue={clamp(state.regime.longFlowRatio / 100, 0, 1)}
            />
          </div>
        )}

        {tab === "pre" && (
          <div className="space-y-2">
            {state.preSignals.slice(0, 24).map((p, idx) => (
              <button
                key={`${p.sym}-${p.type}-${idx}`}
                type="button"
                onClick={() => setSelectedSymbol(p.sym)}
                className="w-full rounded border border-white/[0.06] bg-black/30 p-2 text-left hover:bg-white/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-bold text-slate-100">{p.sym.replace("USDT", "")}</span>
                  <span className={cn("text-[10px] font-bold", p.dir > 0 ? "text-cyan-300" : "text-rose-300")}>
                    {p.dir > 0 ? "▲" : "▼"} {p.score > 0 ? "+" : ""}{p.score}
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-slate-200">{p.title}</div>
                <div className="mt-0.5 text-[9px] text-slate-500">{p.desc}</div>
              </button>
            ))}
            {!state.preSignals.length && <EmptyText text="선행 시그널 없음" />}
          </div>
        )}
      </div>
    </div>
  );
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function stageClass(stage: number, dir: number) {
  if (stage === 3) return dir > 0 ? "text-cyan-300" : "text-rose-300";
  if (stage === 2) return dir > 0 ? "text-blue-300" : "text-rose-300";
  if (stage === 1) return "text-amber-300";
  return "text-slate-500";
}

function stageLabel(stage: number, score: number, dir: number) {
  const sign = score > 0 ? "+" : "";
  if (stage === 0) return `S0 ${sign}${score}`;
  if (stage === 1) return `S1 ${sign}${score}`;
  if (stage === 2) return `${dir > 0 ? "▲" : "▼"}S2 ${sign}${score}`;
  return `${dir > 0 ? "▲▲" : "▼▼"}S3 ${sign}${score}`;
}

function SummaryBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded border border-white/[0.06] bg-black/30 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-0.5 font-mono text-[12px] font-black", tone)}>{value}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-wider",
        active
          ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-300"
          : "border-white/[0.08] text-slate-500 hover:text-slate-300",
      )}
    >
      {children}
    </button>
  );
}

function SortButton({
  label,
  mode,
  current,
  onClick,
}: {
  label: string;
  mode: HunterSortMode;
  current: HunterSortMode;
  onClick: (mode: HunterSortMode) => void;
}) {
  const active = mode === current;
  return (
    <button
      type="button"
      onClick={() => onClick(mode)}
      className={cn(
        "rounded border px-2 py-1 text-[9px] font-bold uppercase tracking-wider",
        active
          ? "border-amber-400/60 bg-amber-400/10 text-amber-300"
          : "border-white/[0.08] text-slate-500 hover:text-slate-300",
      )}
    >
      {label}
    </button>
  );
}

function RegimeItem({
  label,
  value,
  tone,
  barValue,
}: {
  label: string;
  value: string;
  tone: string;
  barValue: number;
}) {
  return (
    <div className="rounded border border-white/[0.06] bg-black/30 p-2">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-1 font-mono text-[12px] font-bold", tone)}>{value}</div>
      <div className="mt-1.5 h-1.5 rounded bg-white/[0.06]">
        <div
          className="h-full rounded bg-cyan-400/70"
          style={{ width: `${Math.round(barValue * 100)}%` }}
        />
      </div>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return (
    <div className="rounded border border-dashed border-white/[0.08] bg-black/20 p-3 text-center text-[10px] text-slate-500">
      {text}
    </div>
  );
}
