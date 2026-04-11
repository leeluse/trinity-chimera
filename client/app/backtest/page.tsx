"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CandlestickSeries, IChartApi, ISeriesApi, createChart, createSeriesMarkers, type ISeriesMarkersPluginApi, type Time } from "lightweight-charts";

import { fetchWithBypass } from "@/lib/api";

// Centralized Components Import
import {
  PageLayout,
  PageHeader,
  StatsGrid,
  AiAnalysisModal,
  BacktestChart,
  BacktestRightPanel,
  BacktestHeader,
  EquityChart,
  StrategyCodeSection,
  PerformanceDetails,
  TradeAnalysis
} from "@/components";

// Externalized
import { Results, TimeFrame } from "@/types/backtest";
import { cardClass, ambientGlows } from "@/styles/common";

const parseResults = (payload: any): Results => ({
  netProfitAmt: Number(payload?.results?.total_pnl ?? 0),
  totalReturnNum: Number(payload?.results?.total_return ?? 0),
  winRateNum: Number(payload?.results?.win_rate ?? 0),
  mddPct: Number(payload?.results?.max_drawdown ?? 0),
  sharpeRatio: Number(payload?.results?.sharpe_ratio ?? 0),
  profitFactor: Number(payload?.results?.profit_factor ?? 0),
  totalTradesCount: Number(payload?.results?.total_trades ?? 0),
  bestTradeFinal: Number(payload?.results?.best_trade ?? 0),
  worstTradeFinal: Number(payload?.results?.worst_trade ?? 0),
  winCount: Number(payload?.results?.win_count ?? 0),
  lossCount: Number(payload?.results?.loss_count ?? 0),
  trades: payload?.trades || [],
  markers: payload?.markers || [],
  // Extended
  sortinoRatio: Number(payload?.results?.sortino_ratio ?? 0),
  calmarRatio: Number(payload?.results?.calmar_ratio ?? 0),
  alphaReturn: Number(payload?.results?.alpha ?? 0),
  buyHoldReturn: Number(payload?.results?.buy_hold ?? 0),
  totalFees: Number(payload?.results?.total_fees ?? 0),
  longReturn: Number(payload?.results?.long_return ?? 0),
  longPF: Number(payload?.results?.long_pf ?? 0),
  shortReturn: Number(payload?.results?.short_return ?? 0),
  shortPF: Number(payload?.results?.short_pf ?? 0),
  expectedReturn: Number(payload?.results?.expected_return ?? 0),
  // Trade Analysis
  avgProfitPct: Number(payload?.results?.avg_profit ?? 0),
  avgLossPct: Number(payload?.results?.avg_loss ?? 0),
  maxConsecutiveWins: Number(payload?.results?.max_consecutive_wins ?? 0),
  maxConsecutiveLosses: Number(payload?.results?.max_consecutive_losses ?? 0),
  avgHoldBars: Number(payload?.results?.avg_bars ?? 0),
  longCount: Number(payload?.results?.long_count ?? 0),
  shortCount: Number(payload?.results?.short_count ?? 0),
});

