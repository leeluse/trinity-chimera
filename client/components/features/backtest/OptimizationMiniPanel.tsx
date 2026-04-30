"use client";

import { useMemo, useState } from "react";
import { BarChart3, CalendarRange, ChevronDown, Gauge, SlidersHorizontal, Sparkles, Target } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";

type OptimizeResponse = {
  success?: boolean;
  error?: string;
  selected_params?: Array<{ name: string; current: number; min: number; max: number; step: number }>;
  tested_combos?: number;
  successful_combos?: number;
  score_weights?: Record<string, number> | null;
  best?: {
    score?: number;
    params?: Record<string, number>;
    metrics?: {
      total_return?: number;
      sharpe_ratio?: number;
      max_drawdown?: number;
      total_trades?: number;
      win_rate?: number;
      profit_factor?: number;
    };
    code?: string;
    backtest_payload?: unknown;
  };
};

interface OptimizationMiniPanelProps {
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  strategy: string;
  strategyCode: string;
  busy?: boolean;
  onApplyOptimizedCode: (code: string, payload?: unknown) => void;
}

const unsupportedTf = new Set(["1d"]);
type ObjectiveMode = "trinity" | "sharpe" | "return" | "weighted";
type SearchMethod = "grid" | "random";

type ScoreWeights = {
  total_return: number;
  sharpe_ratio: number;
  win_rate: number;
  profit_factor: number;
  trades: number;
  max_drawdown: number;
};

const objectiveTabs: Array<{ key: ObjectiveMode; label: string }> = [
  { key: "trinity", label: "Trinity" },
  { key: "sharpe", label: "Sharpe" },
  { key: "return", label: "Return" },
  { key: "weighted", label: "Weighted" },
];

const methodTabs: Array<{ key: SearchMethod; label: string }> = [
  { key: "grid", label: "Grid" },
  { key: "random", label: "Random" },
];

