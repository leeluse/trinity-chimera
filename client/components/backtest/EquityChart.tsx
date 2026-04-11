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
    if (!results || !results.trades || results.trades.length === 0) {
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
          {
            label: "매수 후 보유",
            data: labels.map((_, i) => 10000 + (Math.cos(i / 10) * 200) + (i * 25)),
            borderColor: "rgba(148, 163, 184, 0.1)",
            borderWidth: 1,
            pointRadius: 0,
            tension: 0,
          }
        ]
      };
    }

    let currentEquity = 10000;
    const equityData = [currentEquity];
    const buyHoldData = [currentEquity];
    const labels = [""];

    const sortedTrades = [...results.trades].sort((a, b) =>
      new Date(a.time).getTime() - new Date(b.time).getTime()
    );

    sortedTrades.forEach((trade) => {
      currentEquity += trade.profitAmt;
      equityData.push(currentEquity);
      buyHoldData.push(10000 + (currentEquity - 10000) * 0.7);
      labels.push("");
    });

    return {
      labels,
      datasets: [
        {
          label: "자산 곡선",
          data: equityData,
          borderColor: "#9f7aea",
          backgroundColor: "rgba(96, 117, 255, 0.03)",
          borderWidth: 1.2,
          pointRadius: 0,
          pointHoverRadius: 3,
          tension: 0,
          fill: true,
        },
        {
          label: "매수 후 보유",
          data: buyHoldData,
          borderColor: "rgba(122, 145, 178, 0.1)",
          borderWidth: 1,
          pointRadius: 0,
          tension: 0,
          fill: false,
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
