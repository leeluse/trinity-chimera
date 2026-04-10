"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Chart from "chart.js/auto";
import Head from "next/head";
import AgentCard from "@/components/AgentCard";
import LogCard from "@/components/LogCard";
import CodeEditor from "@/components/CodeEditor";
import { supabase } from "@/lib/supabase";
import { AGENT_IDS } from "@/lib/api";

// ─────────────────────────────────────────────────────────
// Trinity Score 합성 지수 공식
// ─────────────────────────────────────────────────────────

// Real-time data from Supabase
interface BacktestResult {
  id: string;
  agent_id: string;
  strategy_id: string;
  return_percentage: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  trinity_score: number;
  created_at: string;
}

interface AgentPerformance {
  id: string;
  name: string;
  return_percentage?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  win_rate?: number;
  trinity_score?: number;
  timeseries?: {
    score?: number[];
    return?: number[];
    sharpe?: number[];
    mdd?: number[];
    win?: number[];
  };
}

const hintMap = {
  score: '수식: Return×0.4 + Sharpe×25×0.35 + (1+MDD)×100×0.25',
  return: '누적 일별 수익률 (%)',
  sharpe: '롤링 샤프지수 (일간 추정)',
  mdd: '누적 최대 낙폭 (MDD, 매일 갱신)',
  win: '누적 승률 % (일별 롤링)',
};

type MetricKey = keyof typeof hintMap;

// Interface for Strategy data
interface Strategy {
  id: string;
  agent_id: string;
  code: string;
  version: string;
  created_at: string;
}

// Interface for Agent status data
interface AgentStatus {
  id: string;
  name: string;
  status: string;
  current_strategy_id?: string;
  last_active: string;
  created_at: string;
}

