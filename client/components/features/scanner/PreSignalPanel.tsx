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
  cat: "SETUP" | "TRIGGER";
}

function derivePreSignals(candidates: Candidate[]): DerivedSignal[] {
  const signals: DerivedSignal[] = [];

  candidates.forEach((c) => {
    const sym = c.symbol.replace("USDT", "");
    const fr = c.funding ?? 0;
    const oi = c.oiChange24 ?? 0;
    const capScore = c.signals.capitulation?.score ?? 0;
    const lsRatio = c.lsRatio ?? null;

    if (Math.abs(fr) > 0.0007) {
      signals.push({
        symbol: sym,
        dir: fr < 0 ? 1 : -1,
        title: "⚡ 펀딩 극단치",
        desc: `${(fr * 100).toFixed(4)}% ${fr < 0 ? "— 숏 스퀴즈 대기" : "— 롱 과열 위험"}`,
        severity: Math.abs(fr) * 120000,
        cat: "SETUP",
      });
    } else if (Math.abs(fr) > 0.0003) {
      signals.push({
        symbol: sym,
        dir: fr < 0 ? 1 : -1,
        title: "⚡ 펀딩 경고",
        desc: `${(fr * 100).toFixed(4)}% ${fr < 0 ? "— 숏 편향" : "— 롱 편향"}`,
        severity: Math.abs(fr) * 80000,
        cat: "SETUP",
      });
    }

    if (oi > 20 && Math.abs(c.change24) < 3) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "📊 OI 빌드업",
        desc: `OI +${oi.toFixed(1)}% 가격 횡보 — 축적 가능성`,
        severity: oi * 2,
        cat: "SETUP",
      });
    }

    if (lsRatio !== null && lsRatio < 0.6) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "📡 숏 과적 반등",
        desc: `L/S ${lsRatio.toFixed(2)} — 숏 커버링 가능성`,
        severity: (0.6 - lsRatio) * 150,
        cat: "SETUP",
      });
    }
    if (lsRatio !== null && lsRatio > 2.2) {
      signals.push({
        symbol: sym,
        dir: -1,
        title: "📡 롱 과적 경고",
        desc: `L/S ${lsRatio.toFixed(2)} — 롱 청산 위험`,
        severity: (lsRatio - 2.2) * 80,
        cat: "SETUP",
      });
    }

    if (capScore > 65) {
      signals.push({
        symbol: sym,
        dir: 1,
        title: "💀 청산 과열",
        desc: `청산 시그널 ${capScore.toFixed(0)}pt — 역발상 반등 가능`,
        severity: capScore * 1.2,
        cat: "TRIGGER",
      });
    }

    if ((c.stage ?? 0) >= 3) {
      signals.push({
        symbol: sym,
        dir: (c.contextScore ?? 50) >= 55 ? 1 : -1,
        title: "🎯 S3 트리플 활성",
        desc: `컨텍스트 ${(c.contextScore ?? 50).toFixed(0)}pt · 기회 ${c.score.toFixed(0)}pt · 거래량급등`,
        severity: c.score * 1.5,
        cat: "TRIGGER",
      });
    }
  });

  return signals.sort((a, b) => b.severity - a.severity).slice(0, 16);
}

export function PreSignalPanel({ candidates }: PreSignalPanelProps) {
  const signals = useMemo(() => derivePreSignals(candidates), [candidates]);

  if (signals.length === 0) return null;

  return (
    <div className="border border-white/10 rounded-xl bg-white/[0.02] backdrop-blur-xl overflow-hidden">
      <div className="px-4 py-2.5 border-b border-white/5 flex items-center gap-2">
        <div className="w-1 h-3 bg-amber-400" />
        <span className="font-mono text-[9px] tracking-[0.3em] text-slate-400 uppercase">
          Pre-Signal Radar
        </span>
        <span className="ml-auto font-mono text-[8px] tracking-[0.15em] text-slate-600">
          {signals.length} DETECTED
        </span>
      </div>

      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
        {signals.map((s, i) => (
          <div
            key={`${s.symbol}-${s.title}-${i}`}
            className={cn(
              "p-3 border rounded-md flex flex-col gap-1.5 transition-opacity hover:opacity-90",
              s.dir > 0
                ? "bg-[rgba(0,136,255,0.05)] border-[rgba(0,136,255,0.18)]"
                : "bg-[rgba(255,51,85,0.05)]  border-[rgba(255,51,85,0.18)]"
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[11px] font-black text-white/90">{s.symbol}</span>
                <span
                  className={cn(
                    "font-mono text-[10px] font-bold",
                    s.dir > 0 ? "text-[#0088ff]" : "text-[#ff3355]"
                  )}
                >
                  {s.dir > 0 ? "▲" : "▼"}
                </span>
              </div>
              <span
                className={cn(
                  "font-mono text-[7px] font-bold tracking-[0.15em] px-1.5 py-0.5 rounded-sm border",
                  s.cat === "TRIGGER"
                    ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
                    : "text-cyan-400 border-cyan-500/30 bg-cyan-500/10"
                )}
              >
                {s.cat}
              </span>
            </div>
            <div className="font-mono text-[8.5px] text-slate-300">{s.title}</div>
            <div className="text-[8px] text-slate-500 leading-snug">{s.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
