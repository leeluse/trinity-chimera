"use client";

import { Results, TimeFrame } from "@/types/backtest";

// Extracted Sections
import PanelTabs from "./sections/PanelTabs";
import ChatInterface from "../chat/ChatInterface";

interface BacktestRightPanelProps {
  activeAgent: string;
  setActiveAgent: (name: string) => void;
  symbol: string;
  timeframe: TimeFrame;
  startDate: string;
  endDate: string;
  results: Results | null;
  onBacktestGenerated: (payload: any) => void;
  onApplyCode?: (code: string, name?: string, payload?: any) => void;
}

export default function BacktestRightPanel({
  activeAgent,
  setActiveAgent,
  symbol,
  timeframe,
  startDate,
  endDate,
  results,
  onBacktestGenerated,
  onApplyCode,
}: BacktestRightPanelProps) {
  return (
    <>
      <PanelTabs />
      <div className="flex-1 overflow-y-auto min-h-0 bg-[#060912]/30 flex flex-col">
        <ChatInterface
          context={{
            symbol,
            timeframe,
            start_date: startDate,
            end_date: endDate,
            netProfitAmt: results?.netProfitAmt,
            winRate: results?.winRateNum,
            maxDrawdown: results?.mddPct,
            sharpe: results?.sharpeRatio,
            profitFactor: results?.profitFactor,
            trades: results?.totalTradesCount,
          }}
          onBacktestGenerated={onBacktestGenerated}
          onApplyCode={onApplyCode}
        />
      </div>
    </>
  );
}
