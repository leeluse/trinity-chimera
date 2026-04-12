"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { useEffect, useRef, useState } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";
import { APIClient, DashboardMetrics, DashboardProgress, EvolutionLogEvent } from "../lib/api";

// Centralized Components Import
import {
  PageLayout,
  PageHeader,
  MetricSelector,
  AgentsList,
  ChartLegend,
  PerformanceChart,
  DashboardRightPanel
} from "@/components";

// Externalized Constants/Types/Styles
import { COLORS, NAMES } from "@/constants";
import { MetricKey } from "@/types";

const DAYS = 96;
const labels: string[] = [];
const startDate = new Date('2026-01-01');
for (let i = 0; i < DAYS; i++) {
  const d = new Date(startDate);
  d.setDate(d.getDate() + i);
  labels.push(d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
}
for (let i = 0; i < 5; i++) {
  labels.push("");
}

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState<MetricKey>("score");
  // Separate states for Chart and Log filtering
  const [chartActiveAgent, setChartActiveAgent] = useState("ALL");
  const [logActiveAgent, setLogActiveAgent] = useState("ALL");
  const [dashboardProgress, setDashboardProgress] = useState<DashboardProgress | null>(null);
  const [metricsData, setMetricsData] = useState<DashboardMetrics | null>(null);
  const [evolutionEvents, setEvolutionEvents] = useState<EvolutionLogEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoopRunning, setIsLoopRunning] = useState(false);
  const [loopNotice, setLoopNotice] = useState("");
  const [labelPositions, setLabelPositions] = useState<any[]>([]);
  const labelPositionsRef = useRef<any[]>([]);
  const [agentNames, setAgentNames] = useState<string[]>(NAMES);

  useEffect(() => {
    const loadDashboardData = async (silent = false) => {
      try {
        if (!silent) setIsLoading(true);
        const [progress, metrics, events] = await Promise.all([
          APIClient.getDashboardProgress(),
          APIClient.getDashboardMetrics(),
          APIClient.getEvolutionLog(220),
        ]);

        setDashboardProgress(progress);
        setMetricsData(metrics);
        setEvolutionEvents(events);

        // Update names from DB
        const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];
        const newNames = ids.map(id => metrics.agents[id]?.name || NAMES[ids.indexOf(id)]);
        newNames.push("BTC BnH"); // Benchmark always stays
        setAgentNames(newNames);

      } catch (error) {
        console.error('대시보드 데이터 로드 실패:', error);
      } finally {
        if (!silent) setIsLoading(false);
      }
    };

    loadDashboardData(false);
    const pollTimer = window.setInterval(() => {
      loadDashboardData(true);
    }, 4000);

    return () => {
      window.clearInterval(pollTimer);
    };
  }, []);

  useEffect(() => {
    if (!loopNotice) return;
    const clearTimer = window.setTimeout(() => setLoopNotice(""), 7000);
    return () => window.clearTimeout(clearTimer);
  }, [loopNotice]);

  const handleRunLoop = async () => {
    try {
      setIsLoopRunning(true);
      const result = await APIClient.runEvolutionLoop();
      setLoopNotice(`ITER #${result.iteration} · ${result.queued_agents.length} agents`);
      const [progress, events] = await Promise.all([
        APIClient.getDashboardProgress(),
        APIClient.getEvolutionLog(220),
      ]);
      setDashboardProgress(progress);
      setEvolutionEvents(events);
    } catch (error) {
      console.error("Run loop 실행 실패:", error);
      setLoopNotice("Run loop 실패");
    } finally {
      setIsLoopRunning(false);
    }
  };

  const buildDynamicDatasets = (metric: MetricKey, names: string[]) => {
    const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent', 'BTC BnH'];
    const metricFieldMap: Record<
      MetricKey,
      "current_score" | "current_return" | "current_sharpe" | "current_mdd" | "current_win_rate"
    > = {
      score: "current_score",
      return: "current_return",
      sharpe: "current_sharpe",
      mdd: "current_mdd",
      win: "current_win_rate",
    };

    return ids.map((id, i) => {
      let data: number[] = [];

      if (id === "BTC BnH") {
        // Benchmark data - currently we use a flat line or simulated trend as benchmark
        // In a real scenario, this would be fetched from a benchmark API
        data = Array(DAYS).fill(100).map((v, idx) => v + (idx * 0.1));
      } else if (metricsData?.agents[id]) {
        // Map API current value to a flat line for the chart
        // until getAgentTimeseries is fully integrated into the dashboard loop
        const metricField = metricFieldMap[metric];
        const agentMetrics = metricsData.agents[id as keyof typeof metricsData.agents];
        const currentVal = agentMetrics?.[metricField] ?? 0;
        data = Array(DAYS).fill(currentVal || 0);
      } else {
        data = Array(DAYS).fill(0);
      }

      const isHidden = chartActiveAgent !== "ALL" && id !== chartActiveAgent && i !== 4;

      return {
        label: names[i] || NAMES[i],
        data,
        borderColor: COLORS[i],
        backgroundColor: 'transparent',
        borderWidth: i === 0 ? 1.4 : (i === 4 ? 0.8 : 1),
        pointRadius: 0,
        tension: 0.42,
        fill: false,
        borderDash: i === 3 ? [5, 4] : (i === 4 ? [1, 5] : []),
        hidden: isHidden
      };
    });
  };

  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;
    chartInstance.current = new Chart(ctx, {
      type: 'line',
      plugins: [{
        id: 'endLineLabels',
        afterDraw: (chart) => {
          const positions: any[] = [];
          const metas = chart.data.datasets.map((_, i) => chart.getDatasetMeta(i));
          metas.forEach((meta) => {
            if (meta.hidden || !meta.visible) return;
            const lastPoint = meta.data[meta.data.length - 1];
            if (lastPoint) {
              const dataset = chart.data.datasets[meta.index];
              const lastValue = dataset.data[dataset.data.length - 1] as number;
              const avatar = dataset.label?.charAt(0) || "?";

              positions.push({
                x: lastPoint.x, y: lastPoint.y, label: dataset.label,
                color: dataset.borderColor, value: lastValue, avatar
              });
            }
          });
          if (JSON.stringify(labelPositionsRef.current) !== JSON.stringify(positions)) {
            labelPositionsRef.current = positions;
            setLabelPositions(positions);
          }
        }
      }],
      data: { labels, datasets: buildDynamicDatasets(currentMetric, agentNames) },
      options: {
        responsive: true, maintainAspectRatio: false,
        layout: { padding: { right: 20, left: 10 } },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(6,9,18,0.95)',
            padding: 12,
            callbacks: {
              title: items => `📅 ${items[0].label}`,
              label: item => ` ${item.dataset.label}: ${Number(item.raw).toFixed(1)}`
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10 } }, max: labels.length - 1 },
          y: { grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#475569', font: { size: 10 } } }
        }
      }
    });
    return () => chartInstance.current?.destroy();
  }, [agentNames]);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = buildDynamicDatasets(currentMetric, agentNames);
      chartInstance.current.update();
    }
  }, [currentMetric, agentNames, chartActiveAgent, metricsData]);

  return (
    <>
      <Head>
        <title>Trinity AI Trading Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </Head>

      <PageLayout>
        <PageLayout.Side>
          <DashboardRightPanel
            activeAgent={logActiveAgent}
            setActiveAgent={setLogActiveAgent}
            names={agentNames}
            metricsData={metricsData ?? undefined}
            progress={dashboardProgress ?? undefined}
            evolutionEvents={evolutionEvents}
            isLoopRunning={isLoopRunning}
          />
        </PageLayout.Side>

        <PageLayout.Main>
          <PageHeader
            isLoading={isLoading}
            statusText={dashboardProgress ? `${dashboardProgress.active_improvements}개 개선 진행` : 'System Live'}
            statusColor={(dashboardProgress?.active_improvements || 0) > 0 || isLoopRunning ? "blue" : "green"}
            extra={
              <div className="flex items-center gap-2">
                {loopNotice && (
                  <span className="hidden sm:inline-flex rounded-full border border-[#244c8c]/50 bg-[#102340]/50 px-3 py-1 text-[10px] font-bold tracking-[0.12em] text-[#8fb6ff]">
                    {loopNotice}
                  </span>
                )}
                <button
                  onClick={handleRunLoop}
                  disabled={isLoopRunning}
                  className={`rounded-xl border px-3 py-1.5 text-[10px] font-black tracking-[0.16em] transition-all ${
                    isLoopRunning
                      ? "cursor-not-allowed border-[#2b4e87]/40 bg-[#13284a]/45 text-[#5c84c2]"
                      : "border-[#6f4fff]/35 bg-[#2a1f56]/60 text-[#c7b6ff] hover:border-[#7f65ff]/70 hover:bg-[#34256d]/70"
                  }`}
                >
                  {isLoopRunning ? "LOOPING..." : "RUN LOOP"}
                </button>
              </div>
            }
          />

          <div className="relative px-6 py-2">
            <div className="flex flex-col gap-4 relative z-10">
              <MetricSelector currentMetric={currentMetric} setCurrentMetric={setCurrentMetric} />

              <AgentsList
                activeAgent={chartActiveAgent}
                setActiveAgent={setChartActiveAgent}
                names={agentNames}
                metrics={metricsData?.agents}
              />

              <div className="flex flex-col min-h-0 gap-3 mt-2">
                <ChartLegend names={agentNames} />
                <PerformanceChart
                  chartRef={chartRef}
                  labelPositions={labelPositions}
                  currentMetric={currentMetric}
                />
              </div>
            </div>
          </div>
        </PageLayout.Main>
      </PageLayout>
    </>
  );
}
