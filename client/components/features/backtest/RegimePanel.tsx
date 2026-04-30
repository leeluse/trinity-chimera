"use client";

import { useMemo, useState, type ReactNode } from "react";
import { BarChart3, CalendarRange, Download, Flame, PlayCircle, RefreshCw } from "lucide-react";
import { fetchWithBypass } from "@/lib/api";

type RegimeBreakdown = {
  count: number;
  pct: number;
  avg_duration_bars: number;
  avg_duration_hours: number;
  num_episodes: number;
};

type RegimeRunResponse = {
  success?: boolean;
  error?: string;
  run_id?: string;
  base_dir?: string;
  logs?: string[];
  stats?: {
    total_bars?: number;
    generated_at?: string;
    symbol?: string;
    timeframe?: string;
    start_date?: string;
    end_date?: string;
    params?: Record<string, number>;
    logs?: string[];
    diagnostics?: {
      cache_hit_disk?: boolean;
      cache_path?: string;
      validation_window?: string;
      duration_sec?: number;
    };
    regimes?: Record<string, RegimeBreakdown>;
    yearly?: Record<string, Record<string, number>>;
  };
  preview_url?: string;
  download_urls?: {
    parquet?: string;
    stats?: string;
    chart?: string;
  };
};

interface RegimePanelProps {
  symbol: string;
  startDate: string;
  endDate: string;
  busy?: boolean;
}

const REGIME_ORDER = ["Bull", "Bear", "Range", "HighVol"] as const;

