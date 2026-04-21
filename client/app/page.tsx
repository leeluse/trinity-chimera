"use client";

import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";
import { usePathname, useSearchParams } from "next/navigation";
import {
  AGENT_IDS as DEFAULT_AGENT_IDS
} from "../lib/api";

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
import { useDashboardStore } from "@/store/useDashboardStore";
import { useDashboardQueries, useAgentTimeseries } from "@/hooks/useDashboardQueries";

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

type LabelPosition = {
  x: number;
  y: number;
  label: string;
  color: string;
  value: number;
  avatar: string;
};

const areLabelPositionsEqual = (prev: LabelPosition[], next: LabelPosition[]) => {
  if (prev.length !== next.length) return false;
  for (let i = 0; i < prev.length; i += 1) {
    const a = prev[i];
    const b = next[i];
    if (
      a.x !== b.x ||
      a.y !== b.y ||
      a.label !== b.label ||
      a.color !== b.color ||
      a.value !== b.value ||
      a.avatar !== b.avatar
    ) {
      return false;
    }
  }
  return true;
};

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const currentMetric = useDashboardStore((state) => state.currentMetric);
  const chartActiveAgent = useDashboardStore((state) => state.chartActiveAgent);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") || "").toLowerCase();
  const isEvolutionView = pathname === "/" && view === "evolution";
  const isLogsView = pathname === "/" && (view === "" || view === "logs");

  // TanStack Query Hooks
  const {
    isLoading: isLoadingInitial,
    evolutionEvents,
    decisionLogs,
    automationStatus,
    metricsData,
    dashboardProgress,
    toggleAutomation
  } = useDashboardQueries({
    enableEvolutionLogs: isEvolutionView,
    enableDecisionLogs: isLogsView,
    statsIntervalMs: 6000,
    logsIntervalMs: 8000,
    evolutionLogLimit: 120,
    decisionLogLimit: 140,
  });

  // Runtime Agent IDs derivation
  const runtimeAgentIds = useMemo(() => {
    if (!dashboardProgress && !metricsData) return Array.from(DEFAULT_AGENT_IDS.slice(0, 1));
    const idsFromProgress = (dashboardProgress?.active_agents && dashboardProgress.active_agents.length > 0)
      ? dashboardProgress.active_agents
      : (dashboardProgress?.agents || []);
    const idsFromMetrics = Object.keys(metricsData?.agents || {});
    return idsFromProgress.length > 0
      ? idsFromProgress
      : (idsFromMetrics.length > 0 ? idsFromMetrics : Array.from(DEFAULT_AGENT_IDS));
  }, [dashboardProgress, metricsData]);
  const runtimeAgentIdsKey = useMemo(() => runtimeAgentIds.join("|"), [runtimeAgentIds]);

  const { data: timeseriesData = {} } = useAgentTimeseries(currentMetric, runtimeAgentIds, {
    refetchIntervalMs: 7000,
  });

  const [labelPositions, setLabelPositions] = useState<LabelPosition[]>([]);
  const labelPositionsRef = useRef<LabelPosition[]>([]);

  const agentNames = useMemo(() => {
    return runtimeAgentIds.map((id, idx) => {
      // 1. DB에서 가져온 실제 이름이 있는지 확인
      const realName = metricsData?.agents[id]?.name;
      if (realName && realName !== id) return realName;
      
      // 2. ID 자체가 사람이 읽기 좋은 형태인 경우 (예: Momentum Hunter)
      if (id.includes("_") || id.includes(" ")) {
        return id.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
      }
      
      // 3. 마지막 폴백: NAMES 배열의 값 (NaN)
      return NAMES[idx] || "NaN";
    });
  }, [metricsData, runtimeAgentIds]);

  const chartNames = useMemo(() => {
    return [...agentNames, "BTC BnH"];
  }, [agentNames]);

  const handleToggleAutomation = (enabled: boolean) => {
    toggleAutomation(enabled);
  };

  const buildDynamicDatasets = useCallback((metric: MetricKey, names: string[]) => {
    const ids = [...runtimeAgentIds, 'BTC BnH'];
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
      const isBenchmark = id === "BTC BnH";

      if (isBenchmark) {
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

      const isHidden = chartActiveAgent !== "ALL" && id !== chartActiveAgent && !isBenchmark;

      return {
        label: names[i] || NAMES[i],
        data,
        borderColor: COLORS[i % COLORS.length],
        backgroundColor: 'transparent',
        borderWidth: i === 0 ? 1.4 : (isBenchmark ? 0.8 : 1),
        pointRadius: 0,
        tension: 0.42,
        fill: false,
        borderDash: isBenchmark ? [1, 5] : (i === 3 ? [5, 4] : []),
        hidden: isHidden
      };
    });
  }, [runtimeAgentIds, chartActiveAgent, metricsData, timeseriesData]);

  const chartDatasets = useMemo(
    () => buildDynamicDatasets(currentMetric, chartNames),
    [buildDynamicDatasets, currentMetric, chartNames]
  );
  const chartDatasetsRef = useRef(chartDatasets);
  useEffect(() => {
    chartDatasetsRef.current = chartDatasets;
  }, [chartDatasets]);

  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;
    chartInstance.current = new Chart(ctx, {
      type: 'line',
      plugins: [{
        id: 'endLineLabels',
        afterDraw: (chart) => {
          const positions: LabelPosition[] = [];
          const metas = chart.data.datasets.map((_, i) => chart.getDatasetMeta(i));
          metas.forEach((meta) => {
            if (meta.hidden || !meta.visible) return;
            const lastPoint = meta.data[meta.data.length - 1];
            if (lastPoint) {
              const dataset = chart.data.datasets[meta.index];
              const lastValue = dataset.data[dataset.data.length - 1] as number;
              const avatar = dataset.label?.charAt(0) || "?";
              const colorValue = Array.isArray(dataset.borderColor)
                ? String(dataset.borderColor[0] ?? "")
                : String(dataset.borderColor ?? "");

              positions.push({
                x: lastPoint.x,
                y: lastPoint.y,
                label: String(dataset.label ?? ""),
                color: colorValue,
                value: lastValue,
                avatar,
              });
            }
          });
          if (!areLabelPositionsEqual(labelPositionsRef.current, positions)) {
            labelPositionsRef.current = positions;
            setLabelPositions(positions);
          }
        }
      }],
      data: { labels, datasets: chartDatasetsRef.current },
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
  }, [chartNames, runtimeAgentIdsKey]);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = chartDatasets;
      chartInstance.current.update('none'); // Update without animation to prevent bounce on tick
    }
  }, [chartDatasets]);

  return (
    <>
      <Head>
        <title>Trinity AI Trading Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </Head>

      <PageLayout>
        <PageLayout.Side>
          <DashboardRightPanel
            agentIds={runtimeAgentIds}
            names={agentNames}
            metricsData={metricsData ?? undefined}
            progress={dashboardProgress ?? undefined}
            evolutionEvents={evolutionEvents}
            decisionLogs={decisionLogs}
            automationStatus={automationStatus}
            onToggleAutomation={handleToggleAutomation}
          />
        </PageLayout.Side>

        <PageLayout.Main>
          <PageHeader
            isLoading={isLoadingInitial}
            statusText={dashboardProgress ? `${dashboardProgress.active_improvements}개 개선 진행` : 'System Live'}
            statusColor={(dashboardProgress?.active_improvements || 0) > 0 ? "blue" : "green"}
          />

          <div className="relative px-6 py-2">
            <div className="flex flex-col gap-4 relative z-10">
              <MetricSelector />

              <AgentsList
                agentIds={runtimeAgentIds}
                names={agentNames}
                metrics={metricsData?.agents}
              />

              <div className="flex flex-col min-h-0 gap-3 mt-2">
                <ChartLegend names={chartNames} />
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
