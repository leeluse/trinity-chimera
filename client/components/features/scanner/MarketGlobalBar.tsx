import { cn } from "@/lib/utils";
import { MarketGlobal, LiqData } from "@/app/scanner/types";

interface MarketGlobalBarProps {
  global: MarketGlobal;
  liq: LiqData;
}

function MiniStat({
  label,
  value,
  sub,
  valueColor,
}: {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 p-2.5 bg-white/5 border border-white/10 rounded-md min-w-0">
      <div className="font-mono text-[7.5px] tracking-[0.25em] text-slate-600 uppercase">{label}</div>
      <div className={cn("font-mono text-sm font-black truncate", valueColor ?? "text-slate-300")}>{value}</div>
      {sub && <div className="font-mono text-[8px] text-slate-600 truncate">{sub}</div>}
    </div>
  );
}

function fmtUsd(v: number) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return "$0";
}

export function MarketGlobalBar({ global: g, liq }: MarketGlobalBarProps) {
  const fgColor =
    g.fearGreed === null
      ? "text-slate-500"
      : g.fearGreed <= 30
      ? "text-green-400"
      : g.fearGreed >= 70
      ? "text-red-400"
      : "text-amber-400";

  const kimchiColor =
    g.btcKrwKimchi === null
      ? "text-slate-500"
      : g.btcKrwKimchi > 3
      ? "text-red-400"
      : g.btcKrwKimchi < -1
      ? "text-green-400"
      : "text-slate-300";

  const btcTxColor =
    g.btcTx === null
      ? "text-slate-500"
      : g.btcTx > 450000
      ? "text-green-400"
      : g.btcTx > 250000
      ? "text-slate-300"
      : "text-red-400";

  const feeColor =
    g.mempoolFee === null
      ? "text-slate-500"
      : g.mempoolFee > 80
      ? "text-red-400"
      : g.mempoolFee > 30
      ? "text-amber-400"
      : "text-green-400";

  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-mono text-[9px] tracking-[0.3em] text-slate-500 uppercase flex items-center gap-2">
        <div className="w-1 h-2.5 bg-cyan-400" /> Market Global
      </h3>

      <div className="grid grid-cols-2 gap-1.5">
        <MiniStat
          label="5m 숏청산"
          value={fmtUsd(liq.globalShortLiq5m)}
          sub="Short Liq"
          valueColor={liq.globalShortLiq5m > 5_000_000 ? "text-green-400" : "text-slate-300"}
        />
        <MiniStat
          label="5m 롱청산"
          value={fmtUsd(liq.globalLongLiq5m)}
          sub="Long Liq"
          valueColor={liq.globalLongLiq5m > 5_000_000 ? "text-red-400" : "text-slate-300"}
        />
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <MiniStat
          label="공포탐욕"
          value={g.fearGreed !== null ? String(g.fearGreed) : "—"}
          sub={g.fearGreedLabel}
          valueColor={fgColor}
        />
        <MiniStat
          label="USD/KRW"
          value={g.usdKrw !== null ? g.usdKrw.toLocaleString() : "—"}
          sub="환율"
          valueColor="text-cyan-400"
        />
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <MiniStat
          label="김치프리미엄"
          value={
            g.btcKrwKimchi !== null
              ? (g.btcKrwKimchi >= 0 ? "+" : "") + g.btcKrwKimchi.toFixed(2) + "%"
              : "—"
          }
          sub="BTC KRW Gap"
          valueColor={kimchiColor}
        />
        <MiniStat
          label="BTC 온체인Tx"
          value={g.btcTx !== null ? (g.btcTx / 1000).toFixed(0) + "K" : "—"}
          sub={g.btcTxLabel}
          valueColor={btcTxColor}
        />
      </div>

      <MiniStat
        label="Mempool 수수료"
        value={g.mempoolFee !== null ? `${g.mempoolFee} sat/vB` : "—"}
        sub={g.mempoolFeeLabel}
        valueColor={feeColor}
      />
    </div>
  );
}
