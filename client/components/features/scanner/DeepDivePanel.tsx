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
    <div className="flex flex-col gap-1 rounded-md border border-white/10 bg-white/[0.025] px-3 py-2.5">
      <div className="font-mono text-[7px] tracking-[0.22em] text-slate-500 uppercase">{label}</div>
      <div className={cn("font-mono text-[11px] font-semibold", color ?? "text-slate-200")}>{value}</div>
    </div>
  );
}

function FlowTag({ text, type }: { text: string; type: string }) {
  const cls =
    type === "bull"
      ? "text-emerald-300 bg-emerald-500/10 border-emerald-500/25"
      : type === "bear"
      ? "text-rose-300 bg-rose-500/10 border-rose-500/25"
      : type === "warn"
      ? "text-amber-300 bg-amber-500/10 border-amber-500/25"
      : "text-slate-400 bg-white/[0.02] border-white/10";

  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-1 font-mono text-[8px]", cls)}>
      {text}
    </span>
  );
}

function StateChip({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" | "neutral" }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[8px]",
        tone === "up" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
        tone === "down" && "border-rose-500/30 bg-rose-500/10 text-rose-300",
        (!tone || tone === "neutral") && "border-white/10 bg-white/[0.02] text-slate-300"
      )}
    >
      <span className="tracking-[0.16em] text-slate-500">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
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
  const flowData = (c.signals?.flow as { flowData?: { signals: Array<{ text: string; type: string }> } } | undefined)?.flowData;

  const lsColor =
    c.lsRatio == null
      ? "text-slate-500"
      : c.lsRatio < 0.7
      ? "text-emerald-300"
      : c.lsRatio > 1.8
      ? "text-rose-300"
      : "text-slate-200";

  const tkColor =
    c.takerRatio == null
      ? "text-slate-500"
      : c.takerRatio > 1.15
      ? "text-emerald-300"
      : c.takerRatio < 0.85
      ? "text-rose-300"
      : "text-slate-200";

  const narrativeTone = c.narrativeMult > 1 ? "up" : c.narrativeMult < 1 ? "down" : "neutral";
  const narrativeLabel =
    c.narrativeMult > 1
      ? `+${((c.narrativeMult - 1) * 100).toFixed(0)}%`
      : c.narrativeMult < 1
      ? `-${((1 - c.narrativeMult) * 100).toFixed(0)}%`
      : "NEUTRAL";

  const sectorTone = topSectors.has(c.sector) ? "up" : botSectors.has(c.sector) ? "down" : "neutral";

  const signalItems = SIGNAL_META
    .map(({ key, emoji, name, color }: { key: string; emoji: string; name: string; color: string }) => {
      const sig = c.signals[key];
      if (!sig) return null;
      return { key, label: `${emoji} ${name}`, value: sig.score, note: sig.note, color };
    })
    .filter((v): v is { key: string; label: string; value: number; note?: string; color: string } => Boolean(v))
    .sort((a, b) => b.value - a.value);

  const visibleSignals = signalItems.slice(0, 8);
  const hiddenSignals = Math.max(0, signalItems.length - visibleSignals.length);
  const flowTags = (flowData?.signals ?? []).slice(0, 5);
  const flowOverflow = Math.max(0, (flowData?.signals?.length ?? 0) - flowTags.length);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3.5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <InfoBox label="24H RANGE" value={`${fmt.price(c.low24)} → ${fmt.price(c.high24)}`} />
          <InfoBox label="24H VOL" value={`${(c.quoteVolume / 1_000_000).toFixed(1)}M`} />
          <InfoBox
            label="7D CHANGE"
            value={c.change7d != null ? fmt.pct(c.change7d) : "—"}
            color={c.change7d != null ? (c.change7d > 0 ? "text-emerald-300" : "text-rose-300") : undefined}
          />
          <InfoBox label="1H / 4H" value={`${fmt.pct(c.change1h ?? 0, 1)} / ${fmt.pct(c.change4h ?? 0, 1)}`} />
        </div>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <StateChip label="STAGE" value={`S${c.stage}`} tone={c.stage >= 3 ? "up" : c.stage <= 1 ? "neutral" : "down"} />
          <StateChip label="NARR" value={narrativeLabel} tone={narrativeTone} />
          <StateChip label="SECTOR" value={c.sector || "—"} tone={sectorTone} />
          <StateChip label="REGIME" value={regimeLabel} />
          <StateChip label="STRONG" value={`${c.strongCount}`} tone={c.strongCount >= 4 ? "up" : "neutral"} />
        </div>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.015] p-3.5">
        <div className="mb-2.5 font-mono text-[8px] tracking-[0.28em] text-slate-500 uppercase">Flow Snapshot</div>

        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2">
          <InfoBox
            label="FUNDING"
            value={c.funding != null ? (c.funding * 100).toFixed(4) + "%" : "—"}
            color={
              c.funding != null
                ? c.funding < -0.005
                  ? "text-emerald-300"
                  : c.funding > 0.04
                  ? "text-rose-300"
                  : "text-slate-200"
                : undefined
            }
          />
          <InfoBox
            label="OI 24H"
            value={c.oiChange24 != null ? fmt.pct(c.oiChange24, 1) : "—"}
            color={c.oiChange24 != null ? (c.oiChange24 > 0 ? "text-emerald-300" : "text-rose-300") : undefined}
          />
          <InfoBox
            label="OI 1H"
            value={c.oiChange1h != null ? fmt.pct(c.oiChange1h, 2) : "—"}
            color={c.oiChange1h != null ? (c.oiChange1h > 0 ? "text-emerald-300" : "text-rose-300") : undefined}
          />
          <InfoBox label="L/S" value={c.lsRatio != null ? `${c.lsRatio.toFixed(2)}×` : "—"} color={lsColor} />
          <InfoBox label="TAKER" value={c.takerRatio != null ? `${c.takerRatio.toFixed(2)}×` : "—"} color={tkColor} />
          <InfoBox label="5M LIQ" value={`${fmtUsd(shortLiq5m)} / ${fmtUsd(longLiq5m)}`} color="text-slate-300" />
        </div>

        {flowTags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {flowTags.map((s, i) => (
              <FlowTag key={`${s.text}-${i}`} text={s.text} type={s.type} />
            ))}
            {flowOverflow > 0 && (
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.02] px-2 py-1 font-mono text-[8px] text-slate-400">
                +{flowOverflow} more
              </span>
            )}
          </div>
        )}
      </div>

      <div className="pt-1">
        <div className="mb-2.5 flex items-center justify-between">
          <div className="font-mono text-[8px] tracking-[0.28em] text-slate-500 uppercase">Signal Breakdown</div>
          <div className="font-mono text-[8px] text-slate-600">TOP {visibleSignals.length}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2.5">
          {visibleSignals.map(({ key, label, value, note, color }) => (
            <SignalBar key={key} label={label} value={value} note={note} color={color} />
          ))}
        </div>

        {hiddenSignals > 0 && (
          <div className="mt-2 font-mono text-[8px] text-slate-600 tracking-[0.12em] uppercase">+{hiddenSignals} signals hidden for readability</div>
        )}
      </div>
    </div>
  );
}
