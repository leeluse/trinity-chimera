"use client";

import React, { useState, useEffect, useRef } from "react";
import { Skull } from "lucide-react";
import { useCrimeStore } from "@/store/useCrimeStore";
import { CoinData, stageColor, fmtPrice, scoreDanger, trapColor } from "./crimeData";

type FilterKey = "ALL" | "PRE_IGNITION" | "IGNITION" | "SPRING" | "ACCUMULATE";
type SortKey =
  | "rank" | "symbol" | "stage" | "score" | "fuel"
  | "funding" | "oi24h" | "short" | "price1h" | "rr" | "trap";

function fmtMMSS(sec: number): string {
  return `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
}

function normalizeStage(stage: string): string {
  if (stage.includes("PRE_IGNITION")) return "PRE_IGNITION";
  if (stage.includes("IGNITION")) return "IGNITION";
  if (stage.includes("SPRING")) return "SPRING";
  if (stage.includes("ACCUMULATE")) return "ACCUMULATE";
  return stage;
}

function stageLabel(stage: string): string {
  const n = normalizeStage(stage);
  if (n === "PRE_IGNITION") return "PRE_IGN";
  if (n === "IGNITION") return "IGNITION";
  if (n === "SPRING") return "SPRING";
  if (n === "ACCUMULATE") return "ACCUM";
  return n;
}

// ─── 연료 게이지 ──────────────────────────────────────────
function FuelBlocks({ value }: { value: number }) {
  const BLOCKS = 6;
  const filled = Math.round((value / 100) * BLOCKS);
  const color =
    value >= 80 ? "bg-indigo-400 shadow-[0_0_4px_rgba(99,102,241,0.6)]"
      : value >= 60 ? "bg-violet-500"
        : value >= 40 ? "bg-indigo-500"
          : "bg-white/10";
  return (
    <div className="flex gap-[2px] items-center">
      {Array.from({ length: BLOCKS }).map((_, i) => (
        <div key={i} className={`w-[3px] h-[8px] rounded-[1px] ${i < filled ? color : "bg-white/[0.06]"}`} />
      ))}
    </div>
  );
}

// ─── 점수 바 ──────────────────────────────────────────────
function ScoreBar({ score }: { score: number }) {
  const pct = Math.min((score / 200) * 100, 100);
  const grad =
    score >= 150 ? "from-indigo-500 to-violet-400"
      : score >= 100 ? "from-indigo-600 to-indigo-400"
        : score >= 60 ? "from-indigo-700 to-indigo-500"
          : "from-white/20 to-white/10";
  return (
    <div className="w-12 h-[2px] bg-white/[0.06] rounded-full overflow-hidden mt-0.5">
      <div className={`h-full rounded-full bg-gradient-to-r ${grad}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ─── 컬럼 헤더 ────────────────────────────────────────────
function Th({ label, col, sortKey, sortDir, onSort, className = "" }: {
  label: string; col: SortKey; sortKey: SortKey; sortDir: "asc" | "desc";
  onSort: (k: SortKey) => void; className?: string;
}) {
  const active = sortKey === col;
  return (
    <div
      className={`text-[10px] uppercase font-bold tracking-widest cursor-pointer select-none whitespace-nowrap px-2 py-2.5 flex items-center transition-colors
        ${active ? "text-indigo-400" : "text-white/20 hover:text-white/40"} ${className}`}
      onClick={() => onSort(col)}
    >
      {label}
      {active && <span className="ml-0.5 text-indigo-400">{sortDir === "desc" ? "↓" : "↑"}</span>}
    </div>
  );
}

// ─── 데이터 행 ────────────────────────────────────────────
function CrimeRow({ coin, rank, selected, onSelect }: {
  coin: CoinData; rank: number; selected: boolean; onSelect: () => void;
}) {
  const d = scoreDanger(coin.score);
  const sc = stageColor(coin.pump_stage);
  const norm = normalizeStage(coin.pump_stage);
  const isPreIgn = norm === "PRE_IGNITION";

  const rankCls =
    rank === 1 ? "text-indigo-400"
    : rank === 2 ? "text-violet-400"
    : rank === 3 ? "text-indigo-500"
    : "text-white/20";

  const fundingCls =
    coin.funding_rate < -0.3 ? "text-indigo-400"
    : coin.funding_rate < -0.1 ? "text-violet-400"
    : "text-indigo-300";

  const oi24hCls =
    coin.oi_change_pct_24h >= 40 ? "text-indigo-400"
    : coin.oi_change_pct_24h >= 20 ? "text-violet-400"
    : "text-white/40";

  const shortCls =
    coin.short_ratio >= 62 ? "text-indigo-400"
    : coin.short_ratio >= 55 ? "text-violet-400"
    : "text-white/40";

  const price1hCls = coin.price_change_1h >= 0 ? "text-emerald-400" : "text-red-400";

  const rrCls =
    coin.risk.risk_reward >= 2.5 ? "text-emerald-400"
    : coin.risk.risk_reward >= 1.5 ? "text-amber-400"
    : "text-white/25";

  const trapFirst = coin.risk.dump_trap_risk.split(" ")[0];

  return (
    <div
      className={`grid grid-cols-[40px_100px_110px_repeat(7,1fr)_70px] items-center border-b cursor-pointer transition-all group
        ${selected
          ? "border-indigo-500/30 bg-gradient-to-r from-indigo-500/[0.06] to-indigo-500/[0.04] shadow-[inset_2px_0_0_#6366f1]"
          : isPreIgn
          ? "border-violet-500/10 bg-violet-500/[0.03] hover:bg-violet-500/[0.06]"
          : "border-white/[0.03] hover:bg-white/[0.025]"
        }`}
      onClick={onSelect}
    >
      {/* 순위 */}
      <div className="px-2 py-2.5 text-[10px] font-mono font-black text-center">
        <span className={rankCls}>{String(rank).padStart(2, "0")}</span>
      </div>

      {/* 심볼 */}
      <div className="px-2 py-2.5">
        <span className="font-mono font-black text-[13px] text-white/60 tracking-tight leading-none">
          {coin.symbol.replace("USDT", "")}
        </span>
      </div>

      {/* 단계 */}
      <div className="px-2 py-2.5">
        <span className={`inline-flex items-center gap-1.5 px-1.5 py-1 rounded-[4px] text-[10px] font-bold border backdrop-blur-sm ${sc.text} ${sc.border} ${sc.bg}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${sc.dot} shrink-0 ${isPreIgn ? "animate-pulse" : ""}`} />
          {stageLabel(coin.pump_stage)}
        </span>
      </div>

      {/* 점수 */}
      <div className="pl-4 pr-2 py-2.5">
        <div className={`text-[13px] font-mono font-black leading-none ${d.cls}`}>{coin.score}</div>
        <ScoreBar score={coin.score} />
      </div>

      {/* 연료 */}
      <div className="px-2 py-2.5"><FuelBlocks value={coin.squeeze_fuel} /></div>

      {/* 펀딩 */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={fundingCls}>{coin.funding_rate > 0 ? "+" : ""}{coin.funding_rate.toFixed(3)}%</span>
      </div>

      {/* OI 24h */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={oi24hCls}>+{coin.oi_change_pct_24h.toFixed(0)}%</span>
      </div>

      {/* 숏% */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={shortCls}>{coin.short_ratio.toFixed(1)}%</span>
      </div>

      {/* 1h% */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={price1hCls}>{coin.price_change_1h > 0 ? "+" : ""}{coin.price_change_1h.toFixed(1)}%</span>
      </div>

      {/* R:R */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={rrCls}>{coin.risk.risk_reward.toFixed(2)}R</span>
      </div>

      {/* 트랩 */}
      <div className="px-2 py-2.5 text-[11px] font-mono">
        <span className={trapColor(coin.risk.dump_trap_risk)}>{trapFirst}</span>
      </div>
    </div>
  );
}

// ─── 메인 패널 ────────────────────────────────────────────
export default function CrimeMainPanel() {
  const {
    status, wsStatus, errorMessage, progress, bybitEnabled, binanceEnabled,
    results, nextScanIn, lastScanAt, selectedSymbol,
    selectSymbol, toggleBybit, toggleBinance,
    tickCountdown, runScan, stopScan,
  } = useCrimeStore();

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 카운트다운만 담당 (엔진이 스캔 타이밍을 직접 관리하므로 runScan 호출 불필요)
  useEffect(() => {
    timerRef.current = setInterval(() => { tickCountdown(); }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const isLive = wsStatus === "live" || wsStatus === "scanning";

  const [filter, setFilter] = useState<FilterKey>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const filtered = results.filter((c) => filter === "ALL" || normalizeStage(c.pump_stage) === filter);

  const sorted = [...filtered].sort((a, b) => {
    let va: number | string = 0, vb: number | string = 0;
    switch (sortKey) {
      case "rank": case "score": va = a.score; vb = b.score; break;
      case "symbol": va = a.symbol; vb = b.symbol; break;
      case "stage": va = normalizeStage(a.pump_stage); vb = normalizeStage(b.pump_stage); break;
      case "fuel": va = a.squeeze_fuel; vb = b.squeeze_fuel; break;
      case "funding": va = a.funding_rate; vb = b.funding_rate; break;
      case "oi24h": va = a.oi_change_pct_24h; vb = b.oi_change_pct_24h; break;
      case "short": va = a.short_ratio; vb = b.short_ratio; break;
      case "price1h": va = a.price_change_1h; vb = b.price_change_1h; break;
      case "rr": va = a.risk.risk_reward; vb = b.risk.risk_reward; break;
      case "trap": va = a.risk.dump_trap_risk; vb = b.risk.dump_trap_risk; break;
    }
    if (typeof va === "string" && typeof vb === "string")
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === "asc" ? (va as number) - (vb as number) : (vb as number) - (va as number);
  });

  function handleSort(k: SortKey) {
    sortKey === k ? setSortDir((d) => (d === "asc" ? "desc" : "asc")) : (setSortKey(k), setSortDir("desc"));
  }

  const FILTERS: { key: FilterKey; label: string }[] = [
    { key: "ALL", label: "ALL" },
    { key: "PRE_IGNITION", label: "PRE_IGN" },
    { key: "IGNITION", label: "IGNITION" },
    { key: "SPRING", label: "SPRING" },
    { key: "ACCUMULATE", label: "ACCUM" },
  ];

  const thProps = { sortKey, sortDir, onSort: handleSort };

  return (
    <div className="flex flex-col h-full bg-[#070810] overflow-hidden">

      {/* ── 스캔 컨트롤 바 ── */}
      <div className="shrink-0 px-3 py-2.5 border-b border-white/[0.06] bg-[#070810] backdrop-blur-xl space-y-2 relative z-30">
        <div className="pb-1.5">
          <div className="flex items-center gap-3">
            {/* 패널 타이틀 */}
            <div className="flex items-center gap-2.5 pr-4 border-r border-white/10">
              <Skull size={15} className="text-indigo-500/60" />
              <span className="text-[13px] font-black tracking-[0.1em] uppercase bg-gradient-to-r from-indigo-400/80 to-violet-400/80 bg-clip-text text-transparent whitespace-nowrap">
                Crime Panel
              </span>
            </div>

            {/* 거래소 토글 */}
            <div className="flex items-center gap-1.5">
              {[
                { label: "BYBIT", active: bybitEnabled, toggle: toggleBybit },
                { label: "BINANCE", active: binanceEnabled, toggle: toggleBinance },
              ].map(({ label, active, toggle }) => (
                <button
                  key={label}
                  onClick={toggle}
                  className={`px-2.5 py-1 rounded-[5px] text-[9px] font-bold tracking-wider transition-all border backdrop-blur-sm ${active
                    ? "bg-indigo-500/15 border-indigo-500/35 text-indigo-300 shadow-[0_0_8px_rgba(99,102,241,0.15)]"
                    : "bg-white/[0.03] border-white/[0.07] text-white/25 hover:text-white/40"
                    }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* 라이브 버튼 */}
            <div className="flex items-center gap-1.5 shrink-0 relative z-50">
              {isLive ? (
                <button
                  onClick={() => stopScan()}
                  className="px-3 py-1 rounded-[5px] text-[9px] font-bold tracking-wider bg-white/10 border border-white/20 text-white hover:bg-white/20 transition-all shadow-lg"
                >
                  ■ DISCONNECT
                </button>
              ) : (
                <button
                  onClick={() => runScan()}
                  className="px-4 py-1 rounded-[5px] text-[9px] font-bold tracking-wider bg-indigo-500 text-white hover:bg-indigo-400 active:scale-95 transition-all shadow-[0_0_15px_rgba(99,102,241,0.4)]"
                >
                  ▶ LIVE START
                </button>
              )}
            </div>
          </div>

          {/* WS 연결 중 */}
          {wsStatus === "connecting" && (
            <div className="flex items-center gap-2 py-2 px-1">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse shrink-0" />
              <span className="text-[10px] font-mono text-indigo-400/70">WS 연결 중... (Binance Futures 스트림)</span>
            </div>
          )}
          {/* REST 보완 스캔 중 */}
          {wsStatus === "scanning" && (
            <div className="flex flex-col gap-2 py-3 px-1">
              <div className="w-full h-[5px] bg-white/[0.05] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-violet-400 rounded-full transition-all duration-700 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.4)]"
                  style={{ width: `${progress.total > 0 ? Math.min((progress.current / progress.total) * 100, 100) : 2}%` }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-white/40 font-bold">상위 {progress.total}개 심볼 OI/LS 스캔 중 ({progress.current}/{progress.total})</span>
                {progress.estimatedSecondsLeft > 0 && (
                  <span className="text-[10px] font-mono text-indigo-400/80 font-bold">약 {progress.estimatedSecondsLeft}초 남음</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── 필터 바 (프로그레스 바 밑으로 이동) ── */}
        <div className="flex items-center gap-1.5 px-1 py-1 border-t border-white/[0.03] mt-1">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-2.5 py-1 rounded-[4px] text-[10px] font-bold tracking-wider transition-all border ${filter === key
                ? "bg-gradient-to-r from-indigo-500/15 to-indigo-600/15 border-indigo-500/35 text-indigo-300 shadow-[0_0_6px_rgba(99,102,241,0.1)]"
                : "border-transparent text-white/20 hover:text-white/40 hover:border-white/[0.07]"
                }`}
            >
              {label}
            </button>
          ))}
          <span className="ml-auto text-[8px] font-mono text-white/15">{sorted.length}개</span>
        </div>

        {/* LIVE 상태: 실시간 수신 중 */}
        {wsStatus === "live" && (
          <div className="flex items-center gap-2 text-[10px] font-mono text-white/40 px-1 pt-4 pb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.5)] shrink-0 animate-pulse" />
            <span className="text-emerald-400/70 font-bold">LIVE</span>
            {lastScanAt && <span className="text-white/30">· 마지막 스캔: {lastScanAt}</span>}
            {nextScanIn > 0 && (
              <span className="ml-auto text-white/20">다음 스캔: {fmtMMSS(nextScanIn)} 후</span>
            )}
          </div>
        )}
        {/* 에러 상태 */}
        {status === "error" && (
          <div className="flex items-center gap-2 text-[8px] font-mono text-red-400/70 bg-red-500/5 px-2 py-1 rounded border border-red-500/15">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span>{errorMessage || "WS 연결 오류 — 재연결 중..."}</span>
          </div>
        )}
      </div>

      {/* ── 랭킹 테이블 ── */}
      <div className="flex-1 overflow-y-auto no-scrollbar relative">
        <div className="flex flex-col min-w-max">
          {/* 헤더 */}
          <div className="sticky top-0 z-20 bg-[#070810]/95 backdrop-blur-md grid grid-cols-[40px_100px_110px_repeat(7,1fr)_70px] border-b border-white/[0.04]">
            <Th label="#" col="rank"    {...thProps} className="justify-center" />
            <Th label="심볼" col="symbol"  {...thProps} />
            <Th label="단계" col="stage"   {...thProps} />
            <Th label="점수" col="score"   {...thProps} className="pl-4" />
            <Th label="연료" col="fuel"    {...thProps} />
            <Th label="펀딩" col="funding" {...thProps} />
            <Th label="OI 24h" col="oi24h"  {...thProps} />
            <Th label="숏%" col="short"   {...thProps} />
            <Th label="1h%" col="price1h" {...thProps} />
            <Th label="R:R" col="rr"      {...thProps} />
            <Th label="트랩" col="trap"    {...thProps} />
          </div>

          {/* 바디 */}
          <div className="flex flex-col">
            {sorted.length === 0 ? (
              <div className="text-center py-12 text-[10px] font-mono text-white/15">
                해당 필터 결과 없음
              </div>
            ) : (
              sorted.map((coin, i) => {
                const globalRank = results.findIndex((r) => r.symbol === coin.symbol) + 1;
                return (
                  <CrimeRow
                    key={coin.symbol}
                    coin={coin}
                    rank={globalRank || i + 1}
                    selected={selectedSymbol === coin.symbol}
                    onSelect={() => selectSymbol(selectedSymbol === coin.symbol ? null : coin.symbol)}
                  />
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
