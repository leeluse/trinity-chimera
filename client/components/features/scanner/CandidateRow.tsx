import { cn } from "@/lib/utils";
import { ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import { Candidate } from "@/app/scanner/types";
import { fmt } from "@/app/scanner/utils";
import { SIGNAL_META } from "@/app/scanner/constants";
import { DeepDivePanel } from "./DeepDivePanel";

interface CandidateRowProps {
  candidate: Candidate;
  rank: number;
  btcChange24: number;
  expanded: boolean;
  onToggle: () => void;
  topSectors: Set<string>;
  botSectors: Set<string>;
  regimeLabel: string;
  regimeAdaptive: boolean;
  shortLiq5m?: number;
  longLiq5m?: number;
}

export function CandidateRow({
  candidate: c,
  rank,
  btcChange24,
  expanded,
  onToggle,
  topSectors,
  botSectors,
  regimeLabel,
  regimeAdaptive,
  shortLiq5m,
  longLiq5m,
}: CandidateRowProps) {
  const rs = c.change24 - btcChange24;

  return (
    <>
      <tr className="border-b border-white/5 hover:bg-white/[0.04] transition-colors group">
        <td className="px-3 py-3 font-mono text-[10px] text-slate-500/60 tracking-[0.1em]">
          {String(rank).padStart(2, "0")}
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[13px] font-bold text-white/90">{c.symbol.replace("USDT", "")}</span>
            {c.pumpFlagged && (
              <span className="px-1 py-0.5 text-[8px] font-mono font-black tracking-[0.2em] bg-red-500/15 text-red-500 border border-red-500/20 rounded-sm">PUMP</span>
            )}
          </div>
          <div className="font-mono text-[9px] text-slate-600 font-bold tracking-[0.2em] uppercase mt-0.5">
            {c.sector || "—"}
            {topSectors.has(c.sector) && <span className="text-green-500"> ▲</span>}
            {botSectors.has(c.sector) && <span className="text-red-500"> ▼</span>}
          </div>
        </td>
        <td className="px-3 py-3 text-right font-mono text-[11px] font-medium tabular-nums text-slate-300">{fmt.price(c.price)}</td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] font-bold tabular-nums", c.change24 > 0 ? "text-green-400" : c.change24 < 0 ? "text-red-400" : "text-slate-500")}>
          {fmt.pct(c.change24, 2)}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", rs > 0 ? "text-green-400" : rs < 0 ? "text-red-400" : "text-slate-600")}>
          {fmt.pct(rs, 1)}
        </td>
        <td className="px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell text-slate-600">
          {c.volRatio != null ? fmt.multiplier(c.volRatio) : "—"}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", c.funding && c.funding > 0 ? "text-green-400" : c.funding && c.funding < 0 ? "text-red-400" : "text-slate-600")}>
          {c.funding != null ? (c.funding * 100).toFixed(4) + "%" : "—"}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono text-[11px] tabular-nums hidden md:table-cell", c.oiChange24 && c.oiChange24 > 0 ? "text-green-400" : c.oiChange24 && c.oiChange24 < 0 ? "text-red-400" : "text-slate-600")}>
          {c.oiChange24 != null ? fmt.pct(c.oiChange24, 1) : "—"}
        </td>
        <td className="px-3 py-3 text-right">
          <div className="relative inline-flex items-center">
            <div
              className={cn(
                "absolute inset-0 rounded-sm -z-10 opacity-30",
                c.score >= 70 ? "bg-green-500/40 shadow-[0_0_10px_rgba(34,211,238,0.15)]" :
                  c.score >= 40 ? "bg-amber-500/25" :
                    "bg-white/10"
              )}
              style={{ width: `${c.score}%` }}
            />
            <span className="font-mono text-[11px] font-black tabular-nums px-2 py-0.5 text-white/90">{c.score.toFixed(0)}</span>
          </div>
        </td>
        <td className="px-3 py-3">
          <div className="flex gap-1 flex-wrap">
            {SIGNAL_META.filter(({ key }: { key: string }) => c.signals[key]?.score > 40).map(({ key, emoji }: { key: string; emoji: string }) => (
              <span
                key={key}
                className="inline-flex items-center justify-center w-5 h-5 text-xs bg-white/5 border border-white/10 rounded-sm cursor-help hover:bg-white/10 transition-colors"
                title={`${SIGNAL_META.find(s => s.key === key)?.name} ${c.signals[key].score.toFixed(0)} ${c.signals[key].note ? "· " + c.signals[key].note : ""}`}
              >
                {emoji}
              </span>
            ))}
            {SIGNAL_META.filter(({ key }: { key: string }) => c.signals[key]?.score > 40).length === 0 && (
              <span className="text-muted-foreground/30 text-[10px] tracking-[0.1em]">—</span>
            )}
          </div>
        </td>
        <td className="px-3 py-3">
          <button
            onClick={onToggle}
            className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground hover:text-cyan-400 transition-colors px-2 py-1 flex items-center gap-1.5"
          >
            {expanded ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
            {expanded ? "CLOSE" : "INFO"}
          </button>
        </td>
        <td className="px-3 py-3">
          <a
            href={`https://www.tradingview.com/chart/?symbol=BINANCE:${c.symbol}.P`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-2 py-1 font-mono text-[9px] tracking-[0.1em] uppercase text-muted-foreground/60 border border-white/5 rounded-sm hover:text-cyan-400 hover:border-cyan-500/30 transition-all"
          >
            <ExternalLink className="w-2.5 h-2.5" />
          </a>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-white/[0.01]">
          <td colSpan={12} className="px-6 py-6 border-b border-white/5">
            <DeepDivePanel
              candidate={c}
              regimeLabel={regimeLabel}
              topSectors={topSectors}
              botSectors={botSectors}
              shortLiq5m={shortLiq5m}
              longLiq5m={longLiq5m}
            />
          </td>
        </tr>
      )}
    </>
  );
}