export default function BacktestPage() {
  const today = useMemo(() => new Date(), []);
  const defaultStart = useMemo(() => { const d = new Date(today); d.setDate(d.getDate() - 90); return d; }, [today]);

  const [activeAgent, setActiveAgent] = useState("ALL");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeFrame, setTimeFrame] = useState<TimeFrame>("1h");
  const [strategy, setStrategy] = useState("optPredator");
  const [strategies, setStrategies] = useState<any[]>([]);
  const [startDate, setStartDate] = useState(defaultStart.toISOString().split('T')[0]);
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Results | null>(null);

  const [aiOpen, setAiOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState("");

  const [activeTab, setActiveTab] = useState("지표");
  const [strategyCode, setStrategyCode] = useState("");
  const [codeLoading, setCodeLoading] = useState(false);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const codeSectionRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markerSeriesRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    const loadStrategies = async () => {
      const res = await fetchWithBypass("/api/backtest/strategies");
      const data = await res.json();
      if (!res.ok || !data?.success) return;
      setStrategies((data?.strategies || []).map((s: any) => ({ key: String(s.key), label: String(s.label || s.key) })));
    };
    void loadStrategies();
  }, []);

  // Removed automatic code clearing on strategy change to preserve AI-generated code
  /*
  useEffect(() => {
    setStrategyCode("");
  }, [strategy]);
  */

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      layout: { 
        background: { color: "transparent" }, 
        textColor: "#94a3b8", 
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace"
      },
      grid: { 
        vertLines: { color: "rgba(189, 147, 249, 0.03)" }, 
        horzLines: { color: "rgba(189, 147, 249, 0.03)" } 
      },
      width: chartContainerRef.current.clientWidth,
      height: 450,
      timeScale: {
        borderColor: "rgba(189, 147, 249, 0.1)",
      },
    });
    const series = chart.addSeries(CandlestickSeries, { 
      upColor: "#6075ffff", 
      downColor: "#ffa2f1ff", 
      borderVisible: false, 
      wickUpColor: "#6075ffff", 
      wickDownColor: "#ffa2f1ff" 
    });
    chartRef.current = chart; 
    candleSeriesRef.current = series; 
    markerSeriesRef.current = createSeriesMarkers(series, []);
    return () => chart.remove();
  }, []);

  const applyBacktestPayload = (payload: any) => {
    if (!payload) return;
    const res = parseResults(payload);
    setResults(res);

    if (payload.candles && candleSeriesRef.current) {
      candleSeriesRef.current.setData(payload.candles);
    }
    
    if (payload.markers && markerSeriesRef.current) {
      markerSeriesRef.current.setMarkers(payload.markers);
    }

    if (chartRef.current && payload.candles?.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  };

  const handleStartTest = async () => {
    setLoading(true);
    try {
      // If the strategy name is not in the list, or it's a code-focused tab, we send the code directly
      const isKnown = strategies.some(s => s.key === strategy);
      const params = new URLSearchParams({ 
        symbol, 
        interval: timeFrame, 
        strategy, 
        start_date: startDate, 
        end_date: endDate, 
        include_candles: "true" 
      });
      
      if (!isKnown && strategyCode) {
        params.append("code", strategyCode);
      } else if (strategyCode) {
        // Even for known strategies, if there's modified code in editor, we use it
        params.append("code", strategyCode);
      }

      const res = await fetchWithBypass(`/api/backtest?${params.toString()}`);
      const data = await res.json();
      if (!res.ok || !data?.success) throw new Error(data?.error || "백테스트 실패");
      applyBacktestPayload(data);
    } catch (e) { alert(e instanceof Error ? e.message : "Error"); } finally { setLoading(false); }
  };

  const applyGeneratedCode = (code: string, name?: string, payload?: any) => {
    // 1. Apply code
    setStrategyCode(code);
    if (name) {
      setStrategy(name); 
    }
    
    // 2. Apply backtest results if present
    if (payload) {
      applyBacktestPayload(payload);
      setActiveTab("백테스트"); // Switch to chart/results view
    } else {
      setActiveTab("코드"); // Switch to code if no results yet
    }

    // 3. Scroll to editor if needed
    setTimeout(() => {
      codeSectionRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  const loadStrategyCode = async (targetStrategy: string) => {
    const isKnownStrategy = strategies.some(s => s.key === targetStrategy);
    if (!isKnownStrategy) return;

    setCodeLoading(true);
    try {
      const res = await fetchWithBypass(`/api/backtest/strategies/${targetStrategy}/code`);
      const data = await res.json();
      if (data.success) {
        setStrategyCode(data.code);
      } else {
        setStrategyCode(`// Error: ${data.error || "Failed to load code"}`);
      }
    } catch (e) {
      setStrategyCode(`// Network Error: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setCodeLoading(false);
    }
  };

  // Automatically load code when strategy changes (if it's an official strategy)
  useEffect(() => {
    if (strategy && strategies.length > 0) {
      const isKnown = strategies.some(s => s.key === strategy);
      // We only auto-load if it's a known official strategy
      if (isKnown) {
        void loadStrategyCode(strategy);
      }
    }
  }, [strategy, strategies]);

  const handleTabChange = async (tab: string) => {
    setActiveTab(tab);
    
    // Fallback in case code didn't load during strategy change
    if (tab === "코드" && (!strategyCode || strategyCode.startsWith("// Error"))) {
      void loadStrategyCode(strategy);
    }
  };

  const fmtMoney = (v: number) => `$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <PageLayout rightWidth="lg:w-[400px]">
      <PageLayout.Side>
        <BacktestRightPanel
          activeAgent={activeAgent}
          setActiveAgent={setActiveAgent}
          symbol={symbol}
          timeframe={timeFrame}
          startDate={startDate}
          endDate={endDate}
          results={results}
          onBacktestGenerated={applyBacktestPayload}
          onApplyCode={applyGeneratedCode}
        />
      </PageLayout.Side>

      <PageLayout.Main>
        <PageHeader
          statusText={loading ? "Simulating..." : "Ready"}
          statusColor="blue"
        />

        <div className="flex flex-col flex-1 relative p-4 overflow-hidden">
          <div className="flex flex-col gap-4 relative z-10 overflow-y-auto custom-scrollbar pr-1">
            <BacktestChart
              chartContainerRef={chartContainerRef}
              results={results}
              loading={loading}
              symbol={symbol}
              timeFrame={timeFrame}
              cardClass={cardClass}
            />

            <BacktestHeader
              symbol={symbol} setSymbol={setSymbol}
              timeframe={timeFrame} setTimeframe={setTimeFrame}
              startDate={startDate} setStartDate={setStartDate}
              endDate={endDate} setEndDate={setEndDate}
              strategy={strategy} strategies={strategies} setStrategy={setStrategy}
              onRun={handleStartTest}
              activeTab={activeTab}
              onTabChange={handleTabChange}
              loading={loading}
            />

            {activeTab === "지표" && (
              <>
                <StatsGrid results={results} fmtMoney={fmtMoney} />
                <EquityChart results={results} />
                <div className="flex flex-col lg:flex-row gap-4">
                  <div className="flex-1 min-w-0">
                    <PerformanceDetails results={results} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <TradeAnalysis results={results} />
                  </div>
                </div>
              </>
            )}

            {activeTab === "코드" && (
              <div ref={codeSectionRef}>
                <StrategyCodeSection
                  strategyName={strategies.find(s => s.key === strategy)?.label || strategy}
                  code={strategyCode}
                  loading={codeLoading}
                />
              </div>
            )}
          </div>
        </div>

        <AiAnalysisModal
          isOpen={aiOpen}
          onClose={() => setAiOpen(false)}
          isLoading={aiLoading}
          report={aiReport}
        />
      </PageLayout.Main>
    </PageLayout>
  );
}
