"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { useEffect, useRef, useState } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";
import { APIClient } from "../lib/api";

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
import { COLORS, NAMES, HINT_MAP } from "@/constants";
import { MetricKey } from "@/types";
import { ambientGlows } from "@/styles/common";

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

function simTrinityScore(retDrift: number, retNoise: number, sharpeBase: number, mddFloor: number) {
  let cumRet = 0, peakRet = 0, mdd = 0;
  return Array.from({ length: DAYS }).map(() => {
    const dailyRet = retDrift + (Math.random() - 0.46) * retNoise;
    cumRet += dailyRet;
    peakRet = Math.max(peakRet, cumRet);
    if (peakRet > 0) mdd = Math.min(mdd, (cumRet - peakRet) / peakRet);
    const sharpe = sharpeBase + (Math.random() - 0.4) * 0.3;
    const score = (cumRet * 0.40) + (sharpe * 25 * 0.35) + ((1 + Math.max(mdd, mddFloor)) * 100 * 0.25);
    return parseFloat((100 + score).toFixed(2));
  });
}

function simReturn(drift: number, noise: number) {
  let v = 0;
  return Array.from({ length: DAYS }).map(() => { v += drift + (Math.random() - 0.46) * noise; return parseFloat(v.toFixed(2)); });
}

function simSharpe(base: number, noise: number) {
  return Array.from({ length: DAYS }).map(() => parseFloat((base + (Math.random() - 0.4) * noise).toFixed(3)));
}

const metrics = {
  score: [
    simTrinityScore(2.8, 4.5, 2.41, -12.3),
    simTrinityScore(0.3, 3.2, 1.87, -8.1),
    simTrinityScore(-0.1, 2.8, 1.23, -15.2),
    simTrinityScore(-0.4, 4.5, -0.31, -24.7),
    simTrinityScore(0.05, 1.2, 1.5, -30.0),
  ],
  return: [
    simReturn(2.4, 5.5),
    simReturn(0.4, 3.8),
    simReturn(-0.1, 3.5),
    simReturn(-0.5, 5.2),
    simReturn(0.1, 1.5)
  ],
  sharpe: [
    simSharpe(2.8, 0.8),
    simSharpe(1.6, 0.6),
    simSharpe(1.1, 0.7),
    simSharpe(-0.4, 1.5),
    simSharpe(0.2, 0.9)
  ],
  mdd: [
    simReturn(-10, 5),
    simReturn(-6, 4),
    simReturn(-18, 10),
    simReturn(-28, 8),
    simReturn(-38, 12)
  ],
  win: [
    simSharpe(67, 3), simSharpe(71, 2),
    simSharpe(52, 4), simSharpe(44, 3), simSharpe(30, 5)
  ]
} as any;

function buildDatasets(metric: MetricKey) {
  return metrics[metric].map((data: number[], i: number) => ({
    label: NAMES[i], data,
    borderColor: COLORS[i],
    backgroundColor: i === 0 ? `color-mix(in srgb, ${COLORS[0]}, transparent 98%)` : 'transparent',
    borderWidth: i === 0 ? 1.4 : (i === 4 ? 0.8 : 1),
    pointRadius: 0, tension: 0.42,
    fill: i === 0,
    borderDash: i === 3 ? [5, 4] : (i === 4 ? [1, 5] : []),
    clip: false,
  }));
}

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState<MetricKey>("score");
  // Separate states for Chart and Log filtering
  const [chartActiveAgent, setChartActiveAgent] = useState("ALL");
  const [logActiveAgent, setLogActiveAgent] = useState("ALL");
  const [dashboardProgress, setDashboardProgress] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [labelPositions, setLabelPositions] = useState<any[]>([]);
  const labelPositionsRef = useRef<any[]>([]);
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);
  const [agentNames, setAgentNames] = useState<string[]>(NAMES);

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);
        const [progress, metricsData] = await Promise.all([
          APIClient.getDashboardProgress(),
          APIClient.getDashboardMetrics()
        ]);

        setDashboardProgress(progress);

        // Update names from DB
        const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent'];
        const newNames = ids.map(id => metricsData.agents[id]?.name || NAMES[ids.indexOf(id)]);
        newNames.push("BTC BnH"); // Benchmark always stays
        setAgentNames(newNames);

      } catch (error) {
        console.error('대시보드 데이터 로드 실패:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadDashboardData();
  }, []);

  const buildDynamicDatasets = (metric: MetricKey, names: string[]) => {
    const ids = ['momentum_hunter', 'mean_reverter', 'macro_trader', 'chaos_agent', 'BTC BnH'];
    return metrics[metric].map((data: number[], i: number) => {
      const id = ids[i];
      // Hide if a specific agent is selected and this isn't it, and it's not the benchmark
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
        clip: false,
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
              label: item => `  ${item.dataset.label}: ${Number(item.raw).toFixed(1)}`
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
  }, [agentNames]); // Refresh chart when names are loaded

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = buildDynamicDatasets(currentMetric, agentNames);
      chartInstance.current.update();
    }
  }, [currentMetric, agentNames, chartActiveAgent]);

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
          />
        </PageLayout.Side>

        <PageLayout.Main>
          <PageHeader
            isLoading={isLoading}
            statusText={dashboardProgress ? `${dashboardProgress.active_improvements}개 개선 진행` : 'System Live'}
          />

          <div className="relative px-6 py-2">
            <div className="flex flex-col gap-4 relative z-10">
              <MetricSelector currentMetric={currentMetric} setCurrentMetric={setCurrentMetric} />

              <AgentsList activeAgent={chartActiveAgent} setActiveAgent={setChartActiveAgent} names={agentNames} />

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