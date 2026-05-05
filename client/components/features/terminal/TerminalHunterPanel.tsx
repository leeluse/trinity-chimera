"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { useTerminalStore, type TerminalResult } from "./terminalStore";

type HunterTab = "lb" | "rg" | "pre";

type PreSignalType = "oiBuild" | "cvdCons" | "fundExt" | "absorption" | "cross" | "whale";

interface DerivedSignal {
  type: PreSignalType;
  dir: -1 | 1;
  score: number;
  title: string;
  desc: string;
}

interface HunterDerivedRow {
  symbol: string;
  total: number;
  stage: 0 | 1 | 2 | 3;
  dir: -1 | 0 | 1;
  latchRatio: number;
  regimeMult: number;
  setupCount: number;
  alpha: number;
  pricePct: number;
  fr: number;
  oiChangePct: number;
  cvd: number;
  surge: number;
  signals: DerivedSignal[];
}

interface PreSignalCard {
  symbol: string;
  dir: -1 | 1;
  type: PreSignalType;
  title: string;
  desc: string;
  score: number;
}

interface RegimeSummary {
  ready: boolean;
  btcAltDelta: number;
  avgFunding: number;
  oiExpansionRate: number;
  longFlowRatio: number;
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function signOf(n: number): -1 | 0 | 1 {
  if (n > 0) return 1;
  if (n < 0) return -1;
  return 0;
}

function getRegimeMultiplier(dir: -1 | 0 | 1, regime: RegimeSummary): number {
  if (!regime.ready || dir === 0) return 1;
  let mult = 1;

  if (dir > 0) {
    if (regime.btcAltDelta > 1.0) mult *= 1.3;
    else if (regime.btcAltDelta < -1.0) mult *= 0.5;

    if (regime.avgFunding > 0.03) mult *= 0.6;
    else if (regime.avgFunding < -0.03) mult *= 1.4;
  } else {
    if (regime.btcAltDelta < -1.0) mult *= 1.3;
    else if (regime.btcAltDelta > 1.0) mult *= 0.5;

    if (regime.avgFunding < -0.03) mult *= 0.6;
    else if (regime.avgFunding > 0.03) mult *= 1.4;
  }

  return clamp(mult, 0.3, 2.0);
}

function deriveHunterFromResult(r: TerminalResult, regime: RegimeSummary): HunterDerivedRow {
  const signals: DerivedSignal[] = [];

  const cvdScore = Number(r.cvdScore || 0);
  const flowScore = Number(r.flowScore || 0);
  const obScore = Number(r.layers?.ob?.score ?? 0);
  const liqScore = Number(r.realLiqScore || 0);
  const momScore = Number(r.momScore || 0);
  const surgeScore = Number(r.surgeScore || 0);
  const fr = Number(r.fr || 0);

  let oiBuild = 0;
  if (Math.abs(r.oiChangePct) >= 1.5 && Math.abs(r.pricePct) <= 1.0) {
    const cvdTrend = Number(r.layers?.cvd?.cvdTrend ?? 0);
    const dirSeed =
      cvdTrend !== 0
        ? cvdTrend
        : cvdScore !== 0
          ? cvdScore
          : flowScore !== 0
            ? flowScore
            : r.pricePct;
    const dir = signOf(dirSeed);
    if (dir !== 0) {
      oiBuild = dir * 30;
      signals.push({
        type: "oiBuild",
        dir,
        score: oiBuild,
        title: "OI 빌드업",
        desc: `OI ${r.oiChangePct > 0 ? "+" : ""}${r.oiChangePct.toFixed(2)}% · 가격 횡보`,
      });
    }
  }

  let cvdCons = 0;
  if (Math.abs(cvdScore) >= 8 && Math.abs(flowScore) >= 10 && signOf(cvdScore) === signOf(flowScore)) {
    const dir = signOf(cvdScore);
    cvdCons = dir * 25;
    signals.push({
      type: "cvdCons",
      dir,
      score: cvdCons,
      title: "CVD 합의",
      desc: `CVD ${cvdScore > 0 ? "+" : ""}${cvdScore} · Flow ${flowScore > 0 ? "+" : ""}${flowScore}`,
    });
  }

  let funding = 0;
  if (fr <= -0.08) funding = 25;
  else if (fr <= -0.05) funding = 15;
  else if (fr >= 0.08) funding = -25;
  else if (fr >= 0.05) funding = -15;

  if (funding !== 0) {
    const dir = signOf(funding) as -1 | 1;
    signals.push({
      type: "fundExt",
      dir,
      score: funding,
      title: "펀딩 극단",
      desc: `FR ${fr > 0 ? "+" : ""}${fr.toFixed(4)}%`,
    });
  }

  let spoof = 0;
  if (Math.abs(obScore) >= 8) spoof = signOf(obScore) * 20;
  else if (Math.abs(obScore) >= 4) spoof = signOf(obScore) * 10;

  let absorption = 0;
  if (Boolean(r.layers?.cvd?.absorption)) {
    const dir = signOf(cvdScore || flowScore || r.pricePct);
    if (dir !== 0) {
      absorption = dir * 25;
      signals.push({
        type: "absorption",
        dir,
        score: absorption,
        title: "흡수 시그널",
        desc: "가격-체결 괴리 기반 흡수 감지",
      });
    }
  }

  let cross = 0;
  if (spoof !== 0 && absorption !== 0 && signOf(spoof) === signOf(absorption)) {
    cross = signOf(spoof) * 30;
    signals.push({
      type: "cross",
      dir: signOf(cross) as -1 | 1,
      score: cross,
      title: "크로스 트리거",
      desc: "스푸핑 + 흡수 동방향",
    });
  }

  let whale = 0;
  if (Math.abs(surgeScore) >= 13) whale = signOf(surgeScore) * 20;
  else if (Math.abs(surgeScore) >= 8) whale = signOf(surgeScore) * 10;

  if (whale !== 0) {
    signals.push({
      type: "whale",
      dir: signOf(whale) as -1 | 1,
      score: whale,
      title: "고래 유동성",
      desc: `Surge ${surgeScore > 0 ? "+" : ""}${surgeScore}`,
    });
  }

  let tick = 0;
  if (Math.abs(momScore) >= 25) tick = signOf(momScore) * 40;
  else if (Math.abs(momScore) >= 18) tick = signOf(momScore) * 30;
  else if (Math.abs(momScore) >= 12) tick = signOf(momScore) * 20;
  else if (Math.abs(momScore) >= 7) tick = signOf(momScore) * 10;

  let liq = 0;
  if (Math.abs(liqScore) >= 10) liq = signOf(liqScore) * 20;
  else if (Math.abs(liqScore) >= 6) liq = signOf(liqScore) * 10;

  let imb = 0;
  if (obScore >= 8) imb = 15;
  else if (obScore >= 4) imb = 10;
  else if (obScore <= -8) imb = -15;
  else if (obScore <= -4) imb = -10;

  const setupRaw = oiBuild + cvdCons + funding;
  const triggerRaw = spoof + absorption + cross + whale;
  const momentumRaw = tick + liq;

  const bullSetup = [oiBuild, cvdCons, funding].filter((v) => v > 0).length;
  const bearSetup = [oiBuild, cvdCons, funding].filter((v) => v < 0).length;
  const setupCount = Math.max(bullSetup, bearSetup);
  const setupActive = setupCount >= 1;

  const hasTrigger = Math.abs(triggerRaw) > 5;
  const hasMomentum = Math.abs(momentumRaw) > 10;

  let stage: 0 | 1 | 2 | 3 = 0;
  if (setupActive) {
    stage = 1;
    if (hasTrigger) {
      stage = 2;
      if (hasMomentum) stage = 3;
    }
  }

  let triggerMult = 0.3;
  let momentumMult = 0.3;
  if (setupCount >= 2) {
    triggerMult = 1.0;
    momentumMult = stage >= 2 ? 1.3 : 0.7;
  } else if (setupCount === 1) {
    triggerMult = 0.7;
    momentumMult = stage >= 2 ? 1.0 : 0.5;
  }

  const raw = setupRaw + triggerRaw * triggerMult + momentumRaw * momentumMult + imb;
  const dir = signOf(raw);
  const regimeMult = getRegimeMultiplier(dir, regime);
  const total = clamp(Math.round(raw * regimeMult), -180, 180);

  const latchRatio =
    stage === 0 ? 0 : clamp(0.25 + Math.abs(total) / 140, 0.25, 1);

  return {
    symbol: r.symbol,
    total,
    stage,
    dir,
    latchRatio,
    regimeMult,
    setupCount,
    alpha: r.alphaScore,
    pricePct: r.pricePct,
    fr: r.fr,
    oiChangePct: r.oiChangePct,
    cvd: r.cvdScore,
    surge: r.surgeScore,
    signals,
  };
}

function stageLabel(row: HunterDerivedRow) {
  const score = `${row.total > 0 ? "+" : ""}${row.total}`;
  if (row.stage === 0) return `S0 미확인 ${score}`;
  if (row.stage === 1) return `S1 대기 ${score}`;
  if (row.stage === 2) return `${row.dir > 0 ? "▲" : "▼"} S2 진입 ${score}`;
  return `${row.dir > 0 ? "▲▲" : "▼▼"} S3 확신 ${score}`;
}

function stageClass(row: HunterDerivedRow) {
  if (row.stage === 3) return row.dir > 0 ? "text-cyan-300" : "text-rose-300";
  if (row.stage === 2) return row.dir > 0 ? "text-blue-300" : "text-rose-300";
  if (row.stage === 1) return "text-amber-300";
  return "text-slate-500";
}

export default function TerminalHunterPanel() {
  const { results, setSelectedSymbol } = useTerminalStore();
  const [tab, setTab] = useState<HunterTab>("lb");

  const computed = useMemo(() => {
    if (!results.length) {
      return {
        summary: { snipers: 0, s2plus: 0, s1: 0, bias: "—", pre: 0 },
        rows: [] as HunterDerivedRow[],
        preSignals: [] as PreSignalCard[],
        regime: {
          ready: false,
          btcAltDelta: 0,
          avgFunding: 0,
          oiExpansionRate: 0,
          longFlowRatio: 50,
        } satisfies RegimeSummary,
      };
    }

    const btc = results.find((r) => r.symbol === "BTCUSDT");
    const alts = results.filter((r) => r.symbol !== "BTCUSDT");

    const btcPricePct = btc?.pricePct ?? 0;
    const avgAltPricePct = alts.length
      ? alts.reduce((s, r) => s + r.pricePct, 0) / alts.length
      : 0;

    const avgFunding =
      results.reduce((s, r) => s + r.fr, 0) / Math.max(1, results.length);

    const oiExpansionRate =
      (results.filter((r) => r.oiChangePct > 0.5).length / Math.max(1, results.length)) *
      100;

    const posFlow = results
      .filter((r) => r.flowScore > 0)
      .reduce((s, r) => s + Math.abs(r.flowScore), 0);
    const negFlow = results
      .filter((r) => r.flowScore < 0)
      .reduce((s, r) => s + Math.abs(r.flowScore), 0);
    const longFlowRatio = (posFlow / Math.max(1, posFlow + negFlow)) * 100;

    const regime: RegimeSummary = {
      ready: results.length >= 5,
      btcAltDelta: avgAltPricePct - btcPricePct,
      avgFunding,
      oiExpansionRate,
      longFlowRatio,
    };

    const rows = results
      .map((r) => deriveHunterFromResult(r, regime))
      .sort((a, b) => b.stage - a.stage || Math.abs(b.total) - Math.abs(a.total));

    const preSignals: PreSignalCard[] = [];
    rows.slice(0, 20).forEach((row) => {
      row.signals
        .filter((s) => ["oiBuild", "cvdCons", "fundExt", "absorption", "cross"].includes(s.type))
        .forEach((s) => {
          preSignals.push({
            symbol: row.symbol,
            dir: s.dir,
            type: s.type,
            title: s.title,
            desc: s.desc,
            score: s.score,
          });
        });
    });

    const s2plus = rows.filter((r) => r.stage >= 2).length;
    const s1 = rows.filter((r) => r.stage === 1).length;

    const bias =
      regime.btcAltDelta > 1
        ? "▲ ALT 강세"
        : regime.btcAltDelta < -1
          ? "▼ ALT 약세"
          : "— 중립";

    return {
      summary: {
        snipers: rows.length,
        s2plus,
        s1,
        bias,
        pre: preSignals.length,
      },
      rows,
      preSignals,
      regime,
    };
  }, [results]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/[0.06] px-4 py-3">
        <div className="text-[11px] font-black uppercase tracking-[0.2em] text-cyan-300">
          Hunter Fusion
        </div>
        <div className="mt-1 text-[10px] text-slate-500">Terminal right-panel integration preview</div>
      </div>

      <div className="grid grid-cols-2 gap-2 border-b border-white/[0.06] p-3">
        <SummaryBox label="Snipers" value={String(computed.summary.snipers)} tone="text-amber-300" />
        <SummaryBox label="S2+" value={String(computed.summary.s2plus)} tone="text-cyan-300" />
        <SummaryBox label="S1" value={String(computed.summary.s1)} tone="text-orange-300" />
        <SummaryBox label="Pre" value={String(computed.summary.pre)} tone="text-violet-300" />
      </div>

      <div className="border-b border-white/[0.06] px-3 py-2">
        <div className="text-[10px] uppercase tracking-widest text-slate-500">Bias</div>
        <div
          className={cn(
            "mt-1 text-[11px] font-bold",
            computed.summary.bias.includes("ALT 강세")
              ? "text-cyan-300"
              : computed.summary.bias.includes("ALT 약세")
                ? "text-rose-300"
                : "text-slate-300",
          )}
        >
          {computed.summary.bias}
        </div>
      </div>

      <div className="flex border-b border-white/[0.06] px-2 py-2">
        <TabButton active={tab === "lb"} onClick={() => setTab("lb")}>
          리더보드
        </TabButton>
        <TabButton active={tab === "rg"} onClick={() => setTab("rg")}>
          레짐
        </TabButton>
        <TabButton active={tab === "pre"} onClick={() => setTab("pre")}>
          선행
        </TabButton>
      </div>

      <div className="flex-1 overflow-y-auto no-scrollbar p-3">
        {tab === "lb" && (
          <div className="space-y-2">
            {computed.rows.slice(0, 18).map((row, idx) => (
              <button
                key={row.symbol}
                type="button"
                onClick={() => setSelectedSymbol(row.symbol)}
                className="w-full rounded border border-white/[0.06] bg-black/30 px-2.5 py-2 text-left hover:bg-white/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-600">{idx + 1}.</span>
                    <span className="font-mono text-[12px] font-black text-slate-100">
                      {row.symbol.replace("USDT", "")}
                    </span>
                  </div>
                  <span className={cn("font-mono text-[11px] font-bold", stageClass(row))}>
                    {stageLabel(row)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 w-full rounded bg-white/[0.06]">
                  <div
                    className={cn(
                      "h-full rounded",
                      row.dir > 0 ? "bg-cyan-400/80" : row.dir < 0 ? "bg-rose-400/80" : "bg-slate-500/60",
                    )}
                    style={{ width: `${Math.round(row.latchRatio * 100)}%` }}
                  />
                </div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
                  <span>Alpha {row.alpha > 0 ? "+" : ""}{row.alpha}</span>
                  <span>RM ×{row.regimeMult.toFixed(2)}</span>
                </div>
              </button>
            ))}
            {!computed.rows.length && <EmptyText text="Hunter 데이터 대기중..." />}
          </div>
        )}

        {tab === "rg" && (
          <div className="space-y-3">
            <RegimeItem
              label="BTC vs ALT"
              value={`${computed.regime.btcAltDelta >= 0 ? "+" : ""}${computed.regime.btcAltDelta.toFixed(2)}%`}
              tone={
                computed.regime.btcAltDelta > 0.5
                  ? "text-cyan-300"
                  : computed.regime.btcAltDelta < -0.5
                    ? "text-rose-300"
                    : "text-slate-300"
              }
              barValue={clamp((computed.regime.btcAltDelta + 5) / 10, 0, 1)}
            />
            <RegimeItem
              label="평균 Funding"
              value={`${computed.regime.avgFunding >= 0 ? "+" : ""}${computed.regime.avgFunding.toFixed(4)}%`}
              tone={
                Math.abs(computed.regime.avgFunding) > 0.03
                  ? "text-amber-300"
                  : "text-slate-300"
              }
              barValue={clamp((computed.regime.avgFunding + 0.2) / 0.4, 0, 1)}
            />
            <RegimeItem
              label="OI 확장 비율"
              value={`${computed.regime.oiExpansionRate.toFixed(1)}%`}
              tone={computed.regime.oiExpansionRate > 60 ? "text-amber-300" : "text-slate-300"}
              barValue={clamp(computed.regime.oiExpansionRate / 100, 0, 1)}
            />
            <RegimeItem
              label="Long Flow"
              value={`${computed.regime.longFlowRatio.toFixed(0)}%`}
              tone={
                computed.regime.longFlowRatio > 60
                  ? "text-cyan-300"
                  : computed.regime.longFlowRatio < 40
                    ? "text-rose-300"
                    : "text-slate-300"
              }
              barValue={clamp(computed.regime.longFlowRatio / 100, 0, 1)}
            />
          </div>
        )}

        {tab === "pre" && (
          <div className="space-y-2">
            {computed.preSignals.slice(0, 24).map((p, idx) => (
              <button
                key={`${p.symbol}-${p.type}-${idx}`}
                type="button"
                onClick={() => setSelectedSymbol(p.symbol)}
                className="w-full rounded border border-white/[0.06] bg-black/30 p-2 text-left hover:bg-white/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-bold text-slate-100">
                    {p.symbol.replace("USDT", "")}
                  </span>
                  <span className={cn("text-[10px] font-bold", p.dir > 0 ? "text-cyan-300" : "text-rose-300")}>
                    {p.dir > 0 ? "▲" : "▼"} {p.score > 0 ? "+" : ""}{p.score}
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-slate-200">{p.title}</div>
                <div className="mt-0.5 text-[9px] text-slate-500">{p.desc}</div>
              </button>
            ))}
            {!computed.preSignals.length && <EmptyText text="선행 시그널 없음" />}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryBox({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="rounded border border-white/[0.06] bg-black/30 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-0.5 font-mono text-[12px] font-black", tone)}>{value}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-wider",
        active
          ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-300"
          : "border-white/[0.08] text-slate-500 hover:text-slate-300",
      )}
    >
      {children}
    </button>
  );
}

function RegimeItem({
  label,
  value,
  tone,
  barValue,
}: {
  label: string;
  value: string;
  tone: string;
  barValue: number;
}) {
  return (
    <div className="rounded border border-white/[0.06] bg-black/30 p-2">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={cn("mt-1 font-mono text-[12px] font-bold", tone)}>{value}</div>
      <div className="mt-1.5 h-1.5 rounded bg-white/[0.06]">
        <div className="h-full rounded bg-cyan-400/70" style={{ width: `${Math.round(barValue * 100)}%` }} />
      </div>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return (
    <div className="rounded border border-dashed border-white/[0.08] bg-black/20 p-3 text-center text-[10px] text-slate-500">
      {text}
    </div>
  );
}
