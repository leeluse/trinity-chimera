"use client";

import React, { useState } from "react";
import { Skull, AlertTriangle, Shield, Target, ChevronDown, ChevronUp, X, Zap } from "lucide-react";
import { useCrimeStore } from "@/store/useCrimeStore";
import {
  CoinData, CrimeSignal, SignalType,
  fmtPrice, fmtVol, stageColor, trapColor, scoreDanger,
} from "./crimeData";

// ─── 시그널 표시 설정 ────────────────────────────────────
const SIGNAL_META: Record<SignalType, { icon: string; color: string; bg: string }> = {
  PRE_IGNITION: { icon: "💥", color: "text-fuchsia-300", bg: "bg-fuchsia-950/40 border-fuchsia-500/30" },
  IGNITION:     { icon: "🔥", color: "text-red-300",     bg: "bg-red-950/40 border-red-500/30" },
  STAGE_UP:     { icon: "⚡", color: "text-amber-300",   bg: "bg-amber-950/30 border-amber-500/20" },
  FUEL_MAX:     { icon: "💡", color: "text-orange-300",  bg: "bg-orange-950/30 border-orange-500/20" },
  SCORE_SPIKE:  { icon: "📈", color: "text-rose-300",    bg: "bg-rose-950/30 border-rose-500/20" },
  EXIT_ALERT:   { icon: "⚠️", color: "text-amber-300",   bg: "bg-amber-950/30 border-amber-500/20" },
  TRAP_ALERT:   { icon: "🚨", color: "text-red-300",     bg: "bg-red-950/30 border-red-500/20" },
};

function fmtAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}초 전`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}분 전`;
  return `${Math.floor(m / 60)}시간 전`;
}

// ─── 진입 판단 ───────────────────────────────────────────
function entryVerdict(coin: CoinData): { label: string; cls: string; bg: string } {
  const { entry_score, dump_trap_risk } = coin.risk;
  if (dump_trap_risk.includes("CRITICAL") || dump_trap_risk.includes("HIGH") || entry_score < 50)
    return { label: "ABORT", cls: "text-red-400", bg: "bg-red-500/10 border-red-500/30" };
  if (entry_score >= 70 && (dump_trap_risk.includes("LOW") || dump_trap_risk.includes("MEDIUM") && entry_score >= 75))
    return { label: "GO", cls: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" };
  return { label: "WAIT", cls: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30" };
}

// ─── 시그널 피드 행 ──────────────────────────────────────
function SignalRow({ sig, onClick }: { sig: CrimeSignal; onClick: () => void }) {
  const meta = SIGNAL_META[sig.type];
  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 border-b border-white/[0.04] cursor-pointer hover:bg-white/[0.03] transition-colors`}
      onClick={onClick}
    >
      <span className="text-[11px] shrink-0 mt-0.5">{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-[9px] font-mono font-black ${meta.color}`}>
            {sig.symbol.replace("USDT", "")}
          </span>
          <span className={`text-[7px] font-bold px-1 py-0.5 rounded border ${meta.bg} ${meta.color}`}>
            {sig.type}
          </span>
          <span className="text-[7px] text-slate-700 ml-auto shrink-0">{fmtAgo(sig.timestamp)}</span>
        </div>
        <p className="text-[8px] text-slate-500 mt-0.5 leading-snug truncate">{sig.message}</p>
      </div>
    </div>
  );
}

// ─── 상위 3개 진입 추천 카드 ─────────────────────────────
function TopEntryCard({
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
  const verdict = entryVerdict(coin);
  const sc = stageColor(coin.pump_stage);
  const d = scoreDanger(coin.score);

  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 border-b border-white/[0.04] cursor-pointer transition-colors ${selected ? "bg-rose-950/10 border-l-2 border-rose-500" : "hover:bg-white/[0.03]"}`}
      onClick={onSelect}
    >
      <span className={`text-[9px] font-mono font-black shrink-0 ${rank === 1 ? "text-fuchsia-500" : rank === 2 ? "text-red-500" : "text-orange-500"}`}>
        {rank}위
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-mono font-black text-[12px] text-slate-100 tracking-tight">
            {coin.symbol.replace("USDT", "")}
          </span>
          <span className={`text-[8px] font-bold ${sc.text}`}>{coin.pump_stage}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-[8px] font-mono ${d.cls}`}>{coin.score}pt</span>
          <span className="text-[7px] text-slate-600">x{coin.risk.recommended_leverage}</span>
          <span className={`text-[7px] font-bold ${coin.risk.risk_reward >= 2 ? "text-emerald-400" : "text-amber-400"}`}>
            {coin.risk.risk_reward.toFixed(2)}R
          </span>
        </div>
      </div>
      <div className={`px-2 py-0.5 rounded border text-[9px] font-black ${verdict.bg} ${verdict.cls}`}>
        {verdict.label}
      </div>
    </div>
  );
}