export default function RegimePanel({ symbol, startDate, endDate, busy = false }: RegimePanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RegimeRunResponse | null>(null);
  const [error, setError] = useState<string>("");
  const timeframe = "15m";
  const logs = result?.logs?.length ? result.logs : (result?.stats?.logs || []);

  const canRun = useMemo(() => !!symbol && !!startDate && !!endDate, [symbol, startDate, endDate]);

  const runLabeling = async () => {
    if (!canRun) {
      alert("심볼/기간을 먼저 확인해주세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetchWithBypass("/api/backtest/regime/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          timeframe,
          start_date: startDate,
          end_date: endDate,
        }),
      });
      const data = (await res.json()) as RegimeRunResponse;
      if (!res.ok || !data?.success) {
        throw new Error(data?.error || "레짐 라벨링 실행 실패");
      }
      setResult(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "레짐 라벨링 중 오류가 발생했습니다.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const refreshLast = async () => {
    if (!result?.run_id || !result?.base_dir) return;
    setLoading(true);
    setError("");
    try {
      const url = `/api/backtest/regime/result/${encodeURIComponent(result.run_id)}?out_dir=${encodeURIComponent(result.base_dir)}`;
      const res = await fetchWithBypass(url, { method: "GET" });
      const data = (await res.json()) as RegimeRunResponse;
      if (!res.ok || !data?.success) {
        throw new Error(data?.error || "최근 실행 결과 조회 실패");
      }
      setResult(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "최근 실행 결과 조회 중 오류가 발생했습니다.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-full overflow-hidden rounded-[22px] border border-white/[0.08] bg-[#070810] text-white/90 shadow-[0_18px_48px_rgba(3,6,16,0.45)]">
      <div className="pointer-events-none absolute -right-24 top-0 h-64 w-64 rounded-full bg-emerald-500/12 blur-[90px]" />
      <div className="pointer-events-none absolute -bottom-20 left-0 h-52 w-52 rounded-full bg-amber-500/10 blur-[90px]" />

      <div className="relative flex min-h-full min-h-0 flex-col">
        <header className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-3 py-2.5">
          <div className="inline-flex items-center gap-1.5 rounded-sm border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-emerald-200">
            <Flame size={11} />
            Regime
          </div>
          <MetaChip label={symbol || "BTCUSDT"} />
          <MetaChip label={timeframe} />
          <MetaChip icon={<CalendarRange size={11} className="text-amber-300/80" />} label={`${startDate || "-"} -> ${endDate || "-"}`} />
          {result?.stats?.diagnostics ? (
            <MetaChip label={result.stats.diagnostics.cache_hit_disk ? "cache: HIT" : "cache: MISS"} />
          ) : null}
          {typeof result?.stats?.diagnostics?.duration_sec === "number" ? (
            <MetaChip label={`t: ${result.stats.diagnostics.duration_sec}s`} />
          ) : null}
          {result?.run_id ? <MetaChip label={`run: ${result.run_id}`} /> : null}
        </header>

        <div className="grid min-h-0 flex-1 overflow-y-auto 2xl:grid-cols-[minmax(0,1.2fr)_330px]">
          <section className="flex min-h-0 flex-col gap-3 px-3 py-3 2xl:border-r 2xl:border-white/[0.06]">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={runLabeling}
                disabled={loading || busy || !canRun}
                className="inline-flex items-center gap-1.5 rounded-sm border border-emerald-300/35 bg-gradient-to-r from-emerald-500/25 via-lime-500/20 to-emerald-500/25 px-3 py-1.5 text-[11px] font-semibold text-emerald-100 transition hover:from-emerald-500/35 hover:via-lime-500/30 hover:to-emerald-500/35 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <PlayCircle size={13} className={loading ? "animate-pulse" : ""} />
                {loading ? "라벨링 실행 중" : "라벨링 실행"}
              </button>

              <button
                onClick={refreshLast}
                disabled={loading || !result?.run_id}
                className="inline-flex items-center gap-1.5 rounded-sm border border-white/[0.14] bg-white/[0.05] px-3 py-1.5 text-[11px] font-semibold text-slate-200 transition hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RefreshCw size={12} />
                결과 새로고침
              </button>

              {result?.download_urls?.parquet ? (
                <a className="inline-flex items-center gap-1 rounded-sm border border-white/[0.12] bg-black/20 px-2.5 py-1 text-[10px] text-slate-300 hover:bg-white/[0.08]" href={result.download_urls.parquet} target="_blank" rel="noreferrer">
                  <Download size={11} />
                  parquet
                </a>
              ) : null}
              {result?.download_urls?.stats ? (
                <a className="inline-flex items-center gap-1 rounded-sm border border-white/[0.12] bg-black/20 px-2.5 py-1 text-[10px] text-slate-300 hover:bg-white/[0.08]" href={result.download_urls.stats} target="_blank" rel="noreferrer">
                  <Download size={11} />
                  stats
                </a>
              ) : null}
              {result?.download_urls?.chart ? (
                <a className="inline-flex items-center gap-1 rounded-sm border border-white/[0.12] bg-black/20 px-2.5 py-1 text-[10px] text-slate-300 hover:bg-white/[0.08]" href={result.download_urls.chart} target="_blank" rel="noreferrer">
                  <Download size={11} />
                  chart
                </a>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-sm border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-200">{error}</div>
            ) : null}

            <div className="min-h-[440px] flex-1 rounded-sm border border-white/[0.08] bg-black/20">
              {result?.preview_url ? (
                <iframe
                  key={result.preview_url}
                  src={result.preview_url}
                  title="Regime Chart Preview"
                  className="h-full min-h-[440px] w-full rounded-sm"
                />
              ) : (
                <div className="flex h-full min-h-[440px] items-center justify-center px-4 text-center text-[12px] text-slate-500">
                  레짐 라벨링을 실행하면 차트 프리뷰가 여기에 표시됩니다.
                </div>
              )}
            </div>
          </section>

          <aside className="flex flex-col gap-3 px-3 py-3">
            <section className="rounded-sm border border-white/[0.06] bg-white/[0.02] px-2.5 py-2.5">
              <div className="pb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 size={13} className="text-emerald-300/80" />
                  <span className="text-[11px] font-semibold text-white">Regime Summary</span>
                </div>
                <span className="text-[10px] text-slate-400">{result?.stats?.total_bars ? `${result.stats.total_bars.toLocaleString()} bars` : "Ready"}</span>
              </div>
              <div className="grid gap-1.5">
                {REGIME_ORDER.map((regime) => {
                  const stat = result?.stats?.regimes?.[regime];
                  return (
                    <div key={regime} className="rounded-sm border border-white/[0.08] bg-black/25 px-2 py-1.5">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="font-semibold text-slate-300">{regime}</span>
                        <span className="font-mono text-emerald-200">{stat ? `${stat.pct}%` : "-"}</span>
                      </div>
                      <div className="mt-0.5 text-[10px] text-slate-500">
                        {stat ? `${stat.count.toLocaleString()} bars · avg ${stat.avg_duration_hours}h` : "No data"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="rounded-sm border border-white/[0.06] bg-white/[0.02] px-2.5 py-2.5">
              <div className="pb-2 text-[11px] font-semibold text-white">Yearly Mix</div>
              <div className="max-h-[260px] overflow-y-auto pr-1">
                {Object.entries(result?.stats?.yearly || {}).map(([year, row]) => (
                  <div key={year} className="mb-1.5 rounded-sm border border-white/[0.08] bg-black/20 px-2 py-1.5">
                    <div className="text-[10px] font-semibold text-slate-300">{year}</div>
                    <div className="mt-0.5 grid grid-cols-2 gap-x-2 text-[10px] text-slate-400">
                      <span>Bull {row.Bull ?? 0}%</span>
                      <span>Bear {row.Bear ?? 0}%</span>
                      <span>Range {row.Range ?? 0}%</span>
                      <span>HighVol {row.HighVol ?? 0}%</span>
                    </div>
                  </div>
                ))}
                {!Object.keys(result?.stats?.yearly || {}).length ? (
                  <div className="text-[10px] text-slate-500">실행 후 연도별 분포가 표시됩니다.</div>
                ) : null}
              </div>
            </section>

            <section className="rounded-sm border border-white/[0.06] bg-white/[0.02] px-2.5 py-2.5">
              <div className="pb-2 text-[11px] font-semibold text-white">Run Logs</div>
              <div className="max-h-[220px] overflow-y-auto rounded-sm border border-white/[0.08] bg-black/30 p-2 font-mono text-[10px] text-slate-300">
                {logs.length ? (
                  logs.map((line, idx) => (
                    <div key={`${idx}-${line}`} className="leading-5">{line}</div>
                  ))
                ) : (
                  <div className="text-slate-500">실행 후 로그가 표시됩니다.</div>
                )}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function MetaChip({ icon, label }: { icon?: ReactNode; label: string }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-sm border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-300">
      {icon}
      <span className="truncate">{label}</span>
    </span>
  );
}
