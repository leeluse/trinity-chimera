import { cn } from "@/lib/utils";
import { Candidate } from "@/app/scanner/types";
import { fmt } from "@/app/scanner/utils";
import { SIGNAL_META } from "@/app/scanner/constants";
import { SignalBar } from "./SignalBar";

interface DeepDivePanelProps {
  candidate: Candidate;
  regimeLabel: string;
  topSectors: Set<string>;
  botSectors: Set<string>;
  shortLiq5m?: number;
  longLiq5m?: number;
}

function InfoBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-1 p-2.5 bg-white/5 border border-white/10 rounded-md">
      <div className="font-mono text-[7.5px] tracking-[0.25em] text-slate-600 uppercase">{label}</div>
      <div className={cn("font-mono text-[11px] font-bold", color ?? "text-slate-300")}>{value}</div>
    </div>
  );
}

function FlowTag({ text, type }: { text: string; type: string }) {
  const cls =
    type === "bull"
      ? "text-green-400 bg-green-500/10 border-green-500/20"
      : type === "bear"
      ? "text-red-400 bg-red-500/10 border-red-500/20"
      : type === "warn"
      ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
      : "text-slate-500 bg-white/5 border-white/10";
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 text-[8px] font-mono border rounded-sm", cls)}>
      {text}
    </span>
  );
}

function fmtUsd(v: number) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return "$0";
}

export function DeepDivePanel({
  candidate: c,
  regimeLabel,
  topSectors,
  botSectors,
  shortLiq5m = 0,
  longLiq5m = 0,
}: DeepDivePanelProps) {
  const flowData = (c.signals?.flow as any)?.flowData as {
    fundingRate: number;
    oiPct: number;
    lsRatio: number | null;
    takerRatio: number;
    signals: Array<{ text: string; type: string }>;
  } | undefined;

  const lsColor =
    c.lsRatio == null
      ? "text-slate-500"
      : c.lsRatio < 0.7
      ? "text-green-400"
      : c.lsRatio > 1.8
      ? "text-red-400"
      : "text-slate-300";

  const tkColor =
    c.takerRatio == null
      ? "text-slate-500"
      : c.takerRatio > 1.15
      ? "text-green-400"
      : c.takerRatio < 0.85
      ? "text-red-400"
      : "text-slate-300";

  return (
    <div className="space-y-5">
      {/* Basic stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
        <InfoBox label="24h RANGE" value={`${fmt.price(c.low24)} → ${fmt.price(c.high24)}`} />
        <InfoBox
          label="24h VOL"
          value={`${(c.quoteVolume / 1_000_000).toFixed(1)}M`}
        />
        <InfoBox
          label="7d CHANGE"
          value={c.change7d != null ? fmt.pct(c.change7d) : "—"}
          color={c.change7d != null ? (c.change7d > 0 ? "text-green-400" : "text-red-400") : undefined}
        />
        <InfoBox
          label="1h / 4h"
          value={`${fmt.pct(c.change1h ?? 0, 1)} / ${fmt.pct(c.change4h ?? 0, 1)}`}
        />
        <InfoBox
          label="NARRATIVE"
          value={
            c.narrativeMult > 1
              ? `+${((c.narrativeMult - 1) * 100).toFixed(0)}%`
              : c.narrativeMult < 1
              ? `−${((1 - c.narrativeMult) * 100).toFixed(0)}%`
              : "NEUTRAL"
          }
        />
        <InfoBox
          label="SECTOR"
          value={c.sector || "—"}
          color={
            topSectors.has(c.sector)
              ? "text-green-400"
              : botSectors.has(c.sector)
              ? "text-red-400"
              : undefined
          }
        />
        <InfoBox label="REGIME" value={regimeLabel} />
        <InfoBox label="STRONG SIG" value={`${c.strongCount} ACTIVE`} />
      </div>

      {/* L2 Flow analysis */}
      <div className="border border-white/10 rounded-lg p-4 bg-white/[0.02]">
        <div className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase mb-3 flex items-center gap-2">
          <div className="w-1 h-2 bg-cyan-400" /> L2 Flow Analysis
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <InfoBox
            label="FUNDING RATE"
            value={c.funding != null ? (c.funding * 100).toFixed(4) + "%" : "—"}
            color={
              c.funding != null
                ? c.funding < -0.005
                  ? "text-green-400"
                  : c.funding > 0.04
                  ? "text-red-400"
                  : "text-slate-300"
                : undefined
            }
          />
          <InfoBox
            label="OI CHANGE"
            value={c.oiChange24 != null ? fmt.pct(c.oiChange24, 1) : "—"}
            color={
              c.oiChange24 != null
                ? c.oiChange24 > 0
                  ? "text-green-400"
                  : "text-red-400"
                : undefined
            }
          />
          <InfoBox
            label="L/S RATIO"
            value={c.lsRatio != null ? c.lsRatio.toFixed(2) + "×" : "—"}
            color={lsColor}
          />
          <InfoBox
            label="TAKER RATIO"
            value={c.takerRatio != null ? c.takerRatio.toFixed(2) + "×" : "—"}
            color={tkColor}
          />
        </div>

        <div className="grid grid-cols-2 gap-2 mb-3">
          <InfoBox
            label="5m 숏청산"
            value={fmtUsd(shortLiq5m)}
            color={shortLiq5m > 500_000 ? "text-green-400" : "text-slate-500"}
          />
          <InfoBox
            label="5m 롱청산"
            value={fmtUsd(longLiq5m)}
            color={longLiq5m > 500_000 ? "text-red-400" : "text-slate-500"}
          />
        </div>

        {flowData?.signals && flowData.signals.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {flowData.signals.map((s, i) => (
              <FlowTag key={i} text={s.text} type={s.type} />
            ))}
          </div>
        )}
      </div>

      {/* Signal breakdown */}
      <div className="border-t border-white/5 pt-4">
        <div className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase mb-3 pl-1">
          Signal Breakdown
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-3">
          {SIGNAL_META.map(
            ({ key, emoji, name, color }: { key: string; emoji: string; name: string; color: string }) =>
              c.signals[key] ? (
                <SignalBar
                  key={key}
                  label={`${emoji} ${name}`}
                  value={c.signals[key].score}
                  note={c.signals[key].note}
                  color={color}
                />
              ) : null
          )}
          {c.signals.flow && (
            <SignalBar
              label="🌊 플로우"
              value={c.signals.flow.score}
              note={c.signals.flow.note}
              color="var(--accent-teal)"
            />
          )}
          {c.signals.volSurge && c.signals.volSurge.score > 0 && (
            <SignalBar
              label="⚡ 거래량급등"
              value={c.signals.volSurge.score}
              note={c.signals.volSurge.note}
              color="var(--accent-orange)"
            />
          )}
        </div>
      </div>
    </div>
  );
}
