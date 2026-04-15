"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { useEffect, useRef, useState, useMemo } from "react";
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

const DAYS = 96; // 96 intervals of 15 minutes = 24 hours
const labels: string[] = [];
// Assuming a starting time, e.g., midnight
const startDate = new Date('2026-04-13T00:00:00');
for (let i = 0; i < DAYS; i++) {
  const d = new Date(startDate);
  d.setMinutes(d.getMinutes() + i * 15);
  labels.push(d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }));
}
for (let i = 0; i < 5; i++) {
  labels.push("");
}

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState<MetricKey>("score");
  const [chartActiveAgent, setChartActiveAgent] = useState("ALL");
  const [logActiveAgent, setLogActiveAgent] = useState("ALL");

  // React Query 대체 상태 및 로딩
  const [dashboardProgress, setDashboardProgress] = useState<DashboardProgress | null>(null);
  const [metricsData, setMetricsData] = useState<DashboardMetrics | null>(null);
  const [evolutionEvents, setEvolutionEvents] = useState<EvolutionLogEvent[]>([]);
  const [automationStatus, setAutomationStatus] = useState<{enabled: boolean, status: string} | null>(null);
  const [timeseriesData, setTimeseriesData] = useState<Record<string, number[]>>({});
  
  const [isLoadingProgress, setIsLoadingProgress] = useState(true);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(true);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);

  // 데이터 fetch 로직
  const fetchAllData = async () => {
    try {
      const [prog, met, logs, auto] = await Promise.all([
        APIClient.getDashboardProgress(),
        APIClient.getDashboardMetrics(),
        APIClient.getEvolutionLog(220),
        APIClient.getAutomationStatus()
      ]);
      setDashboardProgress(prog);
      setMetricsData(met);
      setEvolutionEvents(logs);
      setAutomationStatus(auto);
      setIsLoadingProgress(false);
      setIsLoadingMetrics(false);
      setIsLoadingEvents(false);
    } catch (e) {
      console.error("Data fetch error:", e);
    }
  };

  const fetchTimeseries = async (metric: MetricKey) => {
    const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];
    const results: Record<string, number[]> = {};
    await Promise.all(ids.map(async (id) => {
      try {
        results[id] = await APIClient.getAgentTimeseries(id, metric);
      } catch (e) {
        results[id] = [];
      }
    }));
    setTimeseriesData(results);
  };

  // 폴링 설정
  useEffect(() => {
    fetchAllData();
    fetchTimeseries(currentMetric);

    const mainInterval = setInterval(fetchAllData, 4000);
    const tsInterval = setInterval(() => fetchTimeseries(currentMetric), 4000);

    return () => {
      clearInterval(mainInterval);
      clearInterval(tsInterval);
    };
  }, [currentMetric]);

  const isLoading = isLoadingProgress || isLoadingMetrics || isLoadingEvents;
  const [isLoopRunning, setIsLoopRunning] = useState(false);
  const [loopNotice, setLoopNotice] = useState("");
  const [labelPositions, setLabelPositions] = useState<any[]>([]);
  const labelPositionsRef = useRef<any[]>([]);

  const metricsDataSignature = JSON.stringify(metricsData?.agents);
  const timeseriesSignature = JSON.stringify(timeseriesData);

  const agentNames = useMemo(() => {
    const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];
    const newNames = ids.map(id => metricsData?.agents[id]?.name || NAMES[ids.indexOf(id)]);
    newNames.push("BTC BnH"); // Benchmark always stays
    return newNames;
  }, [metricsDataSignature]);

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
      // 즉시 새로고침
      await fetchAllData();
    } catch (error) {
      console.error("Run loop 실행 실패:", error);
      setLoopNotice("Run loop 실패");
    } finally {
      setIsLoopRunning(false);
    }
  };

  const handleToggleAutomation = async () => {
    try {
      const current = automationStatus?.enabled ?? false;
      await APIClient.setAutomationStatus(!current);
      const newStatus = await APIClient.getAutomationStatus();
      setAutomationStatus(newStatus);
    } catch (error) {
      console.error("자동화 상태 변경 실패:", error);
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
        let base = 50, step = 0.2;
        if (metric === "return") { base = 0.05; step = 0.001; }
        else if (metric === "sharpe") { base = 0.5; step = 0.002; }
        else if (metric === "mdd") { base = -0.15; step = 0; }
        else if (metric === "win") { base = 0.5; step = 0.001; }
        data = Array(DAYS).fill(base).map((v, idx) => v + (idx * step));
      } else if (metricsData?.agents[id]) {
        // Map API timeseries value
        const metricField = metricFieldMap[metric];
        const agentMetrics = metricsData.agents[id as keyof typeof metricsData.agents];
        const currentVal = agentMetrics?.[metricField] ?? 0;
        
        if (timeseriesData && timeseriesData[id] && timeseriesData[id].length > 0) {
           const history = timeseriesData[id];
           if (history.length >= DAYS) {
             data = history.slice(-DAYS);
           } else {
             // Pad beginning with first value or 0 if shorter than DAYS
             const padding = Array(DAYS - history.length).fill(history[0] || 0);
             data = [...padding, ...history];
           }
        } else {
           data = Array(DAYS).fill(currentVal || 0);
        }
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
      chartInstance.current.update('none'); // Update without animation to prevent bounce on tick
    }
  }, [currentMetric, agentNames, chartActiveAgent, metricsDataSignature, timeseriesSignature]);

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
            automationEnabled={automationStatus?.enabled ?? false}
            onToggleAutomation={handleToggleAutomation}
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
