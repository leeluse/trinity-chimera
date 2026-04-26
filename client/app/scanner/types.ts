export interface Ticker {
  symbol: string;
  price: number;
  change24: number;
  change7d?: number;
  change1h?: number;
  change4h?: number;
  quoteVolume: number;
  high24: number;
  low24: number;
  funding: number | null;
  volRatio?: number;
  oiChange24?: number;
  oiChange1h?: number;
  dailyCloses?: number[];
  hourlyCloses?: number[];
  candles5m?: Array<{ o: number; h: number; l: number; c: number; v: number; buyVol: number; quoteVol: number }>;
  lsRatio?: number | null;
  takerRatio?: number | null;
}

export interface Signal {
  score: number;
  note?: string;
}

export interface Candidate extends Ticker {
  score: number;
  signals: Record<string, Signal>;
  strongCount: number;
  pumpFlagged: boolean;
  narrativeMult: number;
  sector: string;
  contextScore?: number;        // optional until Task 5 fills this in
  contextMult?: number;         // optional until Task 5 fills this in
  stage?: 0 | 1 | 2 | 3;      // optional until Task 5 fills this in
}

export interface SectorData {
  tokens: string[];
  sum24: number;
  sum7d: number;
  count: number;
  avg24: number;
  avg7d: number;
  momentum: number;
}

export interface MarketGlobal {
  fearGreed: number | null;
  fearGreedLabel: string;
  usdKrw: number | null;
  btcKrwKimchi: number | null;
  btcTx: number | null;
  btcTxLabel: string;
  mempoolFee: number | null;
  mempoolFeeLabel: string;
}

export interface LiqData {
  globalShortLiq5m: number;
  globalLongLiq5m: number;
  bySymbol: Record<string, { shortLiq: number; longLiq: number }>;
  connected: boolean;
}

export interface PreSignal {
  symbol: string;
  type: "fundExt" | "oiBuild" | "capitulation";
  dir: 1 | -1;
  title: string;
  desc: string;
  ts: number;
}

export interface FlowData {
  score: number;
  signals: Array<{ text: string; type: "bull" | "bear" | "warn" | "neut" }>;
  fundingRate: number;
  oiPct: number;
  lsRatio: number | null;
  takerRatio: number;
}