// ─── 선택된 코인 상세 ────────────────────────────────────
function CoinDetail({ coin }: { coin: CoinData }) {
  const [open, setOpen] = useState(true);
  const verdict = entryVerdict(coin);
  const slPct = (coin.risk.stop_loss / coin.price - 1) * 100;
  const t1Pct = (coin.risk.target_1 / coin.price - 1) * 100;
  const t2Pct = (coin.risk.target_2 / coin.price - 1) * 100;
  const t3Pct = (coin.risk.target_3 / coin.price - 1) * 100;

  return (
    <div className="border-t border-rose-500/20 bg-[#0c0a0f]">
      {/* 코인 헤더 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.05]">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-black text-[14px] text-slate-100">
              {coin.symbol.replace("USDT", "")}
            </span>
            <span className="text-[9px] font-mono text-slate-400">{fmtPrice(coin.price)}</span>
            <span className={`text-[8px] font-bold ${coin.price_change_1h >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {coin.price_change_1h > 0 ? "+" : ""}{coin.price_change_1h.toFixed(2)}%
            </span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`text-[8px] font-bold ${stageColor(coin.pump_stage).text}`}>{coin.pump_stage}</span>
            <span className={`text-[8px] font-black ${scoreDanger(coin.score).cls}`}>· {coin.score}pt</span>
          </div>
        </div>
        <button onClick={() => setOpen(!open)} className="text-slate-600 hover:text-slate-400">
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {open && (
        <>
          {/* 진입 판단 트래픽라이트 */}
          <div className={`mx-3 my-2 px-3 py-2 rounded border ${verdict.bg} flex items-center gap-3`}>
            <span className={`text-[18px] font-black ${verdict.cls}`}>{verdict.label}</span>
            <div className="flex-1 text-[8px] text-slate-500 space-y-0.5">
              <div>진입점수 <span className={`font-bold ${verdict.cls}`}>{coin.risk.entry_score.toFixed(0)}/100</span></div>
              <div>트랩 <span className={`font-bold ${trapColor(coin.risk.dump_trap_risk)}`}>{coin.risk.dump_trap_risk.split(" ")[0]}</span></div>
              <div>R:R <span className="text-slate-300 font-bold">{coin.risk.risk_reward.toFixed(2)}</span></div>
            </div>
            <div className="text-right text-[8px] text-slate-600 space-y-0.5">
              <div>레버리지 <span className="text-amber-400 font-bold">x{coin.risk.recommended_leverage}</span></div>
              <div>포지션 <span className="text-slate-300 font-bold">${coin.risk.position_size_usd}</span></div>
            </div>
          </div>

          {/* 가격 레벨 */}
          <div className="px-3 pb-2 space-y-1">
            <div className="text-[7px] font-bold text-slate-600 uppercase tracking-widest mb-1.5 flex items-center gap-1">
              <Shield size={7} /> 리스크 관리
            </div>
            {[
              { l: "진입구간", v: `${fmtPrice(coin.risk.entry_zone_low)} ~ ${fmtPrice(coin.risk.entry_zone_high)}`, cls: "text-slate-300", bg: "bg-white/[0.02]" },
              { l: "손절", v: `${fmtPrice(coin.risk.stop_loss)}  (${slPct.toFixed(1)}%)`, cls: "text-red-400", bg: "bg-red-950/20" },
              { l: "목표1 1R", v: `${fmtPrice(coin.risk.target_1)}  (+${t1Pct.toFixed(1)}%)`, cls: "text-emerald-400", bg: "bg-emerald-950/20" },
              { l: "목표2 2R", v: `${fmtPrice(coin.risk.target_2)}  (+${t2Pct.toFixed(1)}%)`, cls: "text-emerald-400", bg: "bg-emerald-950/20" },
              { l: "목표3 3.5R", v: `${fmtPrice(coin.risk.target_3)}  (+${t3Pct.toFixed(1)}%)`, cls: "text-emerald-300", bg: "bg-emerald-950/30" },
            ].map(({ l, v, cls, bg }) => (
              <div key={l} className={`flex items-center justify-between ${bg} rounded px-2 py-1`}>
                <span className="text-[7px] text-slate-600 font-bold">{l}</span>
                <span className={`text-[9px] font-mono font-bold ${cls}`}>{v}</span>
              </div>
            ))}

            {/* 청산 클러스터 */}
            <div className="flex gap-1.5 mt-1">
              <div className="flex-1 bg-emerald-950/20 rounded px-2 py-1 flex justify-between">
                <span className="text-[7px] text-emerald-600 font-bold">청산↑</span>
                <span className="text-[9px] font-mono text-emerald-400">{fmtVol(coin.risk.liq_above_usd)}</span>
              </div>
              <div className="flex-1 bg-red-950/20 rounded px-2 py-1 flex justify-between">
                <span className="text-[7px] text-red-600 font-bold">청산↓</span>
                <span className="text-[9px] font-mono text-red-400">{fmtVol(coin.risk.liq_below_usd)}</span>
              </div>
            </div>
          </div>

          {/* DCA 플랜 */}
          <div className="px-3 pb-2">
            <div className="text-[7px] font-bold text-slate-600 uppercase tracking-widest mb-1.5 flex items-center gap-1">
              <Target size={7} /> 분할진입
            </div>
            <div className="space-y-1">
              {coin.risk.dca_plan.map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[7px] text-slate-700 font-mono w-2">{i + 1}</span>
                  <div className="flex-1 h-[2px] bg-slate-800 rounded overflow-hidden">
                    <div className="h-full bg-amber-600/60" style={{ width: `${step.size_pct}%` }} />
                  </div>
                  <span className="text-[7px] text-amber-400 font-bold w-5 text-right">{step.size_pct}%</span>
                  <span className="text-[8px] font-mono text-slate-300 w-20">{fmtPrice(step.entry)}</span>
                  <span className="text-[7px] text-slate-600 flex-1">{step.note}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 핵심 지표 */}
          <div className="px-3 pb-2 grid grid-cols-3 gap-1">
            {[
              { l: "펀딩", v: `${coin.funding_rate > 0 ? "+" : ""}${coin.funding_rate.toFixed(3)}%`, hot: coin.funding_rate < -0.3 },
              { l: "OI 24h", v: `+${coin.oi_change_pct_24h.toFixed(0)}%`, hot: coin.oi_change_pct_24h >= 40 },
              { l: "숏%", v: `${coin.short_ratio.toFixed(1)}%`, hot: coin.short_ratio >= 62 },
              { l: "테이커B", v: `${coin.taker_buy_ratio.toFixed(0)}%`, hot: coin.taker_buy_ratio >= 60 },
              { l: "북인밸", v: `x${coin.book_imbalance.toFixed(2)}`, hot: coin.book_imbalance >= 3 },
              { l: "스퀴즈", v: `${coin.squeeze_fuel}`, hot: coin.squeeze_fuel >= 80 },
            ].map(({ l, v, hot }) => (
              <div key={l} className="bg-white/[0.02] rounded px-2 py-1">
                <div className="text-[7px] text-slate-600 uppercase font-bold">{l}</div>
                <div className={`text-[10px] font-mono font-bold ${hot ? "text-red-400" : "text-slate-300"}`}>{v}</div>
              </div>
            ))}
          </div>

          {/* 탈출 경보 */}
          {coin.exit_alert.exit_reasons.length > 0 && (
            <div className="mx-3 mb-2 px-2 py-1.5 rounded border border-amber-500/20 bg-amber-950/20">
              <div className="flex items-center gap-1 mb-1">
                <AlertTriangle size={8} className="text-amber-500" />
                <span className="text-[8px] font-bold text-amber-400">{coin.exit_alert.urgency}</span>
                <span className="ml-auto text-[7px] text-slate-600">{coin.exit_alert.exit_score}/100</span>
              </div>
              {coin.exit_alert.exit_reasons.map((r, i) => (
                <div key={i} className="text-[7px] text-amber-400/70">{r}</div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── P0 배너 ─────────────────────────────────────────────
function P0Banner({ signal, onDismiss }: { signal: CrimeSignal; onDismiss: () => void }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-fuchsia-950/60 border-b-2 border-fuchsia-500/50 shrink-0 animate-pulse">
      <span className="text-[10px]">{SIGNAL_META[signal.type].icon}</span>
      <div className="flex-1 min-w-0">
        <span className="text-[9px] font-black text-fuchsia-300 uppercase tracking-wide">
          {signal.symbol.replace("USDT", "")} {signal.type}
        </span>
        <span className="text-[8px] text-fuchsia-400/70 ml-2">{signal.message}</span>
      </div>
      <button onClick={onDismiss} className="text-fuchsia-600 hover:text-fuchsia-400 transition-colors shrink-0">
        <X size={11} />
      </button>
    </div>
  );
}

// ─── 메인 ────────────────────────────────────────────────
export default function CrimeDashboard() {
  const {
    results, signals, p0Banner, dismissBanner,
    selectedSymbol, selectSymbol,
  } = useCrimeStore();

  // 진입점수 상위 3개
  const top3 = [...results]
    .sort((a, b) => b.risk.entry_score - a.risk.entry_score)
    .slice(0, 3);

  const selectedCoin = selectedSymbol
    ? results.find((c) => c.symbol === selectedSymbol) ?? null
    : null;

  const handleSignalClick = (sig: CrimeSignal) => selectSymbol(sig.symbol);
  const handleTopSelect = (symbol: string) =>
    selectSymbol(selectedSymbol === symbol ? null : symbol);

  return (
    <div className="flex flex-col h-full bg-[#080810] text-slate-300 overflow-hidden">
      {/* P0 배너 */}
      {p0Banner && <P0Banner signal={p0Banner} onDismiss={dismissBanner} />}

      {/* 패널 헤더 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-rose-500/10 bg-rose-500/[0.03] shrink-0">
        <Skull size={12} className="text-rose-500" />
        <span className="text-[9px] font-black tracking-widest text-slate-300 uppercase">Crime Panel</span>
        {signals.length > 0 && (
          <span className="ml-auto px-1.5 py-0.5 rounded bg-rose-500/20 border border-rose-500/30 text-[8px] font-bold text-rose-400">
            {signals.length}
          </span>
        )}
      </div>

      {/* 상단 50%: 시그널 피드 */}
      <div className="flex flex-col" style={{ flex: "0 0 50%" }}>
        <div className="px-3 py-1.5 border-b border-white/[0.05] shrink-0">
          <span className="text-[7px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-1">
            <Zap size={7} className="text-amber-500" /> 시그널 피드
          </span>
        </div>
        <div className="flex-1 overflow-y-auto no-scrollbar">
          {signals.length === 0 ? (
            <div className="flex items-center justify-center h-full text-[9px] text-slate-700">
              스캔 후 시그널이 표시됩니다
            </div>
          ) : (
            signals.map((sig) => (
              <SignalRow key={sig.id} sig={sig} onClick={() => handleSignalClick(sig)} />
            ))
          )}
        </div>
      </div>

      {/* 하단 50%: 진입 추천 + 선택 코인 상세 */}
      <div className="flex flex-col border-t border-white/[0.06]" style={{ flex: "0 0 50%" }}>
        {/* 진입 추천 헤더 */}
        <div className="px-3 py-1.5 border-b border-white/[0.05] shrink-0">
          <span className="text-[7px] font-bold text-slate-600 uppercase tracking-widest flex items-center gap-1">
            <Target size={7} className="text-emerald-500" /> 진입 추천
          </span>
        </div>

        <div className="flex-1 overflow-y-auto no-scrollbar">
          {/* Top 3 카드 */}
          {top3.map((coin, i) => (
            <TopEntryCard
              key={coin.symbol}
              coin={coin}
              rank={i + 1}
              selected={selectedSymbol === coin.symbol}
              onSelect={() => handleTopSelect(coin.symbol)}
            />
          ))}

          {/* 선택된 코인 상세 (top3에 없는 경우에도 표시) */}
          {selectedCoin && (
            <CoinDetail coin={selectedCoin} />
          )}

          {!selectedCoin && (
            <div className="flex items-center justify-center py-4 text-[8px] text-slate-700">
              테이블에서 코인 클릭 시 상세 표시
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
