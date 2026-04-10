"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { useEffect, useRef, useState } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";
import { APIClient, AGENT_IDS } from "../lib/api";
import AgentCard from "@/components/AgentCard";
import LogCard from "@/components/LogCard";

// ─────────────────────────────────────────────────────────
// Trinity Score 합성 지수 공식
// ─────────────────────────────────────────────────────────
const DAYS = 96;
const labels: string[] = [];
const startDate = new Date('2026-01-01');
for (let i = 0; i < DAYS; i++) {
  const d = new Date(startDate);
  d.setDate(d.getDate() + i);
  labels.push(d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }));
}
// 선이 끝까지 닿지 않도록 빈 레이블 추가
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
    simTrinityScore(2.8, 4.5, 2.41, -12.3),  // Super star
    simTrinityScore(0.3, 3.2, 1.87, -8.1),
    simTrinityScore(-0.1, 2.8, 1.23, -15.2),
    simTrinityScore(-0.4, 4.5, -0.31, -24.7),
    simTrinityScore(0.05, 1.2, 1.5, -30.0),
  ],
  return: [
    simReturn(2.4, 5.5),   // Dynamic winner
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

const COLORS = [
  '#4acde2', // Sophisticated Aqua Blue (Focus)
  '#c678dd', // One Dark Purple
  '#98c379', // One Dark Green
  '#9f7aea', // Vibrant Purple (final fix)
  '#5c6370'  // One Dark Gray (Benchmark)
]; 
const NAMES = ['MINARA V2', 'ARBITER V1', 'NIM-ALPHA', 'CHIMERA-β', 'BTC BnH'];

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

const hintMap = {
  score: '수식: Return×0.4 + Sharpe×25×0.35 + (1+MDD)×100×0.25',
  return: '누적 일별 수익률 (%)',
  sharpe: '롤링 샤프지수 (일간 추정)',
  mdd: '누적 최대 낙폭 (MDD, 매일 갱신)',
  win: '누적 승률 % (일별 롤링)',
};

type MetricKey = keyof typeof hintMap;

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState<MetricKey>("score");
  const [activeTab, setActiveTab] = useState("strategy");
  const [activeAgent, setActiveAgent] = useState("전체");
  const [dashboardProgress, setDashboardProgress] = useState<any>(null);
  const [agentPerformance, setAgentPerformance] = useState<any[]>([]);
  const [timeseriesData, setTimeseriesData] = useState<{ [key: string]: number[] }>({});
  const [isLoading, setIsLoading] = useState(false);
  const [labelPositions, setLabelPositions] = useState<any[]>([]);
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);

  // API 데이터 로드
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true);

        // 대시보드 진행 상황 로드
        const progress = await APIClient.getDashboardProgress();
        setDashboardProgress(progress);

        // 에이전트별 성과 데이터 로드
        const agentIds = AGENT_IDS;
        const performancePromises = agentIds.map(id =>
          APIClient.getAgentPerformance(id).catch(() => null)
        );
        const performances = await Promise.all(performancePromises);
        setAgentPerformance(performances.filter((p: any) => p !== null));

        // 활성 에이전트의 시계열 데이터 로드
        if (activeAgent !== "전체") {
          const agentId = activeAgent;
          const metrics = ['score', 'return', 'sharpe', 'mdd', 'win'] as const;

          const timeseriesPromises = metrics.map(metric =>
            APIClient.getAgentTimeseries(agentId, metric).catch(() => [])
          );
          const timeseriesResults = await Promise.all(timeseriesPromises);

          const newTimeseriesData: { [key: string]: number[] } = {};
          metrics.forEach((metric, index) => {
            newTimeseriesData[metric] = timeseriesResults[index] || [];
          });
          setTimeseriesData(newTimeseriesData);
        }

      } catch (error) {
        console.error('대시보드 데이터 로드 실패:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, [activeAgent]);

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
          chart.data.datasets.forEach((dataset, i) => {
            const meta = chart.getDatasetMeta(i);
            if (meta.hidden) return;

            const lastPoint = meta.data[meta.data.length - 1];
            if (lastPoint) {
              const lastValue = dataset.data[dataset.data.length - 1] as number;
              const firstValue = dataset.data[0] as number;
              const change = lastValue - firstValue;
              const percentChange = firstValue !== 0 ? (change / Math.abs(firstValue)) * 100 : 0;

              positions.push({
                x: lastPoint.x,
                y: lastPoint.y,
                label: dataset.label,
                color: dataset.borderColor,
                value: lastValue,
                change: change,
                percent: percentChange,
                avatar: NAMES.indexOf(dataset.label as string) === 0 ? 'M' :
                  NAMES.indexOf(dataset.label as string) === 1 ? 'A' :
                    NAMES.indexOf(dataset.label as string) === 2 ? 'N' :
                      NAMES.indexOf(dataset.label as string) === 3 ? 'C' : 'B'
              });
            }
          });
          // State update in plugin is tricky with React, so we use a ref to prevent loops
          // Alternatively, just update the state if it's actually different
          if (JSON.stringify(positions) !== JSON.stringify(labelPositions)) {
            setLabelPositions(positions);
          }
        }
      }],
      data: { labels, datasets: buildDatasets(currentMetric) },
      options: {
        responsive: true, maintainAspectRatio: false,
        layout: { padding: { left: 10, right: 40, top: 20, bottom: 10 } },
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 600, easing: 'easeOutQuart' },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(6,9,18,0.98)',
            borderColor: 'rgba(255,255,255,0.06)',
            borderWidth: 1,
            titleColor: '#94a3b8',
            bodyColor: '#f8fafc',
            padding: 14,
            callbacks: {
              title: items => `📅 ${items[0].label}`,
              label: item => {
                const v = item.raw as any;
                if (currentMetric === 'score') return `  ${item.dataset.label}: ${Number(v).toFixed(1)} pt`;
                if (currentMetric === 'return') return `  ${item.dataset.label}: ${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`;
                if (currentMetric === 'sharpe') return `  ${item.dataset.label}: ${Number(v).toFixed(3)}`;
                return `  ${item.dataset.label}: ${v}`;
              },
              afterBody: () => currentMetric === 'score'
                ? ['', '  Return×0.4 + Sharpe×25×0.35 + (1+MDD)×100×0.25']
                : []
            }
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.01)' },
            ticks: { color: '#475569', font: { size: 10, family: 'monospace' }, maxTicksLimit: 8 },
            max: labels.length - 1
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.015)' },
            ticks: {
              color: '#475569',
              font: { size: 10, family: 'monospace' },
              callback: (v: any) => {
                if (currentMetric === 'score') return Number(v).toFixed(0) + ' pt';
                if (currentMetric === 'return') return (v >= 0 ? '+' : '') + Number(v).toFixed(1) + '%';
                if (currentMetric === 'sharpe') return Number(v).toFixed(2);
                return v;
              }
            }
          }
        }
      }
    });

    return () => {
      if (chartInstance.current) chartInstance.current.destroy();
    };
  }, []);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = buildDatasets(currentMetric);
      chartInstance.current.update();
    }
  }, [currentMetric]);

  return (
    <>
      <Head>
        <title>Trinity AI Trading Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      </Head>

      <header className="flex items-center justify-between px-4 md:px-8 py-3 md:py-4 border-b border-white/[0.05] bg-white/[0.02] backdrop-blur-2xl sticky top-0 z-[100] shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <span className="text-white text-xs font-black">△</span>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-black text-white tracking-widest uppercase">Trinity Chimera</span>
            <span className="text-[9px] font-bold text-blue-400/80 tracking-[0.2em] uppercase leading-none">Intelligence Engine</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)] animate-pulse"></div>
            <span className="text-[10px] font-bold text-green-400 uppercase tracking-wider">
              {isLoading ? '로딩 중...' :
                dashboardProgress ?
                  `${dashboardProgress.active_improvements}개 개선 진행` :
                  'System Live'}
            </span>
          </div>
          <div className="hidden md:flex gap-1.5 bg-white/[0.03] p-1 rounded-xl border border-white/[0.05] backdrop-blur-md">
            {['1D', '1W', '1M', '3M', 'ALL'].map(tf => (
              <button key={tf} className={`px-4 py-1 rounded-lg text-[10px] font-bold transition-all ${tf === '1M' ? 'bg-white/10 text-white shadow-lg border border-white/10' : 'text-slate-500 hover:text-slate-200'}`}>
                {tf}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="flex flex-col lg:flex-row h-auto lg:h-[calc(100vh-65px)] relative overflow-x-hidden overflow-y-auto lg:overflow-hidden">
        {/* Ambient Glows */}
        <div className="absolute top-[10%] left-[10%] w-[400px] h-[400px] bg-blue-500/10 blur-[120px] rounded-full pointer-events-none" />
        <div className="absolute bottom-[20%] right-[10%] w-[350px] h-[350px] bg-purple-500/10 blur-[100px] rounded-full pointer-events-none" />

        {/* LEFT PANEL */}
        <div className="flex flex-col flex-1 border-b lg:border-b-0 lg:border-r border-white/5 overflow-visible lg:overflow-y-auto relative z-10 min-w-0 custom-scrollbar">
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.03] bg-white/[0.01] backdrop-blur-md">
            <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Agent Intelligence Grid</span>
          </div>

          <div className="flex items-center justify-between p-3 sm:p-4 border-b border-white/[0.02] bg-white/[0.01] overflow-hidden">
            <div className="flex bg-white/[0.03] p-1 rounded-xl border border-white/[0.05] overflow-x-auto no-scrollbar max-w-full">
              {(Object.keys(hintMap) as MetricKey[]).map((m) => (
                <button
                  key={m}
                  className={`px-3 sm:px-4 py-1.5 rounded-lg text-[10px] sm:text-[11px] font-bold transition-all whitespace-nowrap border ${currentMetric === m ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-500 hover:text-slate-300 border-transparent'}`}
                  onClick={() => setCurrentMetric(m)}
                >
                  {m.toUpperCase()}
                </button>
              ))}
            </div>
            <div className="ml-auto hidden sm:flex items-center gap-2 px-3 py-1.5 bg-blue-500/5 rounded-lg border border-blue-500/10 shrink-0">
              <span className="text-[10px] text-blue-400 font-mono italic tracking-tight">{hintMap[currentMetric]}</span>
            </div>
            <div className="ml-auto sm:hidden w-8 h-8 rounded-lg bg-blue-500/5 border border-blue-500/10 flex items-center justify-center shrink-0">
              <span className="text-blue-400 text-[12px] cursor-pointer" title={hintMap[currentMetric]}>ⓘ</span>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 p-4 mt-2">
            <AgentCard
              id="momentum_hunter" name="momentum_hunter" avatar="M" strategy="Donchian Breakout"
              sharpe="2.41" mdd="-12.3%" winRate="67.4%" color="var(--agent-1)"
              isActive={activeAgent === "momentum_hunter"}
              onClick={() => setActiveAgent("momentum_hunter")}
            />
            <AgentCard
              id="mean_reverter" name="mean_reverter" avatar="A" strategy="Grid + Mean Rev"
              sharpe="1.87" mdd="-8.1%" winRate="71.2%" color="var(--agent-2)"
              isActive={activeAgent === "mean_reverter"}
              onClick={() => setActiveAgent("mean_reverter")}
            />
            <AgentCard
              id="macro_trader" name="macro_trader" avatar="N" strategy="Trend Following"
              sharpe="1.23" mdd="-18.9%" winRate="52.1%" color="var(--agent-3)"
              isActive={activeAgent === "macro_trader"}
              onClick={() => setActiveAgent("macro_trader")}
            />
            <AgentCard
              id="chaos_agent" name="chaos_agent" avatar="C" strategy="Scalping ATR"
              sharpe="-0.31" mdd="-24.7%" winRate="44.8%" color="var(--agent-4)"
              isActive={activeAgent === "chaos_agent"}
              onClick={() => setActiveAgent("chaos_agent")}
            />
          </div>

          <div className="flex-1 px-4 py-3 flex flex-col min-h-0">
            <div className="flex flex-wrap gap-3 mb-4">
              {NAMES.map((name, i) => (
                <div key={name} className="flex items-center gap-2 px-3 py-1 rounded-lg bg-white/[0.02] border border-white/[0.04] backdrop-blur-sm">
                  <div className="w-1.5 h-1.5 rounded-full shadow-[0_0_8px_currentColor]" style={{ background: COLORS[i], color: COLORS[i] }}></div>
                  <span className="text-[10px] font-black text-slate-400 tracking-widest uppercase">{name}</span>
                </div>
              ))}
            </div>
            <div className="flex-1 relative w-full h-[300px] lg:h-full min-h-[350px]">
              <div className="absolute inset-0 glass rounded-xl shadow-2xl">
                <canvas id="perfChart" ref={chartRef} className="w-full h-full z-10 relative"></canvas>

                {/* Floating End-of-Line Labels */}
                {labelPositions.map((pos, i) => (
                  <div
                    key={i}
                    className="absolute z-20 transition-all duration-300 pointer-events-none"
                    style={{
                      left: pos.x,
                      top: pos.y,
                      transform: 'translate(12px, -50%)'
                    }}
                  >
                    <div className="flex items-center gap-3">
                      {/* Avatar Circle */}
                      <div
                        className="relative shrink-0 pointer-events-auto cursor-pointer"
                        onMouseEnter={() => setHoveredLabel(pos.label)}
                        onMouseLeave={() => setHoveredLabel(null)}
                      >
                        <div
                          className={`w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-black border-2 shadow-lg transition-transform duration-300 ${hoveredLabel === pos.label ? 'scale-110' : ''}`}
                          style={{
                            backgroundColor: 'rgba(6, 9, 18, 0.9)',
                            color: pos.color,
                            borderColor: `color-mix(in srgb, ${pos.color}, transparent 60%)`,
                            boxShadow: `0 0 15px color-mix(in srgb, ${pos.color}, transparent 80%)`
                          }}
                        >
                          {pos.avatar}
                        </div>
                        <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-[#0f172a] border border-white/10 flex items-center justify-center">
                          <span className="text-[7px] font-bold text-white opacity-60">V{NAMES.indexOf(pos.label) < 2 ? NAMES.indexOf(pos.label) + 1 : 1}</span>
                        </div>
                      </div>

                      {/* Info Box - Show only on hover */}
                      {hoveredLabel === pos.label && (
                        <div className="bg-[#0b0f1a]/95 backdrop-blur-3xl border border-white/10 rounded-[8px] py-1.5 px-2.5 shadow-2xl min-w-[110px] flex flex-col gap-0.5 animate-in fade-in zoom-in-95 duration-200">
                          <div className="text-[8px] font-bold text-slate-500 uppercase tracking-tighter">
                            {currentMetric === 'score' ? `SCORE` :
                              currentMetric === 'return' ? `RETURN` :
                                currentMetric === 'sharpe' ? `SHARPE` :
                                  currentMetric.toUpperCase()}
                          </div>

                          <div className="text-[12px] font-bold tracking-tight text-white leading-none my-0.5">
                            {currentMetric === 'score' ? `${pos.value.toFixed(1)} pt` :
                              currentMetric === 'return' ? `${(pos.value).toFixed(2)}%` :
                                currentMetric === 'sharpe' ? pos.value.toFixed(2) :
                                  `${pos.value.toFixed(1)}%`}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div className="w-full lg:w-[380px] flex flex-col border-t lg:border-t-0 lg:border-l border-white/[0.05] bg-white/[0.01] backdrop-blur-2xl relative z-10 shrink-0 lg:overflow-y-auto custom-scrollbar">
          <div className="flex p-2 bg-white/[0.02] border-b border-white/[0.03] gap-1">
            {['strategy', 'params', 'backtest', 'positions'].map((tab) => (
              <button
                key={tab}
                className={`flex-1 py-3 text-[10px] font-black transition-all rounded-xl relative tracking-[0.15em] uppercase border ${activeTab === tab ? 'bg-white/10 text-white shadow-lg border-white/10' : 'text-slate-600 hover:text-slate-300 border-transparent'}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab === 'strategy' ? 'Logs' : tab}
              </button>
            ))}
          </div>

          <div className="flex gap-2 p-4 border-b border-white/[0.02] overflow-x-auto shrink-0 no-scrollbar">
            {['ALL', ...NAMES].filter(n => n !== 'BTC BnH').map(name => (
              <button
                key={name}
                className={`px-4 py-1.5 rounded-xl text-[10px] font-bold border transition-all whitespace-nowrap ${activeAgent === name ? 'bg-blue-400/20 border-blue-400/30 text-blue-200' : 'bg-white/[0.02] border-white/5 text-slate-500 hover:border-white/20'}`}
                onClick={() => setActiveAgent(name)}
              >
                {name}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 bg-[#060912]/30 custom-scrollbar px-4 py-4 flex flex-col gap-5">
            <LogCard
              agentName="MINARA V2" avatar="M" avatarBg="rgba(56,189,248,0.1)" color="var(--agent-1)" time="04/06 · 15:00"
              analysis="BTC가 범위 제한 국면에 진입했습니다. <span class='text-white font-medium'>$64,191 ~ $69,540</span> 사이에서 진동 중이며, 이는 횡보 구간임을 시사합니다. Donchian 채널 돌파 필터(ATR 2.0×)를 통과하여 <span class='text-white font-medium'>그리드 전략(41레벨)</span> 을 배포합니다."
              reason="이전 추세추종 전략이 연속 3회 손절 후 <span class='text-white font-medium'>샤프지수 1.12 → 2.41로 개선</span> 이 필요했습니다. 백테스트 결과 횡보 구간에서 평균복귀 전략 수익률이 38% 높았습니다."
              params={[
                { name: "donchian_len", oldVal: "20", newVal: "15", trend: "neutral" },
                { name: "atr_mult", oldVal: "1.5", newVal: "2.0", trend: "up" },
                { name: "sl_atr", oldVal: "1.5×", newVal: "2.0×", trend: "neutral" },
                { name: "tp_atr", oldVal: "3.0×", newVal: "4.0×", trend: "up" },
              ]}
            />
            <LogCard
              agentName="MINARA V2" avatar="M" avatarBg="rgba(56,189,248,0.1)" color="var(--agent-1)" time="04/06 · 13:15"
              analysis="시장 국면이 전환되었습니다. <span class='text-white font-medium'>$64,117 ~ $69,460</span> 범위 구조가 붕괴되었으며(41 그리드 레벨 무력화), 방향성 추세 이동 준비가 필요합니다."
              reason="범위 제한→추세 국면 전환으로 현재 그리드 전략의 <span class='text-white font-medium'>예상 손실이 +4.2% 악화</span> 될 것으로 판단, 모든 포지션 정리 후 방향성 전략으로 전환합니다."
            />
            <LogCard
              agentName="ARBITER V1" avatar="A" avatarBg="rgba(167,139,250,0.1)" color="var(--agent-2)" time="04/06 · 11:30"
              analysis="1H RSI가 <span class='text-white font-medium'>72.3 (과매수)</span> 에 도달했습니다. 볼린저 밴드 상단 돌파 후 반전 신호가 감지됩니다. 평균복귀 확률 68% 추정."
              reason=""
              params={[
                { name: "rsi_ob", oldVal: "70", newVal: "72", trend: "down" },
                { name: "grid_levels", oldVal: "20", newVal: "15", trend: "neutral" },
              ]}
            />
          </div>

          <div className="p-4 border-t border-white/[0.04] bg-[#060912]/90 shrink-0 backdrop-blur-lg">
            <div className="text-[10px] font-bold text-[#475569] uppercase tracking-[0.14em] mb-4 flex items-center justify-between">
              <span>백테스트 성과 요약</span>
              <div className="flex gap-2">
                <div className="w-1 h-1 rounded-full bg-blue-400"></div>
                <div className="w-1 h-1 rounded-full bg-blue-400/40"></div>
                <div className="w-1 h-1 rounded-full bg-blue-400/20"></div>
              </div>
            </div>
            <div className="overflow-x-auto no-scrollbar">
              <table className="w-full text-left border-collapse min-w-[320px]">
                <thead>
                  <tr className="text-[9px] text-[#475569] uppercase tracking-wider border-b border-white/[0.04]">
                    <th className="pb-2.5 pt-1 font-bold px-3">Agent</th>
                    <th className="pb-2.5 pt-1 font-bold text-center px-2">Return</th>
                    <th className="pb-2.5 pt-1 font-bold text-center px-2">Sharpe</th>
                    <th className="pb-2.5 pt-1 font-bold text-right px-3">MDD</th>
                  </tr>
                </thead>
                <tbody className="text-[12px] font-mono">
                  {[
                    { name: "MINARA V2", color: 'var(--agent-1)', ret: '+79.72%', sh: '2.41', mdd: '-12.3%', pos: true },
                    { name: "ARBITER V1", color: 'var(--agent-2)', ret: '+22.78%', sh: '1.87', mdd: '-8.1%', pos: true },
                    { name: "NIM-ALPHA", color: 'var(--agent-3)', ret: '+15.63%', sh: '1.23', mdd: '-18.9%', pos: true },
                    { name: "CHIMERA-β", color: 'var(--agent-4)', ret: '-4.06%', sh: '-0.31', mdd: '-24.7%', pos: false },
                  ].map(row => (
                    <tr key={row.name} className="group hover:bg-white/[0.02] transition-colors">
                      <td className="py-2.5 px-3 font-bold tracking-tighter border-b border-white/[0.02]" style={{ color: row.color }}>{row.name}</td>
                      <td className={`py-2.5 px-2 text-center border-b border-white/[0.02] font-semibold ${row.pos ? 'text-[#4ade80]' : 'text-[#fb7185]'}`}>{row.ret}</td>
                      <td className="py-2.5 px-2 text-center border-b border-white/[0.02] text-[#94a3b8] font-medium">{row.sh}</td>
                      <td className="py-2.5 px-3 text-right border-b border-white/[0.02] text-[#fb7185] opacity-90 font-medium">{row.mdd}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
