"use client";

import { useRef } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartData,
  ChartOptions
} from "chart.js";
import { Line } from "react-chartjs-2";
import { Results } from "@/types/backtest";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface EquityChartProps {
  results: Results | null;
}

export default function EquityChart({ results }: EquityChartProps) {
  const chartRef = useRef<any>(null);

  const generateData = (): ChartData<"line"> => {
    // 1. 결과가 없을 때 더미 데이터 표시
    if (!results || (!results.equityCurve && (!results.trades || results.trades.length === 0))) {
      const labels = Array.from({ length: 60 }, (_, i) => "");
      return {
        labels,
        datasets: [
          {
            label: "자산 곡선",
            data: labels.map((_, i) => 10000 + (Math.sin(i / 8) * 400) + (i * 45)),
            borderColor: "#6075ffff",
            backgroundColor: "transparent",
            borderWidth: 1,
            pointRadius: 0,
            tension: 0,
          },
        ]
      };
    }

    // 2. 엔진에서 보낸 equityCurve가 있으면 최우선으로 사용
    if (results.equityCurve && results.equityCurve.length > 0) {
      return {
        labels: results.equityCurve.map(d => {
          const date = new Date(d.time * 1000);
          return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:00`;
        }),
        datasets: [
          {
            label: "자산 곡선",
            data: results.equityCurve.map(d => 10000 * d.value),
            borderColor: "#9f7aea",
            backgroundColor: "rgba(159, 122, 234, 0.05)",
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.1,
            fill: true,
          }
        ]
      };
    }

    // 3. (Fallback) 거래 내역만 있을 때 수동 계산
    let currentEquity = 10000;
    const equityData = [currentEquity];
    const labels = ["시작"];

    const sortedTrades = [...results.trades].sort((a, b) =>
      new Date(a.time).getTime() - new Date(b.time).getTime()
    );

    sortedTrades.forEach((trade) => {
      // profitAmt가 없으면 profitPct(string)에서 파싱 시도
      const pAmt = trade.profitAmt || (parseFloat(trade.profitPct) / 100 * currentEquity) || 0;
      currentEquity += pAmt;
      equityData.push(currentEquity);
      labels.push(new Date(trade.time).toLocaleDateString());
    });

    return {
      labels,
      datasets: [
        {
          label: "자산 곡선",
          data: equityData,
          borderColor: "#9f7aea",
          backgroundColor: "rgba(159, 122, 234, 0.05)",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
          fill: true,
        }
      ]
    };
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        align: "end" as const,
        labels: {
          color: "rgba(148, 163, 184, 0.4)",
          font: { size: 9, weight: "bold" },
          usePointStyle: true,
          pointStyle: "circle",
          boxWidth: 4,
          boxHeight: 4,
          padding: 15,
        }
      },
      tooltip: {
        mode: "index",
        intersect: false,
        backgroundColor: "rgba(6, 9, 18, 0.95)",
        borderColor: "rgba(255, 255, 255, 0.05)",
        borderWidth: 1,
        titleFont: { size: 10 },
        bodyFont: { size: 11, weight: "bold" },
        padding: 10,
        callbacks: {
          label: (ctx) => `  ${ctx.dataset.label}: $${(ctx.parsed.y ?? 0).toLocaleString()}`
        }
      }
    },
    scales: {
      x: { display: false, grid: { display: false } },
      y: {
        position: "left",
        grid: { color: "rgba(255, 255, 255, 0.02)" },
        ticks: {
          color: "rgba(71, 85, 105, 0.6)",
          font: { size: 9, family: "JetBrains Mono" },
          callback: (v) => v.toLocaleString(),
          stepSize: 1000,
          padding: 8,
        },
        border: { display: false }
      }
    },
    interaction: { mode: "nearest", axis: "x", intersect: false }
  };

  return (
    <div className="w-full bg-white/[0.01] border-t border-white/[0.05] mt-2 pt-4">
      <div className="flex items-center justify-between px-2 mb-2">
        <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">자산 곡선</h3>
        {results && (
          <div className="text-[10px] font-bold text-slate-600">
            TOTAL PNL <span className="text-[#4ade80] ml-1 tracking-tighter">${results.netProfitAmt.toLocaleString()}</span>
          </div>
        )}
      </div>
      <div className="h-[200px] w-full">
        <Line data={generateData()} options={options} />
      </div>
    </div>
  );
}
