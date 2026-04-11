import { Time } from "lightweight-charts";

export type Candle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Marker = {
  time: number;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowUp" | "arrowDown";
  text: string;
};

export type TimeFrame = "1m" | "5m" | "15m" | "1h" | "4h";

export type Trade = {
  type: "LONG" | "SHORT";
  time: string;
  exitReason: string;
  entry: number;
  exit: number;
  sl: number;
  tp: number;
  posSize: number;
  profitPct: string;
  profitAmt: number;
};

export type Results = {
  netProfitAmt: number;
  totalReturnNum: number;
  winRateNum: number;
  mddPct: number;
  sharpeRatio: number;
  profitFactor: number;
  totalTradesCount: number;
  bestTradeFinal: number;
  worstTradeFinal: number;
  winCount: number;
  lossCount: number;
  trades: Trade[];
  markers: Marker[];
  // Extended metrics
  sortinoRatio?: number;
  calmarRatio?: number;
  alphaReturn?: number;
  buyHoldReturn?: number;
  totalFees?: number;
  longReturn?: number;
  longPF?: number;
  shortReturn?: number;
  shortPF?: number;
  expectedReturn?: number;
  // Trade Analysis
  avgProfitPct?: number;
  avgLossPct?: number;
  maxConsecutiveWins?: number;
  maxConsecutiveLosses?: number;
  avgHoldBars?: number;
  longCount?: number;
  shortCount?: number;
};

export type LeaderboardRow = {
  rank: number;
  tf: string;
  strategy: string;
  strategyLabel: string;
  results: Results;
};
