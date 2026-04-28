"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CandlestickSeries, IChartApi, ISeriesApi, createChart, createSeriesMarkers, type ISeriesMarkersPluginApi, type Time } from "lightweight-charts";

import { fetchWithBypass } from "@/lib/api";

// Centralized Components Import
import {
  PageLayout,
  PageHeader,
  StatsGrid,
  AiAnalysisModal,
  BacktestChart,
  BacktestHeader,
  EquityChart,
  StrategyCodeSection,
  PerformanceDetails,
  TradeAnalysis,
  ExecutionLog
} from "@/components";
import { AppRightPanel } from "@/components/layout/AppRightPanel";
import RegimePanel from "@/components/features/backtest/RegimePanel";
import { useDashboardQueries } from "@/hooks/useDashboardQueries";

// Externalized
import { Results, TimeFrame } from "@/types/backtest";
import { cardClass } from "@/styles/common";

const REGIME_VALIDATION_START = "2021-01-01";
const REGIME_VALIDATION_END = "2026-01-31";

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
  avgProfitPct: Number(payload?.results?.avg_profit ?? 0),
  avgLossPct: Number(payload?.results?.avg_loss ?? 0),
  maxConsecutiveWins: Number(payload?.results?.max_consecutive_wins ?? 0),
  maxConsecutiveLosses: Number(payload?.results?.max_consecutive_losses ?? 0),
  avgHoldBars: Number(payload?.results?.avg_bars ?? 0),
  longCount: Number(payload?.results?.long_count ?? 0),
  shortCount: Number(payload?.results?.short_count ?? 0),
  equityCurve: payload?.equity_curve || [],
});