export default function OptimizationMiniPanel({
  symbol,
  timeframe,
  startDate,
  endDate,
  strategy,
  strategyCode,
  busy = false,
  onApplyOptimizedCode,
}: OptimizationMiniPanelProps) {
  const [paramCount, setParamCount] = useState(4);
  const [maxCombos, setMaxCombos] = useState(50);
  const [method, setMethod] = useState<SearchMethod>("grid");
  const [objective, setObjective] = useState<ObjectiveMode>("trinity");
  const [weights, setWeights] = useState<ScoreWeights>({
    total_return: 0.45,
    sharpe_ratio: 0.3,
    win_rate: 0.05,
    profit_factor: 0.05,
    trades: 0.05,
    max_drawdown: 0.1,
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizeResponse | null>(null);

  const canRun = useMemo(() => {
    if (!strategyCode.trim()) return false;
    if (!startDate || !endDate) return false;
    if (unsupportedTf.has(timeframe)) return false;
    return true;
  }, [strategyCode, startDate, endDate, timeframe]);

  const tested = result?.successful_combos ?? 0;
  const total = result?.tested_combos ?? 0;
  const successRate = total > 0 ? (tested / total) * 100 : 0;

  const runOptimize = async () => {
    if (!canRun) {
      if (unsupportedTf.has(timeframe)) {
        alert("최적화 패널은 현재 1m/5m/15m/1h/4h 타임프레임만 지원합니다.");
      } else {
        alert("전략 코드/기간을 먼저 확인해주세요.");
      }
      return;
    }

    setLoading(true);
    try {
      const res = await fetchWithBypass("/api/backtest/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          interval: timeframe,
          strategy,
          code: strategyCode,
          start_date: startDate,
          end_date: endDate,
          param_count: Math.max(1, Math.min(12, Number(paramCount) || 4)),
          max_combos: Math.max(1, Math.min(300, Number(maxCombos) || 50)),
          method,
          objective,
          score_weights: objective === "weighted" ? weights : undefined,
          top_k: 5,
        }),
      });

      const data = (await res.json()) as OptimizeResponse;
      if (!res.ok || !data?.success) {
        throw new Error(data?.error || "최적화 실패");
      }
      setResult(data);
    } catch (e) {
      alert(e instanceof Error ? e.message : "최적화 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const applyBest = () => {
    const bestCode = result?.best?.code;
    if (!bestCode) {
      alert("적용할 최적 코드가 없습니다.");
      return;
    }
    onApplyOptimizedCode(bestCode, result?.best?.backtest_payload);
  };

  const updateWeight = (key: keyof ScoreWeights, value: number) => {
    setWeights((prev) => ({
      ...prev,
      [key]: Number.isFinite(value) ? value : 0,
    }));
  };

  return (
    <div className="relative min-h-full overflow-hidden rounded-[22px] border border-white/[0.08] bg-[#070810] text-white/90 shadow-[0_18px_48px_rgba(3,6,16,0.45)]">
      <div className="pointer-events-none absolute -right-20 top-0 h-56 w-56 rounded-full bg-indigo-500/16 blur-[90px]" />
      <div className="pointer-events-none absolute -bottom-24 left-0 h-56 w-56 rounded-full bg-violet-500/12 blur-[100px]" />

      <div className="relative flex min-h-full min-h-0 flex-col">
        <header className="flex flex-nowrap items-center gap-3 border-b border-white/[0.06] px-2 py-2.5 overflow-x-auto scrollbar-hide sm:px-2.5">
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-indigo-400/25 bg-indigo-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-indigo-200">
            <SlidersHorizontal size={11} />
            Optimize
          </div>

          <div className="flex flex-nowrap items-center gap-1.5">
            <HeaderChip label={symbol} />
            <HeaderChip label={timeframe} />
            <HeaderChip label={strategy || "custom"} />
            <HeaderChip
              icon={<CalendarRange size={11} className="text-violet-300/80" />}
              label={`${startDate || "-"} -> ${endDate || "-"}`}
            />
          </div>
        </header>

        <div className="grid min-h-0 flex-1 overflow-y-auto 2xl:grid-cols-[minmax(0,1.1fr)_320px]">
          <div className="flex flex-col gap-3 px-3 py-3 sm:px-3.5 2xl:border-r 2xl:border-white/[0.06]">
            <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-[auto_auto_1fr] xl:items-start">
              <NumberField
                label="Params"
                min={1}
                max={12}
                value={paramCount}
                onChange={setParamCount}
              />
              <NumberField
                label="Combos"
                min={1}
                max={300}
                value={maxCombos}
                onChange={setMaxCombos}
              />
              <div>
                <Selector<SearchMethod>
                  label="Method"
                  options={methodTabs}
                  value={method}
                  onChange={setMethod}
                />
              </div>
            </section>

            <div className="flex flex-col gap-2.5">
              <div className="flex flex-col gap-1">
                <section className="flex flex-col gap-1 pb-2">
                  <SectionLabel
                    icon={<Target size={12} className="text-violet-300/80" />}
                    label="Scoring Objective"
                    description="Pick the score model that decides what “best” means."
                  />
                  <Segmented<ObjectiveMode>
                    label={null}
                    options={objectiveTabs}
                    value={objective}
                    onChange={setObjective}
                  />
                </section>

                {objective === "weighted" ? (
                  <section className="flex flex-col gap-2 rounded-sm border border-violet-500/18 bg-violet-500/[0.05] px-2.5 py-2.5">
                    <SectionLabel
                      icon={<Gauge size={12} className="text-violet-300/80" />}
                      label="Weight Mixer"
                      description="Each weight is normalized automatically before scoring."
                    />
                    <div className="grid gap-1.5 sm:grid-cols-2">
                      <WeightControl label="Return" value={weights.total_return} onChange={(v) => updateWeight("total_return", v)} />
                      <WeightControl label="Sharpe" value={weights.sharpe_ratio} onChange={(v) => updateWeight("sharpe_ratio", v)} />
                      <WeightControl label="Win Rate" value={weights.win_rate} onChange={(v) => updateWeight("win_rate", v)} />
                      <WeightControl label="Factor" value={weights.profit_factor} onChange={(v) => updateWeight("profit_factor", v)} />
                      <WeightControl label="Trades" value={weights.trades} onChange={(v) => updateWeight("trades", v)} />
                      <WeightControl label="MDD" value={weights.max_drawdown} onChange={(v) => updateWeight("max_drawdown", v)} />
                    </div>
                  </section>
                ) : (
                  <section className="rounded-sm border border-white/[0.06] bg-white/[0.02] px-2.5 py-1.5 text-[10px] text-slate-400">
                    {objective === "trinity" && "Balanced ranking across multiple backtest qualities."}
                    {objective === "sharpe" && "Prefers smoother return streams over raw upside."}
                    {objective === "return" && "Pure upside bias with less concern for path quality."}
                  </section>
                )}
              </div>

              <section className="flex flex-wrap items-center gap-1.5">
                <button
                  onClick={runOptimize}
                  disabled={loading || busy || !canRun}
                  className="inline-flex items-center gap-1.5 rounded-sm border border-indigo-300/35 bg-gradient-to-r from-indigo-500/24 via-violet-500/22 to-fuchsia-500/24 px-3 py-1.5 text-[11px] font-semibold text-indigo-100 transition hover:from-indigo-500/34 hover:via-violet-500/30 hover:to-fuchsia-500/34 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Sparkles size={13} className={loading ? "animate-pulse" : ""} />
                  {loading ? "최적화 실행 중" : "최적화 실행"}
                </button>

                <button
                  onClick={applyBest}
                  disabled={!result?.best?.code || loading || busy}
                  className="rounded-sm border border-white/[0.14] bg-white/[0.05] px-3 py-1.5 text-[11px] font-semibold text-slate-100 transition hover:bg-white/[0.10] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  최적 코드 적용
                </button>
              </section>
            </div>
          </div>

          <aside className="flex flex-col gap-3 px-2.5 py-2.5 sm:px-3">
            <section className="rounded-sm border border-white/[0.06] bg-white/[0.02] px-2.5 py-2.5">
              <div className="pb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 size={13} className="text-indigo-300/80" />
                  <span className="text-[11px] font-semibold text-white ">Result Monitor</span>
                </div>
                {result?.best ? (
                  <span className="text-[10px] text-indigo-100/70">{tested}/{total} · {successRate.toFixed(1)}%</span>
                ) : (
                  <span className="text-[10px] text-slate-500">Ready</span>
                )}
              </div>

              {result?.best ? (
                <div className="flex flex-col gap-3">
                  <div className="rounded-sm border border-indigo-500/18 bg-indigo-500/[0.06] px-3 py-2">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-indigo-100/65">Best Score</div>
                    <div className="mt-1 text-[15px] font-black tracking-[-0.04em] text-white">
                      {Number(result.best.score || 0).toFixed(3)}
                    </div>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-1">
                    <MetricTile label="Return" value={`${Number(result.best.metrics?.total_return || 0).toFixed(2)}%`} />
                    <MetricTile label="Sharpe" value={Number(result.best.metrics?.sharpe_ratio || 0).toFixed(2)} />
                    <MetricTile label="Win Rate" value={`${Number(result.best.metrics?.win_rate || 0).toFixed(1)}%`} />
                    <MetricTile label="Trades" value={`${Math.round(Number(result.best.metrics?.total_trades || 0))}`} />
                    <MetricTile label="Factor" value={Number(result.best.metrics?.profit_factor || 0).toFixed(2)} />
                    <MetricTile label="MDD" value={`${Number(result.best.metrics?.max_drawdown || 0).toFixed(2)}%`} />
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2 text-[11px] text-slate-400">
                  <p>현재 설정을 기준으로 파라미터 탐색을 시작할 준비가 되어 있습니다.</p>
                  <p>좌측에서 탐색 범위와 목표를 정하고 실행하면 결과가 이 영역에 표시됩니다.</p>
                </div>
              )}
            </section>

            <section className="flex-1 rounded-sm border border-white/[0.06] bg-white/[0.02] px-2 py-2">
              <div className="pb-2 text-[11px] font-semibold text-white text-slate-500">
                Best Params
              </div>

              {result?.best?.params ? (
                <div className="flex flex-nowrap gap-1 overflow-x-auto scrollbar-hide pb-0.5">
                  {Object.entries(result.best.params).map(([key, value]) => (
                    <div
                      key={key}
                      className="inline-flex items-center gap-1.5 rounded-sm border border-white/[0.06] bg-black/20 px-1.5 py-0.5"
                    >
                      <span className="text-[10px] font-medium text-slate-400">{key}</span>
                      <span className="text-[11px] font-mono font-bold text-indigo-200">
                        {String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[11px] text-slate-500">
                  실행 후 최적 파라미터가 여기에 정리됩니다.
                </div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function HeaderChip({ icon, label }: { icon?: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-sm border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
      {icon}
      <span className="truncate">{label}</span>
    </span>
  );
}

function SectionLabel({
  icon,
  label,
  description,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">{label}</span>
      </div>
      <p className="text-[10px] text-slate-500">{description}</p>
    </div>
  );
}

function NumberField({
  label,
  min,
  max,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</span>
        <span className="text-[10px] text-slate-600">{max}</span>
      </div>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="min-h-8 w-20 rounded-sm border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[12px] leading-tight text-slate-100 outline-none transition focus:border-indigo-300/45"
      />
    </div>
  );
}

function Selector<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string | null;
  options: Array<{ key: T; label: string }>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center">
        {label ? (
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</div>
        ) : null}
      </div>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as T)}
          className="min-h-8 w-full appearance-none rounded-sm border border-white/10 bg-white/[0.03] pl-2.5 pr-8 py-0.5 text-[12px] font-medium leading-tight text-slate-300 outline-none transition hover:border-white/20 focus:border-violet-400/40"
        >
          {options.map((option) => (
            <option key={option.key} value={option.key} className="bg-[#0f111a] text-slate-300">
              {option.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
          <ChevronDown size={14} />
        </div>
      </div>
    </div>
  );
}

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string | null;
  options: Array<{ key: T; label: string }>;
  value: T;
  onChange: (next: T) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center">
        {label ? (
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</div>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {options.map((option) => (
          <button
            key={option.key}
            onClick={() => onChange(option.key)}
            className={`flex min-h-8 min-w-[76px] items-center justify-center rounded-sm border px-2.5 py-1 text-[11px] font-medium leading-tight transition ${value === option.key
              ? "border-violet-400/40 bg-violet-500/14 text-violet-200 shadow-[0_0_16px_rgba(139,92,246,0.08)]"
              : "border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/20"
              }`}
          >
            <span className="block truncate">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function WeightControl({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <div className="rounded-sm border border-white/10 bg-black/20 px-2 py-1.5">
      <div className="mb-1 flex items-center justify-between text-[10px]">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-violet-200">{value.toFixed(2)}</span>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-1.5 w-full accent-violet-400"
        />
        <input
          type="number"
          min={0}
          step={0.01}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-14 rounded-md border border-white/10 bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-slate-100 outline-none focus:border-violet-300/45"
        />
      </div>
    </div>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border border-white/10 bg-black/20 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className="mt-0.5 text-[11px] font-semibold text-slate-100">{value}</div>
    </div>
  );
}
