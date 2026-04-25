'use client';

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
  BotList,
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
const startDateOrigin = new Date();
startDateOrigin.setHours(startDateOrigin.getHours() - 24);

for (let i = 0; i < DAYS; i++) {
  const d = new Date(startDateOrigin);
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
    if (Math.abs(a.x - b.x) > 0.5 || Math.abs(a.y - b.y) > 0.5 || a.label !== b.label || a.value !== b.value) return false;
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

  const [btcHistory, setBtcHistory] = useState<number[]>([]);

  // 1. 실제 비트코인 히스토리 (Binance) - 지연 로딩으로 초기 렉 방지
  useEffect(() => {
    const fetchBtcData = async () => {
      try {
        const response = await fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=96');
        const klines = await response.json();
        const prices = klines.map((k: any) => parseFloat(k[4]));
        // 초기 렌더링 부하를 줄이기 위해 약간의 지연 후 세팅
        setTimeout(() => setBtcHistory(prices), 300);
      } catch (err) {
        console.error("Failed to fetch BTC history:", err);
      }
    };
    fetchBtcData();
    const interval = setInterval(fetchBtcData, 60000);
    return () => clearInterval(interval);
  }, []);

  const {
    isLoading: isLoadingInitial,
    evolutionEvents,
    decisionLogs,
    botTrades,
    bots,
    automationStatus,
    metricsData,
    dashboardProgress,
    toggleAutomation
  } = useDashboardQueries({
    enableEvolutionLogs: isEvolutionView,
    enableDecisionLogs: isLogsView,
    statsIntervalMs: 6000,
    logsIntervalMs: 8000,
  });

  // 2. 에이전트 ID 목록 (정렬하여 차트 고정)
  const runtimeAgentIds = useMemo(() => {
    let rawIds: string[] = [];
    if (bots && bots.length > 0) {
      rawIds = bots.map((b: any) => b.id);
    } else if (!dashboardProgress && !metricsData) {
      rawIds = [DEFAULT_AGENT_IDS[0]];
    } else {
      const p = (dashboardProgress?.active_agents?.length || 0) > 0 ? dashboardProgress!.active_agents! : (dashboardProgress?.agents || []);
      rawIds = p.length > 0 ? p : (Object.keys(metricsData?.agents || {}).length > 0 ? Object.keys(metricsData!.agents) : Array.from(DEFAULT_AGENT_IDS));
    }
    return [...new Set(rawIds)].sort();
  }, [bots, dashboardProgress, metricsData]);
  const runtimeAgentIdsKey = useMemo(() => runtimeAgentIds.join("|"), [runtimeAgentIds]);

  const { data: timeseriesData = {} } = useAgentTimeseries(currentMetric, runtimeAgentIds);

  const [labelPositions, setLabelPositions] = useState<LabelPosition[]>([]);
  const labelPositionsRef = useRef<LabelPosition[]>([]);

  const agentNames = useMemo(() => {
    return runtimeAgentIds.map((id, idx) => {
      const bot = bots.find((b: any) => b.id === id);
      if (bot) return bot.name;
      const m = metricsData?.agents?.[id]?.name;
      if (m && m !== id) return m;
      return NAMES[idx] || "Agent " + (idx + 1);
    });
  }, [bots, metricsData, runtimeAgentIds]);

  const chartNames = useMemo(() => [...agentNames, "BTC BnH"], [agentNames]);

  // 3. 차트 데이터셋 생성 로직 (참조 최적화)
  const buildDatasets = useCallback(() => {
    const botIds = bots.map((b: any) => b.id);
    const ids = [...runtimeAgentIds, 'BTC BnH'];
    
    return ids.map((id, i) => {
      let data: number[] = [];
      const isBT = id === "BTC BnH";
      const bot = bots.find((b: any) => b.id === id);
      const color = isBT ? "#64748b" : COLORS[i % COLORS.length];

      if (isBT) {
        if (currentMetric === "equity") data = btcHistory.length > 0 ? btcHistory : Array(DAYS).fill(77000);
        else data = btcHistory.length > 0 ? btcHistory.map(p => ((p - btcHistory[0]) / btcHistory[0]) * 100) : Array(DAYS).fill(0);
      } else {
        const ad = timeseriesData[id] || [];
        if (ad.length > 0) {
          data = ad;
        } else if (bot) {
          const s = bot.sim_state || {};
          const b = (currentMetric === "equity") ? (s.equity || 10000) : (s.total_return_pct || 0);
          data = Array(DAYS).fill(b);
        } else {
          data = Array(DAYS).fill(0);
        }
      }

      const isH = chartActiveAgent !== "ALL" && id !== chartActiveAgent && !isBT;
      const cColor = color.length > 7 ? color.substring(0, 7) : color;

      return {
        label: isBT ? "BTC BnH" : (bot?.name || NAMES[i] || "Bot"),
        data,
        borderColor: color,
        borderWidth: isBT ? 2 : 1.5,
        pointRadius: 0,
        tension: 0.4,
        fill: isBT,
        backgroundColor: (context: any) => {
          const area = context.chart.chartArea;
          if (!area) return null;
          const g = context.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
          if (isBT) { g.addColorStop(0, `${cColor}44`); g.addColorStop(1, `${cColor}00`); }
          return g;
        },
        hidden: isH,
        yAxisID: isBT ? 'y1' : 'y',
      };
    });
  }, [runtimeAgentIds, currentMetric, btcHistory, bots, timeseriesData, chartActiveAgent]);

  // [IMPORTANT] 차트 실질 데이터의 핵심 수치만 추출하여 업데이트 트리거로 활용
  const dataValueKey = useMemo(() => {
    const botValues = bots.map(b => `${b.id}:${b.sim_state?.equity || 0}:${b.sim_state?.total_return_pct || 0}`).join("|");
    const btcVal = btcHistory.length > 0 ? btcHistory[btcHistory.length - 1] : 0;
    return `${currentMetric}|${chartActiveAgent}|${botValues}|${btcVal}`;
  }, [bots, btcHistory, currentMetric, chartActiveAgent]);

  // 4. 차트 인스턴스 생성 (최초 및 ID 변경 시에만)
  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx || chartInstance.current) return;

    chartInstance.current = new Chart(ctx, {
      type: 'line',
      plugins: [{
        id: 'endLineLabels',
        afterDraw: (chart) => {
          const positions: LabelPosition[] = [];
          const metas = chart.data.datasets.map((_, i) => chart.getDatasetMeta(i));
          metas.forEach((meta) => {
            if (meta.hidden || !meta.visible) return;
            const ds = chart.data.datasets[meta.index];
            const lv = (ds.data as number[]).slice(-1)[0];
            const lp = meta.data[meta.data.length - 1];
            if (lp && lv !== undefined) {
              positions.push({ x: lp.x, y: lp.y, label: String(ds.label ?? ""), color: String(ds.borderColor || ""), value: lv, avatar: (ds.label?.charAt(0) || "?") });
            }
          });
          if (!areLabelPositionsEqual(labelPositionsRef.current, positions)) {
            labelPositionsRef.current = positions;
            setLabelPositions(positions);
          }
        }
      }],
      data: { labels, datasets: buildDatasets() },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 600 },
        layout: { padding: { right: 40, left: 10 } },
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(6,9,18,0.95)', padding: 12 } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10 } }, max: labels.length - 1 },
          y: { position: 'left', grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#475569', font: { size: 10 } } },
          y1: { position: 'right', grid: { display: false }, ticks: { color: '#475569', font: { size: 10 } } }
        }
      }
    });

    return () => {
      chartInstance.current?.destroy();
      chartInstance.current = null;
    };
  }, [runtimeAgentIdsKey]); // IDs가 바뀌면 어쩔 수 없이 재생성

  // 5. 지표 변화 체크를 통한 실질 업데이트 (버벅거림 해결의 핵심)
  useEffect(() => {
    if (chartInstance.current) {
      const newDs = buildDatasets();
      chartInstance.current.data.datasets = newDs;
      chartInstance.current.update('default');
    }
  }, [dataValueKey]); // 단순 API 성공이 아니라 '수치'가 바뀌었을 때만 업데이트

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
            botTrades={botTrades}
            automationStatus={automationStatus}
            onToggleAutomation={toggleAutomation}
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

              <div className="mt-2">
                <BotList bots={bots} />
              </div>

              <div className="flex flex-col min-h-0 gap-3 mt-2">
                <ChartLegend names={chartNames} />
                <PerformanceChart chartRef={chartRef} labelPositions={labelPositions} currentMetric={currentMetric} />
              </div>
            </div>
          </div>
        </PageLayout.Main>
      </PageLayout>
    </>
  );
}