export default function BacktestPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tabParam = (searchParams.get("tab") || "").toLowerCase();
  const isRegimeRoute = tabParam === "regime";
  const [activeAgent, setActiveAgent] = useState("ALL");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [timeFrame, setTimeFrame] = useState<TimeFrame>("1h");
  const [strategy, setStrategy] = useState("");
  const [strategies, setStrategies] = useState<any[]>([]);
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-04-15");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Results | null>(null);
  const [strategyTitle, setStrategyTitle] = useState("");

  const { evolutionEvents, decisionLogs, automationStatus, toggleAutomation } = useDashboardQueries();

  const [aiOpen, setAiOpen] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState("");

  const [activeTab, setActiveTab] = useState("지표");
  const effectiveActiveTab = isRegimeRoute ? "레짐" : activeTab;
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
      const loaded = (data?.strategies || []).map((s: any) => ({ key: String(s.key), label: String(s.label || s.key) }));
      setStrategies(loaded);
      if (loaded.length > 0 && !strategy) {
        setStrategy(loaded[0].key);
        setStrategyTitle(loaded[0].label);
      }
    };
    void loadStrategies();
  }, [strategy]);

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
        params.append("code", strategyCode);
      }

      const res = await fetchWithBypass(`/api/backtest/run?${params.toString()}`);
      const data = await res.json();
      if (!res.ok || !data?.success) throw new Error(data?.error || "백테스트 실패");
      applyBacktestPayload(data);
    } catch (e) { alert(e instanceof Error ? e.message : "Error"); } finally { setLoading(false); }
  };

  const handleDeploy = async () => {
    if (!strategyCode) {
      alert("배포할 전략 코드가 없습니다.");
      return;
    }

    const currentLabel = strategies.find(s => s.key === strategy)?.label;
    const defaultTitle = strategyTitle || currentLabel || strategy || "";
    
    // 배포 시점에 항상 이름을 묻도록 함 (사용자 요청)
    const customTitle = window.prompt("🚀 배포할 전략의 이름을 입력하세요:", defaultTitle);
    
    if (customTitle === null) return; // 취소 버튼 클릭 시 중단
    
    const title = customTitle.trim() || `${defaultTitle}_deployed`;
    setStrategyTitle(title);
    
    setLoading(true);
    try {
      const res = await fetchWithBypass("/api/chat/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: strategyCode,
          title: title
        })
      });
      
      const data = await res.json();
      if (data.success) {
        alert(`✅ 전략이 성공적으로 배포되었습니다!\nID: ${data.strategy_key}`);
        const sRes = await fetchWithBypass("/api/backtest/strategies");
        const sData = await sRes.json();
        if (sData.success) {
          const loaded = (sData.strategies || []).map((s: any) => ({ key: String(s.key), label: String(s.label || s.key) }));
          setStrategies(loaded);
        }
      } else {
        throw new Error(data.error || "배포 실패");
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "배포 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const applyGeneratedCode = (code: string, name?: string, payload?: any) => {
    setStrategyCode(code);
    if (name) {
      setStrategy(name); 
      setStrategyTitle(name);
    }
    if (payload) {
      applyBacktestPayload(payload);
      setActiveTab("지표");
    } else {
      setActiveTab("코드");
    }
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

  const handleStrategyChange = (newStrategy: string) => {
    setStrategy(newStrategy);
    const label = strategies.find(s => s.key === newStrategy)?.label || newStrategy;
    setStrategyTitle(label);
  };

  useEffect(() => {
    if (strategy && strategies.length > 0) {
      const isKnown = strategies.some(s => s.key === strategy);
      if (isKnown) {
        void loadStrategyCode(strategy);
      }
    }
  }, [strategy, strategies]);

  const handleTabChange = async (tab: string) => {
    setActiveTab(tab);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("tab");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    if (tab === "코드" && (!strategyCode || strategyCode.startsWith("// Error"))) {
      void loadStrategyCode(strategy);
    }
  };

  const handleCopyResults = () => {
    if (!results) {
      alert("복사할 결과가 없습니다.");
      return;
    }
    const { trades: _, markers: __, equityCurve: ___, ...metrics } = results;
    const json = JSON.stringify(metrics, null, 2);
    navigator.clipboard.writeText(json)
      .then(() => alert("지표 수치가 JSON으로 복사되었습니다."))
      .catch((err) => {
        console.error("Copy failed:", err);
        alert("복사 중 오류가 발생했습니다.");
      });
  };

  const fmtMoney = (v: number) => `$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const backtestContext = useMemo(() => ({
    symbol,
    timeframe: timeFrame,
    start_date: startDate,
    end_date: endDate,
    netProfitAmt: results?.netProfitAmt,
    total_return: results?.totalReturnNum,
    winRate: results?.winRateNum,
    maxDrawdown: results?.mddPct,
    sharpe: results?.sharpeRatio,
    profitFactor: results?.profitFactor,
    trades: results?.totalTradesCount,
    strategy: strategy,
    strategy_title: strategy,
    editor_code: strategyCode,
    current_strategy: {
      title: strategy,
      code: strategyCode,
    },
  }), [symbol, timeFrame, startDate, endDate, results, strategy, strategyCode]);

  return (
    <PageLayout rightWidth="lg:w-[400px]">
      <PageLayout.Side>
        <AppRightPanel
          agentIds={[]}
          names={[]}
          evolutionEvents={evolutionEvents}
          decisionLogs={decisionLogs}
          automationStatus={automationStatus}
          onToggleAutomation={toggleAutomation}
          backtestContext={backtestContext}
          onBacktestGenerated={applyBacktestPayload}
          onApplyCode={applyGeneratedCode}
        />
      </PageLayout.Side>

      <PageLayout.Main>
        {isRegimeRoute ? (
          <div className="flex flex-col flex-1 relative p-4 overflow-hidden">
            <RegimePanel
              symbol={symbol}
              startDate={REGIME_VALIDATION_START}
              endDate={REGIME_VALIDATION_END}
              busy={loading}
            />
          </div>
        ) : (
          <>
            <PageHeader
              statusText={loading ? "Simulating..." : "Ready"}
              statusColor="blue"
            />

            <div className="flex flex-col flex-1 relative p-4 overflow-hidden">
              <div className="flex flex-col gap-4 relative z-10 overflow-y-auto no-scrollbar pr-1">
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
                  strategy={strategy} strategies={strategies} setStrategy={handleStrategyChange}
                  strategyTitle={strategyTitle} setStrategyTitle={setStrategyTitle}
                  onRun={handleStartTest}
                  onDeploy={handleDeploy}
                  onCopy={handleCopyResults}
                  activeTab={effectiveActiveTab}
                  onTabChange={handleTabChange}
                  loading={loading}
                />

                {effectiveActiveTab === "지표" && (
                  <>
                    <StatsGrid results={results} fmtMoney={fmtMoney} />
                    <EquityChart results={results} />
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full max-w-[1600px] mx-auto">
                      <PerformanceDetails results={results} />
                      <TradeAnalysis results={results} />
                    </div>
                  </>
                )}

                {effectiveActiveTab === "거래 내역" && (
                  <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl overflow-hidden flex flex-col min-h-[500px]">
                    <ExecutionLog 
                      trades={results?.trades || []} 
                      totalTradesCount={results?.totalTradesCount || 0} 
                      fmtMoney={fmtMoney} 
                    />
                  </div>
                )}

                {effectiveActiveTab === "코드" && (
                  <div ref={codeSectionRef}>
                    <StrategyCodeSection
                      strategyName={strategies.find(s => s.key === strategy)?.label || strategy}
                      code={strategyCode}
                      onChange={setStrategyCode}
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
          </>
        )}
      </PageLayout.Main>
    </PageLayout>
  );
}
