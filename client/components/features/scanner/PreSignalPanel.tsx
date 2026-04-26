import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { Candidate } from "@/app/scanner/types";

interface PreSignalPanelProps {
  candidates: Candidate[];
}

interface DerivedSignal {
  symbol: string;
  dir: 1 | -1;
  title: string;
  desc: string;
  severity: number;
}

function derivePreSignals(candidates: Candidate[]): DerivedSignal[] {
  const signals: DerivedSignal[] = [];

  candidates.forEach((c) => {
    const sym = c.symbol.replace("USDT", "");
    const fr = c.funding ?? 0;
    const oi = c.oiChange24 ?? 0;
    const capScore = c.signals.capitulation?.score ?? 0;

    if (Math.abs(fr) > 0.001) {
      signals.push({
        symbol: sym,
        dir: fr < 0 ? 1 : -1,
        title: "⚡ 펀딩 극단치",
        desc: `${(fr * 100).toFixed(4)}% ${fr < 0 ? "숏 스퀴즈 대기" : "롱 과열 위험"}`,
        severity: Math.abs(fr) * 100000,
      });
    }

    if (oi > 20 && Math.abs(c.change24) < 3) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "📊 OI 빌드업",
        desc: `OI +${oi.toFixed(1)}% 가격 횡보 — 축적 가능성`,
        severity: oi,
      });
    }

    if (capScore > 65) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "💀 청산 과열",
        desc: `청산 시그널 ${capScore.toFixed(0)}점 — 반등 가능성`,
        severity: capScore,
      });
    }

    if (c.lsRatio != null && c.lsRatio < 0.6) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "📡 숏 극단",
        desc: `L/S ${c.lsRatio.toFixed(2)} — 숏 과적 반등 가능`,
        severity: (0.6 - c.lsRatio) * 100,
      });
    }

    if (c.lsRatio != null && c.lsRatio > 2.2) {
      signals.push({
        symbol: sym,
        dir: -1,
        title: "📡 롱 극단",
        desc: `L/S ${c.lsRatio.toFixed(2)} — 롱 과적 청산 위험`,
        severity: (c.lsRatio - 2.2) * 50,
      });
    }
  });

  return signals.sort((a, b) => b.severity - a.severity).slice(0, 12);
}

export function PreSignalPanel({ candidates }: PreSignalPanelProps) {
  const signals = useMemo(() => derivePreSignals(candidates), [candidates]);

  if (signals.length === 0) return null;

  return (
    <div className="border border-white/10 rounded-xl bg-white/[0.02] backdrop-blur-xl p-4">
      <div className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase mb-4 flex items-center gap-2">
        <div className="w-1 h-2.5 bg-cyan-400" /> Pre-Signal Radar
        <span className="ml-auto text-[8px] text-slate-600">{signals.length} DETECTED</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
        {signals.map((s, i) => (
          <div
            key={`${s.symbol}-${s.title}-${i}`}
            className={cn(
              "p-2.5 border rounded-md flex flex-col gap-1",
              s.dir > 0
                ? "bg-green-500/5 border-green-500/15"
                : "bg-red-500/5 border-red-500/15"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[9px] font-black text-white/80">{s.symbol}</span>
              <span
                className={cn(
                  "font-mono text-[8px] font-bold",
                  s.dir > 0 ? "text-green-400" : "text-red-400"
                )}
              >
                {s.dir > 0 ? "▲ 매수" : "▼ 매도"}
              </span>
            </div>
            <div className="font-mono text-[8px] text-slate-400">{s.title}</div>
            <div className="text-[8px] text-slate-600 leading-tight">{s.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