export default function Dashboard() {
  const chartRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstance = useRef<Chart | null>(null);
  const [currentMetric, setCurrentMetric] = useState<MetricKey>("score");
  const [activeTab, setActiveTab] = useState("strategy");
  const [activeAgent, setActiveAgent] = useState<string>("전체");
  const [dashboardProgress, setDashboardProgress] = useState<{active_improvements: number} | null>(null);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformance[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [labelPositions, setLabelPositions] = useState<Array<{x: number, y: number, label: string, color: string, value: number, change: number, percent: number, avatar: string}>>([]);
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);
  const [latestStrategy, setLatestStrategy] = useState<Strategy | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus[]>([]);
  const [subscriptionError, setSubscriptionError] = useState<string | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const subscriptionRefs = useRef<{[key: string]: ReturnType<typeof supabase.channel>}>({});
  const retryCountRef = useRef(0);
  const maxRetries = 5;

  // Chart labels and constants
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

  const COLORS = [
    '#4acde2', // Sophisticated Aqua Blue (Focus)
    '#c678dd', // One Dark Purple
    '#98c379', // One Dark Green
    '#9f7aea', // Vibrant Purple (final fix)
    '#5c6370'  // One Dark Gray (Benchmark)
  ];
  const NAMES = AGENT_IDS;

  const buildDatasets = (agentPerformance: AgentPerformance[], metric: MetricKey) => {
    // Return empty dataset if no real data available
    if (!agentPerformance || agentPerformance.length === 0) {
      return [];
    }

    return agentPerformance.map((agent: AgentPerformance, i: number) => {
      let data: number[] = [];

      switch (metric) {
        case 'score':
          data = agent.timeseries?.score || [];
          break;
        case 'return':
          data = agent.timeseries?.return || [];
          break;
        case 'sharpe':
          data = agent.timeseries?.sharpe || [];
          break;
        case 'mdd':
          data = agent.timeseries?.mdd || [];
          break;
        case 'win':
          data = agent.timeseries?.win || [];
          break;
      }

      return {
        label: agent.name || NAMES[i],
        data,
        borderColor: COLORS[i],
        backgroundColor: i === 0 ? `color-mix(in srgb, ${COLORS[0]}, transparent 98%)` : 'transparent',
        borderWidth: i === 0 ? 1.4 : (i === 4 ? 0.8 : 1),
        pointRadius: 0,
        tension: 0.42,
        fill: i === 0,
        borderDash: i === 3 ? [5, 4] : (i === 4 ? [1, 5] : []),
        clip: false as const,
      };
    });
  };

  const updatePerformance = (current: AgentPerformance[], newResult: BacktestResult) => {
    const updatedPerformance = [...current];

    // Find agent by ID or create new entry
    const agentIndex = updatedPerformance.findIndex(a => a.id === newResult.agent_id);

    if (agentIndex === -1) {
      // Add new agent performance
      updatedPerformance.push({
        id: newResult.agent_id,
        name: newResult.agent_id,
        return_percentage: newResult.return_percentage,
        sharpe_ratio: newResult.sharpe_ratio,
        max_drawdown: newResult.max_drawdown,
        win_rate: newResult.win_rate,
        trinity_score: newResult.trinity_score,
        timeseries: {}
      });
    } else {
      // Update existing agent performance
      updatedPerformance[agentIndex] = {
        ...updatedPerformance[agentIndex],
        return_percentage: newResult.return_percentage,
        sharpe_ratio: newResult.sharpe_ratio,
        max_drawdown: newResult.max_drawdown,
        win_rate: newResult.win_rate,
        trinity_score: newResult.trinity_score,
        timeseries: updatedPerformance[agentIndex].timeseries
      };
    }

    return updatedPerformance;
  };

  const updateStatus = (current: AgentStatus[], updatedAgent: AgentStatus) => {
    const updatedStatus = [...current];

    // Find agent by ID or create new entry
    const agentIndex = updatedStatus.findIndex(a => a.id === updatedAgent.id);

    if (agentIndex === -1) {
      // Add new agent status
      updatedStatus.push({
        id: updatedAgent.id,
        name: updatedAgent.id,
        status: updatedAgent.status,
        current_strategy_id: updatedAgent.current_strategy_id,
        last_active: updatedAgent.last_active,
        created_at: updatedAgent.created_at
      });
    } else {
      // Update existing agent status
      updatedStatus[agentIndex] = {
        ...updatedStatus[agentIndex],
        status: updatedAgent.status,
        current_strategy_id: updatedAgent.current_strategy_id,
        last_active: updatedAgent.last_active
      };
    }

    return updatedStatus;
  };

  // Reconnection function with exponential backoff
  const handleReconnect = useCallback(async (channelName: string) => {
    if (retryCountRef.current >= maxRetries) {
      console.error(`Max retry attempts reached for ${channelName}`);
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
    console.log(`Reconnecting ${channelName} in ${delay}ms (attempt ${retryCountRef.current + 1})`);

    setTimeout(() => {
      retryCountRef.current++;

      // Re-subscribe the channel
      if (subscriptionRefs.current[channelName]) {
        subscriptionRefs.current[channelName].unsubscribe();
        delete subscriptionRefs.current[channelName];
      }

      // Recreate subscription based on channel name
      if (channelName === 'agent-performance') {
        const subscription = supabase
          .channel(channelName)
          .on('postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'backtest_results' },
            (payload) => {
              setAgentPerformance(prev => updatePerformance(prev, payload.new as BacktestResult));
            }
          )
          .on('system', { event: 'ERROR' }, (err) => {
            console.error('Agent performance reconnection error:', err);
            setSubscriptionError('Real-time connection failed - attempting reconnection');
          })
          .subscribe((status) => {
            if (status === 'SUBSCRIBED') {
              console.log(`${channelName} reconnected successfully`);
              setSubscriptionError(null);
              retryCountRef.current = 0;
            } else if (status === 'CHANNEL_ERROR') {
              setSubscriptionError('Reconnection failed');
              handleReconnect(channelName);
            }
          });

        subscriptionRefs.current[channelName] = subscription;
      }
      // Similar logic for other channels...
    }, delay);
  }, [maxRetries]);

  // Manual reconnection function for all subscriptions
  const handleManualReconnect = useCallback(() => {
    console.log('Manual reconnection triggered');
    retryCountRef.current = 0;
    setSubscriptionError(null);

    // Reset and reload all data
    setIsLoadingData(true);
    setAgentPerformance([]);
    setLatestStrategy(null);
    setAgentStatus([]);

    // Re-subscribe all channels
    Object.keys(subscriptionRefs.current).forEach(channelName => {
      if (subscriptionRefs.current[channelName]) {
        subscriptionRefs.current[channelName].unsubscribe();
        delete subscriptionRefs.current[channelName];
      }
    });

    // Reload initial data
    Promise.all([
      // Re-fetch backtest results
      supabase
        .from('backtest_results')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(50)
        .then(({ data, error }) => {
          if (!error && data && data.length > 0) {
            let initialPerformance: AgentPerformance[] = [];
            data.forEach(result => {
              initialPerformance = updatePerformance(initialPerformance, result);
            });
            setAgentPerformance(initialPerformance);
          }
        }),

      // Re-fetch latest strategy
      supabase
        .from('strategies')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(1)
        .then(({ data, error }) => {
          if (!error && data && data.length > 0) {
            setLatestStrategy(data[0] as Strategy);
          }
        }),

      // Re-fetch agent status
      supabase
        .from('agents')
        .select('*')
        .order('last_active', { ascending: false })
        .then(({ data, error }) => {
          if (!error && data && data.length > 0) {
            const initialStatus: AgentStatus[] = data.map(agent => ({
              id: agent.id,
              name: agent.id,
              status: agent.status,
              current_strategy_id: agent.current_strategy_id,
              last_active: agent.last_active,
              created_at: agent.created_at
            }));
            setAgentStatus(initialStatus);
          }
        })
    ]).finally(() => {
      setIsLoadingData(false);
    });
  }, []);

  // Supabase real-time subscription for backtest results with error handling
  useEffect(() => {
    const subscription = supabase
      .channel('agent-performance')
      .on('postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'backtest_results' },
        (payload) => {
          // Update agent performance state with new backtest result
          setAgentPerformance(prev => updatePerformance(prev, payload.new as BacktestResult));
        }
      )
      .on('system', { event: 'ERROR' }, (err) => {
        console.error('Agent performance subscription error:', err);
        setSubscriptionError('Real-time connection failed');
        handleReconnect('agent-performance');
      })
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          setSubscriptionError(null);
        } else if (status === 'CHANNEL_ERROR') {
          setSubscriptionError('Subscription connection error');
          handleReconnect('agent-performance');
        }
      })

    subscriptionRefs.current['agent-performance'] = subscription;

    return () => {
      subscription.unsubscribe();
    }
  }, []);

  // Supabase real-time subscription for strategies table with error handling
  useEffect(() => {
    const subscription = supabase
      .channel('strategy-updates')
      .on('postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'strategies' },
        (payload) => {
          // Update strategy code display
          setLatestStrategy(payload.new as Strategy);
        }
      )
      .on('system', { event: 'ERROR' }, (err) => {
        console.error('Strategy updates subscription error:', err);
        setSubscriptionError('Strategy updates connection failed');
        handleReconnect('strategy-updates');
      })
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          setSubscriptionError(null);
        } else if (status === 'CHANNEL_ERROR') {
          setSubscriptionError('Strategy subscription connection error');
          handleReconnect('strategy-updates');
        }
      })

    subscriptionRefs.current['strategy-updates'] = subscription;

    return () => {
      subscription.unsubscribe();
    }
  }, []);

  // Supabase real-time subscription for agent status updates with error handling
  useEffect(() => {
    const subscription = supabase
      .channel('agent-status')
      .on('postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'agents' },
        (payload) => {
          // Update agent status indicators
          setAgentStatus(prev => updateStatus(prev, payload.new as AgentStatus));
        }
      )
      .on('system', { event: 'ERROR' }, (err) => {
        console.error('Agent status subscription error:', err);
        setSubscriptionError('Agent status connection failed');
        handleReconnect('agent-status');
      })
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          setSubscriptionError(null);
        } else if (status === 'CHANNEL_ERROR') {
          setSubscriptionError('Agent status subscription connection error');
          handleReconnect('agent-status');
        }
      })

    subscriptionRefs.current['agent-status'] = subscription;

    return () => {
      subscription.unsubscribe();
    }
  }, []);

  // Load initial backtest results from Supabase with loading state
  useEffect(() => {
    const loadInitialBacktestResults = async () => {
      try {
        setIsLoadingData(true);
        const { data: results, error } = await supabase
          .from('backtest_results')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(50); // Load recent results

        if (error) {
          console.error('Error loading backtest results:', error);
          setSubscriptionError('Failed to load initial backtest results');
          return;
        }

        if (results && results.length > 0) {
          // Process initial results
          let initialPerformance: AgentPerformance[] = [];
          results.forEach(result => {
            initialPerformance = updatePerformance(initialPerformance, result);
          });
          setAgentPerformance(initialPerformance);
        }
      } catch (error) {
        console.error('Error loading initial backtest results:', error);
        setSubscriptionError('Failed to load initial backtest results');
      } finally {
        setIsLoadingData(false);
      }
    };

    loadInitialBacktestResults();
  }, []);

  // Load initial strategies data from Supabase with loading state
  useEffect(() => {
    const loadInitialStrategies = async () => {
      try {
        setIsLoadingData(true);
        const { data: strategies, error } = await supabase
          .from('strategies')
          .select('*')
          .order('created_at', { ascending: false })
          .limit(1); // Load most recent strategy

        if (error) {
          console.error('Error loading strategies:', error);
          setSubscriptionError('Failed to load strategy data');
          return;
        }

        if (strategies && strategies.length > 0) {
          setLatestStrategy(strategies[0] as Strategy);
        }
      } catch (error) {
        console.error('Error loading initial strategies:', error);
        setSubscriptionError('Failed to load strategy data');
      } finally {
        setIsLoadingData(false);
      }
    };

    loadInitialStrategies();
  }, []);

  // Load initial agent status from Supabase with loading state
  useEffect(() => {
    const loadInitialAgentStatus = async () => {
      try {
        setIsLoadingData(true);
        const { data: agents, error } = await supabase
          .from('agents')
          .select('*')
          .order('last_active', { ascending: false });

        if (error) {
          console.error('Error loading agent status:', error);
          setSubscriptionError('Failed to load agent status');
          return;
        }

        if (agents && agents.length > 0) {
          const initialStatus: AgentStatus[] = agents.map(agent => ({
            id: agent.id,
            name: agent.id,
            status: agent.status,
            current_strategy_id: agent.current_strategy_id,
            last_active: agent.last_active,
            created_at: agent.created_at
          }));
          setAgentStatus(initialStatus);
        }
      } catch (error) {
        console.error('Error loading initial agent status:', error);
        setSubscriptionError('Failed to load agent status');
      } finally {
        setIsLoadingData(false);
      }
    };

    loadInitialAgentStatus();
  }, []);

  // Remove unused API data loading since we use Supabase subscriptions exclusively

  useEffect(() => {
    if (!chartRef.current) return;
    const ctx = chartRef.current.getContext('2d');
    if (!ctx) return;

    chartInstance.current = new Chart(ctx, {
      type: 'line',
      plugins: [{
        id: 'endLineLabels',
        afterDraw: (chart) => {
          const positions: Array<{x: number, y: number, label: string, color: string, value: number, change: number, percent: number, avatar: string}> = [];
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
                label: dataset.label as string,
                color: dataset.borderColor as string,
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
      data: { labels, datasets: buildDatasets(agentPerformance, currentMetric) },
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
                const v = item.raw as number;
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
              callback: (v: string | number) => {
                const numValue = typeof v === 'string' ? parseFloat(v) : v;
                if (currentMetric === 'score') return Number(numValue).toFixed(0) + ' pt';
                if (currentMetric === 'return') return (numValue >= 0 ? '+' : '') + Number(numValue).toFixed(1) + '%';
                if (currentMetric === 'sharpe') return Number(numValue).toFixed(2);
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
  }, [agentPerformance, currentMetric, labelPositions]);

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.data.datasets = buildDatasets(agentPerformance, currentMetric);
      chartInstance.current.update();
    }
  }, [currentMetric, agentPerformance]);

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
          {subscriptionError && (
            <div className="flex items-center gap-2 px-3 py-1 bg-red-500/10 rounded-full border border-red-500/20">
              <div className="w-1.5 h-1.5 rounded-full bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.5)] animate-pulse"></div>
              <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider">
                {subscriptionError}
              </span>
              <button
                onClick={handleManualReconnect}
                className="ml-2 px-2 py-1 text-[8px] bg-red-500/20 hover:bg-red-500/30 rounded-full border border-red-500/30 transition-all"
              >
                Reconnect
              </button>
            </div>
          )}
          <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 rounded-full border border-green-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.5)] animate-pulse"></div>
            <span className="text-[10px] font-bold text-green-400 uppercase tracking-wider">
              {isLoadingData ? '로딩 중...' :
               isLoading ? '로딩 중...' :
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
            {isLoadingData ? (
              // Loading state for agent cards
              Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="bg-white/[0.03] border border-white/[0.05] rounded-2xl p-4 flex flex-col gap-2 animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-slate-700/50"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-slate-700/50 rounded mb-1"></div>
                      <div className="h-3 bg-slate-700/30 rounded w-3/4"></div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              ['minara', 'arbiter', 'nimalpha', 'chimera'].map(agentId => {
                const agentData = agentStatus.find(a => a.id === agentId);
                const agentName = agentId;

                return (
                  <AgentCard
                    key={agentId}
                    id={agentId}
                    name={agentName}
                    avatar={agentName.charAt(0)}
                    strategy={agentData?.status === 'active' ? 'Active' : 'Idle'}
                    status={agentData?.status || 'idle'}
                    lastActive={agentData?.last_active}
                    sharpe="-" mdd="-" winRate="-" color={`var(--agent-${['minara', 'arbiter', 'nimalpha', 'chimera'].indexOf(agentId) + 1})`}
                    isActive={activeAgent === agentName}
                    onClick={() => setActiveAgent(agentName)}
                  />
                );
              })
            )}
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
              {isLoadingData ? (
                <div className="absolute inset-0 flex items-center justify-center glass rounded-xl shadow-2xl">
                  <div className="text-center">
                    <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto"></div>
                    <div className="text-[11px] text-slate-500 mt-4 font-medium">Loading performance data...</div>
                  </div>
                </div>
              ) : (
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
              )}
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
              {['ALL', ...NAMES].map(name => (
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
            {activeTab === 'strategy' ? (
              isLoadingData ? (
                <div className="flex flex-col items-center justify-center h-[500px] text-slate-500">
                  <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
                  <div className="text-[11px] mt-4 font-medium">Loading strategy code...</div>
                </div>
              ) : latestStrategy ? (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-blue-400 uppercase tracking-widest">Latest Strategy Code</span>
                    <span className="text-[9px] text-slate-500 font-mono">Version {latestStrategy.version}</span>
                  </div>
                  <div className="bg-[#111720] border border-[#1e293b] rounded-xl overflow-hidden h-[500px]">
                    <CodeEditor code={latestStrategy.code} />
                  </div>
                  <div className="text-[9px] text-slate-500">
                    Generated: {new Date(latestStrategy.created_at).toLocaleString()}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500 text-[11px]">
                  No strategy code available yet
                </div>
              )
            ) : activeTab === 'params' ? (
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
            ) : (
              <>
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
              </>
            )}
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
                  {agentPerformance.length > 0 ? (
                    agentPerformance.slice(0, 4).map((agent, index) => {
                      const returnPercentage = agent.return_percentage || 0;
                      const isPositive = returnPercentage >= 0;
                      const returnValue = `${returnPercentage >= 0 ? '+' : ''}${returnPercentage.toFixed(2)}%`;
                      const sharpeValue = (agent.sharpe_ratio || 0).toFixed(2);
                      const mddValue = `${Math.abs(agent.max_drawdown || 0).toFixed(1)}%`;

                      const agentColors = ['var(--agent-1)', 'var(--agent-2)', 'var(--agent-3)', 'var(--agent-4)'];
                      const color = agentColors[index] || 'var(--agent-1)';

                      return (
                        <tr key={agent.id} className="group hover:bg-white/[0.02] transition-colors">
                          <td className="py-2.5 px-3 font-bold tracking-tighter border-b border-white/[0.02]" style={{ color }}>{agent.name}</td>
                          <td className={`py-2.5 px-2 text-center border-b border-white/[0.02] font-semibold ${isPositive ? 'text-[#4ade80]' : 'text-[#fb7185]'}`}>{returnValue}</td>
                          <td className="py-2.5 px-2 text-center border-b border-white/[0.02] text-[#94a3b8] font-medium">{sharpeValue}</td>
                          <td className="py-2.5 px-3 text-right border-b border-white/[0.02] text-[#fb7185] opacity-90 font-medium">-{mddValue}</td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-4 text-center text-slate-500 text-[11px]">
                        No performance data available yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
