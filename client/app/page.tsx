"use client";

import { useEffect, useRef, useState, useMemo, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import Chart from "chart.js/auto";


// Centralized Components Import
import {
  PageLayout,
  PageHeader,
  MetricSelector,
  BotList,
  ChartLegend,
  PerformanceChart
} from "@/components";
import { AppRightPanel } from "@/components/layout/AppRightPanel";
import CrimeMainPanel from "@/components/features/crime/CrimeMainPanel";

// Externalized Constants/Types/Styles
import { COLORS, NAMES } from "@/constants";
import { useDashboardStore } from "@/store/useDashboardStore";
import { useDashboardQueries } from "@/hooks/useDashboardQueries";
import { MarketAPI } from "@/api";

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

function DashboardContent() {
  const queryClient = useQueryClient();
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const searchParams = useSearchParams();
  const view = (searchParams.get("view") ?? "").toLowerCase();
  const isCrimeView = view === "crime";
  const chartInstance = useRef<Chart | null>(null);
  const currentMetric = useDashboardStore((state) => state.currentMetric);
  const chartActiveBot = useDashboardStore((state) => state.chartActiveBot);

  const [btcHistory, setBtcHistory] = useState<number[]>([]);

  useEffect(() => {
    const fetchBtcData = async () => {
      try {
        const klines = await MarketAPI.getKlines('BTCUSDT', '15m', 96);
        const prices = klines.map((k: any) => parseFloat(k[4]));
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
    botTrades,
    bots,
    automationStatus,
    toggleAutomation
  } = useDashboardQueries({
    statsIntervalMs: 6000,
    logsIntervalMs: 8000,
  });

  const runtimeAgentIds = useMemo(() => {
    if (bots && bots.length > 0) {
      return [...new Set(bots.map((b: any) => b.id))].sort();
    }
    return [];
  }, [bots]);
  const runtimeAgentIdsKey = useMemo(() => runtimeAgentIds.join("|"), [runtimeAgentIds]);

  const [labelPositions, setLabelPositions] = useState<LabelPosition[]>([]);
  const labelPositionsRef = useRef<LabelPosition[]>([]);

  const agentNames = useMemo(() => {
    return runtimeAgentIds.map((id, idx) => {
      const bot = bots.find((b: any) => b.id === id);
      if (bot) return bot.name;
      return NAMES[idx] || "Bot " + (idx + 1);
    });
  }, [bots, runtimeAgentIds]);

  const chartNames = useMemo(() => [...agentNames, "BTC BnH"], [agentNames]);

  const buildDatasets = useCallback(() => {
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
        if (bot) {
          const s = bot.sim_state || {};
          const b = (currentMetric === "equity") ? (s.equity || 10000) : (s.total_return_pct || 0);
          data = Array(DAYS).fill(b);
        } else {
          data = Array(DAYS).fill(0);
        }
      }

      const isH = chartActiveBot !== "ALL" && id !== chartActiveBot && !isBT;
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
          if (!area || !isBT) return undefined;
          const g = context.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
          g.addColorStop(0, `${cColor}44`);
          g.addColorStop(1, `${cColor}00`);
          return g;
        },
        hidden: isH,
        yAxisID: isBT ? 'y1' : 'y',
      };
    });
  }, [runtimeAgentIds, currentMetric, btcHistory, bots, chartActiveBot]);

  const dataValueKey = useMemo(() => {
    const botValues = bots.map(b => `${b.id}:${b.sim_state?.equity || 0}:${b.sim_state?.total_return_pct || 0}`).join("|");
    const btcVal = btcHistory.length > 0 ? btcHistory[btcHistory.length - 1] : 0;
    return `${currentMetric}|${chartActiveBot}|${botValues}|${btcVal}`;
  }, [bots, btcHistory, currentMetric, chartActiveBot]);

  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx || chartInstance.current) return;

    chartInstance.current = new Chart(ctx, {
      type: 'line',
      plugins: [{
        id: 'endLineLabels',
        afterDraw: (chart: Chart) => {
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
  }, [runtimeAgentIdsKey, buildDatasets]);

  useEffect(() => {
    if (chartInstance.current) {
      const newDs = buildDatasets();
      chartInstance.current.data.datasets = newDs;
      chartInstance.current.update('none');
    }
  }, [dataValueKey, buildDatasets]);

  return (
    <PageLayout>
      <PageLayout.Side>
        <AppRightPanel
          agentIds={runtimeAgentIds}
          names={agentNames}
          botTrades={botTrades}
          automationStatus={automationStatus}
          onToggleAutomation={() => toggleAutomation(!automationStatus?.enabled)}
        />
      </PageLayout.Side>

      <PageLayout.Main>
        <PageHeader
          isLoading={isLoadingInitial}
          statusText="System Live"
          statusColor="green"
        />

        {isCrimeView ? (
          <CrimeMainPanel />
        ) : (
          <div className="relative px-6 py-2">
              <div className="flex flex-col gap-4 relative z-10">
                <MetricSelector />

                <div className="mt-2">
                  <BotList
                    bots={bots}
                    onRefresh={() => queryClient.invalidateQueries({ queryKey: ["dashboard", "bots"] })}
                  />
                </div>

                <div className="flex flex-col min-h-0 gap-3 mt-2">
                  <ChartLegend names={chartNames} />
                  <PerformanceChart chartRef={chartRef} labelPositions={labelPositions} currentMetric={currentMetric} />
                </div>
              </div>
            </div>
          </>
        )}
      </PageLayout.Main>
    </PageLayout>
  );
}

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen bg-background text-white">동기화 중...</div>}>
      <DashboardContent />
    </Suspense>
  );
}
