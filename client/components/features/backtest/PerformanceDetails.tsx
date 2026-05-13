"use client";

import { Results } from "@/types/backtest";

interface PerformanceDetailsProps {
  results: Results | null;
}

const fmtPct = (value: number | undefined, withSign = true) => {
  const numeric = Number(value ?? 0);
  const sign = withSign && numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
};

const fmtMoney = (value: number | undefined) => {
  const numeric = Number(value ?? 0);
  return `$${numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const valueTone = (value: number | undefined) => {
  const numeric = Number(value ?? 0);
  if (numeric > 0) return "text-violet-300";
  if (numeric < 0) return "text-pink-300";
  return "text-slate-500";
};

function MetricPair({
  leftLabel,
  leftValue,
  leftTone = "text-slate-100",
  rightLabel,
  rightValue,
  rightTone = "text-slate-100",
}: {
  leftLabel: string;
  leftValue: string;
  leftTone?: string;
  rightLabel: string;
  rightValue: string;
  rightTone?: string;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr_auto] items-end gap-x-5 gap-y-1 py-1.5">
      <div className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-600">
        {leftLabel}
      </div>
      <div className={`font-mono text-[13px] font-black tracking-tight ${leftTone}`}>{leftValue}</div>
      <div className="text-[9px] font-black uppercase tracking-[0.15em] text-slate-600">
        {rightLabel}
      </div>
      <div className={`font-mono text-[13px] font-black tracking-tight text-right ${rightTone}`}>{rightValue}</div>
    </div>
  );
}

export const PerformanceDetails = ({ results }: PerformanceDetailsProps) => {
  if (!results) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-white/[0.06] bg-[#090a12] shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
      <header className="relative border-b border-white/[0.06] bg-[#080910] px-5 py-3">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-400/20 to-transparent" />
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-violet-400/80 shadow-[0_0_8px_rgba(167,139,250,0.6)]" />
          <h3 className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-200">Performance Metrics</h3>
        </div>
      </header>

      <div className="px-5 py-4">
        <div className="space-y-1.5">
          <div className="pb-1 text-[8px] font-black uppercase tracking-[0.2em] text-violet-300/40">Returns</div>
          <MetricPair
            leftLabel="총 수익률"
            leftValue={fmtPct(results.totalReturnNum)}
            leftTone={valueTone(results.totalReturnNum)}
            rightLabel="수수료 제외"
            rightValue={fmtPct(results.grossReturnNum)}
            rightTone={valueTone(results.grossReturnNum)}
          />
          <MetricPair
            leftLabel="초과 성과"
            leftValue={fmtPct(results.alphaReturn)}
            leftTone={valueTone(results.alphaReturn)}
            rightLabel="매수 후 보유"
            rightValue={fmtPct(results.buyHoldReturn)}
            rightTone={valueTone(results.buyHoldReturn)}
          />
          <MetricPair
            leftLabel="수수료"
            leftValue={fmtMoney(results.totalFees)}
            rightLabel="예상 수익"
            rightValue={fmtPct(results.expectedReturn)}
            rightTone={valueTone(results.expectedReturn)}
          />
        </div>

        <div className="my-3 h-px bg-white/[0.06]" />

        <div className="space-y-1.5">
          <div className="pb-1 text-[8px] font-black uppercase tracking-[0.2em] text-pink-300/40">Risk</div>
          <MetricPair
            leftLabel="최대 낙폭"
            leftValue={fmtPct(results.mddPct, false)}
            leftTone="text-pink-300"
            rightLabel="샤프 비율"
            rightValue={results.sharpeRatio.toFixed(2)}
          />
          <MetricPair
            leftLabel="소르티노 비율"
            leftValue={(results.sortinoRatio ?? 0).toFixed(2)}
            rightLabel="Calmar 비율"
            rightValue={(results.calmarRatio ?? 0).toFixed(2)}
          />
        </div>
      </div>
    </section>
  );
};

export default PerformanceDetails;
