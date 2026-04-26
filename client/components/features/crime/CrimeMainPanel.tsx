"use client";

import React, { useState, useEffect, useRef } from "react";
import { useCrimeStore } from "@/store/useCrimeStore";
import { CoinData, stageColor, fmtPrice, scoreDanger, trapColor } from "./crimeData";

// ─── 타입 ──────────────────────────────────────────────────────────────────────
type FilterKey = "ALL" | "PRE_IGNITION" | "IGNITION" | "SPRING" | "ACCUMULATE";
type SortKey =
  | "rank"
  | "symbol"
  | "stage"
  | "score"
  | "fuel"
  | "funding"
  | "oi24h"
  | "short"
  | "price1h"
  | "rr"
  | "trap";

// ─── 유틸 ──────────────────────────────────────────────────────────────────────
function fmtMMSS(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
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

// ─── 연료 블록 게이지 (6블록) ─────────────────────────────────────────────────
function FuelBlocks({ value }: { value: number }) {
  const BLOCKS = 6;
  const filled = Math.round((value / 100) * BLOCKS);
  const color =
    value >= 80
      ? "bg-fuchsia-500"
      : value >= 60
      ? "bg-red-500"
      : value >= 40
      ? "bg-amber-500"
      : "bg-slate-600";
  return (
    <div className="flex gap-[2px] items-center">
      {Array.from({ length: BLOCKS }).map((_, i) => (
        <div
          key={i}
          className={`w-[3px] h-[8px] rounded-[1px] ${i < filled ? color : "bg-slate-800"}`}
        />
      ))}
    </div>
  );
}

// ─── 점수 그라디언트 바 ───────────────────────────────────────────────────────
function ScoreBar({ score }: { score: number }) {
  const d = scoreDanger(score);
  const pct = Math.min((score / 200) * 100, 100);
  return (
    <div className="w-full h-[2px] bg-slate-800/80 rounded-full overflow-hidden mt-0.5">
      <div
        className={`h-full rounded-full bg-gradient-to-r ${d.barCls}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ─── 컬럼 헤더 셀 ────────────────────────────────────────────────────────────
function Th({
  label,
  col,
  sortKey,
  sortDir,
  onSort,
  className = "",
}: {
  label: string;
  col: SortKey;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (k: SortKey) => void;
  className?: string;
}) {
  const active = sortKey === col;
  return (
    <th
      className={`text-[8px] text-slate-600 uppercase font-bold tracking-widest cursor-pointer select-none whitespace-nowrap px-2 py-1.5 text-left hover:text-slate-400 transition-colors ${active ? "text-rose-500" : ""} ${className}`}
      onClick={() => onSort(col)}
    >
      {label}
      {active && (
        <span className="ml-0.5 text-rose-500">{sortDir === "desc" ? "↓" : "↑"}</span>
      )}
    </th>
  );
}

// ─── 각 데이터 행 ────────────────────────────────────────────────────────────
function CrimeRow({
  coin,
  rank,
  selected,
  onSelect,
}: {
  coin: CoinData;
  rank: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const d = scoreDanger(coin.score);
  const sc = stageColor(coin.pump_stage);
  const norm = normalizeStage(coin.pump_stage);
  const isPreIgn = norm === "PRE_IGNITION";

  const rankCls =
    rank === 1
      ? "text-fuchsia-500"
      : rank === 2
      ? "text-red-500"
      : rank === 3
      ? "text-orange-500"
      : "text-slate-600";

  const fundingCls =
    coin.funding_rate < -0.3
      ? "text-red-400"
      : coin.funding_rate < -0.1
      ? "text-orange-400"
      : "text-amber-400";

  const oi24hCls =
    coin.oi_change_pct_24h >= 40
      ? "text-red-400"
      : coin.oi_change_pct_24h >= 20
      ? "text-orange-400"
      : "text-slate-400";

  const shortCls =
    coin.short_ratio >= 62
      ? "text-red-400"
      : coin.short_ratio >= 55
      ? "text-orange-400"
      : "text-slate-400";

  const price1hCls = coin.price_change_1h >= 0 ? "text-emerald-400" : "text-red-400";

  const rrCls =
    coin.risk.risk_reward >= 2.5
      ? "text-emerald-400"
      : coin.risk.risk_reward >= 1.5
      ? "text-amber-400"
      : "text-slate-500";

  const trapFirst = coin.risk.dump_trap_risk.split(" ")[0];
  const trapCls = trapColor(coin.risk.dump_trap_risk);

  return (
    <tr
      className={`border-b border-white/[0.04] cursor-pointer transition-colors
        ${selected ? "border-l-2 border-rose-500 bg-rose-950/10" : ""}
        ${isPreIgn && !selected ? "bg-fuchsia-950/10" : ""}
        hover:bg-white/[0.03]`}
      onClick={onSelect}
    >
      {/* # 순위 */}
      <td className="px-2 py-1.5 text-[10px] font-mono font-black text-center w-8">
        <span className={rankCls}>{String(rank).padStart(2, "0")}</span>
      </td>

      {/* 심볼 */}
      <td className="px-2 py-1.5 w-20">
        <span className="font-mono font-black text-[13px] text-slate-100 tracking-tight leading-none">
          {coin.symbol.replace("USDT", "")}
        </span>
      </td>

      {/* 단계 */}
      <td className="px-2 py-1.5">
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold border ${sc.text} ${sc.border} ${sc.bg}`}
        >
          <span
            className={`w-1 h-1 rounded-full ${sc.dot} shrink-0 ${isPreIgn ? "animate-pulse" : ""}`}
          />
          {stageLabel(coin.pump_stage)}
        </span>
      </td>

      {/* 점수 */}
      <td className="px-2 py-1.5 w-16">
        <div className={`text-[11px] font-mono font-black ${d.cls} leading-none`}>
          {coin.score}
        </div>
        <ScoreBar score={coin.score} />
      </td>

      {/* 연료 */}
      <td className="px-2 py-1.5">
        <FuelBlocks value={coin.squeeze_fuel} />
      </td>

      {/* 펀딩 */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={fundingCls}>
          {coin.funding_rate > 0 ? "+" : ""}
          {coin.funding_rate.toFixed(3)}%
        </span>
      </td>

      {/* OI 24h */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={oi24hCls}>
          +{coin.oi_change_pct_24h.toFixed(0)}%
        </span>
      </td>

      {/* 숏% */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={shortCls}>{coin.short_ratio.toFixed(1)}%</span>
      </td>

      {/* 1h% */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={price1hCls}>
          {coin.price_change_1h > 0 ? "+" : ""}
          {coin.price_change_1h.toFixed(1)}%
        </span>
      </td>

      {/* R:R */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={rrCls}>{coin.risk.risk_reward.toFixed(2)}R</span>
      </td>

      {/* 트랩 */}
      <td className="px-2 py-1.5 text-[10px] font-mono">
        <span className={trapCls}>{trapFirst}</span>
      </td>
    </tr>
  );
}

// ─── 메인 패널 ────────────────────────────────────────────────────────────────
export default function CrimeMainPanel() {
  const {
    status,
    progress,
    bybitEnabled,
    binanceEnabled,
    results,
    nextScanIn,
    lastScanAt,
    selectedSymbol,
    selectSymbol,
    toggleBybit,
    toggleBinance,
    stopScan,
    tickCountdown,
    runScan,
  } = useCrimeStore();

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 1초마다 카운트다운 tick
  useEffect(() => {
    timerRef.current = setInterval(() => {
      tickCountdown();
      // nextScanIn이 0이 되면 자동 재스캔
      const { nextScanIn: remaining, status: s } = useCrimeStore.getState();
      if (remaining <= 0 && s === "complete") {
        useCrimeStore.getState().runScan();
      }
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStartScan = () => runScan();

  const [filter, setFilter] = useState<FilterKey>("ALL");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // 필터
  const filtered = results.filter((c) => {
    if (filter === "ALL") return true;
    return normalizeStage(c.pump_stage) === filter;
  });

  // 정렬
  const sorted = [...filtered].sort((a, b) => {
    let va: number | string = 0;
    let vb: number | string = 0;
    switch (sortKey) {
      case "rank":
      case "score":
        va = a.score; vb = b.score; break;
      case "symbol":
        va = a.symbol; vb = b.symbol; break;
      case "stage":
        va = normalizeStage(a.pump_stage); vb = normalizeStage(b.pump_stage); break;
      case "fuel":
        va = a.squeeze_fuel; vb = b.squeeze_fuel; break;
      case "funding":
        va = a.funding_rate; vb = b.funding_rate; break;
      case "oi24h":
        va = a.oi_change_pct_24h; vb = b.oi_change_pct_24h; break;
      case "short":
        va = a.short_ratio; vb = b.short_ratio; break;
      case "price1h":
        va = a.price_change_1h; vb = b.price_change_1h; break;
      case "rr":
        va = a.risk.risk_reward; vb = b.risk.risk_reward; break;
      case "trap":
        va = a.risk.dump_trap_risk; vb = b.risk.dump_trap_risk; break;
    }
    if (typeof va === "string" && typeof vb === "string") {
      return sortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    }
    return sortDir === "asc"
      ? (va as number) - (vb as number)
      : (vb as number) - (va as number);
  });

  function handleSort(k: SortKey) {
    if (sortKey === k) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir("desc");
    }
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
    <div className="flex flex-col h-full bg-[#080810] overflow-hidden">
      {/* ── 영역1: 스캔 컨트롤 바 ── */}
      <div className="shrink-0 px-3 py-2 border-b border-white/[0.06] space-y-2">
        {/* 상단 줄 */}
        <div className="flex items-center gap-2">
          {/* 타이틀 */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[11px]">💀</span>
            <span className="text-[11px] font-black tracking-[0.08em] text-slate-100 uppercase">
              CRIME HUNTER
            </span>
            <span className="text-[9px] font-bold text-rose-500/60 font-mono">V5</span>
          </div>

          {/* 거래소 토글 */}
          <div className="flex items-center gap-1.5 mx-auto">
            <button
              onClick={toggleBybit}
              className={`px-2.5 py-1 rounded text-[9px] font-bold tracking-wider transition-colors border ${
                bybitEnabled
                  ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300"
                  : "bg-slate-800/30 border-slate-700/30 text-slate-600"
              }`}
            >
              BYBIT
            </button>
            <button
              onClick={toggleBinance}
              className={`px-2.5 py-1 rounded text-[9px] font-bold tracking-wider transition-colors border ${
                binanceEnabled
                  ? "bg-indigo-600/20 border-indigo-500/40 text-indigo-300"
                  : "bg-slate-800/30 border-slate-700/30 text-slate-600"
              }`}
            >
              BINANCE
            </button>
          </div>

          {/* 스캔 버튼 + 상태 */}
          <div className="flex items-center gap-2 shrink-0 ml-auto">
            {status === "complete" && lastScanAt && (
              <span className="text-[8px] font-mono text-slate-600 hidden sm:block">
                마지막: {lastScanAt}
              </span>
            )}
            {status === "scanning" ? (
              <button
                onClick={stopScan}
                className="px-3 py-1 rounded text-[9px] font-bold tracking-wider bg-slate-700/40 border border-slate-600/40 text-slate-300 hover:bg-slate-600/40 transition-colors"
              >
                ■ STOP
              </button>
            ) : (
              <button
                onClick={handleStartScan}
                className="px-3 py-1 rounded text-[9px] font-bold tracking-wider bg-rose-600/20 border border-rose-500/40 text-rose-300 hover:bg-rose-600/30 transition-colors"
              >
                ▶ SCAN START
              </button>
            )}
          </div>
        </div>

        {/* 하단 줄: 스캐닝 중 */}
        {status === "scanning" && (
          <div className="space-y-1">
            <div className="w-full h-[3px] bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-rose-600 to-rose-400 rounded-full transition-all duration-300"
                style={{
                  width:
                    progress.total > 0
                      ? `${Math.min((progress.current / progress.total) * 100, 100)}%`
                      : "0%",
                }}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[8px] font-mono text-slate-500">
                {progress.current} / {progress.total}
              </span>
              {progress.estimatedSecondsLeft > 0 && (
                <span className="text-[8px] font-mono text-slate-600">
                  ~{progress.estimatedSecondsLeft}초
                </span>
              )}
            </div>
          </div>
        )}

        {/* 하단 줄: 스캔 완료 */}
        {status === "complete" && (
          <div className="flex items-center gap-2 text-[8px] font-mono text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            <span>
              마지막 스캔: {lastScanAt}
            </span>
            {nextScanIn > 0 && (
              <span className="ml-auto text-slate-700">
                다음: {fmtMMSS(nextScanIn)} 후
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── 영역2: 랭킹 테이블 ── */}
      <div className="flex-1 overflow-y-auto no-scrollbar flex flex-col">
        {/* 필터 버튼 — sticky */}
        <div className="sticky top-0 z-10 bg-[#080810] border-b border-white/[0.04] px-3 py-1.5 flex items-center gap-1.5">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-2 py-0.5 rounded text-[8px] font-bold tracking-wider transition-colors ${
                filter === key
                  ? "bg-rose-600/20 border border-rose-500/40 text-rose-300"
                  : "text-slate-600 border border-transparent hover:text-slate-400 hover:border-slate-700/40"
              }`}
            >
              {label}
            </button>
          ))}
          <span className="ml-auto text-[8px] font-mono text-slate-700">
            {sorted.length}개
          </span>
        </div>

        {/* 테이블 */}
        <table className="w-full border-collapse min-w-max">
          <thead className="sticky top-[33px] z-10 bg-[#0a0812]">
            <tr>
              <Th label="#" col="rank" {...thProps} className="w-8 text-center" />
              <Th label="심볼" col="symbol" {...thProps} />
              <Th label="단계" col="stage" {...thProps} />
              <Th label="점수" col="score" {...thProps} />
              <Th label="연료" col="fuel" {...thProps} />
              <Th label="펀딩" col="funding" {...thProps} />
              <Th label="OI 24h" col="oi24h" {...thProps} />
              <Th label="숏%" col="short" {...thProps} />
              <Th label="1h%" col="price1h" {...thProps} />
              <Th label="R:R" col="rr" {...thProps} />
              <Th label="트랩" col="trap" {...thProps} />
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={11}
                  className="text-center py-12 text-[10px] font-mono text-slate-700"
                >
                  해당 필터 결과 없음
                </td>
              </tr>
            ) : (
              sorted.map((coin, i) => {
                // 전체 results 기준 실제 랭크 계산
                const globalRank = results.findIndex((r) => r.symbol === coin.symbol) + 1;
                return (
                  <CrimeRow
                    key={coin.symbol}
                    coin={coin}
                    rank={globalRank || i + 1}
                    selected={selectedSymbol === coin.symbol}
                    onSelect={() =>
                      selectSymbol(selectedSymbol === coin.symbol ? null : coin.symbol)
                    }
                  />
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
