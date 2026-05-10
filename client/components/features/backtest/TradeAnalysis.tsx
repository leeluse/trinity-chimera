"use client";

import { Results } from "@/types/backtest";

interface TradeAnalysisProps {
  results: Results | null;
}

const fmtPct = (value: number | undefined, withSign = true) => {
  const numeric = Number(value ?? 0);
  const sign = withSign && numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)}%`;
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

export const TradeAnalysis = ({ results }: TradeAnalysisProps) => {
  if (!results) return null;

  const totalTrades = Math.max(0, results.totalTradesCount || 0);
  const wins = Math.max(0, results.winCount || 0);
  const losses = Math.max(0, results.lossCount || 0);
  const neutral = Math.max(0, totalTrades - wins - losses);
  const winWidth = totalTrades > 0 ? (wins / totalTrades) * 100 : 0;
  const neutralWidth = totalTrades > 0 ? (neutral / totalTrades) * 100 : 0;
  const lossWidth = totalTrades > 0 ? (losses / totalTrades) * 100 : 0;

  return (
    <section className="overflow-hidden rounded-xl border border-white/[0.06] bg-[#090a12] shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
      <header className="relative border-b border-white/[0.06] bg-[#080910] px-5 py-3">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet-400/20 to-transparent" />
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-violet-400/80 shadow-[0_0_8px_rgba(167,139,250,0.6)]" />
          <h3 className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-200">Trade Analysis</h3>
        </div>
      </header>

      <div className="px-5 py-4">
        <div className="flex items-end justify-between pb-3">
          <div className="text-[8px] font-black uppercase tracking-[0.2em] text-violet-300/40">Win Ratio</div>
          <div className="text-[10px] font-black uppercase tracking-[0.15em] text-slate-500">
            Win Rate <span className="ml-1 text-violet-200">{fmtPct(results.winRateNum)}</span>
          </div>
        </div>

        <div className="overflow-hidden rounded-sm border border-white/[0.06] bg-black/35">
          <div className="flex h-2.5 w-full">
            <div className="bg-violet-500/80 transition-all duration-1000" style={{ width: `${winWidth}%` }} />
            <div className="bg-slate-700/50 transition-all duration-1000" style={{ width: `${neutralWidth}%` }} />
            <div className="bg-pink-500/80 transition-all duration-1000" style={{ width: `${lossWidth}%` }} />
          </div>
        </div>

        <div className="flex items-center justify-between pt-2.5 pb-4 text-[9px] font-black uppercase tracking-widest text-slate-600">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-500/80" />
              <span className="text-violet-300/80">{wins}W</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-pink-500/80" />
              <span className="text-pink-300/80">{losses}L</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-700/80" />
              <span className="text-slate-500">{neutral}E</span>
            </div>
          </div>
          <div className="font-mono text-[13px] font-black text-violet-200">{totalTrades} Total</div>
        </div>

        <div className="my-3 h-px bg-white/[0.06]" />

        <MetricPair
          leftLabel="가장 큰 승리"
          leftValue={fmtPct(results.bestTradeFinal)}
          leftTone="text-violet-300"
          rightLabel="최대 손실"
          rightValue={fmtPct(results.worstTradeFinal, false)}
          rightTone="text-pink-300"
        />
        <MetricPair
          leftLabel="평균 수익"
          leftValue={fmtPct(results.avgProfitPct)}
          leftTone="text-violet-300"
          rightLabel="평균 손실"
          rightValue={fmtPct(results.avgLossPct, false)}
          rightTone="text-pink-300"
        />
        <MetricPair
          leftLabel="수익 팩터"
          leftValue={(results.profitFactor ?? 0).toFixed(2)}
          rightLabel="평균 막대"
          rightValue={(results.avgHoldBars ?? 0).toFixed(2)}
        />

        <div className="my-3 h-px bg-white/[0.06]" />

        <MetricPair
          leftLabel="최대 연속 승리"
          leftValue={String(results.maxConsecutiveWins ?? 0)}
          leftTone="text-violet-300"
          rightLabel="최대 연속 손실"
          rightValue={String(results.maxConsecutiveLosses ?? 0)}
          rightTone="text-pink-300"
        />
      </div>
    </section>
  );
};

export default TradeAnalysis;
